"""
Unit tests for application sender and email drafting module.
"""

import json
import unittest
from pathlib import Path
import tempfile
import shutil

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from src.application_sender import (
    detect_application_channel,
    draft_job_emails,
    generate_form_answer_bank,
    build_rfc822_eml,
    create_application_bundle,
    execute_application_dispatch
)


class TestApplicationSender(unittest.TestCase):
    def setUp(self):
        cand_path = PROJECT_ROOT / "data" / "candidates" / "my_profile.json"
        if not cand_path.exists():
            cand_path = PROJECT_ROOT / "tests" / "fixtures" / "candidate_mock_profile.json"
        self.candidate = json.loads(cand_path.read_text(encoding="utf-8"))
        self.test_dir = PROJECT_ROOT / ".local" / "test_sender_temp"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_detect_channel_email(self):
        jd_data = {"text": "Ứng viên vui lòng gửi CV về địa chỉ: recruitment@techcorp.vn trước ngày 30/11."}
        ch = detect_application_channel(jd_data, {})
        self.assertEqual(ch["channel"], "email")
        self.assertEqual(ch["recipient"], "recruitment@techcorp.vn")
        self.assertTrue(ch["verified"])

    def test_detect_channel_form(self):
        jd_data = {"text": "Nộp đơn tại cổng tuyển dụng trực tuyến.", "source": "https://company.com/jobs/123"}
        ch = detect_application_channel(jd_data, {})
        self.assertEqual(ch["channel"], "form")
        self.assertEqual(ch["recipient"], "https://company.com/jobs/123")
        self.assertTrue(ch["verified"])

    def test_detect_channel_missing(self):
        jd_data = {"text": "Tuyển dụng kỹ sư bảo mật tại Hà Nội.", "source": "file://local_jd.txt"}
        ch = detect_application_channel(jd_data, {})
        self.assertEqual(ch["channel"], "missing_channel")
        self.assertIsNone(ch["recipient"])
        self.assertFalse(ch["verified"])

    def test_draft_emails_options_a_and_b(self):
        eval_result = {"match_score": 93, "hard_requirements": []}
        drafts = draft_job_emails(
            self.candidate,
            company="Hitachi Digital Services",
            role="Cloud & DevOps Intern",
            eval_result=eval_result,
            language="en"
        )
        
        # Option A: Inquiry
        opt_a = drafts["option_a"]
        self.assertIn("Inquiry", opt_a["subject"])
        self.assertIn("GPA is currently 2.9/4.0", opt_a["body"])
        self.assertIn("VKU", opt_a["body"])
        
        # Option B: Direct Application
        opt_b = drafts["option_b"]
        self.assertIn("Application for Cloud & DevOps Intern", opt_b["subject"])
        # Word count between 120 and 180 words
        self.assertGreaterEqual(opt_b["word_count"], 115)
        self.assertLessEqual(opt_b["word_count"], 185)
        self.assertIn("2028", opt_b["body"])
        self.assertIn("These projects have given me opportunities to apply programming and networking concepts", opt_b["body"])
        self.assertNotIn("distributed networking and client-server", opt_b["body"])

    def test_rfc822_eml_creation(self):
        test_pdf = self.test_dir / "sample_cv.pdf"
        test_pdf.write_bytes(b"%PDF-1.4 Mock PDF content")
        eml_out = self.test_dir / "test.eml"
        
        build_rfc822_eml(
            from_email="hien@example.com",
            from_name="Ngô Văn Hiền",
            to_email="hr@hitachi.com",
            subject="Test Application",
            body_text="Please find attached my CV.",
            attachment_paths=[test_pdf],
            output_eml_path=eml_out
        )
        
        self.assertTrue(eml_out.exists())
        eml_bytes = eml_out.read_bytes()
        self.assertIn(b"X-Unsent: 1", eml_bytes)
        self.assertIn(b"sample_cv.pdf", eml_bytes)

    def test_anti_duplicate_prevention(self):
        # Setup application.json with status SENT
        app_json = self.test_dir / "application.json"
        app_json.write_text(json.dumps({
            "job_id": "test_123",
            "company": "Hitachi",
            "role": "Cloud Intern",
            "status": "SENT",
            "channel": "email",
            "recipient": "recruitment@hitachi.com",
            "channel_verified": True,
            "attachments": []
        }), encoding="utf-8")
        
        res = execute_application_dispatch(self.test_dir, action="mark_sent", force=False)
        self.assertEqual(res["status"], "DUPLICATE_PREVENTED")
        
        # With force=True, should succeed
        res_force = execute_application_dispatch(self.test_dir, action="mark_sent", force=True)
        self.assertEqual(res_force["status"], "MARKED_SENT")

    def test_form_answer_bank(self):
        bank = generate_form_answer_bank(self.candidate, "Hitachi", "Cloud Intern")
        self.assertEqual(bank["graduation_year"], "2028")
        self.assertIn("VKU", bank["university"])
        self.assertIn("pre_drafted_responses", bank)
        self.assertIn("why_interested", bank["pre_drafted_responses"])

    def test_missing_recipient_blocks_dispatch(self):
        app_json = self.test_dir / "application.json"
        app_json.write_text(json.dumps({
            "job_id": "test_missing",
            "company": "Unknown Corp",
            "role": "Security Intern",
            "status": "Thiếu kênh nộp",
            "channel": "missing_channel",
            "recipient": None,
            "channel_verified": False,
            "attachments": []
        }), encoding="utf-8")
        
        res = execute_application_dispatch(self.test_dir, action="mark_sent")
        self.assertEqual(res["status"], "REJECTED_MISSING_CHANNEL")
        self.assertIn("CHẶN GỬI", res["message"])

    def test_missing_attachment_blocks_dispatch(self):
        app_json = self.test_dir / "application.json"
        app_json.write_text(json.dumps({
            "job_id": "test_att",
            "company": "Tech Corp",
            "role": "DevOps Intern",
            "status": "DRAFT",
            "channel": "email",
            "recipient": "hr@techcorp.vn",
            "channel_verified": True,
            "attachments": [{"filename": "non_existent_cv.pdf", "sha256": "abcdef"}]
        }), encoding="utf-8")
        
        res = execute_application_dispatch(self.test_dir, action="mark_sent")
        self.assertEqual(res["status"], "REJECTED_MISSING_ATTACHMENT")
        self.assertIn("non_existent_cv.pdf", res["message"])

    def test_file_integrity_mismatch_blocks_dispatch(self):
        test_file = self.test_dir / "tampered_cv.pdf"
        test_file.write_bytes(b"%PDF-1.4 modified content")
        
        app_json = self.test_dir / "application.json"
        app_json.write_text(json.dumps({
            "job_id": "test_integrity",
            "company": "Tech Corp",
            "role": "DevOps Intern",
            "status": "DRAFT",
            "channel": "email",
            "recipient": "hr@techcorp.vn",
            "channel_verified": True,
            "attachments": [{"filename": "tampered_cv.pdf", "sha256": "different_hash_value_123456"}]
        }), encoding="utf-8")
        
        res = execute_application_dispatch(self.test_dir, action="mark_sent")
        self.assertEqual(res["status"], "REJECTED_FILE_INTEGRITY_MISMATCH")
        self.assertIn("sai phiên bản", res["message"])

    def test_user_cancellation_blocks_dispatch(self):
        app_json = self.test_dir / "application.json"
        app_json.write_text(json.dumps({
            "job_id": "test_cancel",
            "company": "Tech Corp",
            "role": "DevOps Intern",
            "status": "DRAFT",
            "channel": "email",
            "recipient": "hr@techcorp.vn",
            "channel_verified": True,
            "attachments": []
        }), encoding="utf-8")
        
        res = execute_application_dispatch(self.test_dir, action="mark_sent", confirmed=False)
        self.assertEqual(res["status"], "CANCELLED_BY_USER")

    def test_timeout_no_auto_retry_safeguard(self):
        app_json = self.test_dir / "application.json"
        app_json.write_text(json.dumps({
            "job_id": "test_timeout",
            "company": "Tech Corp",
            "role": "DevOps Intern",
            "status": "DRAFT",
            "channel": "email",
            "recipient": "hr@techcorp.vn",
            "channel_verified": True,
            "attachments": []
        }), encoding="utf-8")
        
        res = execute_application_dispatch(self.test_dir, action="send_email", simulate_timeout=True)
        self.assertEqual(res["status"], "TIMEOUT_NO_RETRY")
        self.assertIn("KHÔNG tự động gửi lại", res["message"])
        
        # Verify status remained DRAFT, not corrupted
        updated = json.loads(app_json.read_text(encoding="utf-8"))
        self.assertEqual(updated["status"], "DRAFT")
        history_actions = [h["action"] for h in updated["submission_history"]]
        self.assertIn("TIMEOUT_UNCONFIRMED", history_actions)

    def test_send_failure_keeps_draft_status(self):
        app_json = self.test_dir / "application.json"
        app_json.write_text(json.dumps({
            "job_id": "test_fail",
            "company": "Tech Corp",
            "role": "DevOps Intern",
            "status": "DRAFT",
            "channel": "email",
            "recipient": "hr@techcorp.vn",
            "channel_verified": True,
            "attachments": []
        }), encoding="utf-8")
        
        res = execute_application_dispatch(self.test_dir, action="send_email", simulate_failure=True)
        self.assertEqual(res["status"], "SEND_FAILED")
        
        updated = json.loads(app_json.read_text(encoding="utf-8"))
        self.assertEqual(updated["status"], "DRAFT")
        history_actions = [h["action"] for h in updated["submission_history"]]
        self.assertIn("SEND_FAILED", history_actions)

    def test_send_success_records_message_id_and_audit(self):
        app_json = self.test_dir / "application.json"
        app_json.write_text(json.dumps({
            "job_id": "test_success",
            "company": "Tech Corp",
            "role": "DevOps Intern",
            "status": "DRAFT",
            "channel": "email",
            "recipient": "hr@techcorp.vn",
            "channel_verified": True,
            "attachments": []
        }), encoding="utf-8")
        
        res = execute_application_dispatch(self.test_dir, action="send_email")
        self.assertEqual(res["status"], "SENT_SUCCESS")
        self.assertIn("message_id", res)
        
        updated = json.loads(app_json.read_text(encoding="utf-8"))
        self.assertEqual(updated["status"], "SENT")
        history_actions = [h["action"] for h in updated["submission_history"]]
        self.assertIn("EMAIL_SENT_SUCCESS", history_actions)


if __name__ == "__main__":
    unittest.main()
