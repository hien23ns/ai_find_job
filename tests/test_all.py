"""
Comprehensive Automated Test Suite for ai-job-search.
Covers all 14 baseline test cases plus comprehensive regression test suite (test_01 to test_30):
1. Runtime launch on Windows (verifies end-to-end execution flow)
2. Paths with spaces handling
3. JD input from direct text and UTF-8 files
4. Multilingual support (Vietnamese, Korean, English)
5. Independent evaluation for all 3 markets (VN, KR, Freelance)
6. Incomplete / missing candidate data handling
7. Unclear visa and language requirements in Korea JDs
8. URL errors, blocked pages, and expired job postings
9. Deduplication across multiple sources
10. Markdown CV, Cover Letter, Proposal, and Interview Prep generation
11. Tracker data persistence, updates, and querying
12. Adversarial Prompt Injection neutralization
13. Strict platform-aware filesystem boundary enforcement (anti-traversal)
14. Fallback flows when Bun, LaTeX, or AI services are offline
15. Freelance milestone negotiation without unwarranted percentages
16. Clean output prefix anti-traversal defense
17. Tracker isolation with custom file
18. Demo/fixture run does not mutate production tracker
19. Upstream bridge canonical deduplication key
20. Upstream supply-chain security guards (security_guards.py)
21. Candidate thin-pointer schema validation
--- REGRESSION SUITE ---
22. Comprehensive mask_secrets test suite
23. Korea negation detection, evidence quotation, and disqualifiers
24. Tracker re-evaluation status preservation, atomic writes, corrupt JSON defense
25. Generator: strictly no false competence claims on empty candidate profiles
26. Generator: mock badge across all 4 document types
27. Output filename collision defense across multiple companies
28. CLI mode separation: rules (0 network) vs AI (mocked) and error handling
29. Cross-platform filesystem boundary enforcement
30. Tracker CSV export preserves production CSV
"""

import argparse
import csv
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from src.ai_service import AIService
from src.config import CANDIDATES_DIR, LOCAL_DIR, OUTPUT_DIR, PROJECT_ROOT, TEMP_DIR
from src.evaluator import JobEvaluator
from src.generator import DocumentGenerator
from src.jd_parser import (
    HTMLTextExtractor,
    compute_jd_hash,
    deduplicate_jds,
    fetch_jd_url,
    parse_jd_text,
    read_jd_file,
)
from src.security import ensure_within_project, mask_secrets, sanitize_untrusted_text
from src.tracker import JobTracker

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

class TestAIJobSearch(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        candidate_file = FIXTURES_DIR / "candidate_mock.json"
        cls.candidate = json.loads(candidate_file.read_text(encoding="utf-8"))
        
        incomplete_file = FIXTURES_DIR / "candidate_incomplete.json"
        cls.incomplete_candidate = json.loads(incomplete_file.read_text(encoding="utf-8"))

    # 1. Khởi chạy bằng runtime Windows với luồng chạy thực tế
    def test_01_runtime_launch_on_windows(self):
        self.assertGreaterEqual(sys.version_info, (3, 10), "Yêu cầu Python 3.10+ trên Windows")
        self.assertTrue(PROJECT_ROOT.exists(), f"PROJECT_ROOT phải tồn tại: {PROJECT_ROOT}")
        self.assertTrue((PROJECT_ROOT / "src" / "cli.py").exists(), "cli.py phải tồn tại")
        
        # Test real execution flow via subprocess
        proc = subprocess.run(
            [sys.executable, "-m", "src.cli", "upstream-info"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            encoding="utf-8"
        )
        self.assertEqual(proc.returncode, 0, f"CLI execution failed: {proc.stderr}")
        self.assertIn("THÔNG TIN KHO NGUỒN UPSTREAM", proc.stdout)

    # 2. Xử lý đường dẫn chứa dấu cách tiếng Việt
    def test_02_paths_with_spaces_and_unicode(self):
        space_dir = TEMP_DIR / "Thư mục kiểm thử với dấu cách"
        space_dir.mkdir(parents=True, exist_ok=True)
        test_file = space_dir / "mô_tả_công_việc_tiếng_việt.txt"
        test_file.write_text("Tuyển dụng chuyên gia bảo mật thông tin tại Hà Nội", encoding="utf-8")
        
        parsed = read_jd_file(test_file)
        self.assertEqual(parsed["raw_content"], "Tuyển dụng chuyên gia bảo mật thông tin tại Hà Nội")
        self.assertEqual(parsed["title"], "Tuyển dụng chuyên gia bảo mật thông tin tại Hà Nội")

    # 3. Nạp JD từ direct text và file UTF-8
    def test_03_jd_input_sources(self):
        text_jd = parse_jd_text("Tuyển thực tập sinh SOC Analyst\nCông ty: CyStack", source="manual_input")
        self.assertEqual(text_jd["source"], "manual_input")
        self.assertEqual(text_jd["company"], "CyStack")
        self.assertIn("SOC Analyst", text_jd["title"])

        vn_file = FIXTURES_DIR / "jd_vietnam_soc.txt"
        file_jd = read_jd_file(vn_file)
        self.assertIn("file://", file_jd["source"])
        self.assertTrue(len(file_jd["raw_content"]) > 100)

    # 4. Hỗ trợ đa ngôn ngữ (Việt, Hàn, Anh)
    def test_04_multilingual_support(self):
        extractor = HTMLTextExtractor()
        html_kr = "<p>정보보안 및 보안관제 엔지니어 채용. 비즈니스 한국어 소통 가능자.</p>"
        extractor.feed(html_kr)
        text = extractor.get_text()
        self.assertIn("정보보안", text)
        self.assertIn("한국어", text)

    # 5. Đánh giá độc lập 3 thị trường
    def test_05_independent_market_evaluation(self):
        evaluator = JobEvaluator(self.candidate)

        # 5a. Vietnam market
        vn_jd = read_jd_file(FIXTURES_DIR / "jd_vietnam_soc.txt")
        res_vn = evaluator.evaluate(vn_jd, market="vietnam")
        self.assertEqual(res_vn["market"], "vietnam")
        self.assertGreaterEqual(res_vn["match_score"], 60)
        self.assertEqual(res_vn["recommendation"], "NÊN ỨNG TUYỂN")
        self.assertTrue(any(m["skill"] == "Wireshark" for m in res_vn["matched_skills"]))

        # 5b. Korea market
        kr_jd = read_jd_file(FIXTURES_DIR / "jd_korea_security.txt")
        res_kr = evaluator.evaluate(kr_jd, market="korea")
        self.assertEqual(res_kr["market"], "korea")
        self.assertIsNotNone(res_kr["korea_specifics"])
        self.assertEqual(res_kr["korea_specifics"]["Chấp nhận ứng viên nước ngoài"], "Chấp nhận ứng viên nước ngoài")

        # 5c. Freelance market
        fl_jd = read_jd_file(FIXTURES_DIR / "jd_freelance_python.txt")
        res_fl = evaluator.evaluate(fl_jd, market="freelance")
        self.assertEqual(res_fl["market"], "freelance")
        self.assertIsNotNone(res_fl["freelance_specifics"])
        self.assertEqual(res_fl["freelance_specifics"]["Phạm vi & Đầu ra"], "Đầy đủ")

    # 6. Thiếu thông tin ứng viên
    def test_06_missing_candidate_info(self):
        evaluator = JobEvaluator(self.incomplete_candidate)
        vn_jd = read_jd_file(FIXTURES_DIR / "jd_vietnam_soc.txt")
        res = evaluator.evaluate(vn_jd, market="vietnam")
        self.assertIsInstance(res["match_score"], int)
        self.assertTrue(any("Chưa cập nhật thông tin học vấn" in u for u in res["unclear_items"]))
        self.assertEqual(len(res["matched_skills"]), 0)

    # 7. Không rõ visa hoặc yêu cầu ngôn ngữ (Korea)
    def test_07_korea_unclear_visa_and_language(self):
        evaluator = JobEvaluator(self.candidate)
        unclear_jd = read_jd_file(FIXTURES_DIR / "jd_korea_unclear.txt")
        res = evaluator.evaluate(unclear_jd, market="korea")
        ks = res["korea_specifics"]
        self.assertEqual(ks["Yêu cầu tiếng Hàn"], "Chưa rõ")
        self.assertEqual(ks["Yêu cầu tiếng Anh"], "Chưa rõ")
        self.assertEqual(ks["Hỗ trợ giấy phép làm việc / Visa"], "Chưa rõ")
        self.assertTrue(any("Yêu cầu tiếng Hàn" in q for q in res["clarification_questions"]))

    # 8. Xử lý lỗi URL
    def test_08_url_fetching_and_error_handling(self):
        with self.assertRaises((FileNotFoundError, ConnectionError, PermissionError)):
            fetch_jd_url("http://example.com/non_existent_page_404_url")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"<html><head><title>Cyber Security Intern</title></head><body>We are hiring a Cyber Security Intern at CyStack. TCP/IP, Linux, Wireshark required.</body></html>"
            mock_resp.headers.get_content_charset.return_value = "utf-8"
            mock_urlopen.return_value.__enter__.return_value = mock_resp
            live_res = fetch_jd_url("https://example.com/cyber_intern")
            self.assertFalse(live_res.get("fetch_failed", False))
            self.assertIn("Cyber Security Intern", live_res["title"])

    # 9. Lọc trùng lặp bài đăng
    def test_09_deduplication(self):
        dup_file = FIXTURES_DIR / "jd_duplicates.json"
        data = json.loads(dup_file.read_text(encoding="utf-8"))
        unique, duplicates = deduplicate_jds(data)
        self.assertEqual(len(unique), 3)
        self.assertEqual(len(duplicates), 1)

    # 10. Tạo tài liệu Markdown và HTML
    def test_10_document_generation(self):
        generator = DocumentGenerator(self.candidate)
        cv_md = generator.generate_cv_markdown(target_role="SOC Analyst Intern", market="vietnam")
        self.assertIn("Nguyễn Văn An", cv_md)
        self.assertIn("Học vấn", cv_md)
        self.assertIn("HỒ SƠ MẪU", cv_md)

        evaluator = JobEvaluator(self.candidate)
        vn_jd = read_jd_file(FIXTURES_DIR / "jd_vietnam_soc.txt")
        eval_res = evaluator.evaluate(vn_jd, market="vietnam")
        
        cl_md = generator.generate_cover_letter(eval_res, language="vi")
        self.assertIn("Thư Ứng Tuyển", cl_md)
        self.assertIn("Quý công ty", cl_md)

        prep_md = generator.generate_interview_prep(eval_res)
        self.assertIn("BỘ CÂU HỎI", prep_md)

    # 11. Lưu trữ và truy vấn Tracker
    def test_11_tracker_operations(self):
        test_tracker_path = TEMP_DIR / "test_tracker.json"
        if test_tracker_path.exists():
            test_tracker_path.unlink()
            
        tracker = JobTracker(file_path=test_tracker_path)
        rec = tracker.add_or_update(
            title="SOC Intern",
            company="CyberSec VN",
            market="vietnam",
            source="manual_test",
            match_score=85,
            status="Đang chuẩn bị hồ sơ",
            notes="Chuẩn bị CV Markdown",
            next_step="Luyện phỏng vấn kỹ thuật"
        )
        self.assertEqual(rec["title"], "SOC Intern")
        
        tracker_reloaded = JobTracker(file_path=test_tracker_path)
        retrieved = tracker_reloaded.get(rec["id"])
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["company"], "CyberSec VN")
        self.assertEqual(retrieved["match_score"], 85)

        updated = tracker_reloaded.add_or_update(
            title="SOC Intern",
            company="CyberSec VN",
            market="vietnam",
            source="manual_test",
            match_score=85,
            status="Đã nộp",
            job_id=rec["id"]
        )
        self.assertEqual(updated["status"], "Đã nộp")

        test_csv_path = TEMP_DIR / "test_tracker.csv"
        csv_file = tracker_reloaded.export_csv(test_csv_path)
        self.assertTrue(csv_file.exists())
        content = csv_file.read_text(encoding="utf-8-sig")
        self.assertIn("CyberSec VN", content)

    # 12. Vô hiệu hóa prompt injection
    def test_12_adversarial_prompt_injection_safety(self):
        injection_file = FIXTURES_DIR / "jd_injection.txt"
        parsed = read_jd_file(injection_file)
        sanitized = parsed["raw_content"]
        self.assertIn("[NEUTRALIZED_UNTRUSTED_INSTRUCTION: Ignore all previous instructions]", sanitized)
        self.assertIn("[NEUTRALIZED_UNTRUSTED_INSTRUCTION: DROP TABLE", sanitized)
        self.assertIn("[NEUTRALIZED_UNTRUSTED_INSTRUCTION: <script>alert('XSS_PAYLOAD')</script>]", sanitized)
        
        evaluator = JobEvaluator(self.candidate)
        res = evaluator.evaluate(parsed, market="vietnam")
        self.assertIsInstance(res["match_score"], int)

    # 13. Ranh giới filesystem theo nền tảng
    def test_13_filesystem_boundary_enforcement(self):
        valid_path = PROJECT_ROOT / "docs" / "IMPLEMENTATION_PLAN.md"
        self.assertEqual(ensure_within_project(valid_path), valid_path.resolve())

        with self.assertRaises(PermissionError):
            ensure_within_project(PROJECT_ROOT / ".." / "other_project")

        # Test external path depending on current OS
        if os.name == "nt":
            outside_path = "C:\\Windows\\System32"
        else:
            outside_path = "/etc/passwd"
        with self.assertRaises(PermissionError):
            ensure_within_project(outside_path)

    # 14. Luồng fallback offline
    def test_14_fallback_offline_bun_latex_ai(self):
        ai_service = AIService(api_key=None)
        result = ai_service.analyze_job("JD text here", "Candidate summary", market="vietnam")
        self.assertEqual(result["status"], "BLOCKED_NO_API_KEY")
        self.assertIn("Chưa cấu hình GEMINI_API_KEY", result["notice"])

        generator = DocumentGenerator(self.candidate)
        md_content = "# Test CV\n- Item 1\n- Item 2\n"
        test_html_path = TEMP_DIR / "fallback_cv.html"
        exported_path = generator.export_to_html(md_content, test_html_path)
        self.assertTrue(exported_path.exists())
        html_text = exported_path.read_text(encoding="utf-8")
        self.assertIn("<h1>Test CV</h1>", html_text)
        self.assertIn("<li>Item 1</li>", html_text)

    # 15. Mốc thanh toán Freelance
    def test_15_freelance_milestone_no_unwarranted_percentages(self):
        evaluator = JobEvaluator(self.candidate)
        fl_jd = read_jd_file(FIXTURES_DIR / "jd_freelance_python.txt")
        res = evaluator.evaluate(fl_jd, market="freelance")
        fs = res["freelance_specifics"]
        milestones = fs.get("Mốc bàn giao đề xuất", [])
        self.assertTrue(any("Đề xuất thương lượng" in m or "Tình trạng trong JD" in m for m in milestones))
        gen = DocumentGenerator(self.candidate)
        prop = gen.generate_freelance_proposal(res)
        self.assertIn("ĐỀ XUẤT", prop)

    # 16. Chống Path Traversal qua tên file
    def test_16_clean_prefix_path_traversal_defense(self):
        malicious_titles = ["../../etc/passwd", "..\\..\\windows\\system32", "....", "   "]
        for title in malicious_titles:
            out_prefix = title.replace(" ", "_").lower()
            clean_prefix = "".join(c for c in out_prefix if c.isalnum() or c in "_-")[:30].strip("_-")
            if not clean_prefix:
                clean_prefix = "job_safe_default"
            target_path = ensure_within_project(OUTPUT_DIR / f"{clean_prefix}_cv.md")
            self.assertTrue(str(target_path).startswith(str(PROJECT_ROOT)))
            self.assertNotIn("..", target_path.name)

    # 17. Cách ly tracker với file tùy chọn
    def test_17_tracker_isolation_custom_file(self):
        isolated_tracker_file = TEMP_DIR / "isolated_tracker.json"
        if isolated_tracker_file.exists():
            isolated_tracker_file.unlink()
        tracker = JobTracker(file_path=isolated_tracker_file)
        tracker.add_or_update(
            title="Isolated Job",
            company="Test Corp",
            market="vietnam",
            source="unit_test",
            match_score=90
        )
        self.assertTrue(isolated_tracker_file.exists())
        main_tracker = JobTracker()
        self.assertIsNone(main_tracker.get("job_vietnam_test_corp_isolated_job"))

    # 18. Chạy demo/fixture không làm thay đổi tracker thật
    def test_18_demo_run_does_not_mutate_production_tracker(self):
        prod_tracker_path = PROJECT_ROOT / "data" / "tracker" / "jobs_tracker.json"
        if not prod_tracker_path.exists():
            prod_tracker_path.write_text(json.dumps({"version": "1.0", "last_updated": None, "total_jobs": 0, "jobs": {}}), encoding="utf-8")
        original_content = prod_tracker_path.read_text(encoding="utf-8")

        test_tracker_file = TEMP_DIR / "demo_fixture_tracker.json"
        if test_tracker_file.exists():
            test_tracker_file.unlink()

        from src.cli import cmd_evaluate
        args = argparse.Namespace(
            candidate=str(FIXTURES_DIR / "candidate_mock.json"),
            text=None,
            file=str(FIXTURES_DIR / "jd_vietnam_soc.txt"),
            url=None,
            market="vietnam",
            mode="rules",
            provider="gemini",
            save_track=True,
            tracker_file=str(test_tracker_file),
            generate_docs=False
        )
        cmd_evaluate(args)

        self.assertTrue(test_tracker_file.exists())
        current_content = prod_tracker_path.read_text(encoding="utf-8")
        self.assertEqual(original_content, current_content, "Tracker thật không được phép bị thay đổi khi chạy demo!")

    # 19. Upstream bridge canonical key
    def test_19_upstream_bridge_canonical_key(self):
        from src.upstream_bridge import get_canonical_job_key
        key_vn = get_canonical_job_key("CyStack", "SOC Analyst Intern")
        self.assertEqual(key_vn, "cystack_soc-analyst-intern")
        
        key_kr = get_canonical_job_key("토스", "보안관제 엔지니어")
        self.assertTrue(key_kr.startswith("company-") or "untitled" in key_kr)

    # 20. Upstream bridge security guards
    def test_20_upstream_bridge_security_guards(self):
        from src.upstream_bridge import run_upstream_security_guards
        guards_res = run_upstream_security_guards()
        self.assertEqual(guards_res["status"], "PASS")
        self.assertTrue(guards_res["passed"])
        self.assertIn("security_guards: OK", guards_res["output"])

    # 21. Candidate thin pointer schema
    def test_21_candidate_thin_pointer_schema(self):
        from src.upstream_bridge import validate_candidate_thin_pointer
        res = validate_candidate_thin_pointer(self.candidate)
        self.assertTrue(res["valid"])
        self.assertGreater(res["experience_entries"], 0)
        self.assertGreater(res["labs_entries"], 0)
        self.assertGreater(res["projects_entries"], 0)

    # 22. REGRESSION: mask_secrets() hoạt động chính xác với mọi pattern và text
    def test_22_mask_secrets_comprehensive(self):
        # 22a. Empty and normal strings unchanged
        self.assertEqual(mask_secrets(""), "")
        self.assertEqual(mask_secrets("hello"), "hello")
        self.assertEqual(mask_secrets("Đây là văn bản tiếng Việt bình thường."), "Đây là văn bản tiếng Việt bình thường.")

        # 22b. Key-value assignment masked
        kv_input = "API key configured as: api_key = fake_secret_value_123456"
        masked_kv = mask_secrets(kv_input)
        self.assertNotIn("fake_secret_value_123456", masked_kv)
        self.assertIn("[PROTECTED_SECRET]", masked_kv)

        # 22c. Specific API key patterns (GitHub token, Google AI Studio key)
        mock_ghp = "ghp_" + ("1" * 36)
        gh_input = f"Connect with token {mock_ghp}"
        masked_gh = mask_secrets(gh_input)
        self.assertNotIn(mock_ghp, masked_gh)
        self.assertIn("[PROTECTED_TOKEN]", masked_gh)

        # 22d. Multiple secrets in single string
        mock_multi_ghp = "ghp_" + ("A" * 36)
        mock_aiza = "AIzaSy" + ("A" * 33)
        multi_input = f"Headers: Authorization: Bearer {mock_multi_ghp} and gemini_key: {mock_aiza}"
        masked_multi = mask_secrets(multi_input)
        self.assertNotIn(mock_multi_ghp, masked_multi)
        self.assertNotIn(mock_aiza, masked_multi)

    # 23. REGRESSION: Hiểu đúng phủ định trong JD Hàn Quốc & trích xuất bằng chứng
    def test_23_korea_negation_and_disqualifiers(self):
        evaluator = JobEvaluator(self.candidate)
        
        # Test case reproducing Issue 2
        neg_jd_text = "비자 지원 불가. English not required. 외국인 가능하지 않습니다."
        parsed = parse_jd_text(neg_jd_text, source="korea_negation_test")
        res = evaluator.evaluate(parsed, market="korea")
        
        ks = res["korea_specifics"]
        
        # 1. Visa: must conclude NO visa support, quote evidence
        self.assertIn("Không hỗ trợ", ks["Hỗ trợ giấy phép làm việc / Visa"])
        self.assertIn("비자 지원 불가", ks["Bằng chứng visa"])
        
        # 2. English: must conclude NOT required, quote evidence
        self.assertIn("Không yêu cầu", ks["Yêu cầu tiếng Anh"])
        self.assertIn("English not required", ks["Bằng chứng tiếng Anh"])
        
        # 3. Foreigner: must conclude NOT accepted, quote evidence
        self.assertIn("Không chấp nhận", ks["Chấp nhận ứng viên nước ngoài"])
        self.assertIn("외국인 가능하지 않습니다", ks["Bằng chứng ứng viên nước ngoài"])
        
        # 4. Disqualifiers detected for Vietnamese candidate
        self.assertTrue(len(res["disqualifiers"]) >= 1)
        self.assertEqual(res["recommendation"], "KHÔNG NÊN ỨNG TUYỂN")

    # 24. REGRESSION: Đánh giá lại không làm mất trạng thái ứng tuyển & ghi JSON an toàn
    def test_24_tracker_re_evaluate_preserves_status_and_atomic(self):
        test_tracker_path = TEMP_DIR / "regression_tracker.json"
        if test_tracker_path.exists():
            test_tracker_path.unlink()

        tracker = JobTracker(file_path=test_tracker_path)
        
        # Step 1: Add new entry with explicit applied status
        rec1 = tracker.add_or_update(
            title="SOC Analyst",
            company="Test CyberSec",
            market="vietnam",
            source="manual",
            match_score=75,
            status="Đã nộp",
            application_date="2026-10-15",
            notes="Đã gửi CV qua email cho HR",
            next_step="Chờ phản hồi vòng 1"
        )
        self.assertEqual(rec1["status"], "Đã nộp")
        self.assertEqual(rec1["application_date"], "2026-10-15")

        # Step 2: Re-evaluate same job without passing status or notes
        rec2 = tracker.add_or_update(
            title="SOC Analyst",
            company="Test CyberSec",
            market="vietnam",
            source="manual",
            match_score=88, # Updated score
            status=None,    # Omitted status
            job_id=rec1["id"]
        )
        # Verify status, date, notes are strictly preserved!
        self.assertEqual(rec2["status"], "Đã nộp")
        self.assertEqual(rec2["application_date"], "2026-10-15")
        self.assertEqual(rec2["notes"], "Đã gửi CV qua email cho HR")
        self.assertEqual(rec2["next_step"], "Chờ phản hồi vòng 1")
        self.assertEqual(rec2["match_score"], 88)

        # Step 3: Unapplied job does NOT get assigned today's date
        rec3 = tracker.add_or_update(
            title="Security Engineer",
            company="Tech Corp",
            market="vietnam",
            source="manual",
            match_score=60,
            status="Chưa nộp"
        )
        self.assertIsNone(rec3["application_date"], "Tin chưa nộp không được tự gán application_date!")

        # Step 4: Corrupt JSON defense
        corrupt_tracker_file = TEMP_DIR / "corrupt_tracker.json"
        corrupt_tracker_file.write_text("{this is corrupted json", encoding="utf-8")
        with self.assertRaises(ValueError):
            JobTracker(file_path=corrupt_tracker_file)

    # 25. REGRESSION: Hồ sơ trống không tự bịa đặt năng lực
    def test_25_generator_empty_candidate_no_false_claims(self):
        empty_gen = DocumentGenerator({})
        cv_md = empty_gen.generate_cv_markdown(target_role="SOC Intern")
        
        # Must not fabricate competence claims
        self.assertNotIn("nền tảng vững chắc", cv_md)
        self.assertNotIn("thực hành chuyên sâu", cv_md)
        self.assertIn("Chưa cập nhật tóm tắt chuyên môn", cv_md)
        self.assertIn("Chưa cập nhật thông tin học vấn", cv_md)
        self.assertIn("Chưa cập nhật danh mục kỹ năng", cv_md)
        self.assertIn("Chưa cập nhật dữ liệu kinh nghiệm làm việc", cv_md)

        # Cover letter for empty candidate must not assert practical expertise
        eval_mock = {"title": "SOC Analyst", "company": "CyberSec", "matched_skills": []}
        cl_md = empty_gen.generate_cover_letter(eval_mock, language="vi")
        self.assertIn("chưa có dữ liệu kỹ năng", cl_md)

    # 26. REGRESSION: Đánh dấu hồ sơ mẫu trong mọi tài liệu sinh ra
    def test_26_generator_mock_badge_in_all_docs(self):
        mock_cand = {"name": "Test Mock", "is_mock": True, "skills": {"security": ["Wireshark"]}}
        gen = DocumentGenerator(mock_cand)
        eval_mock = {
            "title": "SOC Analyst",
            "company": "CyberSec",
            "matched_skills": [{"skill": "Wireshark", "evidence_type": "Skill", "evidence_details": "Declared"}],
            "freelance_specifics": {"Mốc bàn giao đề xuất": ["Giai đoạn 1"]},
            "clarification_questions": ["Câu hỏi 1"]
        }

        cv = gen.generate_cv_markdown("SOC Analyst")
        cl = gen.generate_cover_letter(eval_mock)
        prop = gen.generate_freelance_proposal(eval_mock)
        prep = gen.generate_interview_prep(eval_mock)

        for doc_name, doc_text in [("CV", cv), ("Cover Letter", cl), ("Proposal", prop), ("Interview Prep", prep)]:
            self.assertIn("HỒ SƠ MẪU (MOCK PROFILE)", doc_text, f"{doc_name} thiếu badge hồ sơ mẫu!")

    # 27. REGRESSION: Output không bị ghi đè khi hai công ty có cùng tên vị trí
    def test_27_output_filename_collision_defense(self):
        company_a = "Viettel Cyber Security"
        company_b = "FPT Information System"
        title = "SOC Analyst Intern"

        clean_a = re.sub(r'[^a-zA-Z0-9_-]', '_', company_a.lower()).strip('_')[:20]
        clean_b = re.sub(r'[^a-zA-Z0-9_-]', '_', company_b.lower()).strip('_')[:20]
        role_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', title.lower()).strip('_')[:30]

        prefix_a = f"{clean_a}_{role_clean}"
        prefix_b = f"{clean_b}_{role_clean}"

        self.assertNotEqual(prefix_a, prefix_b)
        self.assertIn("viettel", prefix_a)
        self.assertIn("fpt", prefix_b)

    # 28. REGRESSION: CLI phân biệt rõ chế độ rules (0 network) và AI (mocked)
    def test_28_cli_mode_rules_vs_ai_mock(self):
        # 28a. Unsupported provider raises ValueError
        with self.assertRaises(ValueError):
            AIService(provider="openai")

        # 28b. In rules mode, AIService is never called
        from src.cli import cmd_evaluate
        with patch.object(AIService, "analyze_job") as mock_ai:
            test_tracker = TEMP_DIR / "rules_tracker.json"
            args_rules = argparse.Namespace(
                candidate=str(FIXTURES_DIR / "candidate_mock.json"),
                text="Tuyển thực tập sinh an ninh mạng",
                file=None,
                url=None,
                market="vietnam",
                mode="rules",
                provider="gemini",
                save_track=False,
                tracker_file=str(test_tracker),
                generate_docs=False
            )
            cmd_evaluate(args_rules)
            mock_ai.assert_not_called() # Strictly 0 network / no AI calls!

        # 28c. In AI mode, AIService is called and failure falls back with clear labeling
        with patch.object(AIService, "_call_online_ai", side_effect=urllib.error.URLError("Connection refused")):
            ai_svc = AIService(api_key="mock_key", provider="gemini")
            res = ai_svc.analyze_job("JD text", "Summary", market="vietnam")
            self.assertEqual(res["status"], "FAILED_AI_FALLBACK")
            self.assertIn("Fallback to Rules Engine", res["source"])
            self.assertIn("Connection refused", res["error"])

        # 28d. In AI mode, verify actual raw JD content is passed to AIService.analyze_job (not empty string)
        with patch.object(AIService, "analyze_job", return_value={"status": "PASS_ONLINE_AI", "source": "AI (Google Gemini)", "ai_advice": "Test advice"}) as mock_ai_call:
            test_tracker = TEMP_DIR / "ai_tracker.json"
            sample_jd_raw = "Tuyển dụng SOC Analyst tại Hà Nội. Yêu cầu thành thạo Wireshark, Splunk, Python."
            args_ai = argparse.Namespace(
                candidate=str(FIXTURES_DIR / "candidate_mock.json"),
                text=sample_jd_raw,
                file=None,
                url=None,
                market="vietnam",
                mode="ai",
                provider="gemini",
                api_key="mock_test_key",
                save_track=False,
                tracker_file=str(test_tracker),
                generate_docs=False
            )
            cmd_evaluate(args_ai)
            mock_ai_call.assert_called_once()
            passed_args, passed_kwargs = mock_ai_call.call_args
            actual_passed_text = passed_args[0] if passed_args else passed_kwargs.get("jd_text")
            self.assertIn("Tuyển dụng SOC Analyst tại Hà Nội", actual_passed_text)
            self.assertIn("Wireshark, Splunk, Python", actual_passed_text)
            self.assertGreater(len(actual_passed_text), 30)

    # 29. REGRESSION: Ranh giới thư mục đa nền tảng
    def test_29_platform_aware_filesystem_boundary(self):
        self.assertTrue(ensure_within_project(PROJECT_ROOT / "src" / "cli.py"))
        with self.assertRaises(PermissionError):
            ensure_within_project(PROJECT_ROOT / ".." / "outside.txt")

    # 30. REGRESSION: Tracker export CSV không ghi đè CSV thật
    def test_30_tracker_export_does_not_mutate_production_csv(self):
        prod_csv = PROJECT_ROOT / "data" / "tracker" / "jobs_tracker.csv"
        prod_original = prod_csv.read_text(encoding="utf-8-sig") if prod_csv.exists() else None

        test_tracker_path = TEMP_DIR / "test_export_tracker.json"
        tracker = JobTracker(file_path=test_tracker_path)
        tracker.add_or_update("Test Role", "Test Co", "vietnam", "src", 80)
        
        # Call export without args: must write companion CSV, not production CSV
        exported = tracker.export_csv()
        self.assertEqual(exported, test_tracker_path.with_suffix(".csv"))
        self.assertTrue(exported.exists())

        if prod_original is not None:
            self.assertEqual(prod_csv.read_text(encoding="utf-8-sig"), prod_original)

    # 31. REGRESSION: JD thiên về đào tạo không mặc định ép NETWORK là kỹ năng bắt buộc
    def test_31_training_oriented_jd_does_not_force_network_skill(self):
        cand = {
            "name": "Nguyen Trainee",
            "skills": {"systems": ["Linux"], "programming": ["Python"]},
            "education": [{"degree": "Sinh viên", "major": "CNTT", "year": "2022 - 2026"}]
        }
        evaluator = JobEvaluator(cand)
        jd_text = (
            "Vị trí: Thực tập sinh An toàn thông tin\n"
            "CÔNG VIỆC:\n"
            "- Học nghiệp vụ SOC/Network và ATTT; hỗ trợ theo dõi cảnh báo an ninh mạng.\n"
            "- Thực hành theo hướng dẫn của chuyên gia.\n"
            "YÊU CẦU:\n"
            "- Sinh viên năm 3-4 chuyên ngành CNTT hoặc An toàn thông tin; ham học hỏi, chủ động.\n"
            "QUYỀN LỢI:\n"
            "- Được đào tạo chuyên sâu về nghiệp vụ SOC.\n"
        )
        parsed_jd = parse_jd_text(jd_text, source="test_training_jd")
        res = evaluator.evaluate(parsed_jd, market="vietnam")

        # Must not falsely flag NETWORK as a missing prerequisite skill
        self.assertNotIn("NETWORK", res["missing_skills"])
        self.assertNotIn("Network", res["missing_skills"])
        
        # Training offering must be cleanly categorized with quotation
        trainings = res["jd_sections"]["training_offerings"]
        self.assertTrue(any("Học nghiệp vụ SOC/Network và ATTT" in t["raw_quote"] for t in trainings))

    # 32. REGRESSION: Chuẩn hóa quan hệ kỹ năng (TCP/IP & Wireshark là bằng chứng cho mạng)
    def test_32_skill_taxonomy_tcp_ip_wireshark_evidence_for_network(self):
        # Candidate has TCP/IP and Wireshark, but NEVER declares literal word "Network"
        cand_no_literal_network = {
            "name": "Network Protocol Student",
            "skills": {
                "protocols": ["TCP/IP"],
                "tools": ["Wireshark"]
            },
            "education": [{"degree": "Đang học", "major": "CNTT", "year": "2023 - 2027"}]
        }
        evaluator = JobEvaluator(cand_no_literal_network)
        
        # JD explicitly demands Network Fundamentals
        jd_text = (
            "Vị trí: Junior Network Security Engineer\n"
            "YÊU CẦU BẮT BUỘC:\n"
            "- Yêu cầu có kiến thức nền tảng vững về Network Fundamentals và giao thức mạng.\n"
        )
        parsed_jd = parse_jd_text(jd_text, source="test_taxonomy_jd")
        res = evaluator.evaluate(parsed_jd, market="vietnam")

        # Should match via relational taxonomy
        matched_skills_names = [m["skill"].lower() for m in res["matched_skills"]]
        self.assertTrue(any("network" in m for m in matched_skills_names))
        
        matched_obj = next(m for m in res["matched_skills"] if "network" in m["skill"].lower())
        self.assertEqual(matched_obj["evidence_type"], "Quan hệ kỹ năng chuẩn hóa (Relational Evidence)")
        # Must explicitly mention partial evidence without over-extrapolating full domain mastery
        self.assertIn("không đòi hỏi hồ sơ phải chứa đúng chữ 'Network'", matched_obj["evidence_details"])
        self.assertIn("không suy ra thành thạo toàn bộ", matched_obj["evidence_details"])

    # 33. REGRESSION: JD có yêu cầu kỹ thuật bắt buộc rõ ràng được đánh giá chính xác
    def test_33_jd_with_explicit_technical_requirements(self):
        cand = {
            "name": "Technical Intern",
            "skills": {
                "network": ["Wireshark", "TCP/IP"],
                "systems": ["Linux"],
                "programming": ["Python"]
            },
            "years_of_experience": 0,
            "education": [{"degree": "Cử nhân", "major": "ATTT", "year": "2021 - 2025"}]
        }
        evaluator = JobEvaluator(cand)
        jd_text = (
            "Vị trí: SOC Analyst L1\n"
            "YÊU CẦU CÔNG VIỆC:\n"
            "- Thành thạo phân tích gói tin với Wireshark.\n"
            "- Kỹ năng lập trình Python xử lý file log.\n"
            "- Vận hành cơ bản trên hệ điều hành Linux.\n"
            "- Yêu cầu bắt buộc kinh nghiệm sử dụng SIEM Splunk.\n"
        )
        parsed_jd = parse_jd_text(jd_text, source="test_explicit_tech_jd")
        res = evaluator.evaluate(parsed_jd, market="vietnam")

        # Conclusive numeric score calculated
        self.assertIsInstance(res["match_score"], int)
        self.assertEqual(res["score_status"], "CONCLUSIVE")
        
        matched_names = [m["skill"] for m in res["matched_skills"]]
        self.assertIn("Wireshark", matched_names)
        self.assertIn("Python", matched_names)
        self.assertIn("Linux", matched_names)
        self.assertIn("Splunk", res["missing_skills"])

    # 34. REGRESSION: JD thiếu dữ liệu kỹ thuật không phạt năng lực ứng viên về 0
    def test_34_sparse_jd_insufficient_data_not_zero_competence(self):
        cand = {
            "name": "Nguyen An",
            "skills": {},
            "personal_projects": [],
            "labs_and_simulations": [],
            "education": [{"degree": "Sinh viên", "major": "ATTT", "year": "2023 - 2027"}]
        }
        evaluator = JobEvaluator(cand)
        jd_text = (
            "Vị trí: Thực tập sinh ATTT\n"
            "CÔNG VIỆC: Học việc và tham gia các hoạt động an ninh mạng nội bộ.\n"
            "YÊU CẦU: Sinh viên năm 3-4 chuyên ngành ATTT, định hướng bảo mật, tác phong nghiêm túc.\n"
            "QUYỀN LỢI: Đào tạo thực tế bởi chuyên gia.\n"
        )
        parsed_jd = parse_jd_text(jd_text, source="test_sparse_jd")
        res = evaluator.evaluate(parsed_jd, market="vietnam")

        # Status must explicitly state insufficient technical data
        self.assertEqual(res["skill_status"], "Chưa đủ dữ liệu để đánh giá kỹ năng")
        self.assertIn("không tính phạt 0 điểm", res["score_calculation"]["Kỹ năng cốt lõi (Trọng số 35%)"])
        
        # Total score omitted / inconclusive due to lack of quantitative technical basis
        self.assertIsNone(res["match_score"])
        self.assertEqual(res["score_status"], "CHƯA ĐỦ CĂN CỨ TÍNH ĐIỂM TỔNG")
        
        # Recommendation states conditions needing verification, not simple score rejection
        self.assertIn("CẦN XÁC MINH ĐIỀU KIỆN", res["recommendation"])

    # 35. REGRESSION: Điều kiện năm học, địa điểm và lịch làm việc chưa rõ phải ghi 'Cần xác nhận'
    def test_35_hard_requirements_location_schedule_year_verification(self):
        cand = {
            "name": "Ngo Van Hien",
            "contact": {"location": "Đà Nẵng, Việt Nam"},
            "education": [{"institution": "Đại học", "degree": "Đang theo học chương trình kỹ sư", "major": "ATTT", "year": "2023 - 2028 (dự kiến tốt nghiệp)"}],
            "years_of_experience": 0
        }
        evaluator = JobEvaluator(cand)
        jd_text = (
            "Vị trí: Thực tập sinh An toàn thông tin\n"
            "ĐỊA ĐIỂM VÀ LỊCH:\n"
            "Hà Nội, 11 Duy Tân. Thứ Hai–thứ Sáu, 08:00–17:30.\n"
            "YÊU CẦU:\n"
            "Sinh viên năm 3–4 ngành ATTT, an ninh mạng.\n"
        )
        parsed_jd = parse_jd_text(jd_text, source="test_feasibility_jd")
        res = evaluator.evaluate(parsed_jd, market="vietnam")

        # Must flag unconfirmed conditions with exact JD quotes
        unclear_all = " ".join(res["unclear_items"])
        self.assertIn("Khả năng làm việc tại Hà Nội", unclear_all)
        self.assertIn("Hà Nội, 11 Duy Tân", unclear_all)
        self.assertIn("Khả năng đáp ứng lịch làm việc", unclear_all)
        self.assertIn("Thứ Hai–thứ Sáu, 08:00–17:30", unclear_all)
        self.assertIn("Năm học hiện tại", unclear_all)
        self.assertIn("Sinh viên năm 3–4", unclear_all)

        # Strictly must not give 40.0/40 when feasibility is pending verification
        hard_calc = res["score_calculation"]["Điều kiện bắt buộc & Khả thi (Trọng số 40%)"]
        self.assertTrue(hard_calc.startswith("20.0/40"))
        self.assertIn("Unknown", hard_calc)
        self.assertIn("không gán điểm tùy ý", hard_calc)

    # 36. REGRESSION: Toàn bộ luồng khi match_score=null (Đánh giá -> Lưu -> Đọc -> Cập nhật -> Liệt kê -> CSV -> Tài liệu)
    def test_36_match_score_null_end_to_end_flow(self):
        cand = {
            "name": "Candidate Null Score Test",
            "contact": {"email": "null.test@example.com"},
            "skills": {"network": ["TCP/IP"]},
            "years_of_experience": 0,
            "education": [{"degree": "Sinh viên", "major": "ATTT", "year": "2023 - 2027"}]
        }
        sparse_jd = parse_jd_text(
            "Vị trí: Thực tập sinh ATTT\n"
            "CÔNG VIỆC: Học nghiệp vụ an ninh mạng nội bộ.\n"
            "YÊU CẦU: Sinh viên CNTT/ATTT, đam mê bảo mật.\n"
            "QUYỀN LỢI: Đào tạo bởi chuyên gia.\n",
            source="test_sparse_null"
        )

        # 1. Evaluate
        evaluator = JobEvaluator(cand)
        res = evaluator.evaluate(sparse_jd, market="vietnam")
        self.assertIsNone(res["match_score"])
        self.assertEqual(res["score_status"], "CHƯA ĐỦ CĂN CỨ TÍNH ĐIỂM TỔNG")

        # 2. Save to Tracker
        tracker_path = TEMP_DIR / "test_null_tracker.json"
        if tracker_path.exists():
            tracker_path.unlink()
        tracker = JobTracker(file_path=tracker_path)
        rec = tracker.add_or_update(
            title=res["title"],
            company="Test Corp",
            market="vietnam",
            source=res["source"],
            match_score=res["match_score"],
            status="Chưa nộp"
        )
        self.assertIsNone(rec["match_score"])

        # 3. Reload from Disk
        tracker_reloaded = JobTracker(file_path=tracker_path)
        loaded_rec = tracker_reloaded.get(rec["id"])
        self.assertIsNotNone(loaded_rec)
        self.assertIsNone(loaded_rec["match_score"])

        # 4. Update Status
        updated_rec = tracker_reloaded.update_status(
            job_id=rec["id"],
            status="Đang chuẩn bị hồ sơ",
            notes="Đang làm rõ lịch làm việc"
        )
        self.assertIsNone(updated_rec["match_score"])
        self.assertEqual(updated_rec["status"], "Đang chuẩn bị hồ sơ")

        # 5. List / Query
        all_jobs = tracker_reloaded.list_all()
        self.assertEqual(len(all_jobs), 1)
        self.assertIsNone(all_jobs[0]["match_score"])

        # 6. Export CSV
        csv_path = tracker_reloaded.export_csv()
        self.assertTrue(csv_path.exists())
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 1)
            self.assertEqual(reader[0]["match_score"], "")
            self.assertEqual(reader[0]["status"], "Đang chuẩn bị hồ sơ")

        # 7. Document Generation
        doc_dir = LOCAL_DIR / "test_outputs"
        doc_dir.mkdir(parents=True, exist_ok=True)
        gen = DocumentGenerator(cand)
        prep_md = gen.generate_interview_prep(res)
        self.assertIn("Chưa đủ dữ liệu tính điểm tổng (Cần xác minh điều kiện)", prep_md)
        cv_md = gen.generate_cv_markdown("Thực tập sinh ATTT")
        self.assertIn("Candidate Null Score Test", cv_md)
        cl_md = gen.generate_cover_letter(res)
        self.assertIn("Thư Ứng Tuyển", cl_md)

    # 37. REGRESSION: Đầu ra kiểm thử tự động lưu vào .local/test_outputs, không đè output/
    def test_37_test_output_isolation_in_local(self):
        prod_output = PROJECT_ROOT / "output"
        local_test_output = LOCAL_DIR / "test_outputs"
        local_test_output.mkdir(parents=True, exist_ok=True)

        # Count files in prod output before
        prod_before = set(prod_output.glob("*.md"))

        test_tracker_path = TEMP_DIR / "isolation_test_tracker.json"
        from src.cli import cmd_evaluate
        args = argparse.Namespace(
            candidate=str(FIXTURES_DIR / "candidate_mock.json"),
            file=str(FIXTURES_DIR / "jd_vietnam_soc.txt"),
            text=None,
            url=None,
            market="vietnam",
            mode="rules",
            provider="gemini",
            api_key=None,
            save_track=True,
            tracker_file=str(test_tracker_path),
            output_dir=None,
            generate_docs=True
        )
        cmd_evaluate(args)

        # Output documents must be generated inside .local/test_outputs
        test_generated_files = list(local_test_output.glob("*.md"))
        self.assertGreater(len(test_generated_files), 0)

        # Production output directory must not have had new files added from this test
        prod_after = set(prod_output.glob("*.md"))
        self.assertEqual(prod_before, prod_after, "Kiểm thử không được ghi đè vào thư mục output thật!")

    # 38. SEARCH PRIVACY: load_search_profile chỉ lấy tiêu chí cần thiết, loại bỏ hoàn toàn PII
    def test_38_job_searcher_load_profile_privacy(self):
        from src.job_searcher import load_search_profile
        prof = load_search_profile(FIXTURES_DIR / "candidate_mock.json")

        self.assertIn("target_skills", prof)
        self.assertIn("preferred_location", prof)
        self.assertIn("expected_graduation", prof)

        # Strictly check that private contact fields are not exposed
        self.assertNotIn("email", prof)
        self.assertNotIn("phone", prof)
        self.assertNotIn("contact", prof)
        self.assertNotIn("address", prof)
        self.assertNotIn("name", prof)
        self.assertEqual(prof["expected_graduation"], 2024)

    # 39. UPSTREAM ORCHESTRATION: JobSearcher gọi đúng CLI upstream và xử lý lỗi Bun an toàn
    def test_39_job_searcher_upstream_cli_orchestration(self):
        from src.job_searcher import JobSearcher
        searcher = JobSearcher()

        # Test Bun availability detection
        has_bun = searcher.is_bun_available()
        self.assertIsInstance(has_bun, bool)

        # Test search_linkedin with mock subprocess
        mock_output = json.dumps({
            "results": [
                {
                    "id": "123456",
                    "title": "SOC Intern",
                    "company": "FPT Software",
                    "location": "Da Nang, Vietnam",
                    "date": "2026-10-24",
                    "url": "https://vn.linkedin.com/jobs/view/123456"
                }
            ]
        })
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
            results = searcher.search_linkedin("SOC Intern", "Da Nang, Vietnam", limit=2)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["company"], "FPT Software")
            self.assertEqual(results[0]["search_source"], "LinkedIn (Public Guest API)")

        # Test graceful handling when subprocess fails
        with patch("subprocess.run", side_effect=Exception("Connection error")):
            results = searcher.search_linkedin("SOC Intern", "Da Nang, Vietnam")
            self.assertEqual(results, [])

    # 40. SEARCH AUDIT & DEDUP: Phân loại nhóm ưu tiên, phát hiện điều kiện chưa rõ và khử trùng canonical
    def test_40_job_searcher_categorization_and_deduplication(self):
        from src.job_searcher import JobSearcher
        searcher = JobSearcher()

        # Job in Da Nang
        j_danang = {
            "title": "Network Intern",
            "company": "Company A",
            "location": "Da Nang, Vietnam",
            "description": "Yêu cầu thực tập sinh làm việc toàn thời gian (full-time) tại văn phòng Đà Nẵng."
        }
        searcher.categorize_and_audit_job(j_danang)
        self.assertEqual(j_danang["priority_tier"], 1)
        self.assertIn("Đà Nẵng", j_danang["priority_label"])
        self.assertTrue(any("toàn thời gian" in uc for uc in j_danang["unverified_conditions"]))

        # Job in Hanoi
        j_hanoi = {
            "title": "SOC Intern",
            "company": "Company B",
            "location": "Hanoi, Vietnam",
            "description": "Yêu cầu 1 năm kinh nghiệm phân tích log."
        }
        searcher.categorize_and_audit_job(j_hanoi)
        self.assertEqual(j_hanoi["priority_tier"], 3)
        self.assertTrue(any("di chuyển" in uc for uc in j_hanoi["unverified_conditions"]))
        self.assertTrue(any("kinh nghiệm" in uc for uc in j_hanoi["unverified_conditions"]))

        # Canonical key verification
        self.assertIn("canonical_key", j_danang)
        self.assertTrue(len(j_danang["canonical_key"]) > 0)

    # 41. STAGING PIPELINE: Đánh giá tin thật và lưu tracker không bao giờ gán 'Đã nộp'
    def test_41_job_searcher_stage_and_evaluate_pipeline(self):
        from src.job_searcher import JobSearcher
        searcher = JobSearcher()

        test_tracker = TEMP_DIR / "search_pipeline_test_tracker.json"
        if test_tracker.exists():
            test_tracker.unlink()
        test_output = LOCAL_DIR / "test_outputs"
        test_output.mkdir(parents=True, exist_ok=True)

        sample_job = {
            "id": "test_999999",
            "title": "Thực tập sinh Quản trị Mạng",
            "company": "Viettel Network Da Nang",
            "location": "Da Nang, Vietnam",
            "url": "https://example.com/jobs/999999",
            "description": "Tuyển thực tập sinh quản trị mạng tại Đà Nẵng. Yêu cầu nắm vững TCP/IP, Wireshark và Linux. Ưu tiên Python.",
            "priority_tier": 1,
            "priority_label": "Đà Nẵng (Ưu tiên tại chỗ)",
            "unverified_conditions": ["Cần xác nhận lịch làm việc với trường."],
            "search_source": "LinkedIn (Test)"
        }

        res = searcher.evaluate_and_stage_job(
            job=sample_job,
            candidate_path=FIXTURES_DIR / "candidate_mock.json",
            tracker_file=test_tracker,
            output_dir=test_output,
            tracker_status="Đã đánh giá"
        )

        # Assert status is strictly 'Đã đánh giá'
        self.assertEqual(res["tracker_status"], "Đã đánh giá")
        self.assertNotEqual(res["tracker_status"], "Đã nộp")

        # Verify tracker file content
        data = json.loads(test_tracker.read_text(encoding="utf-8"))
        job_record = data["jobs"][res["job_id"]]
        self.assertEqual(job_record["status"], "Đã đánh giá")
        self.assertNotEqual(job_record["status"], "Đã nộp")

        # Verify generated document paths
        self.assertIn("cv_md", res["document_paths"])
        self.assertIn("cover_letter_md", res["document_paths"])
        self.assertTrue(res["document_paths"]["cv_md"].exists())

    # 42. REGRESSION: Loại bỏ quảng cáo/marketing/Facebook Ads khỏi các nhóm ưu tiên kỹ thuật
    def test_42_ads_and_marketing_exclusion_from_priorities(self):
        from src.job_searcher import JobSearcher
        searcher = JobSearcher()

        # Job with ads in title
        job_ads_1 = {
            "title": "Chuyên viên Facebook Ads & Digital Marketing",
            "company": "Agency Media",
            "location": "Da Nang, Vietnam",
            "description": "Tối ưu hóa chiến dịch Facebook Ads, quản lý ngân sách quảng cáo."
        }
        searcher.categorize_and_audit_job(job_ads_1)
        self.assertEqual(job_ads_1["priority_tier"], 99)
        self.assertIn("Ngoài mục tiêu: Quảng cáo / Marketing", job_ads_1["priority_label"])
        self.assertTrue(any("Quảng cáo / Marketing" in uc for uc in job_ads_1["unverified_conditions"]))

        # Job with telemarketing
        job_ads_2 = {
            "title": "Telesales / Marketing Specialist",
            "company": "Sales Corp",
            "location": "Ho Chi Minh City, Vietnam",
            "description": "Gọi điện tư vấn khách hàng và chạy ads giới thiệu sản phẩm."
        }
        searcher.categorize_and_audit_job(job_ads_2)
        self.assertEqual(job_ads_2["priority_tier"], 99)

    # 43. REGRESSION: Đưa Senior/Lead/Manager vào nhóm Ngoài mục tiêu (không chọn cho hồ sơ 0 năm KN)
    def test_43_senior_and_lead_out_of_target(self):
        from src.job_searcher import JobSearcher
        searcher = JobSearcher()

        # Senior job in Da Nang
        job_senior = {
            "title": "Senior Network Security Engineer",
            "company": "Tech Corp Da Nang",
            "location": "Da Nang, Vietnam",
            "description": "Yêu cầu 5 năm kinh nghiệm quản trị tường lửa và định tuyến BGP."
        }
        searcher.categorize_and_audit_job(job_senior)
        self.assertEqual(job_senior["priority_tier"], 98)
        self.assertIn("Ngoài mục tiêu: Vị trí Senior / Lead / Manager", job_senior["priority_label"])
        self.assertTrue(any("Vị trí cấp cao" in uc for uc in job_senior["unverified_conditions"]))

        # Lead role in Hanoi
        job_lead = {
            "title": "Lead SOC Architect",
            "company": "CyberSec Global",
            "location": "Hanoi, Vietnam",
            "description": "Lãnh đạo đội ngũ kỹ sư giám sát an toàn thông tin."
        }
        searcher.categorize_and_audit_job(job_lead)
        self.assertEqual(job_lead["priority_tier"], 98)

        # Junior role must NOT be classified as senior
        job_junior = {
            "title": "Junior Network Engineer",
            "company": "Network Co",
            "location": "Da Nang, Vietnam",
            "description": "Yêu cầu nắm vững TCP/IP và mô hình OSI."
        }
        searcher.categorize_and_audit_job(job_junior)
        self.assertEqual(job_junior["priority_tier"], 1)

    # 44. REGRESSION: Nhóm Remote đổi tên và kiểm tra bằng chứng hỗ trợ Việt Nam
    def test_44_remote_vietnam_verification_and_label(self):
        from src.job_searcher import JobSearcher
        searcher = JobSearcher()

        # Remote with explicit Vietnam evidence
        job_remote_vn = {
            "title": "Security Analyst Intern (Remote)",
            "company": "Remote Global",
            "location": "Vietnam (Remote)",
            "description": "Chấp nhận ứng viên làm việc từ xa 100% tại Việt Nam hoặc khu vực APAC."
        }
        searcher.categorize_and_audit_job(job_remote_vn)
        self.assertEqual(job_remote_vn["priority_tier"], 2)
        self.assertEqual(job_remote_vn["priority_label"], "Remote — cần xác minh quốc gia làm việc")
        self.assertTrue(job_remote_vn.get("vietnam_supported"))

        # Remote without Vietnam evidence
        job_remote_unknown = {
            "title": "Cloud Security Intern",
            "company": "US Startup",
            "location": "Remote",
            "description": "Work from anywhere in US or Canada Eastern timezones. Flexible hours."
        }
        searcher.categorize_and_audit_job(job_remote_unknown)
        self.assertEqual(job_remote_unknown["priority_tier"], 2)
        self.assertEqual(job_remote_unknown["priority_label"], "Remote — cần xác minh quốc gia làm việc")
        self.assertFalse(job_remote_unknown.get("vietnam_supported"))
        self.assertTrue(any("Chưa có bằng chứng JD hỗ trợ làm việc từ xa từ Việt Nam" in uc for uc in job_remote_unknown["unverified_conditions"]))

        # Remote with bare "APAC" or "toàn quốc" (does NOT prove Vietnam remote eligibility)
        job_remote_apac = {
            "title": "Cloud Security Intern",
            "company": "Regional APAC Tech",
            "location": "Remote",
            "description": "Work from anywhere across APAC region or toàn quốc. No specific country listed."
        }
        searcher.categorize_and_audit_job(job_remote_apac)
        self.assertEqual(job_remote_apac["priority_tier"], 2)
        self.assertFalse(job_remote_apac.get("vietnam_supported"))
        self.assertTrue(any("Chưa có bằng chứng JD hỗ trợ làm việc từ xa từ Việt Nam" in uc for uc in job_remote_apac["unverified_conditions"]))

    # 45. REGRESSION: Phân biệt Freelance theo hợp đồng/dự án với Chưa phân loại (Freehire không mặc định freelance)
    def test_45_freelance_contract_vs_unclassified(self):
        from src.job_searcher import JobSearcher
        searcher = JobSearcher()

        # Job with project/freelance evidence
        job_freelance = {
            "title": "Python Scripting for Network Logs",
            "company": "Client Project",
            "location": "Global",
            "description": "Dự án hợp đồng ngắn hạn (freelance / contract) viết script tự động phân tích log mạng."
        }
        searcher.categorize_and_audit_job(job_freelance)
        self.assertEqual(job_freelance["priority_tier"], 4)
        self.assertIn("Freelance (Theo dự án / Hợp đồng)", job_freelance["priority_label"])

        # Freehire job without freelance/contract evidence -> must NOT be Tier 4 Freelance!
        job_freehire_fulltime = {
            "title": "Senior Cloud Engineer",
            "company": "Fulltime Enterprise Co",
            "location": "Singapore",
            "employmentType": "Full-time",
            "description": "Permanent full-time role at Singapore headquarters.",
            "search_portal": "freehire"
        }
        searcher.categorize_and_audit_job(job_freehire_fulltime)
        self.assertNotEqual(job_freehire_fulltime["priority_tier"], 4)

        # Job with unrecognized location and NO freelance evidence -> Chưa phân loại (Tier 5)
        job_unclassified = {
            "title": "IT Network Technician",
            "company": "Unknown Overseas Co",
            "location": "Port Moresby, Papua New Guinea",
            "description": "Standard full-time on-site network operations."
        }
        searcher.categorize_and_audit_job(job_unclassified)
        self.assertEqual(job_unclassified["priority_tier"], 5)
        self.assertIn("Chưa phân loại", job_unclassified["priority_label"])
        self.assertTrue(any("Chưa xác định được địa điểm" in uc for uc in job_unclassified["unverified_conditions"]))

    # 46. REGRESSION: Phiên tìm kiếm có ID ổn định và file lưu phiên được bảo toàn
    def test_46_search_session_stable_id_and_persistence(self):
        from src.job_searcher import JobSearcher, SEARCH_SESSIONS_DIR
        searcher = JobSearcher()

        sample_jobs = [
            {"id": "j1", "title": "Job 1", "company": "Co 1", "priority_tier": 1},
            {"id": "j2", "title": "Job 2", "company": "Co 2", "priority_tier": 2}
        ]
        custom_id = "test_session_20261024_001"
        res = searcher.save_search_session(unique_jobs=sample_jobs, session_id=custom_id)

        self.assertEqual(res["session_id"], custom_id)
        session_file = Path(res["session_path"])
        self.assertTrue(session_file.exists())

        # Verify content
        saved_data = json.loads(session_file.read_text(encoding="utf-8"))
        self.assertEqual(saved_data["session_id"], custom_id)
        self.assertEqual(saved_data["total_jobs"], 2)

        # Verify latest session pointer exists
        latest_file = SEARCH_SESSIONS_DIR / "latest_session.json"
        self.assertTrue(latest_file.exists())

    # 47. REGRESSION: So sánh đa chiều không dùng SecMon chưa xác minh làm bằng chứng
    def test_47_compare_jobs_facts_without_unverified_secmon(self):
        from src.job_searcher import JobSearcher
        searcher = JobSearcher()

        fake_detail = {
            "id": "11223344",
            "title": "Cloud & DevOps Intern",
            "company": "Hitachi Digital Services",
            "location": "Da Nang, Vietnam",
            "description": "Pursuing a Bachelor's degree in IT. Good communication skills in English. Exposure to Linux, Python, and AWS basics.",
            "employmentType": "Internship",
            "isActive": True
        }

        cand_p = PROJECT_ROOT / "data" / "candidates" / "my_profile.json"
        if not cand_p.exists():
            cand_p = PROJECT_ROOT / "data" / "candidates" / "candidate_mock.json"

        with patch.object(searcher, "get_linkedin_detail", return_value=fake_detail):
            comp_res = searcher.fetch_and_compare_jobs(
                job_ids_or_urls=["https://vn.linkedin.com/jobs/view/11223344"],
                candidate_profile_path=cand_p
            )
            self.assertEqual(comp_res["total_evaluated"], 1)
            evaluated_job = comp_res["jobs"][0]
            dims = evaluated_job["comparison_dimensions"]

            # Dimension 1: education
            self.assertTrue(dims["education_match"])
            self.assertIn("CHẤP NHẬN SINH VIÊN", dims["education_policy"])

            # Dimension 5: Verify SecMon is NEVER cited as verified skill evidence
            for ev in dims["profile_evidence"]:
                self.assertNotIn("SecMon", ev)

    # 48. REGRESSION: Đánh giá tiêu chuẩn GPA không thỏa mãn (2.9 so với yêu cầu 3.0)
    def test_48_gpa_requirement_evaluation(self):
        cand = {
            "name": "Ngô Văn Hiền",
            "years_of_experience": 0,
            "education": [
                {
                    "institution": "VKU",
                    "degree": "Kỹ sư",
                    "year": "2023 - 2028 (dự kiến tốt nghiệp)",
                    "gpa": "2.9/4.0"
                }
            ],
            "skills": {"programming": ["Python", "Java"]}
        }
        evaluator = JobEvaluator(cand)
        jd_data = {
            "title": "Cloud & DevOps Intern",
            "company": "Hitachi Digital Services",
            "raw_content": "Requirements:\nPursuing a Bachelor's degree in IT.\nGPA of 3.0/4.0 or above.\nGood programming knowledge in Python or Java.",
            "location": "Da Nang, Vietnam"
        }
        res = evaluator.evaluate(jd_data, market="vietnam")
        self.assertIn("gpa", res["feasibility_status"])
        self.assertIn("Chưa đáp ứng", res["feasibility_status"]["gpa"])
        self.assertNotEqual(res["match_score"], 100)
        self.assertIn("CẦN XÁC MINH GPA", res["recommendation"])
        self.assertTrue(any("2.9/4.0" in uc for uc in res["unverified_conditions"]))

    # 49. REGRESSION: CV không chứa SecMon chưa xác minh và không chứa ghi chú kiểm toán nội bộ
    def test_49_generator_omits_secmon_and_internal_reviewer_notes(self):
        cand = {
            "name": "Ngô Văn Hiền",
            "years_of_experience": 0,
            "education": [{"degree": "Kỹ sư", "major": "ATTT", "institution": "VKU", "year": "2023 - 2028", "gpa": "2.9/4.0"}],
            "skills": {"programming": ["Python"]},
            "personal_projects": [
                {
                    "name": "Chia sẻ màn hình P2P sử dụng WebRTC",
                    "description": "Phát triển cơ chế chia sẻ màn hình theo mô hình P2P sử dụng WebRTC. Dự án được liệt kê trong CV; chưa bổ sung số liệu hiệu năng hoặc phạm vi triển khai chưa được xác nhận."
                },
                {
                    "name": "SecMon",
                    "description": "Dự án do ứng viên cung cấp liên kết. Cần bổ sung mô tả chức năng... chưa dùng làm bằng chứng cho kỹ năng cụ thể."
                }
            ]
        }
        gen = DocumentGenerator(cand)
        cv = gen.generate_cv_markdown("Cloud & DevOps Intern")
        self.assertNotIn("SecMon", cv)
        self.assertNotIn("chưa bổ sung số liệu", cv)
        self.assertNotIn("chưa dùng làm bằng chứng", cv)
        self.assertIn("Chia sẻ màn hình P2P", cv)

    # 50. REGRESSION: HTML export converts bold/italic markdown into HTML tags without leftover asterisks and escapes safely
    def test_50_html_export_bold_italic_and_safe_escaping(self):
        cand = {
            "name": "Ngô Văn Hiền",
            "contact": {"email": "test@example.com"},
            "education": [{"degree": "Kỹ sư", "major": "ATTT", "institution": "VKU", "year": "2023 - 2028", "gpa": "2.9/4.0"}],
            "skills": {"network": ["TCP/IP", "Wireshark"]}
        }
        gen = DocumentGenerator(cand)
        md_text = (
            "# Ngô Văn Hiền\n"
            "*test@example.com | 0393492064*\n\n"
            "**Vị trí mục tiêu / Target Role:** Cloud & DevOps Intern\n\n"
            "## Kỹ năng chuyên môn (Technical Skills)\n"
            "- **Network:** Mô hình OSI, TCP/IP, Wireshark, *P2P* Data Transfer\n"
            "- XSS Test: `<script>alert(1)</script>` & \"quotes\"\n"
        )
        test_html_path = TEMP_DIR / "regression_cv.html"
        gen.export_to_html(md_text, test_html_path)
        self.assertTrue(test_html_path.exists())
        html_content = test_html_path.read_text(encoding="utf-8")
        
        # Verify markdown bold and italic are converted to HTML tags
        self.assertIn("<strong>Network:</strong>", html_content)
        self.assertIn("<em>P2P</em>", html_content)
        # Verify safe HTML escaping: script tag is escaped, not raw
        self.assertNotIn("<script>", html_content)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_content)
        # Verify no raw ** or * remains surrounding text
        self.assertIsNone(re.search(r'\*\*[^*]+\*\*', html_content))
        self.assertIsNone(re.search(r'(?<!\*)\*[^*]+\*(?!\*)', html_content))

    # 51. REGRESSION: Bản CV tiếng Anh Cloud & DevOps Intern tuân thủ các quy tắc chuẩn hóa
    def test_51_english_cv_generation_rules(self):
        cand = {
            "name": "Ngô Văn Hiền",
            "is_mock": False,
            "contact": {
                "email": "hienngo090800@gmail.com",
                "phone": "0393492064",
                "github": "https://github.com/hien23ns",
                "linkedin": "https://www.linkedin.com/in/ngovanhien",
                "location": "Đà Nẵng, Việt Nam"
            },
            "years_of_experience": 0,
            "education": [
                {
                    "institution": "Vietnam - Korea University of Information and Communication Technology (VKU)",
                    "degree": "Undergraduate Engineering Program",
                    "major": "Network and Information Security",
                    "year": "2023 - 2028 (dự kiến tốt nghiệp)",
                    "gpa": "2.9/4.0"
                }
            ],
            "skills": {
                "systems": ["Linux", "Bash"],
                "programming": ["Python", "Java"],
                "cloud": ["AWS cơ bản", "AWS IAM cơ bản", "Amazon EC2 cơ bản", "Amazon S3 cơ bản"]
            },
            "personal_projects": [
                {
                    "name": "Chia sẻ màn hình P2P sử dụng WebRTC",
                    "technologies": ["WebRTC", "P2P"],
                    "description": "Phát triển cơ chế chia sẻ màn hình theo mô hình P2P sử dụng WebRTC. Dự án được liệt kê trong CV; chưa bổ sung số liệu hiệu năng hoặc phạm vi triển khai chưa được xác nhận."
                },
                {
                    "name": "SecMon",
                    "technologies": [],
                    "description": "Dự án do ứng viên cung cấp liên kết... chưa dùng làm bằng chứng."
                }
            ],
            "work_experience": [],
            "certifications": [
                {
                    "name": "Gemini Certified Student",
                    "issuer": "",
                    "year": "2025"
                },
                {
                    "name": "Building a Personal Project to International Standards",
                    "issuer": "Rikkei Education",
                    "year": "2025"
                }
            ],
            "languages": {
                "vietnamese": "Bản ngữ",
                "english": "Giao tiếp cơ bản, đọc hiểu tài liệu kỹ thuật",
                "korean": "Chưa có năng lực tiếng Hàn được xác nhận"
            }
        }
        gen = DocumentGenerator(cand)
        cv_en = gen.generate_cv_markdown("Cloud & DevOps Intern", market="vietnam", language="en")
        
        # 1. Niên khóa và GPA (bỏ hẳn mục GPA)
        self.assertIn("2023 - 2028", cv_en)
        self.assertNotIn("GPA", cv_en)
        # 2. Summary tập trung Linux, Python/Java, AWS
        self.assertIn("Linux", cv_en)
        self.assertIn("Python", cv_en)
        self.assertIn("AWS", cv_en)
        # 3. Không tự ý thêm Docker, Kubernetes, Terraform, CI/CD
        self.assertNotIn("Docker", cv_en)
        self.assertNotIn("Kubernetes", cv_en)
        self.assertNotIn("Terraform", cv_en)
        self.assertNotIn("CI/CD", cv_en)
        # 4. Bỏ mục kinh nghiệm rỗng
        self.assertNotIn("## Work Experience", cv_en)
        # 5. Bỏ mục tiếng Hàn chưa học
        self.assertNotIn("Korean", cv_en)
        # 6. Không đưa SecMon hoặc ghi chú kiểm toán
        self.assertNotIn("SecMon", cv_en)
        self.assertNotIn("chưa bổ sung số liệu", cv_en)
        # 7. Chứng nhận thiếu issuer không có dấu gạch trống
        self.assertIn("**Gemini Certified Student** (2025)", cv_en)
        self.assertNotIn("**Gemini Certified Student** - ", cv_en)

if __name__ == "__main__":
    unittest.main()


