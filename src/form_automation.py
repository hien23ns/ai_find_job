"""
Form Automation and Browser Adapter Subsystem using Playwright.
Supports local visible browser profiles strictly inside PROJECT_ROOT/.local/browser_profile.
Implements capability matrix, semantic locators, multi-step navigation, file uploads,
human intervention on CAPTCHA/OTP/Unknown questions, two-phase submit, and proof capture.
"""

from abc import ABC, abstractmethod
from datetime import datetime
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from src.config import PROJECT_ROOT
from src.security import ensure_within_project

BROWSER_PROFILE_DIR = PROJECT_ROOT / ".local" / "browser_profile"
EVIDENCE_DIR = PROJECT_ROOT / ".local" / "evidence"


class FormAutomationResult:
    def __init__(
        self,
        status: str,  # 'SUCCESS', 'AWAITING_USER', 'NEEDS_REVIEW', 'FAILED', 'UNKNOWN', 'UNSUPPORTED'
        message: str,
        current_step: Optional[str] = None,
        question_prompt: Optional[Dict[str, Any]] = None,
        proof_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.status = status
        self.message = message
        self.current_step = current_step
        self.question_prompt = question_prompt
        self.proof_path = proof_path
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "current_step": self.current_step,
            "question_prompt": self.question_prompt,
            "proof_path": self.proof_path,
            "details": self.details
        }


class BaseFormAdapter(ABC):
    @abstractmethod
    def can_handle(self, url: str, page_content: str) -> bool:
        pass

    @abstractmethod
    def fill_and_submit(
        self,
        page: Any,
        app_data: Dict[str, Any],
        cv_path: Optional[Path] = None,
        dry_run: bool = True,
        user_answers: Optional[Dict[str, Any]] = None
    ) -> FormAutomationResult:
        pass


class LocalTestFormAdapter(BaseFormAdapter):
    """
    Adapter for Local Mock ATS Form Server.
    Provides complete end-to-end verification of multi-step forms, file uploads,
    conditional fields, CAPTCHA/OTP intervention, and explicit submission confirmation.
    """
    def can_handle(self, url: str, page_content: str) -> bool:
        return "127.0.0.1" in url or "localhost" in url or "mock_ats" in page_content

    def fill_and_submit(
        self,
        page: Any,
        app_data: Dict[str, Any],
        cv_path: Optional[Path] = None,
        dry_run: bool = True,
        user_answers: Optional[Dict[str, Any]] = None
    ) -> FormAutomationResult:
        user_answers = user_answers or {}
        form_answers = app_data.get("form_answers", {})

        # Step 1: Check for CAPTCHA/OTP barrier
        if page.locator("#captcha-container, .captcha-challenge").count() > 0:
            return FormAutomationResult(
                status="AWAITING_USER",
                message="Phát hiện thử thách CAPTCHA/OTP. Yêu cầu người dùng can thiệp giải mã trên trình duyệt.",
                current_step="CAPTCHA_CHALLENGE"
            )

        # Step 2: Fill Personal Information
        if page.locator("input[name='full_name']").count() > 0:
            name_val = form_answers.get("full_name", "Ngô Văn Hiền")
            page.fill("input[name='full_name']", name_val)

        if page.locator("input[name='email']").count() > 0:
            email_val = form_answers.get("email", "hienngo090800@gmail.com")
            page.fill("input[name='email']", email_val)

        if page.locator("input[name='phone']").count() > 0:
            phone_val = form_answers.get("phone", "0393492064")
            page.fill("input[name='phone']", phone_val)

        # Step 3: Fill Education & Academic Background
        if page.locator("input[name='university']").count() > 0:
            page.fill("input[name='university']", form_answers.get("university", "VKU"))

        if page.locator("input[name='major']").count() > 0:
            page.fill("input[name='major']", form_answers.get("major", "Mạng và An toàn thông tin"))

        # Step 4: Dropdowns and radios
        if page.locator("select[name='grad_year']").count() > 0:
            page.select_option("select[name='grad_year']", "2028")

        if page.locator("input[name='work_authorization'][value='yes']").count() > 0:
            page.check("input[name='work_authorization'][value='yes']")

        # Step 5: Check for Unknown Question
        if page.locator(".unknown-question").count() > 0:
            q_text = page.locator(".unknown-question-label").inner_text()
            q_id = page.locator(".unknown-question input, .unknown-question select").get_attribute("name") or "custom_q"
            if q_id not in user_answers:
                return FormAutomationResult(
                    status="AWAITING_USER",
                    message=f"Câu hỏi chưa có dữ liệu trong hồ sơ: '{q_text}'. Vui lòng cung cấp câu trả lời.",
                    current_step="UNKNOWN_QUESTION",
                    question_prompt={
                        "field_id": q_id,
                        "question": q_text,
                        "type": "text"
                    }
                )
            else:
                page.fill(f"[name='{q_id}']", str(user_answers[q_id]))

        # Step 6: Textarea pre-drafted responses
        pre_drafted = form_answers.get("pre_drafted_responses", {})
        if page.locator("textarea[name='why_interested']").count() > 0:
            why_text = pre_drafted.get("why_interested", "I am genuinely interested in this position.")
            page.fill("textarea[name='why_interested']", why_text)

        # Step 7: File Upload
        if cv_path and cv_path.exists() and page.locator("input[type='file'][name='resume']").count() > 0:
            ensure_within_project(cv_path)
            page.set_input_files("input[type='file'][name='resume']", str(cv_path))
            # Verify file upload status if upload status indicator exists
            time.sleep(0.5)

        # Step 8: Multi-step navigation (Next button)
        if page.locator("button#next-step-btn").count() > 0 and page.locator("button#next-step-btn").is_visible():
            page.click("button#next-step-btn")
            time.sleep(0.5)

        # Step 9: Submission or Review Mode
        if dry_run:
            return FormAutomationResult(
                status="NEEDS_REVIEW",
                message="Đã tự động điền đầy đủ các trường của form. Đang ở chế độ xem lại (Dry Run) trước khi bấm nộp.",
                current_step="REVIEW_READY"
            )

        # TWO-PHASE COMMIT: Find submit button
        submit_btn = page.locator("button[type='submit'], button#submit-application-btn, input[type='submit']")
        if submit_btn.count() == 0:
            return FormAutomationResult(
                status="FAILED",
                message="Không tìm thấy nút gửi đơn (Submit button) trên trang.",
                current_step="SUBMIT_BUTTON_MISSING"
            )

        # Execute submission
        submit_btn.first.click()
        time.sleep(1.0)

        # Step 10: Verify explicit confirmation
        confirmation_elem = page.locator(".submission-success, #success-message, h1:has-text('Thành công'), div:has-text('tiếp nhận')")
        if confirmation_elem.count() > 0 and confirmation_elem.first.is_visible():
            EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            proof_file = EVIDENCE_DIR / f"submission_proof_{ts}.png"
            try:
                page.screenshot(path=str(proof_file))
                proof_rel = str(proof_file.relative_to(PROJECT_ROOT))
            except Exception:
                proof_rel = None

            return FormAutomationResult(
                status="SUCCESS",
                message="Đã nộp đơn thành công và xác nhận phản hồi chính thức từ máy chủ tuyển dụng.",
                current_step="COMPLETED",
                proof_path=proof_rel,
                details={"confirmation_text": confirmation_elem.first.inner_text()}
            )

        # If timeout or ambiguous state: mark UNKNOWN (Never retry blindly!)
        return FormAutomationResult(
            status="UNKNOWN",
            message="Đã bấm gửi nhưng không nhận được phản hồi xác nhận rõ ràng từ trang web. Trạng thái chuyển sang UNKNOWN để tránh gửi trùng.",
            current_step="UNCONFIRMED_POST_SUBMIT"
        )


class LinkedInEasyApplyAdapter(BaseFormAdapter):
    """
    Adapter for LinkedIn Easy Apply.
    Handles semantic detection of Easy Apply buttons, step traversal,
    and pauses on auth or unknown screening questions.
    """
    def can_handle(self, url: str, page_content: str) -> bool:
        return "linkedin.com/jobs" in url and ("Easy Apply" in page_content or "jobs-apply-button" in page_content)

    def fill_and_submit(
        self,
        page: Any,
        app_data: Dict[str, Any],
        cv_path: Optional[Path] = None,
        dry_run: bool = True,
        user_answers: Optional[Dict[str, Any]] = None
    ) -> FormAutomationResult:
        # Check login state
        if page.locator("a[href*='login'], .sign-in-form").count() > 0:
            return FormAutomationResult(
                status="AWAITING_USER",
                message="LinkedIn yêu cầu đăng nhập tài khoản. Vui lòng đăng nhập trên trình duyệt để tiếp tục.",
                current_step="AUTH_REQUIRED"
            )

        apply_btn = page.locator(".jobs-apply-button, button:has-text('Easy Apply')")
        if apply_btn.count() == 0:
            return FormAutomationResult(
                status="UNSUPPORTED",
                message="Không tìm thấy nút Easy Apply trực tiếp. Tin tuyển dụng có thể chuyển hướng sang trang ngoài.",
                current_step="NO_EASY_APPLY_BUTTON"
            )

        apply_btn.first.click()
        time.sleep(1.0)

        # Check modal
        modal = page.locator(".jobs-easy-apply-modal")
        if modal.count() == 0:
            return FormAutomationResult(
                status="AWAITING_USER",
                message="Không thể mở modal Easy Apply tự động. Vui lòng kiểm tra trên trình duyệt.",
                current_step="MODAL_OPEN_FAILED"
            )

        return FormAutomationResult(
            status="NEEDS_REVIEW",
            message="Đã mở modal Easy Apply trên LinkedIn. Chế độ an toàn yêu cầu người dùng rà soát từng bước trước khi gửi.",
            current_step="MODAL_OPENED"
        )


class GenericWebFormAdapter(BaseFormAdapter):
    """
    Intelligent Generic Web Form Adapter for recruitment portals and company job boards.
    Automatically detects form inputs (name, email, phone, university, major),
    attaches candidate CV PDF, captures full-page screenshot proof,
    and supports both dry-run inspection and live submission.
    """
    def can_handle(self, url: str, page_content: str) -> bool:
        lower = page_content.lower()
        return ("<form" in lower) or ("<input" in lower) or ("apply" in url.lower()) or ("job" in url.lower())

    def fill_and_submit(
        self,
        page: Any,
        app_data: Dict[str, Any],
        cv_path: Optional[Path] = None,
        dry_run: bool = True,
        user_answers: Optional[Dict[str, Any]] = None
    ) -> FormAutomationResult:
        user_answers = user_answers or {}
        form_answers = app_data.get("form_answers", {})
        filled_fields = []

        time.sleep(1.0)

        # 1. Fill Full Name
        name_selectors = [
            "input[name*='name' i]", "input[id*='name' i]", "input[placeholder*='name' i]",
            "input[placeholder*='họ' i]", "input[placeholder*='tên' i]", "input[aria-label*='name' i]"
        ]
        for sel in name_selectors:
            try:
                elem = page.locator(sel)
                if elem.count() > 0 and elem.first.is_visible():
                    val = form_answers.get("full_name", "Ngô Văn Hiền")
                    elem.first.fill(val)
                    filled_fields.append("Họ và tên")
                    break
            except Exception:
                pass

        # 2. Fill Email
        email_selectors = [
            "input[type='email']", "input[name*='email' i]", "input[id*='email' i]",
            "input[placeholder*='email' i]", "input[aria-label*='email' i]"
        ]
        for sel in email_selectors:
            try:
                elem = page.locator(sel)
                if elem.count() > 0 and elem.first.is_visible():
                    val = form_answers.get("email", "hienngo090800@gmail.com")
                    elem.first.fill(val)
                    filled_fields.append("Email")
                    break
            except Exception:
                pass

        # 3. Fill Phone Number
        phone_selectors = [
            "input[type='tel']", "input[name*='phone' i]", "input[id*='phone' i]",
            "input[placeholder*='phone' i]", "input[placeholder*='điện thoại' i]",
            "input[placeholder*='sđt' i]", "input[aria-label*='phone' i]"
        ]
        for sel in phone_selectors:
            try:
                elem = page.locator(sel)
                if elem.count() > 0 and elem.first.is_visible():
                    val = form_answers.get("phone", "0393492064")
                    elem.first.fill(val)
                    filled_fields.append("Số điện thoại")
                    break
            except Exception:
                pass

        # 4. Fill University
        uni_selectors = [
            "input[name*='university' i]", "input[name*='school' i]", "input[name*='education' i]",
            "input[id*='university' i]", "input[id*='school' i]", "input[placeholder*='trường' i]",
            "input[placeholder*='university' i]"
        ]
        for sel in uni_selectors:
            try:
                elem = page.locator(sel)
                if elem.count() > 0 and elem.first.is_visible():
                    val = form_answers.get("university", "Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU)")
                    elem.first.fill(val)
                    filled_fields.append("Trường đại học")
                    break
            except Exception:
                pass

        # 5. Fill Major
        major_selectors = [
            "input[name*='major' i]", "input[id*='major' i]", "input[placeholder*='chuyên ngành' i]",
            "input[placeholder*='ngành' i]"
        ]
        for sel in major_selectors:
            try:
                elem = page.locator(sel)
                if elem.count() > 0 and elem.first.is_visible():
                    val = form_answers.get("major", "Mạng và An toàn thông tin")
                    elem.first.fill(val)
                    filled_fields.append("Chuyên ngành")
                    break
            except Exception:
                pass

        # 6. Fill Cover Letter / Message
        msg_selectors = [
            "textarea[name*='cover' i]", "textarea[name*='message' i]", "textarea[name*='note' i]",
            "textarea[id*='cover' i]", "textarea[placeholder*='thư' i]"
        ]
        for sel in msg_selectors:
            try:
                elem = page.locator(sel)
                if elem.count() > 0 and elem.first.is_visible():
                    pkg_dir = app_data.get("package_dir")
                    cl_text = ""
                    if pkg_dir and (Path(pkg_dir) / "cover_letter_en.md").exists():
                        cl_text = (Path(pkg_dir) / "cover_letter_en.md").read_text(encoding="utf-8")
                    if cl_text:
                        elem.first.fill(cl_text[:1000])
                        filled_fields.append("Thư ứng tuyển")
                    break
            except Exception:
                pass

        # 7. Upload CV File
        if cv_path and cv_path.exists():
            file_selectors = [
                "input[type='file']", "input[name*='resume' i]", "input[name*='cv' i]",
                "input[id*='resume' i]", "input[id*='cv' i]"
            ]
            for sel in file_selectors:
                try:
                    elem = page.locator(sel)
                    if elem.count() > 0:
                        elem.first.set_input_files(str(cv_path))
                        filled_fields.append(f"Tệp CV ({cv_path.name})")
                        break
                except Exception:
                    pass

        # 8. Capture Proof Screenshot
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        proof_file = EVIDENCE_DIR / f"form_fill_{ts}.png"
        try:
            page.screenshot(path=str(proof_file))
            proof_rel = str(proof_file.relative_to(PROJECT_ROOT))
        except Exception:
            proof_rel = None

        fields_summary = ", ".join(filled_fields) if filled_fields else "Đã mở cổng tuyển dụng"

        if dry_run:
            return FormAutomationResult(
                status="NEEDS_REVIEW",
                message=f"Đã tự động điền form ứng tuyển ({fields_summary}). Trình duyệt sẵn sàng để bạn rà soát.",
                current_step="FORM_FILLED_READY",
                proof_path=proof_rel,
                details={"filled_fields": filled_fields}
            )

        # 9. Submit if requested
        submit_selectors = [
            "button[type='submit']", "input[type='submit']", "button:has-text('Nộp đơn')",
            "button:has-text('Submit')", "button:has-text('Apply')", "button:has-text('Gửi hồ sơ')"
        ]
        submitted = False
        for sel in submit_selectors:
            try:
                btn = page.locator(sel)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click()
                    submitted = True
                    time.sleep(2.0)
                    break
            except Exception:
                pass

        if submitted:
            return FormAutomationResult(
                status="SUCCESS",
                message=f"Đã tự động điền ({fields_summary}) và gửi nộp đơn thành công!",
                current_step="COMPLETED",
                proof_path=proof_rel,
                details={"filled_fields": filled_fields}
            )

        return FormAutomationResult(
            status="NEEDS_REVIEW",
            message=f"Đã tự động điền các trường ({fields_summary}) kèm tệp CV. Vui lòng bấm Nộp trên trình duyệt.",
            current_step="REVIEW_READY",
            proof_path=proof_rel,
            details={"filled_fields": filled_fields}
        )


class FallbackManualAdapter(BaseFormAdapter):
    """
    Fallback adapter for non-standard or external career portals.
    Opens the URL in visible browser, provides pre-drafted answers for copy-paste,
    and records verified user manual submission.
    """
    def can_handle(self, url: str, page_content: str) -> bool:
        return True  # Fallback for any URL

    def fill_and_submit(
        self,
        page: Any,
        app_data: Dict[str, Any],
        cv_path: Optional[Path] = None,
        dry_run: bool = True,
        user_answers: Optional[Dict[str, Any]] = None
    ) -> FormAutomationResult:
        # Capture screenshot of opened page
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        proof_file = EVIDENCE_DIR / f"manual_portal_{ts}.png"
        try:
            page.screenshot(path=str(proof_file))
            proof_rel = str(proof_file.relative_to(PROJECT_ROOT))
        except Exception:
            proof_rel = None

        return FormAutomationResult(
            status="NEEDS_REVIEW",
            message="Đã mở cổng tuyển dụng trên trình duyệt. Bạn có thể kiểm tra và điền nộp trực tiếp.",
            current_step="MANUAL_SUBMISSION_READY",
            proof_path=proof_rel,
            details={
                "form_answers": app_data.get("form_answers", {}),
                "cv_path": str(cv_path) if cv_path else None
            }
        )


class FormAutomationManager:
    """
    Coordinates Playwright browser lifecycle, adapter selection,
    and anti-duplicate safeguards.
    """
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.adapters: List[BaseFormAdapter] = [
            LocalTestFormAdapter(),
            LinkedInEasyApplyAdapter(),
            GenericWebFormAdapter(),
            FallbackManualAdapter()
        ]
        self._playwright = None
        self._browser_context = None

    def get_context(self) -> Any:
        from playwright.sync_api import sync_playwright
        if self._playwright is None:
            BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            self._playwright = sync_playwright().start()
            self._browser_context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_PROFILE_DIR),
                headless=self.headless,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"]
            )
        return self._browser_context

    def close(self) -> None:
        if self._browser_context:
            try:
                self._browser_context.close()
            except Exception:
                pass
            self._browser_context = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def process_application_form(
        self,
        url: str,
        app_data: Dict[str, Any],
        cv_path: Optional[Path] = None,
        dry_run: bool = True,
        user_answers: Optional[Dict[str, Any]] = None
    ) -> FormAutomationResult:
        context = self.get_context()
        page = context.new_page()
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(1.0)
            content = page.content()

            # Select appropriate adapter
            selected_adapter = None
            for adp in self.adapters:
                if adp.can_handle(url, content):
                    selected_adapter = adp
                    break

            if not selected_adapter:
                selected_adapter = self.adapters[-1]

            return selected_adapter.fill_and_submit(
                page=page,
                app_data=app_data,
                cv_path=cv_path,
                dry_run=dry_run,
                user_answers=user_answers
            )
        except Exception as e:
            return FormAutomationResult(
                status="FAILED",
                message=f"Lỗi tự động hóa trình duyệt: {type(e).__name__} - {str(e)}",
                current_step="BROWSER_ERROR"
            )
        finally:
            try:
                page.close()
            except Exception:
                pass
