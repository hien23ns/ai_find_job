"""
Unit and integration tests for FastAPI Web Server & Security Middlewares.
Tests Host header validation, CSRF defenses, path traversal protection,
and REST API endpoints.
"""

from pathlib import Path
import shutil
import unittest

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from src.web_server import app, CSRF_TOKEN
from src.db import DatabaseManager, init_database


class TestWebApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, base_url="http://127.0.0.1:8000")

    def test_health_check(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")

    def test_csrf_token_endpoint(self):
        resp = self.client.get("/api/csrf-token")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["csrf_token"], CSRF_TOKEN)

    def test_host_header_validation_blocks_foreign_host(self):
        # Client sends a foreign Host header (DNS Rebinding simulation)
        resp = self.client.get("/api/health", headers={"Host": "evil-attacker.com"})
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Lỗi bảo mật", resp.text)

    def test_csrf_protection_rejects_missing_or_invalid_token(self):
        # State-mutating POST without CSRF token
        resp = self.client.post("/api/queue/stop-all")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("CSRF", resp.json().get("error", ""))

        # With invalid CSRF token
        resp2 = self.client.post("/api/queue/stop-all", headers={"X-CSRF-Token": "invalid_token_123"})
        self.assertEqual(resp2.status_code, 403)

        # With valid CSRF token
        resp3 = self.client.post("/api/queue/stop-all", headers={"X-CSRF-Token": CSRF_TOKEN})
        self.assertEqual(resp3.status_code, 200)

    def test_path_traversal_defense_blocks_escape(self):
        # Attempt to access outside PROJECT_ROOT via path traversal
        resp = self.client.get("/files/../../Windows/System32/drivers/etc/hosts")
        self.assertIn(resp.status_code, [403, 404])

    def test_dashboard_endpoint(self):
        resp = self.client.get("/api/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("summary", data)
        self.assertIn("worker_status", data)
        self.assertIn("browser_status", data)

    def test_profile_endpoint_retrieval(self):
        resp = self.client.get("/api/profile")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("name", data)
        self.assertIn("education", data)

    def test_channel_update_and_direct_actions_validation(self):
        db = DatabaseManager()
        # Seed test job and application
        db.save_job({
            "id": "test_job_123",
            "title": "Security Intern",
            "company": "Test Direct Corp",
            "market": "vietnam",
            "status": "Đã tìm thấy"
        })
        test_app = {
            "id": "app_test_direct_action",
            "job_id": "test_job_123",
            "company": "Test Direct Corp",
            "role": "Security Intern",
            "status": "READY",
            "channel": "form",
            "recipient": "https://company.com/apply"
        }
        db.save_application(test_app)

        # 1. Update Channel
        resp = self.client.put(
            "/api/applications/app_test_direct_action/channel",
            headers={"X-CSRF-Token": CSRF_TOKEN},
            json={"channel": "email", "recipient": "hr@testdirect.com"}
        )
        self.assertEqual(resp.status_code, 200)
        updated = db.get_application("app_test_direct_action")
        self.assertEqual(updated["channel"], "email")
        self.assertEqual(updated["recipient"], "hr@testdirect.com")

        # 2. Direct Send Email Validation (Missing or bad recipient)
        resp_err = self.client.post(
            "/api/applications/app_test_direct_action/direct-send-email",
            headers={"X-CSRF-Token": CSRF_TOKEN},
            json={"recipient": "invalid-email"}
        )
        self.assertEqual(resp_err.status_code, 400)
        self.assertIn("Vui lòng nhập địa chỉ email", resp_err.json()["detail"])

        # 3. Direct Form Fill Validation (Missing or bad URL)
        resp_url_err = self.client.post(
            "/api/applications/app_test_direct_action/direct-fill",
            headers={"X-CSRF-Token": CSRF_TOKEN},
            json={"recipient": "not_a_url"}
        )
        self.assertEqual(resp_url_err.status_code, 400)
        self.assertIn("đường dẫn URL hợp lệ", resp_url_err.json()["detail"])

    def test_auto_apply_email_and_package_preparation(self):
        db = DatabaseManager()
        # Seed a test job with company AvePoint
        job_id = "test_job_avepoint_auto"
        db.save_job({
            "id": job_id,
            "title": "Cloud Security Intern",
            "company": "AvePoint",
            "market": "vietnam",
            "status": "Đã tìm thấy",
            "source": "https://careers.avepoint.com/job/123",
            "raw_jd": "AvePoint is looking for Cloud Security Intern. Contact hr at careers_vn@avepoint.com"
        })

        # 1. Test get_package_details auto-prepares package on the fly
        resp_pkg = self.client.get(f"/api/packages/{job_id}")
        self.assertEqual(resp_pkg.status_code, 200)
        pkg_data = resp_pkg.json()
        self.assertEqual(pkg_data["auto_hr_email"], "careers_vn@avepoint.com")
        self.assertIn("cv_en.pdf", pkg_data["pdf_url"])

        # 2. Test auto-apply-email automatically sends email with CV attached
        resp_auto = self.client.post(
            f"/api/jobs/{job_id}/auto-apply-email",
            headers={"X-CSRF-Token": CSRF_TOKEN}
        )
        self.assertEqual(resp_auto.status_code, 200)
        auto_res = resp_auto.json()
        self.assertEqual(auto_res["status"], "success")
        self.assertEqual(auto_res["hr_email"], "careers_vn@avepoint.com")
        self.assertIn("thành công", auto_res["message"])

        # Verify job status in db updated to 'Đã gửi email'
        updated_job = db.get_job(job_id)
        self.assertEqual(updated_job["status"], "Đã gửi email")

    def test_settings_retrieval_and_email_config(self):
        resp = self.client.get("/api/settings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("automation_mode", data)
        self.assertIn("email_provider", data)
        self.assertIn("is_mock", data)

        # Configure mock provider
        resp_mock = self.client.post(
            "/api/settings/email",
            headers={"X-CSRF-Token": CSRF_TOKEN},
            json={"provider": "mock"}
        )
        self.assertEqual(resp_mock.status_code, 200)
        self.assertTrue(resp_mock.json()["is_mock"])

        # Test email connection endpoint
        resp_conn = self.client.post(
            "/api/email/test-connection",
            headers={"X-CSRF-Token": CSRF_TOKEN}
        )
        self.assertEqual(resp_conn.status_code, 200)
        self.assertTrue(resp_conn.json()["success"])

    def test_candidate_form_assist_endpoint(self):
        resp = self.client.get("/api/candidate/form-assist")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["full_name"], "Ngô Văn Hiền")
        self.assertEqual(data["email"], "hienngo090800@gmail.com")
        self.assertEqual(data["phone"], "0393492064")
        self.assertTrue("VKU" in data["university"] or "Việt - Hàn" in data["university"])

    def test_mark_form_submitted_endpoint(self):
        db = DatabaseManager()
        test_id = "test_form_mark_job"
        db.save_job({
            "id": test_id,
            "title": "Cloud Trainee",
            "company": "Form Test Corp",
            "market": "vietnam",
            "status": "Chưa nộp"
        })
        resp = self.client.post(
            f"/api/jobs/{test_id}/mark-form-submitted",
            headers={"X-CSRF-Token": CSRF_TOKEN}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "success")
        updated = db.get_job(test_id)
        self.assertEqual(updated["status"], "Đã nộp qua form")


if __name__ == "__main__":
    unittest.main()

