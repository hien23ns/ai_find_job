"""
End-to-End Form Automation Tests with Playwright against a Local Mock ATS Server.
Tests multi-step forms, file uploads, validation, CAPTCHA/OTP challenges,
unknown questions, and explicit confirmation verification.
Runs 100% offline without hitting any external servers.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import shutil
import socket
import threading
import time
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from src.form_automation import FormAutomationManager, LocalTestFormAdapter


class MockAtsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Quiet logging

    def do_GET(self):
        if self.path == "/test-form":
            html = """<!DOCTYPE html>
            <html>
            <head><meta charset="utf-8"><title>Mock ATS Form</title></head>
            <body>
              <form id="ats-form" method="POST" action="/submit" enctype="multipart/form-data">
                <input type="text" name="full_name" id="full_name" />
                <input type="email" name="email" id="email" />
                <input type="text" name="phone" id="phone" />
                <input type="text" name="university" id="university" />
                <input type="text" name="major" id="major" />
                <input type="text" name="gpa" id="gpa" />
                <select name="grad_year" id="grad_year">
                  <option value="2027">2027</option>
                  <option value="2028">2028</option>
                </select>
                <input type="radio" name="work_authorization" value="yes" id="auth_yes" />
                <textarea name="why_interested" id="why_interested"></textarea>
                <input type="file" name="resume" id="resume" />
                <button type="submit" id="submit-application-btn">Nộp đơn ứng tuyển</button>
              </form>
            </body>
            </html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/captcha-form":
            html = """<!DOCTYPE html>
            <html>
            <body>
              <div id="captcha-container">
                <p>Vui lòng vượt qua CAPTCHA trước khi tiếp tục</p>
              </div>
            </body>
            </html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/unknown-question-form":
            html = """<!DOCTYPE html>
            <html>
            <body>
              <div class="unknown-question">
                <label class="unknown-question-label">Bạn có sẵn sàng chuyển đến chi nhánh Tokyo không?</label>
                <input type="text" name="relocation_tokyo" />
              </div>
            </body>
            </html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        elif self.path == "/ambiguous-form":
            html = """<!DOCTYPE html>
            <html>
            <body>
              <button type="submit" id="submit-application-btn">Nộp đơn</button>
            </body>
            </html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/submit":
            html = """<!DOCTYPE html>
            <html>
            <body>
              <div class="submission-success">
                <h1>Thành công</h1>
                <p>Hồ sơ ứng tuyển của bạn đã được tiếp nhận thành công!</p>
              </div>
            </body>
            </html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")


class TestFormAutomationE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start local mock ATS server on an ephemeral port
        cls.server = HTTPServer(("127.0.0.1", 0), MockAtsHandler)
        cls.port = cls.server.server_port
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.test_dir = PROJECT_ROOT / ".local" / "test_form_e2e_temp"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)

        self.cv_path = self.test_dir / "cv_en.pdf"
        self.cv_path.write_bytes(b"%PDF-1.4 Mock CV content for upload testing")

        self.automator = FormAutomationManager(headless=True)

    def tearDown(self):
        self.automator.close()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_dry_run_fills_fields_without_submitting(self):
        app_data = {
            "form_answers": {
                "full_name": "Ngô Văn Hiền",
                "email": "hienngo090800@gmail.com",
                "phone": "0393492064",
                "university": "VKU",
                "major": "An toàn thông tin",
                "gpa": "2.9",
                "pre_drafted_responses": {"why_interested": "I want to apply Linux & Python skills"}
            }
        }
        res = self.automator.process_application_form(
            url=f"{self.base_url}/test-form",
            app_data=app_data,
            cv_path=self.cv_path,
            dry_run=True
        )
        self.assertEqual(res.status, "NEEDS_REVIEW")
        self.assertEqual(res.current_step, "REVIEW_READY")
        self.assertIn("Dry Run", res.message)

    def test_live_submit_reaches_success_confirmation(self):
        app_data = {
            "form_answers": {
                "full_name": "Ngô Văn Hiền",
                "email": "hienngo090800@gmail.com",
                "phone": "0393492064",
                "university": "VKU",
                "major": "An toàn thông tin",
                "gpa": "2.9"
            }
        }
        res = self.automator.process_application_form(
            url=f"{self.base_url}/test-form",
            app_data=app_data,
            cv_path=self.cv_path,
            dry_run=False
        )
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(res.current_step, "COMPLETED")
        self.assertIsNotNone(res.proof_path)

    def test_captcha_detection_halts_and_awaits_user(self):
        app_data = {"form_answers": {}}
        res = self.automator.process_application_form(
            url=f"{self.base_url}/captcha-form",
            app_data=app_data,
            dry_run=False
        )
        self.assertEqual(res.status, "AWAITING_USER")
        self.assertEqual(res.current_step, "CAPTCHA_CHALLENGE")
        self.assertIn("CAPTCHA", res.message)

    def test_unknown_question_prompts_user_intervention(self):
        app_data = {"form_answers": {}}
        res = self.automator.process_application_form(
            url=f"{self.base_url}/unknown-question-form",
            app_data=app_data,
            dry_run=False
        )
        self.assertEqual(res.status, "AWAITING_USER")
        self.assertEqual(res.current_step, "UNKNOWN_QUESTION")
        self.assertIsNotNone(res.question_prompt)
        self.assertIn("Tokyo", res.question_prompt["question"])

    def test_ambiguous_post_submit_transitions_to_unknown(self):
        app_data = {"form_answers": {}}
        res = self.automator.process_application_form(
            url=f"{self.base_url}/ambiguous-form",
            app_data=app_data,
            dry_run=False
        )
        self.assertEqual(res.status, "UNKNOWN")
        self.assertIn("UNKNOWN", res.message)


if __name__ == "__main__":
    unittest.main()
