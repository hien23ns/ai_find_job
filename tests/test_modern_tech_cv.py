"""
Unit tests for Modern Tech CV Template and Generator.
Verifies layout requirements, factual integrity, security boundaries, and ATS companion.
"""

import json
from pathlib import Path
import re
import unittest

from src.modern_tech_cv import (
    generate_ats_html,
    generate_modern_tech_html,
    create_job_application_package,
    generate_job_cover_letter,
    is_project_verified,
    PROJECT_ROOT,
    OUTPUT_DIR,
    LOCAL_DIR
)
from src.avatar import get_avatar_base64


class TestModernTechCV(unittest.TestCase):
    def setUp(self):
        cand_path = PROJECT_ROOT / "data" / "candidates" / "my_profile.json"
        if not cand_path.exists():
            cand_path = PROJECT_ROOT / "tests" / "fixtures" / "candidate_mock_profile.json"
        self.candidate = json.loads(cand_path.read_text(encoding="utf-8"))

    def test_modern_tech_html_en_structure(self):
        html = generate_modern_tech_html(self.candidate, language="en", target_role="Cloud & DevOps Intern")
        
        # Name and Role
        self.assertIn("NGÔ VĂN HIỀN", html)
        self.assertIn("CLOUD &amp; DEVOPS INTERN", html.replace("&", "&amp;"))
        
        # Contact items
        self.assertIn("hienngo090800@gmail.com", html)
        self.assertIn("0393492064", html)
        self.assertIn("Da Nang, Vietnam", html)
        self.assertIn("github.com/hien23ns", html)
        self.assertIn("linkedin.com/in/ngovanhien", html)
        self.assertIn("ngovanhien.id.vn", html)
        
        # Education: GPA completely omitted
        html_text = re.sub(r'data:image/[^"]+', '', html)
        self.assertNotIn("GPA", html_text)
        self.assertNotIn("2.9/4.0", html_text)
        self.assertNotIn("2.9 / 4.0", html_text)
        self.assertIn("2023 – 2028", html)
        self.assertIn("VKU", html)
        
        # Factual integrity: NO fabricated buzzwords
        self.assertNotIn("Docker", html)
        self.assertNotIn("Kubernetes", html)
        self.assertNotIn("Terraform", html)
        self.assertNotIn("CI/CD", html)
        
        # No unverified projects / languages
        self.assertNotIn("SecMon", html)
        self.assertNotIn("seccmon", html)
        self.assertNotIn("Korean", html)
        self.assertNotIn("Tiếng Hàn", html)

    def test_modern_tech_html_vi_structure(self):
        html = generate_modern_tech_html(self.candidate, language="vi", target_role="Cloud & DevOps Intern")
        html_text = re.sub(r'data:image/[^"]+', '', html)
        
        self.assertIn("NGÔ VĂN HIỀN", html)
        self.assertIn("Tóm tắt Chuyên môn", html)
        self.assertIn("Dự án Kỹ thuật &amp; Đồ án", html)
        self.assertIn("Học vấn", html)
        self.assertIn("Chứng chỉ &amp; Bằng cấp", html)
        self.assertIn("Đà Nẵng, Việt Nam", html)
        self.assertNotIn("GPA", html_text)
        self.assertNotIn("2.9/4.0", html_text)
        self.assertNotIn("2.9 / 4.0", html_text)
        self.assertIn("Chia sẻ màn hình P2P sử dụng WebRTC", html)
        self.assertIn("Ứng dụng mạng xã hội Android", html)

    def test_no_unverified_claims(self):
        """
        Verify that unconfirmed details identified by user are completely absent:
        - JavaScript in WebRTC
        - Signaling, DataChannel, no relay, low latency
        - Login/registration, newsfeed, profile views, modular architecture
        - Relevant coursework / Systems Programming self-added
        """
        html_en = generate_modern_tech_html(self.candidate, language="en")
        html_vi = generate_modern_tech_html(self.candidate, language="vi")
        
        for html_doc in [html_en, html_vi]:
            # WebRTC unconfirmed claims
            self.assertNotIn("JavaScript", html_doc)
            self.assertNotIn("signaling", html_doc.lower())
            self.assertNotIn("datachannel", html_doc.lower())
            self.assertNotIn("relay", html_doc.lower())
            self.assertNotIn("low-latency", html_doc.lower())
            self.assertNotIn("độ trễ", html_doc.lower())
            
            # Android unconfirmed claims
            self.assertNotIn("authentication", html_doc.lower())
            self.assertNotIn("xác thực", html_doc.lower())
            self.assertNotIn("profile views", html_doc.lower())
            self.assertNotIn("bảng tin", html_doc.lower())
            self.assertNotIn("modular", html_doc.lower())
            self.assertNotIn("hướng đối tượng", html_doc.lower())
            self.assertNotIn("secure network", html_doc.lower())
            
            # Coursework
            self.assertNotIn("Systems Programming", html_doc)
            self.assertNotIn("Lập trình hệ thống", html_doc)
            self.assertNotIn("Relevant Coursework", html_doc)
            self.assertNotIn("Học phần trọng tâm", html_doc)

    def test_left_aligned_summary_and_no_gpa_in_summary(self):
        html_en = generate_modern_tech_html(self.candidate, language="en")
        html_vi = generate_modern_tech_html(self.candidate, language="vi")
        
        # Ensure left alignment, not justify
        self.assertIn("text-align: left;", html_en)
        self.assertNotIn("text-align: justify;", html_en)
        
        # Extract summary text from HTML and verify GPA is not inside summary
        summary_match_en = re.search(r'<p class="summary-p">(.*?)</p>', html_en, re.DOTALL)
        self.assertTrue(summary_match_en)
        self.assertNotIn("GPA", summary_match_en.group(1))
        self.assertNotIn("2.9", summary_match_en.group(1))

        summary_match_vi = re.search(r'<p class="summary-p">(.*?)</p>', html_vi, re.DOTALL)
        self.assertTrue(summary_match_vi)
        self.assertNotIn("GPA", summary_match_vi.group(1))
        self.assertNotIn("2.9", summary_match_vi.group(1))

    def test_job_tailoring_differences(self):
        """
        Verify that Cloud vs Security roles produce distinct, tailored summaries and skill order.
        """
        html_cloud = generate_modern_tech_html(self.candidate, language="en", target_role="Cloud & DevOps Intern")
        html_sec = generate_modern_tech_html(self.candidate, language="en", target_role="Security Analyst Intern")
        
        # Role headers differ
        self.assertIn("CLOUD &amp; DEVOPS INTERN", html_cloud.replace("&", "&amp;"))
        self.assertIn("SECURITY ANALYST INTERN", html_sec)
        
        # Cloud summary emphasizes cloud and infrastructure
        self.assertIn("cloud infrastructure and automation", html_cloud)
        
        # Security summary emphasizes network protocols and traffic analysis
        self.assertIn("security monitoring and network traffic analysis", html_sec)
        
        # Skill order in sidebar differs:
        # In cloud: Cloud & Architecture comes before Networking & Security
        cloud_pos = html_cloud.find("Cloud &amp; Architecture")
        net_pos = html_cloud.find("Networking &amp; Security")
        self.assertLess(cloud_pos, net_pos)
        
        # In security: Networking & Security comes before Cloud & Architecture
        cloud_pos_sec = html_sec.find("Cloud &amp; Architecture")
        net_pos_sec = html_sec.find("Networking &amp; Security")
        self.assertLess(net_pos_sec, cloud_pos_sec)

    def test_certifications_no_dangling_dash(self):
        html_en = generate_modern_tech_html(self.candidate, language="en")
        html_vi = generate_modern_tech_html(self.candidate, language="vi")
        
        self.assertNotIn("— (2025)", html_en)
        self.assertNotIn("— ()", html_en)
        self.assertNotIn("— (2025)", html_vi)
        self.assertNotIn("— ()", html_vi)
        self.assertIn("Gemini Certified Student", html_en)
        self.assertIn("Rikkei Education", html_en)

    def test_generic_project_verification_filter(self):
        verified_proj = {"name": "Test Project", "description": "Verified factual work", "technologies": ["Python"]}
        unverified_proj1 = {"name": "Unverified 1", "description": "Dự án cần bổ sung thông tin từ mã nguồn"}
        unverified_proj2 = {"name": "Unverified 2", "description": "Chưa dùng làm bằng chứng cho kỹ năng cụ thể"}
        unverified_proj3 = {"name": "Unverified 3", "is_verified": False}
        
        self.assertTrue(is_project_verified(verified_proj))
        self.assertFalse(is_project_verified(unverified_proj1))
        self.assertFalse(is_project_verified(unverified_proj2))
        self.assertFalse(is_project_verified(unverified_proj3))

    def test_ats_companion_generation(self):
        html_ats_en = generate_ats_html(self.candidate, language="en")
        html_ats_vi = generate_ats_html(self.candidate, language="vi")
        
        self.assertIn("PROFESSIONAL SUMMARY", html_ats_en)
        self.assertIn("TECHNICAL SKILLS", html_ats_en)
        self.assertIn("TÓM TẮT CHUYÊN MÔN", html_ats_vi)
        self.assertIn("KỸ NĂNG KỸ THUẬT", html_ats_vi)

    def test_avatar_helper_safe(self):
        b64 = get_avatar_base64()
        if b64 is not None:
            self.assertTrue(b64.startswith("data:image/"))

    def test_cover_letter_tailoring(self):
        cl_hitachi = generate_job_cover_letter(self.candidate, company="Hitachi Digital Services", target_role="Cloud & DevOps Intern", language="en")
        cl_sec = generate_job_cover_letter(self.candidate, company="CyStack", target_role="Security Analyst Intern", language="en")
        
        self.assertIn("Hitachi Digital Services", cl_hitachi)
        self.assertIn("Cloud & DevOps Intern", cl_hitachi)
        self.assertIn("VKU", cl_hitachi)
        self.assertNotIn("2.9/4.0", cl_hitachi)
        self.assertNotIn("GPA", cl_hitachi)
        
        self.assertIn("CyStack", cl_sec)
        self.assertIn("Security Analyst Intern", cl_sec)
        self.assertIn("Wireshark and Nmap", cl_sec)


if __name__ == "__main__":
    unittest.main()
