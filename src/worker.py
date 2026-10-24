"""
Background Worker and State Machine Subsystem.
Implements the formal Application State Machine:
DISCOVERED -> PREPARING -> READY -> NEEDS_REVIEW -> QUEUED -> FILLING
-> AWAITING_USER -> SUBMITTING -> SUBMITTED / FAILED / UNKNOWN / CANCELLED.

Includes ACID transaction safety, crash recovery, timezone-aware daily limits,
anti-duplicate locks, and emergency kill-switch controls.
"""

from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from src.config import PROJECT_ROOT
from src.db import DatabaseManager, get_connection, _DB_LOCK
from src.form_automation import FormAutomationManager, FormAutomationResult
from src.email_sender import get_configured_email_provider, EmailDispatchResult
from src.security import ensure_within_project

HEARTBEAT_FILE = PROJECT_ROOT / ".local" / "worker_heartbeat.json"

# Timezone Asia/Ho_Chi_Minh (+07:00)
ICT_TIMEZONE = timezone(timedelta(hours=7))

VALID_TRANSITIONS = {
    "DISCOVERED": ["PREPARING", "READY", "CANCELLED"],
    "PREPARING": ["READY", "NEEDS_REVIEW", "FAILED", "CANCELLED"],
    "READY": ["NEEDS_REVIEW", "QUEUED", "FILLING", "SUBMITTING", "SUBMITTED", "CANCELLED"],
    "NEEDS_REVIEW": ["READY", "QUEUED", "FILLING", "SUBMITTING", "SUBMITTED", "CANCELLED"],
    "QUEUED": ["FILLING", "AWAITING_USER", "SUBMITTING", "SUBMITTED", "NEEDS_REVIEW", "CANCELLED"],
    "FILLING": ["AWAITING_USER", "NEEDS_REVIEW", "READY", "SUBMITTING", "SUBMITTED", "FAILED", "CANCELLED"],
    "AWAITING_USER": ["QUEUED", "FILLING", "SUBMITTING", "SUBMITTED", "CANCELLED"],
    "SUBMITTING": ["SUBMITTED", "FAILED", "UNKNOWN"],
    "SUBMITTED": [],  # Terminal state!
    "FAILED": ["READY", "QUEUED", "SUBMITTING", "CANCELLED"],
    "UNKNOWN": ["CANCELLED"],
    "CANCELLED": ["READY", "QUEUED"]
}


class ApplicationWorker:
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager()
        self.worker_id = f"worker_{os.getpid()}_{int(time.time())}"
        self.is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """
        Starts the background worker thread.
        Runs crash recovery on startup.
        """
        if self.is_running:
            return
        self.recover_from_crash()
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    def write_heartbeat(self) -> None:
        HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
        now_ict = datetime.now(ICT_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "worker_id": self.worker_id,
            "status": "RUNNING" if self.is_running else "STOPPED",
            "last_heartbeat": now_ict,
            "pid": os.getpid()
        }
        HEARTBEAT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def recover_from_crash(self) -> None:
        """
        Recovers interrupted applications after system restart or crash.
        - SUBMITTING -> UNKNOWN (Safeguard: never blindly re-submit!)
        - FILLING -> READY or NEEDS_REVIEW (Safe to re-fill)
        """
        apps = self.db.list_applications()
        for app in apps:
            status = app.get("status")
            if status == "SUBMITTING":
                self.transition_state(
                    app["id"],
                    "UNKNOWN",
                    action="CRASH_RECOVERY",
                    details="Phát hiện hệ thống khởi động lại khi đang ở bước SUBMITTING. Chuyển sang UNKNOWN để tránh gửi trùng đơn."
                )
            elif status == "FILLING":
                self.transition_state(
                    app["id"],
                    "READY",
                    action="CRASH_RECOVERY",
                    details="Phát hiện hệ thống khởi động lại khi đang điền form. Đặt lại trạng thái READY an toàn."
                )

    def transition_state(
        self,
        app_id: str,
        new_status: str,
        action: str,
        details: str,
        proof_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Atomically validates and transitions application state.
        """
        with _DB_LOCK:
            app = self.db.get_application(app_id)
            if not app:
                return False

            curr_status = app.get("status", "DISCOVERED")
            allowed = VALID_TRANSITIONS.get(curr_status, [])
            if new_status not in allowed and curr_status != new_status:
                self.db.add_history(
                    application_id=app_id,
                    action="INVALID_TRANSITION_REJECTED",
                    status=curr_status,
                    details=f"Từ chối chuyển trạng thái không hợp lệ: {curr_status} -> {new_status}."
                )
                return False

            app["status"] = new_status
            self.db.save_application(app)
            self.db.add_history(
                application_id=app_id,
                action=action,
                status=new_status,
                details=details,
                proof_data=proof_data
            )

            # Sync job status in jobs table if final state
            job_id = app.get("job_id")
            if job_id:
                job = self.db.get_job(job_id)
                if job:
                    now_str = datetime.now(ICT_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
                    if new_status == "SUBMITTED":
                        job_status = "Đã nộp qua form" if app.get("channel") == "form" else "Đã gửi email"
                        job["status"] = job_status
                        job["application_date"] = now_str[:10]
                        job["notes"] = f"{job.get('notes', '')} [{details}]".strip()
                        self.db.save_job(job)
                    elif new_status == "FAILED":
                        job["status"] = "FAILED"
                        job["notes"] = f"{job.get('notes', '')} [Lỗi: {details}]".strip()
                        self.db.save_job(job)

            return True

    def check_daily_limit(self) -> Tuple[bool, int, int]:
        """
        Checks daily application limit in Asia/Ho_Chi_Minh timezone.
        Returns (is_allowed, today_count, limit).
        """
        limit = int(self.db.get_setting("daily_limit", "5"))
        today_prefix = datetime.now(ICT_TIMEZONE).strftime("%Y-%m-%d")

        conn = get_connection(self.db.db_path)
        try:
            cur = conn.execute("""
                SELECT COUNT(*) as count FROM application_history
                WHERE status = 'SUBMITTED' AND timestamp LIKE ?
            """, (f"{today_prefix}%",))
            row = cur.fetchone()
            count = row["count"] if row else 0
            return (count < limit), count, limit
        finally:
            conn.close()

    def process_application(self, app_id: str, dry_run: bool = False) -> None:
        """
        Executes single application workflow based on current automation mode and channel.
        """
        # 1. Kill-switch check
        if self.db.get_setting("kill_switch_activated", "0") == "1":
            self.transition_state(
                app_id, "CANCELLED",
                action="KILL_SWITCH_HALT",
                details="Hàng đợi bị dừng do kích hoạt nút Dừng khẩn cấp (Kill Switch)."
            )
            return

        app = self.db.get_application(app_id)
        if not app:
            return

        # 2. Anti-duplicate verification
        job_id = app.get("job_id")
        job = self.db.get_job(job_id)
        if job and job.get("status") in ["Đã nộp", "Đã nộp qua form", "Đã gửi email", "SUBMITTED"]:
            self.transition_state(
                app_id, "CANCELLED",
                action="DUPLICATE_PREVENTED",
                details=f"Công việc {app['company']} ({app['role']}) đã được nộp trước đó. Chặn nộp trùng."
            )
            return

        # 3. Check Daily Limit
        allowed, count, limit = self.check_daily_limit()
        if not allowed and not dry_run:
            self.transition_state(
                app_id, "NEEDS_REVIEW",
                action="DAILY_LIMIT_REACHED",
                details=f"Đã đạt hạn mức nộp trong ngày ({count}/{limit} đơn theo giờ Việt Nam). Tạm dừng xử lý tự động."
            )
            return

        mode = self.db.get_setting("automation_mode", "review")
        channel = app.get("channel", "missing_channel")

        # 4. Form Submission Flow
        if channel == "form":
            self._handle_form_application(app, mode, dry_run)
        # 5. Email Submission Flow
        elif channel == "email":
            self._handle_email_application(app, mode, dry_run)
        # 6. Missing Channel Flow
        else:
            self.transition_state(
                app_id, "AWAITING_USER",
                action="MISSING_CHANNEL_INTERVENTION",
                details="Chưa xác minh được kênh nộp chính thức (Email hoặc Form URL). Yêu cầu người dùng kiểm tra."
            )

    def _handle_form_application(self, app: Dict[str, Any], mode: str, dry_run: bool) -> None:
        app_id = app["id"]
        recipient_url = app.get("recipient")
        if not recipient_url or not recipient_url.startswith("http"):
            self.transition_state(
                app_id, "AWAITING_USER",
                action="INVALID_FORM_URL",
                details="URL cổng tuyển dụng không hợp lệ để mở tự động."
            )
            return

        # Phase 1: Filling
        self.transition_state(app_id, "FILLING", action="START_FORM_FILLING", details="Bắt đầu điền form tự động.")

        cv_path = None
        pkg_dir = app.get("package_dir")
        if pkg_dir:
            p_cv = Path(pkg_dir) / "cv_en.pdf"
            if p_cv.exists():
                cv_path = p_cv

        # Execute browser filling
        automator = FormAutomationManager(headless=False)
        try:
            # If in 'prepare' or 'review' mode, run dry_run first
            effective_dry_run = True if mode in ["prepare", "review"] else dry_run
            result = automator.process_application_form(
                url=recipient_url,
                app_data=app,
                cv_path=cv_path,
                dry_run=effective_dry_run
            )

            if result.status == "AWAITING_USER":
                self.transition_state(
                    app_id, "AWAITING_USER",
                    action="USER_INTERVENTION_NEEDED",
                    details=result.message,
                    proof_data=result.question_prompt
                )
            elif result.status == "NEEDS_REVIEW":
                self.transition_state(
                    app_id, "NEEDS_REVIEW",
                    action="FORM_FILLED_AWAITING_APPROVAL",
                    details=result.message
                )
            elif result.status == "SUCCESS":
                self.transition_state(
                    app_id, "SUBMITTED",
                    action="FORM_SUBMISSION_SUCCESS",
                    details=result.message,
                    proof_data={"proof_path": result.proof_path}
                )
            elif result.status == "UNKNOWN":
                self.transition_state(
                    app_id, "UNKNOWN",
                    action="POST_SUBMIT_UNCONFIRMED",
                    details=result.message
                )
            else:
                self.transition_state(
                    app_id, "FAILED",
                    action="FORM_AUTOMATION_FAILED",
                    details=result.message
                )
        finally:
            automator.close()

    def _handle_email_application(self, app: Dict[str, Any], mode: str, dry_run: bool) -> None:
        app_id = app["id"]
        to_email = (app.get("recipient") or "").strip(" \t\r\n.,;:!?'\"()[]<>").lower().rstrip(".")
        if not to_email or "@" not in to_email or "." not in to_email.split("@")[-1]:
            self.transition_state(
                app_id, "AWAITING_USER",
                action="INVALID_RECIPIENT_EMAIL",
                details="Địa chỉ email người nhận chưa xác thực hoặc không hợp lệ."
            )
            return

        if mode == "prepare":
            self.transition_state(
                app_id, "READY",
                action="PREPARED_ONLY",
                details="Đã chuẩn bị xong bản nháp email. Chế độ 'Chuẩn bị' không thực hiện gửi."
            )
            return

        if mode == "review" and not dry_run:
            self.transition_state(
                app_id, "NEEDS_REVIEW",
                action="AWAITING_USER_CONFIRMATION",
                details="Bản nháp email đã sẵn sàng. Chờ ứng viên bấm xác nhận gửi trên giao diện."
            )
            return

        # Two-phase commit: Mark SUBMITTING
        self.transition_state(
            app_id, "SUBMITTING",
            action="EMAIL_DISPATCH_STARTED",
            details=f"Đang tiến hành chuyển email tới {to_email} qua provider..."
        )

        provider = get_configured_email_provider()
        pkg_dir = Path(app.get("package_dir", ""))
        subject_file = pkg_dir / "email_subject.txt"
        body_file = pkg_dir / "email_body.txt"

        subject = f"Application for {app['role']} - Ngô Văn Hiền"
        if subject_file.exists():
            lines = [l.strip() for l in subject_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                subject = lines[0].replace("[LỰA CHỌN B - ỨNG TUYỂN TRỰC TIẾP (KHUYÊN DÙNG)]:", "").strip()

        body = "Please find attached my application documents."
        if body_file.exists():
            body = body_file.read_text(encoding="utf-8")

        attachments = []
        if (pkg_dir / "cv_en.pdf").exists():
            attachments.append(pkg_dir / "cv_en.pdf")

        res = provider.send_email(
            from_email="hienngo090800@gmail.com",
            from_name="Ngô Văn Hiền",
            to_email=to_email,
            subject=subject,
            body_text=body,
            attachment_paths=attachments
        )

        if res.status == "SENT":
            self.transition_state(
                app_id, "SUBMITTED",
                action="EMAIL_SENT_CONFIRMED",
                details=res.message,
                proof_data={"message_id": res.message_id}
            )
        elif res.status == "TIMEOUT_UNCONFIRMED":
            self.transition_state(
                app_id, "UNKNOWN",
                action="EMAIL_TIMEOUT_GUARD",
                details=res.message
            )
        else:
            self.transition_state(
                app_id, "FAILED",
                action="EMAIL_SEND_FAILED",
                details=res.message
            )

    def _run_loop(self) -> None:
        """
        Main worker polling loop.
        """
        while self.is_running and not self._stop_event.is_set():
            try:
                self.write_heartbeat()
                # Check for queued applications
                queued_apps = self.db.list_applications(status="QUEUED")
                for app in queued_apps:
                    if not self.is_running or self._stop_event.is_set():
                        break
                    self.process_application(app["id"])
            except Exception as e:
                time.sleep(1.0)
            time.sleep(2.0)
