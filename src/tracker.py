"""
Job Application and Evaluation Tracker.
Saves and reads structured tracking records in JSON and CSV format within PROJECT_ROOT/data/tracker.
Protects sensitive personal data and follows strict local persistence rules.
Supports atomic writes, re-evaluation without state loss, and corrupt JSON protection.
"""

import csv
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import TRACKER_DIR
from src.security import ensure_within_project
from src.upstream_bridge import get_canonical_job_key

TRACKER_FILE = TRACKER_DIR / "jobs_tracker.json"
TRACKER_CSV = TRACKER_DIR / "jobs_tracker.csv"

class JobTracker:
    def __init__(self, file_path: Path = TRACKER_FILE):
        self.file_path = ensure_within_project(file_path)
        self.records: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        """
        Load tracker records from JSON file.
        Raises ValueError if JSON is corrupt or invalid to prevent silent data loss.
        """
        if not self.file_path.exists():
            self.records = {}
            return

        content = self.file_path.read_text(encoding="utf-8")
        if not content.strip():
            self.records = {}
            return

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Dữ liệu JSON trong file tracker bị hỏng ({e}): {self.file_path}. "
                f"Không thể tải để bảo vệ an toàn dữ liệu, tránh ghi đè làm mất lịch sử ứng tuyển!"
            ) from e

        if not isinstance(data, dict) or "jobs" not in data:
            raise ValueError(
                f"File tracker không đúng định dạng schema chuẩn (thiếu khóa 'jobs'): {self.file_path}"
            )

        self.records = data.get("jobs", {})

    def _save(self):
        """
        Safe atomic write using a temporary file replaced atomically.
        Prevents corrupting tracker files if interrupted mid-write.
        """
        payload = {
            "version": "1.0",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_jobs": len(self.records),
            "jobs": self.records
        }
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.file_path.with_suffix(".tmp")
        temp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_file, self.file_path)

    def add_or_update(
        self,
        title: str,
        company: str,
        market: str,
        source: str,
        match_score: int,
        status: Optional[str] = None,
        application_date: Optional[str] = None,
        notes: Optional[str] = None,
        next_step: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a new job entry or re-evaluate an existing one.
        - If the job already exists: preserves current application status, application_date,
          notes, and next_step unless explicitly overridden.
        - If creating a new job: defaults status to 'Chưa nộp' and does NOT assign today's date
          as application_date unless status is explicitly 'Đã nộp'.
        """
        canonical_key = get_canonical_job_key(company, title, source if source.startswith("http") else "")
        if not job_id:
            import hashlib
            raw_hash = hashlib.sha1(f"{market}_{canonical_key}".encode("utf-8")).hexdigest()[:6]
            job_id = f"job_{raw_hash}"

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = self.records.get(job_id)

        if existing:
            # Re-evaluation / update existing record
            final_status = status if status is not None else existing.get("status", "Chưa nộp")
            final_app_date = application_date if application_date is not None else existing.get("application_date")
            final_notes = notes if notes is not None else existing.get("notes", "")
            final_next_step = next_step if next_step is not None else existing.get("next_step", "")
            created_at = existing.get("created_at", now)
        else:
            # Brand new job entry
            final_status = status if status is not None else "Chưa nộp"
            if application_date is not None:
                final_app_date = application_date
            elif final_status == "Đã nộp":
                final_app_date = now[:10]
            else:
                final_app_date = None  # Never set application date for unsubmitted jobs

            final_notes = notes if notes is not None else ""
            final_next_step = next_step if next_step is not None else ""
            created_at = now

        record = {
            "id": job_id,
            "title": title,
            "company": company,
            "market": market,
            "source": source,
            "match_score": match_score,
            "status": final_status,
            "application_date": final_app_date,
            "notes": final_notes,
            "next_step": final_next_step,
            "canonical_key": canonical_key,
            "created_at": created_at,
            "updated_at": now
        }

        self.records[job_id] = record
        self._save()
        return record

    def update_status(
        self,
        job_id: str,
        status: str,
        application_date: Optional[str] = None,
        notes: Optional[str] = None,
        next_step: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Explicitly update status and tracking metadata for an existing job.
        """
        existing = self.records.get(job_id)
        if not existing:
            raise KeyError(f"Không tìm thấy công việc có ID '{job_id}' trong tracker.")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing["status"] = status
        if application_date is not None:
            existing["application_date"] = application_date
        elif status == "Đã nộp" and not existing.get("application_date"):
            existing["application_date"] = now[:10]

        if notes is not None:
            existing["notes"] = notes
        if next_step is not None:
            existing["next_step"] = next_step

        existing["updated_at"] = now
        self.records[job_id] = existing
        self._save()
        return existing

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.records.get(job_id)

    def list_all(
        self,
        filter_market: Optional[str] = None,
        filter_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results = list(self.records.values())
        if filter_market:
            results = [r for r in results if r.get("market") == filter_market]
        if filter_status:
            results = [r for r in results if r.get("status") == filter_status]
        # Sort by updated_at descending
        results.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
        return results

    def export_csv(self, output_path: Optional[Path] = None) -> Path:
        """
        Export current tracking records to a clean CSV file.
        Defaults to companion CSV based on tracker JSON name to prevent overwriting production CSV in tests.
        """
        if output_path is None:
            safe_out = ensure_within_project(self.file_path.with_suffix(".csv"))
        else:
            safe_out = ensure_within_project(output_path)

        jobs = self.list_all()
        fields = [
            "id", "title", "company", "market", "match_score",
            "status", "application_date", "next_step", "source", "notes", "updated_at"
        ]

        safe_out.parent.mkdir(parents=True, exist_ok=True)
        with open(safe_out, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for j in jobs:
                row = {k: ("" if j.get(k) is None else j.get(k)) for k in fields}
                writer.writerow(row)

        return safe_out
