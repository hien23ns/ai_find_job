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
        from src.db import get_connection
        conn = get_connection(db.db_path)
        with conn:
            conn.execute("DELETE FROM applications WHERE job_id = ? OR id LIKE ?", (job_id, f"app_{job_id}%"))
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.close()

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
        updated = db.get_job(test_id)
        self.assertEqual(updated["status"], "Đã nộp qua form")

    def test_job_filtering_by_category_location_work_mode_employment_type(self):
        db = DatabaseManager()
        # Seed test jobs with diverse domains, locations, and modalities
        db.save_job({
            "id": "test_filter_design",
            "title": "Graphic Design Intern",
            "company": "Creative Hub Studio",
            "market": "vietnam",
            "location": "danang",
            "category": "design",
            "work_mode": "onsite",
            "employment_type": "internship",
            "status": "Chưa nộp"
        })
        db.save_job({
            "id": "test_filter_marketing_remote",
            "title": "Digital Marketing Specialist",
            "company": "Growth Agency VN",
            "market": "vietnam",
            "location": "remote",
            "category": "marketing",
            "work_mode": "remote",
            "employment_type": "fulltime",
            "status": "Chưa nộp"
        })
        db.save_job({
            "id": "test_filter_parttime",
            "title": "Content Creator Part-time",
            "company": "Media House",
            "market": "vietnam",
            "location": "hanoi",
            "category": "marketing",
            "work_mode": "hybrid",
            "employment_type": "parttime",
            "status": "Chưa nộp"
        })

        # Test Category Filter
        resp_cat = self.client.get("/api/jobs?category=design")
        self.assertEqual(resp_cat.status_code, 200)
        jobs_cat = resp_cat.json()
        self.assertTrue(all(j.get("category") == "design" for j in jobs_cat))
        self.assertTrue(any(j["id"] == "test_filter_design" for j in jobs_cat))

        # Test Location Filter
        resp_loc = self.client.get("/api/jobs?location=danang")
        self.assertEqual(resp_loc.status_code, 200)
        jobs_loc = resp_loc.json()
        self.assertTrue(all(any(k in (j.get("location") or "").lower() for k in ["danang", "da nang", "đà"]) for j in jobs_loc))

        # Test Work Mode Filter
        resp_mode = self.client.get("/api/jobs?work_mode=remote")
        self.assertEqual(resp_mode.status_code, 200)
        jobs_mode = resp_mode.json()
        self.assertTrue(all(j.get("work_mode") == "remote" for j in jobs_mode))

        # Test Employment Type Filter
        resp_type = self.client.get("/api/jobs?employment_type=parttime")
        self.assertEqual(resp_type.status_code, 200)
        jobs_type = resp_type.json()
        self.assertTrue(all(j.get("employment_type") in ["parttime", "part_time"] for j in jobs_type))

    def test_job_search_with_category_and_location(self):
        resp = self.client.post(
            "/api/jobs/search",
            headers={"X-CSRF-Token": CSRF_TOKEN},
            json={
                "category": "design",
                "location": "danang",
                "work_mode": "all",
                "employment_type": "all",
                "limit": 5
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_found", data)
        self.assertIn("imported_count", data)
        self.assertGreater(data["total_found"], 0)


if __name__ == "__main__":
    unittest.main()

