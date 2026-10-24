"""
Unit tests for Application State Machine, Worker crash recovery,
ICT timezone limits, and anti-duplicate locks.
"""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from src.db import DatabaseManager, init_database
from src.worker import ApplicationWorker, VALID_TRANSITIONS, ICT_TIMEZONE


class TestStateMachineWorker(unittest.TestCase):
    def setUp(self):
        self.test_dir = PROJECT_ROOT / ".local" / "test_sm_temp"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.test_dir / "test_sm.db"
        init_database(self.db_path)
        self.db = DatabaseManager(self.db_path)
        self.worker = ApplicationWorker(self.db)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_valid_state_transitions(self):
        self.db.save_job({
            "id": "job_1", "company": "Tech Corp", "title": "Cloud Intern",
            "market": "vietnam", "source": "web"
        })
        app_id = "app_test_1"
        self.db.save_application({
            "id": app_id,
            "job_id": "job_1",
            "company": "Tech Corp",
            "role": "Cloud Intern",
            "status": "DISCOVERED"
        })

        # DISCOVERED -> PREPARING
        ok1 = self.worker.transition_state(app_id, "PREPARING", "PREP_START", "Starting preparation")
        self.assertTrue(ok1)
        self.assertEqual(self.db.get_application(app_id)["status"], "PREPARING")

        # PREPARING -> READY
        ok2 = self.worker.transition_state(app_id, "READY", "PREP_FINISH", "Package ready")
        self.assertTrue(ok2)
        self.assertEqual(self.db.get_application(app_id)["status"], "READY")

        # READY -> QUEUED
        ok3 = self.worker.transition_state(app_id, "QUEUED", "USER_QUEUE", "Queued by user")
        self.assertTrue(ok3)
        self.assertEqual(self.db.get_application(app_id)["status"], "QUEUED")

    def test_invalid_state_transition_rejected(self):
        self.db.save_job({
            "id": "job_2", "company": "Secure Corp", "title": "SOC Analyst",
            "market": "vietnam", "source": "web"
        })
        app_id = "app_test_invalid"
        self.db.save_application({
            "id": app_id,
            "job_id": "job_2",
            "company": "Secure Corp",
            "role": "SOC Analyst",
            "status": "SUBMITTED"
        })

        # SUBMITTED is terminal; transition to QUEUED or PREPARING must be rejected
        ok = self.worker.transition_state(app_id, "QUEUED", "INVALID_RETRY", "Trying to queue submitted app")
        self.assertFalse(ok)
        self.assertEqual(self.db.get_application(app_id)["status"], "SUBMITTED")

        history = self.db.get_history(app_id)
        rejected_actions = [h["action"] for h in history if "INVALID" in h["action"]]
        self.assertTrue(len(rejected_actions) > 0)

    def test_crash_recovery_submitting_to_unknown(self):
        self.db.save_job({
            "id": "job_crash", "company": "Finance Corp", "title": "Security Engineer",
            "market": "vietnam", "source": "web"
        })
        app_id = "app_crash_submitting"
        self.db.save_application({
            "id": app_id,
            "job_id": "job_crash",
            "company": "Finance Corp",
            "role": "Security Engineer",
            "status": "SUBMITTING"
        })

        # Worker recovers from crash
        self.worker.recover_from_crash()

        recovered_app = self.db.get_application(app_id)
        self.assertEqual(recovered_app["status"], "UNKNOWN")
        history = self.db.get_history(app_id)
        self.assertIn("CRASH_RECOVERY", [h["action"] for h in history])

    def test_crash_recovery_filling_to_ready(self):
        self.db.save_job({
            "id": "job_fill", "company": "Retail Corp", "title": "DevOps",
            "market": "vietnam", "source": "web"
        })
        app_id = "app_crash_filling"
        self.db.save_application({
            "id": app_id,
            "job_id": "job_fill",
            "company": "Retail Corp",
            "role": "DevOps",
            "status": "FILLING"
        })

        self.worker.recover_from_crash()

        recovered_app = self.db.get_application(app_id)
        self.assertEqual(recovered_app["status"], "READY")

    def test_anti_duplicate_check_rejects_already_submitted_job(self):
        # Create job marked already submitted (like Hitachi 4481162663)
        self.db.save_job({
            "id": "job_hitachi_dup",
            "company": "Hitachi Digital Services",
            "title": "Cloud & DevOps Intern",
            "status": "Đã nộp qua form",
            "market": "vietnam"
        })
        app_id = "app_hitachi_attempt"
        self.db.save_application({
            "id": app_id,
            "job_id": "job_hitachi_dup",
            "company": "Hitachi Digital Services",
            "role": "Cloud & DevOps Intern",
            "status": "QUEUED"
        })

        self.worker.process_application(app_id)

        updated_app = self.db.get_application(app_id)
        self.assertEqual(updated_app["status"], "CANCELLED")
        history = self.db.get_history(app_id)
        self.assertIn("DUPLICATE_PREVENTED", [h["action"] for h in history])

    def test_daily_limit_in_asia_ho_chi_minh_timezone(self):
        self.db.set_setting("daily_limit", "2")
        today_prefix = datetime.now(ICT_TIMEZONE).strftime("%Y-%m-%d")

        # Simulate 2 applications submitted today
        for i in range(2):
            self.db.save_job({
                "id": f"job_q_{i}", "company": f"Corp {i}", "title": "Intern",
                "market": "vietnam", "source": "web"
            })
            self.db.save_application({
                "id": f"app_quota_{i}",
                "job_id": f"job_q_{i}",
                "company": f"Corp {i}",
                "role": "Intern",
                "status": "SUBMITTED"
            })
            self.db.add_history(
                application_id=f"app_quota_{i}",
                action="SUBMITTED",
                status="SUBMITTED",
                details="Sent successfully"
            )

        allowed, count, limit = self.worker.check_daily_limit()
        self.assertEqual(count, 2)
        self.assertEqual(limit, 2)
        self.assertFalse(allowed)

    def test_emergency_kill_switch_halts_processing(self):
        self.db.set_setting("kill_switch_activated", "1")
        self.db.save_job({
            "id": "job_ks", "company": "Target Corp", "title": "Cloud Intern",
            "market": "vietnam", "source": "web"
        })
        app_id = "app_kill_switch"
        self.db.save_application({
            "id": app_id,
            "job_id": "job_ks",
            "company": "Target Corp",
            "role": "Cloud Intern",
            "status": "QUEUED"
        })

        self.worker.process_application(app_id)
        updated = self.db.get_application(app_id)
        self.assertEqual(updated["status"], "CANCELLED")


if __name__ == "__main__":
    unittest.main()
