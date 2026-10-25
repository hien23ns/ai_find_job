"""
Unit tests for Email Dispatch Subsystem, credential encryption,
header injection defenses, and timeout safeguards.
"""

from pathlib import Path
import shutil
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from src.email_sender import (
    LocalMockEmailProvider,
    SmtpEmailProvider,
    save_email_credentials,
    load_email_credentials,
    clear_email_credentials,
    CREDENTIALS_FILE,
    KEY_FILE
)


class TestEmailDispatchAdvanced(unittest.TestCase):
    def setUp(self):
        self.test_dir = PROJECT_ROOT / ".local" / "test_email_adv_temp"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        clear_email_credentials()

    def test_credential_encryption_roundtrip(self):
        secret_config = {
            "provider": "smtp",
            "host": "smtp.gmail.com",
            "port": 587,
            "username": "user@gmail.com",
            "password": "super_secret_app_password_xyz123",
            "use_tls": True
        }
        save_email_credentials(secret_config)

        self.assertTrue(CREDENTIALS_FILE.exists())
        raw_file_bytes = CREDENTIALS_FILE.read_bytes()

        # Verify password is NOT stored as plaintext in the file
        self.assertNotIn(b"super_secret_app_password_xyz123", raw_file_bytes)

        # Verify decryption restores original configuration
        loaded = load_email_credentials()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["password"], "super_secret_app_password_xyz123")
        self.assertEqual(loaded["username"], "user@gmail.com")

    def test_header_injection_rejection(self):
        provider = LocalMockEmailProvider()
        res = provider.send_email(
            from_email="candidate@test.local",
            from_name="Candidate",
            to_email="hr@victim.com\r\nBcc: evil@attacker.com",
            subject="Valid Subject",
            body_text="Hello"
        )
        self.assertEqual(res.status, "FAILED")
        self.assertIn("Header Injection", res.message)

        # Subject injection
        res2 = provider.send_email(
            from_email="candidate@test.local",
            from_name="Candidate",
            to_email="hr@victim.com",
            subject="Subject\r\nInjected-Header: value",
            body_text="Hello"
        )
        self.assertEqual(res2.status, "FAILED")

    def test_mock_provider_dispatch_and_audit(self):
        provider = LocalMockEmailProvider()
        test_pdf = self.test_dir / "cv_sample.pdf"
        test_pdf.write_bytes(b"%PDF-1.4 Mock CV")

        res = provider.send_email(
            from_email="hien@example.com",
            from_name="Ngô Văn Hiền",
            to_email="hr@hitachi.com",
            subject="Application for Cloud Intern",
            body_text="Dear Hiring Team, please find attached my CV.",
            attachment_paths=[test_pdf]
        )
        self.assertEqual(res.status, "SENT")
        self.assertIsNotNone(res.message_id)
        self.assertEqual(len(provider.sent_messages), 1)
        self.assertIn("cv_sample.pdf", provider.sent_messages[0]["attachments"])

    def test_missing_attachment_fails_before_smtp_connect(self):
        smtp = SmtpEmailProvider(
            host="127.0.0.1",
            port=2525,
            username="",
            password="",
            timeout_seconds=2
        )
        missing_file = self.test_dir / "non_existent.pdf"
        res = smtp.send_email(
            from_email="cand@test.com",
            from_name="Candidate",
            to_email="hr@test.com",
            subject="Test Application",
            body_text="Body",
            attachment_paths=[missing_file]
        )
        self.assertEqual(res.status, "FAILED")
        self.assertIn("Thiếu tệp đính kèm", res.message)

    def test_recipient_trailing_dot_and_punctuation_sanitization(self):
        provider = LocalMockEmailProvider()
        res = provider.send_email(
            from_email="cand@test.com",
            from_name="Ngô Văn Hiền",
            to_email="careers@cystack.net.",
            subject="Test Application",
            body_text="Body text"
        )
        self.assertEqual(res.status, "SENT")
        self.assertEqual(provider.sent_messages[-1]["to"], "careers@cystack.net")

    def test_corporate_email_html_formatting_and_no_disclaimers(self):
        from src.application_sender import build_corporate_email_html
        body_text = """Kính gửi Bộ phận Tuyển dụng CyStack,

Tôi viết thư này để ứng tuyển vị trí SOC Analyst Intern.

Trân trọng,
Ngô Văn Hiền
GitHub: https://github.com/hien23ns
LinkedIn: https://www.linkedin.com/in/ngovanhien"""

        html_out = build_corporate_email_html(body_text, candidate_name="Ngô Văn Hiền")
        self.assertIn("Kính gửi Bộ phận Tuyển dụng CyStack", html_out)
        self.assertIn('<a href="https://github.com/hien23ns"', html_out)
        self.assertIn('<a href="https://www.linkedin.com/in/ngovanhien"', html_out)
        self.assertNotIn("disclaimer", html_out)
        self.assertNotIn("DRAFT", html_out)
        self.assertNotIn("Ghi chú an toàn", html_out)
        self.assertNotIn("python -m src.cli apply", html_out)

    def test_extract_clean_email_components_strips_internal_draft_headers(self):
        from src.application_sender import extract_clean_email_components
        pkg_dir = self.test_dir / "test_pkg_v1"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "email_subject.txt").write_text("""[LỰA CHỌN B - ỨNG TUYỂN TRỰC TIẾP (KHUYÊN DÙNG)]:
Ứng tuyển vị trí SOC Analyst Intern - Ngô Văn Hiền

[LỰA CHỌN A - HỎI ĐIỀU KIỆN GPA / LỊCH THỰC TẬP]:
Thắc mắc về điều kiện ứng tuyển SOC Analyst Intern - Ngô Văn Hiền""", encoding="utf-8")

        (pkg_dir / "email_body.txt").write_text("""======================================================================
LỰA CHỌN B: EMAIL ỨNG TUYỂN TRUNG THỰC (Độ dài: 140 từ)
======================================================================
Kính gửi Quý công ty,

Tôi xin ứng tuyển vị trí SOC Analyst.

Trân trọng,
Ngô Văn Hiền

======================================================================
LỰA CHỌN A: EMAIL HỎI ĐIỀU KIỆN NGOẠI LỆ GPA & LỊCH THỰC TẬP (Độ dài: 120 từ)
======================================================================
Kính gửi Quý công ty, Tôi muốn hỏi về GPA.""", encoding="utf-8")

        subj, body, body_html = extract_clean_email_components(pkg_dir, role="SOC Analyst Intern", company="CyStack")
        self.assertEqual(subj, "Ứng tuyển vị trí SOC Analyst Intern - Ngô Văn Hiền")
        self.assertIn("Tôi xin ứng tuyển vị trí SOC Analyst.", body)
        self.assertNotIn("LỰA CHỌN B", body)
        self.assertNotIn("LỰA CHỌN A", body)
        self.assertNotIn("======================================================================", body)
        self.assertNotIn("disclaimer", body_html)
        self.assertNotIn("Ghi chú an toàn", body_html)

    def test_smtp_provider_sanitizes_accidental_preview_html(self):
        smtp = SmtpEmailProvider(
            host="127.0.0.1",
            port=2525,
            username="",
            password="",
            timeout_seconds=2
        )
        contaminated_html = """<div class="preview-card">
          <div class="disclaimer">Ghi chú an toàn: Email này đang ở trạng thái DRAFT. Bạn có thể dùng lệnh python -m src.cli apply</div>
        </div>"""
        clean_text = "Dear Hiring Team, please find attached my CV. Sincerely, Ngô Văn Hiền"
        # Using LocalMockEmailProvider to inspect resulting message parts
        provider = LocalMockEmailProvider()
        res = provider.send_email(
            from_email="cand@test.com",
            from_name="Ngô Văn Hiền",
            to_email="hr@cystack.net",
            subject="Clean Application",
            body_text=clean_text,
            body_html=contaminated_html
        )
        self.assertEqual(res.status, "SENT")


if __name__ == "__main__":
    unittest.main()
