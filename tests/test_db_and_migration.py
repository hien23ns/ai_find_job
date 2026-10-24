"""
Unit tests for Database layer, schema migration, and JSON tracker preservation.
"""

from datetime import datetime
import json
from pathlib import Path
import shutil
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from src.db import (
    DatabaseManager,
    init_database,
    migrate_tracker_json_to_db,
    sync_db_to_tracker_json,
    get_connection
)


class TestDatabaseAndMigration(unittest.TestCase):
    def setUp(self):
        self.test_dir = PROJECT_ROOT / ".local" / "test_db_temp"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.test_dir / "test_app.db"
        self.json_path = self.test_dir / "test_tracker.json"

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_schema_initialization(self):
        init_database(self.db_path)
        self.assertTrue(self.db_path.exists())
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r["name"] for r in cur.fetchall()]
            self.assertIn("schema_version", tables)
            self.assertIn("jobs", tables)
            self.assertIn("applications", tables)
            self.assertIn("application_history", tables)
            self.assertIn("settings", tables)
            self.assertIn("worker_tasks", tables)
        finally:
            conn.close()

    def test_migrate_json_tracker_preserves_records_and_creates_backup(self):
        # Create a mock tracker JSON
        mock_data = {
            "version": "1.0",
            "last_updated": "2026-10-25 01:00:00",
            "total_jobs": 2,
            "jobs": {
                "job_abc": {
                    "id": "job_abc",
                    "title": "SOC Analyst",
                    "company": "CyStack",
                    "market": "vietnam",
                    "source": "https://cystack.net/jobs/1",
                    "match_score": 90,
                    "status": "Chưa nộp",
                    "application_date": None,
                    "notes": "Good match",
                    "canonical_key": "cystack_soc",
                    "created_at": "2026-10-24 10:00:00",
                    "updated_at": "2026-10-24 10:00:00"
                },
                "job_hitachi": {
                    "id": "job_hitachi",
                    "title": "Cloud & DevOps Intern",
                    "company": "Hitachi Digital Services",
                    "market": "vietnam",
                    "source": "https://www.linkedin.com/jobs/view/4481162663",
                    "match_score": 93,
                    "status": "Cần xác minh",
                    "application_date": None,
                    "notes": "User applied via portal",
                    "canonical_key": "hitachi_cloud",
                    "created_at": "2026-10-24 11:00:00",
                    "updated_at": "2026-10-24 11:00:00"
                }
            }
        }
        self.json_path.write_text(json.dumps(mock_data), encoding="utf-8")

        count, backup = migrate_tracker_json_to_db(self.json_path, self.db_path)
        self.assertEqual(count, 2)
        self.assertIsNotNone(backup)
        self.assertTrue(backup.exists())

        # Verify records in DB
        db = DatabaseManager(self.db_path)
        j1 = db.get_job("job_abc")
        self.assertIsNotNone(j1)
        self.assertEqual(j1["title"], "SOC Analyst")
        self.assertEqual(j1["status"], "Chưa nộp")

        # Verify Hitachi is marked submitted to safeguard from duplicate application
        j2 = db.get_job("job_hitachi")
        self.assertIsNotNone(j2)
        self.assertEqual(j2["status"], "Đã nộp qua form")
        self.assertIn("Chống nộp trùng", j2["notes"])

    def test_dashboard_summary_computation(self):
        init_database(self.db_path)
        db = DatabaseManager(self.db_path)
        db.save_job({
            "id": "job_1", "title": "DevOps", "company": "Tech Corp",
            "market": "vietnam", "source": "web", "match_score": 85,
            "status": "Chưa nộp"
        })
        db.save_job({
            "id": "job_2", "title": "Cloud Intern", "company": "Hitachi",
            "market": "vietnam", "source": "web", "match_score": 90,
            "status": "Đã nộp qua form"
        })

        summary = db.get_dashboard_summary()
        self.assertEqual(summary["total_jobs"], 2)
        self.assertEqual(summary["submitted_jobs"], 1)
        self.assertEqual(summary["new_matching_jobs"], 1)


if __name__ == "__main__":
    unittest.main()
