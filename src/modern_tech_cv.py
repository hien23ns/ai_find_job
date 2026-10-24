"""
Modern Tech CV Template & Job-Tailored Application Package Generator.
Strictly confined to PROJECT_ROOT.
Creates a high-contrast, professional Modern Tech CV (A4 1-page) tailored to specific JDs.
Maintains absolute factual integrity: no fabricated certifications, degrees, or experience.
Provides:
- Tailored Modern Tech 2-column CV (EN & VI)
- Tailored Cover Letter (EN & VI)
- 1-column ATS companion (EN & VI)
- Direct PDF-to-Image rendering via PyMuPDF (fitz)
- Strict PDF inspection & text extraction via pypdf
- Full application package bundling: output/applications/<company>_<role>_<job_id>/<version>/
"""

from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
LOCAL_DIR = PROJECT_ROOT / ".local"

# Inject local dependencies if present
LOCAL_LIB = LOCAL_DIR / "lib"
if LOCAL_LIB.exists() and str(LOCAL_LIB.resolve()) not in sys.path:
    sys.path.insert(0, str(LOCAL_LIB.resolve()))

from src.avatar import get_avatar_base64
from src.security import ensure_within_project

# Inline SVGs for contact items (crisp vector, no external font downloads or emojis)
SVG_MAIL = '<svg viewBox="0 0 24 24" class="sidebar-icon"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>'
SVG_PHONE = '<svg viewBox="0 0 24 24" class="sidebar-icon"><path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/></svg>'
SVG_LOCATION = '<svg viewBox="0 0 24 24" class="sidebar-icon"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>'
SVG_GITHUB = '<svg viewBox="0 0 24 24" class="sidebar-icon"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>'
SVG_LINKEDIN = '<svg viewBox="0 0 24 24" class="sidebar-icon"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/></svg>'
SVG_GLOBE = '<svg viewBox="0 0 24 24" class="sidebar-icon"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm7.93 9h-3.18a15.7 15.7 0 0 0-1.37-5.06A8.01 8.01 0 0 1 19.93 11zM12 4.07c.88 1.54 1.56 3.6 1.73 5.93H10.27c.17-2.33.85-4.39 1.73-5.93zM4.07 13h3.18c.17 1.8.64 3.42 1.37 4.78A8.01 8.01 0 0 1 4.07 13zm3.18-2H4.07a8.01 8.01 0 0 1 4.55-4.72A15.7 15.7 0 0 0 7.25 11zm4.75 8.93c-.88-1.54-1.56-3.6-1.73-5.93h3.46c-.17 2.33-.85 4.39-1.73 5.93zm2.62-7.93H9.38c-.14-1.27-.2-2.37-.2-3s.06-1.73.2-3h5.24c.14 1.27.2 2.37.2 3s-.06 1.73-.2 3zm.63 4.72c.73-1.36 1.2-2.98 1.37-4.78h3.18a8.01 8.01 0 0 1-4.55 4.78z"/></svg>'


def is_project_verified(proj: Dict[str, Any]) -> bool:
    """
    General verification filter across all candidate projects.
    Excludes unverified projects (such as SecMon or any placeholder)
    WITHOUT hardcoding project names.
    """
    if proj.get("is_verified") is False:
        return False
    desc = (proj.get("description") or "").lower()
    for phrase in ["chưa dùng làm bằng chứng", "cần bổ sung", "unverified", "chưa xác minh"]:
        if phrase in desc:
            return False
    return True


def render_pdf_to_images(pdf_path: Path, output_prefix: Path) -> List[Path]:
    """
    Rasterize actual PDF pages directly to PNG images using PyMuPDF at 150 DPI.
    Strictly satisfies: 'Xem bản render PDF thực tế; screenshot HTML không thay thế kiểm tra PDF.'
    """
    import pymupdf
    
    doc = pymupdf.open(str(pdf_path))
    generated_images = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=150)
        if len(doc) == 1:
            img_path = output_prefix.parent / f"{output_prefix.name}.png"
        else:
            img_path = output_prefix.parent / f"{output_prefix.name}_page{page_idx + 1}.png"
        pix.save(str(img_path))
        generated_images.append(img_path)
    doc.close()
    return generated_images


def verify_pdf_with_pypdf(pdf_path: Path) -> Dict[str, Any]:
    """
    Use pypdf to inspect page count, text extractability, and reading order.
    """
    import pypdf
    
    reader = pypdf.PdfReader(str(pdf_path))
    num_pages = len(reader.pages)
    text_content = ""
    for p in reader.pages:
        text_content += (p.extract_text() or "") + "\n"
        
    return {
        "num_pages": num_pages,
        "is_single_page": (num_pages == 1),
        "text_length": len(text_content),
        "has_name": "NGÔ VĂN HIỀN" in text_content or "NGO VAN HIEN" in text_content,
        "has_email": "hienngo090800@gmail.com" in text_content,
        "has_phone": "0393492064" in text_content,
        "extracted_text_sample": text_content[:500]
    }


def generate_modern_tech_html(
    candidate: Dict[str, Any],
    language: str = "en",
    target_role: Optional[str] = None,
    company: Optional[str] = None,
    eval_result: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a job-tailored, self-contained A4 Modern Tech CV.
    - Strict 1-page A4
    - Left-aligned text (no awkward justify spacing)
    - Shortened 3-4 line summary (no GPA repetition in summary)
    - Factual project descriptions only (no unverified JavaScript, signaling, login, etc.)
    - Excludes unverified coursework / projects
    - Dynamic skill group ordering based on target role
    """
    is_en = (language == "en")
    name = candidate.get("name", "NGÔ VĂN HIỀN").upper()
    
    # Determine tailored role title
    if target_role:
        role = target_role.upper()
    else:
        role = "CLOUD & DEVOPS INTERN"
    
    is_cloud_devops = any(k in role.lower() for k in ["cloud", "devops", "aws", "infrastructure", "sre"])
    
    # Avatar
    avatar_b64 = get_avatar_base64()
    if avatar_b64:
        avatar_markup = f'<img src="{avatar_b64}" alt="{name}" class="avatar-img" />'
    else:
        # Sleek SVG initials monogram frame when candidate has not yet placed PDF
        avatar_markup = '''<div class="avatar-placeholder">
            <svg viewBox="0 0 100 125" class="placeholder-svg">
              <rect width="100" height="125" rx="6" fill="#1e293b"/>
              <circle cx="50" cy="46" r="23" fill="#334155"/>
              <path d="M20 110 c0 -22 15 -35 30 -35 s30 13 30 35 Z" fill="#334155"/>
              <text x="50" y="53" font-family="system-ui, sans-serif" font-size="16" font-weight="700" fill="#38bdf8" text-anchor="middle">NVH</text>
            </svg>
        </div>'''

    contact = candidate.get("contact", {})
    email = contact.get("email", "hienngo090800@gmail.com")
    phone = contact.get("phone", "0393492064")
    loc = contact.get("location", "Đà Nẵng, Việt Nam")
    if is_en:
        loc = "Da Nang, Vietnam"
    github_url = contact.get("github", "https://github.com/hien23ns")
    github_display = github_url.replace("https://", "").replace("http://", "")
    linkedin_url = contact.get("linkedin", "https://www.linkedin.com/in/ngovanhien")
    linkedin_display = linkedin_url.replace("https://www.", "").replace("https://", "").replace("http://", "")
    website_url = contact.get("website", "https://ngovanhien.id.vn")
    website_display = website_url.replace("https://", "").replace("http://", "")

    # Localized Headings
    if is_en:
        title_summary = "Professional Summary"
        title_projects = "Technical Projects & Capstones"
        title_edu = "Education"
        title_certs = "Certifications"
        title_contact = "Contact"
        title_skills = "Technical Skills"
        title_langs = "Languages"
        
        # Tailored Summary: 3-4 lines, left-aligned, NO GPA repetition
        if is_cloud_devops:
            summary_text = (
                "Undergraduate student in Network and Information Security at Vietnam - Korea University of "
                "Information and Communication Technology (VKU), graduating in 2028. Foundational knowledge "
                "in computer networking (OSI, TCP/IP), Linux/Bash administration, Python, Java, and basic AWS cloud "
                "services (IAM, EC2, S3, Shared Responsibility Model). Seeking a Cloud &amp; DevOps Internship to "
                "acquire practical experience in cloud infrastructure and automation."
            )
        else:
            summary_text = (
                "Undergraduate student in Network and Information Security at Vietnam - Korea University of "
                "Information and Communication Technology (VKU), graduating in 2028. Foundational knowledge "
                "in network protocols (OSI, TCP/IP), network analysis tools (Wireshark, Nmap, Firewall), Linux administration, "
                "and programming with Python and Java. Seeking an Information Security &amp; SOC Analyst Internship to apply "
                "technical skills in security monitoring and network traffic analysis."
            )

        edu_degree = "Undergraduate Engineering Program in Network &amp; Information Security"
        edu_school = "Vietnam - Korea University of Information and Communication Technology (VKU)"
        edu_time = "2023 – 2028 (Expected Graduation)"
        edu_gpa_val = ""

        # Verified Projects: 100% factual according to profile, NO unverified JS/Signaling/Login/Module claims
        p1_title = "P2P Screen Sharing using WebRTC"
        p1_tech = "WebRTC &bull; P2P"
        p1_desc = "Developed a peer-to-peer screen sharing and data transmission mechanism between devices using WebRTC."

        p2_title = "Android Social Networking Application"
        p2_tech = "Android"
        p2_desc = "Developed a mobile social networking application on the Android platform."

        cert1_name = "Gemini Certified Student"
        cert1_meta = "(2025)"
        cert2_name = "Building a Personal Project to International Standards"
        cert2_meta = "Rikkei Education (2025)"

        lang1 = "<strong>Vietnamese:</strong> Native"
        lang2 = "<strong>English:</strong> Technical reading; basic conversational English"

        skill_cloud = {
            "label": "Cloud &amp; Architecture",
            "val": "AWS IAM, Amazon EC2, Amazon S3, Shared Responsibility Model (Foundational)"
        }
        skill_sys = {
            "label": "Systems &amp; Scripting",
            "val": "Linux (Ubuntu), Bash Shell"
        }
        skill_prog = {
            "label": "Programming Languages",
            "val": "Python, Java"
        }
        skill_net = {
            "label": "Networking &amp; Security",
            "val": "OSI Model, TCP/IP, Wireshark, Nmap, Firewall fundamentals, WebRTC, P2P"
        }
    else:
        title_summary = "Tóm tắt Chuyên môn"
        title_projects = "Dự án Kỹ thuật &amp; Đồ án"
        title_edu = "Học vấn"
        title_certs = "Chứng chỉ &amp; Bằng cấp"
        title_contact = "Thông tin Liên hệ"
        title_skills = "Kỹ năng Kỹ thuật"
        title_langs = "Ngoại ngữ"

        # Tailored Summary: 3-4 lines, left-aligned, NO GPA repetition
        if is_cloud_devops:
            summary_text = (
                "Sinh viên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông "
                "Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Có kiến thức nền tảng về mạng máy tính (OSI, "
                "TCP/IP), Linux/Bash, lập trình Python/Java và các dịch vụ đám mây AWS cơ bản (IAM, EC2, S3, "
                "Shared Responsibility Model). Mong muốn thực tập vị trí Cloud &amp; DevOps để tích lũy kinh nghiệm "
                "thực hành hạ tầng đám mây và tự động hóa."
            )
        else:
            summary_text = (
                "Sinh viên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông "
                "Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Có kiến thức nền tảng về mô hình OSI, TCP/IP, "
                "công cụ phân tích mạng (Wireshark, Nmap, Firewall), quản trị Linux và lập trình Python/Java. "
                "Mong muốn thực tập vị trí An toàn thông tin / SOC Analyst để phát triển kỹ năng giám sát an ninh "
                "mạng và phân tích lưu lượng thực tế."
            )

        edu_degree = "Chương trình Kỹ sư ngành Mạng và An toàn thông tin"
        edu_school = "Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU)"
        edu_time = "2023 – 2028 (Dự kiến tốt nghiệp)"
        edu_gpa_val = ""

        # Verified Projects: 100% factual
        p1_title = "Chia sẻ màn hình P2P sử dụng WebRTC"
        p1_tech = "WebRTC &bull; P2P"
        p1_desc = "Phát triển cơ chế chia sẻ màn hình và truyền dữ liệu giữa các thiết bị theo mô hình P2P sử dụng WebRTC."

        p2_title = "Ứng dụng mạng xã hội Android"
        p2_tech = "Android"
        p2_desc = "Thực hiện dự án ứng dụng mạng xã hội trên nền tảng Android."

        cert1_name = "Gemini Certified Student"
        cert1_meta = "(2025)"
        cert2_name = "Xây dựng Dự án Cá nhân theo Tiêu chuẩn Quốc tế"
        cert2_meta = "Rikkei Education (2025)"

        lang1 = "<strong>Tiếng Việt:</strong> Bản ngữ"
        lang2 = "<strong>Tiếng Anh:</strong> Technical reading; basic conversational English"

        skill_cloud = {
            "label": "Điện toán Đám mây (Cơ bản)",
            "val": "AWS IAM, Amazon EC2, Amazon S3, Shared Responsibility Model"
        }
        skill_sys = {
            "label": "Hệ thống &amp; Scripting",
            "val": "Linux (Ubuntu), Bash Shell"
        }
        skill_prog = {
            "label": "Ngôn ngữ Lập trình",
            "val": "Python, Java"
        }
        skill_net = {
            "label": "Mạng &amp; An toàn Thông tin",
            "val": "Mô hình OSI, TCP/IP, Wireshark, Nmap, Firewall, WebRTC, P2P"
        }

    # Dynamic skill ordering based on target job
    if is_cloud_devops:
        skills_ordered = [skill_cloud, skill_sys, skill_prog, skill_net]
    else:
        skills_ordered = [skill_net, skill_sys, skill_prog, skill_cloud]

    skill_blocks_html = "\n".join([
        f"""        <div class="skill-group">
          <div class="skill-label">{s['label']}</div>
          <div class="skill-val">{s['val']}</div>
        </div>"""
        for s in skills_ordered
    ])

    html_doc = f"""<!DOCTYPE html>
<html lang="{language}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} - {role} Curriculum Vitae</title>
<style>
/* Reset & Base Rules */
@page {{
  size: A4 portrait;
  margin: 0;
}}
*, *::before, *::after {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}
html, body {{
  width: 210mm;
  height: 297mm;
  margin: 0;
  padding: 0;
  background: #f1f5f9;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #334155;
  font-size: 10.5pt;
  line-height: 1.5;
}}

/* Outer Container - Strict A4 Frame */
.cv-page {{
  width: 210mm;
  height: 297mm;
  max-height: 297mm;
  margin: 0 auto;
  background: #ffffff;
  display: flex;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  position: relative;
}}

/* =========================================
   SIDEBAR (32.5% Navy Tech Column)
   order: 1 places it visually on the LEFT
   ========================================= */
.sidebar {{
  width: 32.5%;
  background: #0b1528;
  color: #f8fafc;
  padding: 14mm 9mm 14mm 11mm;
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-right: 1.5px solid #1e293b;
  position: relative;
  order: 1;
  flex-shrink: 0;
}}

/* Top Tech Gradient Line */
.sidebar::before {{
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3.5px;
  background: linear-gradient(90deg, #0284c7, #0ea5e9, #38bdf8);
}}

/* Avatar Container */
.avatar-wrap {{
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 6px;
}}
.avatar-img {{
  width: 96px;
  height: 122px;
  object-fit: cover;
  border-radius: 6px;
  border: 2px solid #0284c7;
  box-shadow: 0 4px 14px rgba(2, 132, 199, 0.25);
  display: block;
}}
.avatar-placeholder {{
  width: 96px;
  height: 122px;
  border-radius: 6px;
  border: 2px solid #0284c7;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1e293b;
  box-shadow: 0 4px 14px rgba(2, 132, 199, 0.2);
}}
.placeholder-svg {{
  width: 100%;
  height: 100%;
}}

/* Sidebar Section Headers */
.sidebar-heading {{
  font-size: 9.75pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.9px;
  color: #38bdf8;
  border-bottom: 1px solid rgba(56, 189, 248, 0.25);
  padding-bottom: 3.5px;
  margin-bottom: 7px;
}}

/* Contact Items */
.contact-list {{
  display: flex;
  flex-direction: column;
  gap: 7px;
}}
.contact-item {{
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 8.35pt;
  letter-spacing: -0.1px;
  color: #e2e8f0;
}}
.sidebar-icon {{
  width: 13.5px;
  height: 13.5px;
  fill: #38bdf8;
  flex-shrink: 0;
}}
.contact-link {{
  color: #e2e8f0;
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-block;
  max-width: 172px;
  vertical-align: middle;
  transition: color 0.15s ease;
}}
.contact-link:hover {{
  color: #38bdf8;
  text-decoration: underline;
}}
.contact-text {{
  white-space: nowrap;
}}

/* Skill Blocks */
.skills-list {{
  display: flex;
  flex-direction: column;
  gap: 9.5px;
}}
.skill-group {{
  display: flex;
  flex-direction: column;
  gap: 2px;
}}
.skill-label {{
  font-size: 8.5pt;
  font-weight: 700;
  color: #7dd3fc;
  letter-spacing: 0.2px;
}}
.skill-val {{
  font-size: 8.5pt;
  color: #cbd5e1;
  line-height: 1.35;
}}

/* Languages */
.lang-list {{
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: 8.5pt;
  color: #cbd5e1;
  line-height: 1.35;
}}

/* =========================================
   MAIN COLUMN (67.5% Crisp White Tech Content)
   order: 2 places it visually on the RIGHT
   ========================================= */
.main-content {{
  width: 67.5%;
  background: #ffffff;
  color: #334155;
  padding: 14mm 14mm 14mm 15mm;
  display: flex;
  flex-direction: column;
  gap: 16px;
  justify-content: flex-start;
  order: 2;
}}

/* Header Box */
.header-box {{
  border-bottom: 1.5px solid #e2e8f0;
  padding-bottom: 7px;
  margin-bottom: 2px;
}}
.cand-name {{
  font-size: 21pt;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: 0.5px;
  line-height: 1.1;
  margin-bottom: 4px;
}}
.cand-role {{
  font-size: 11pt;
  font-weight: 700;
  color: #0284c7;
  letter-spacing: 1.3px;
  text-transform: uppercase;
}}

/* Section Structure */
.section-block {{
  display: flex;
  flex-direction: column;
  gap: 5px;
}}
.section-title {{
  font-size: 10.75pt;
  font-weight: 700;
  color: #0f172a;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 2px;
}}
.section-title::before {{
  content: "";
  display: inline-block;
  width: 3.5px;
  height: 14px;
  background: #0ea5e9;
  border-radius: 2px;
}}

/* Professional Summary: strictly left-aligned */
.summary-p {{
  font-size: 10.5pt;
  line-height: 1.5;
  color: #334155;
  text-align: left;
}}

/* Projects */
.project-card {{
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-bottom: 8px;
}}
.project-card:last-child {{
  margin-bottom: 0;
}}
.project-top {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
}}
.project-name {{
  font-size: 10.5pt;
  font-weight: 700;
  color: #0f172a;
}}
.project-tech {{
  font-size: 8.5pt;
  font-weight: 600;
  color: #0369a1;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 3px;
  padding: 1px 7px;
}}
.project-desc {{
  font-size: 10pt;
  line-height: 1.45;
  color: #334155;
  text-align: left;
}}

/* Education Card */
.edu-card {{
  display: flex;
  flex-direction: column;
  gap: 2.5px;
}}
.edu-top {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 10.5pt;
}}
.edu-degree {{
  font-weight: 700;
  color: #0f172a;
}}
.edu-time {{
  font-size: 9pt;
  color: #64748b;
  font-weight: 500;
}}
.edu-school {{
  font-size: 9.75pt;
  color: #0284c7;
  font-weight: 600;
}}
.edu-row {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 9.5pt;
  color: #334155;
  margin-top: 2px;
}}
.edu-gpa-badge {{
  font-weight: 700;
  color: #0f172a;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  padding: 1px 7px;
  border-radius: 3px;
  white-space: nowrap;
}}

/* Certifications */
.cert-list {{
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 10pt;
}}
.cert-item {{
  position: relative;
  padding-left: 14px;
  line-height: 1.45;
  color: #334155;
}}
.cert-item::before {{
  content: "•";
  position: absolute;
  left: 0;
  top: 0;
  color: #0ea5e9;
  font-weight: bold;
  font-size: 11pt;
}}
.cert-name {{
  font-weight: 600;
  color: #0f172a;
}}
.cert-org {{
  font-size: 9.5pt;
  color: #64748b;
}}

/* Print Media Optimization */
@media print {{
  html, body {{
    background: transparent;
  }}
  .cv-page {{
    box-shadow: none;
    margin: 0;
    width: 210mm;
    height: 297mm;
  }}
}}
</style>
</head>
<body>
<div class="cv-page">
  <!-- MAIN COLUMN (67.5% - DOM Order First for ATS & Screen Readers) -->
  <main class="main-content">
    <!-- Header -->
    <header class="header-box">
      <h1 class="cand-name">{name}</h1>
      <div class="cand-role">{role}</div>
    </header>

    <!-- Professional Summary -->
    <section class="section-block">
      <h2 class="section-title">{title_summary}</h2>
      <p class="summary-p">{summary_text}</p>
    </section>

    <!-- Technical Projects (100% Verified Factual Content) -->
    <section class="section-block">
      <h2 class="section-title">{title_projects}</h2>
      <div class="project-card">
        <div class="project-top">
          <span class="project-name">{p1_title}</span>
          <span class="project-tech">{p1_tech}</span>
        </div>
        <p class="project-desc">{p1_desc}</p>
      </div>

      <div class="project-card">
        <div class="project-top">
          <span class="project-name">{p2_title}</span>
          <span class="project-tech">{p2_tech}</span>
        </div>
        <p class="project-desc">{p2_desc}</p>
      </div>
    </section>

    <!-- Education -->
    <section class="section-block">
      <h2 class="section-title">{title_edu}</h2>
      <div class="edu-card">
        <div class="edu-top">
          <span class="edu-degree">{edu_degree}</span>
          <span class="edu-time">{edu_time}</span>
        </div>
        <div class="edu-school">{edu_school}</div>
      </div>
    </section>

    <!-- Certifications -->
    <section class="section-block">
      <h2 class="section-title">{title_certs}</h2>
      <div class="cert-list">
        <div class="cert-item">
          <span class="cert-name">{cert1_name}</span> <span class="cert-org">{cert1_meta}</span>
        </div>
        <div class="cert-item">
          <span class="cert-name">{cert2_name}</span> <span class="cert-org">— {cert2_meta}</span>
        </div>
      </div>
    </section>
  </main>

  <!-- SIDEBAR (32.5% - Visually on the LEFT via CSS order: 1) -->
  <aside class="sidebar">
    <!-- Portrait Avatar -->
    <div class="avatar-wrap">
      {avatar_markup}
    </div>

    <!-- Contact Info -->
    <div>
      <div class="sidebar-heading">{title_contact}</div>
      <div class="contact-list">
        <div class="contact-item">
          {SVG_MAIL}
          <a href="mailto:{email}" class="contact-link" title="{email}">{email}</a>
        </div>
        <div class="contact-item">
          {SVG_PHONE}
          <a href="tel:{phone}" class="contact-link">{phone}</a>
        </div>
        <div class="contact-item">
          {SVG_LOCATION}
          <span class="contact-text">{loc}</span>
        </div>
        <div class="contact-item">
          {SVG_GITHUB}
          <a href="{github_url}" target="_blank" rel="noopener" class="contact-link">{github_display}</a>
        </div>
        <div class="contact-item">
          {SVG_LINKEDIN}
          <a href="{linkedin_url}" target="_blank" rel="noopener" class="contact-link">{linkedin_display}</a>
        </div>
        <div class="contact-item">
          {SVG_GLOBE}
          <a href="{website_url}" target="_blank" rel="noopener" class="contact-link">{website_display}</a>
        </div>
      </div>
    </div>

    <!-- Technical Skills (Dynamically Ordered by Job Role) -->
    <div>
      <div class="sidebar-heading">{title_skills}</div>
      <div class="skills-list">
{skill_blocks_html}
      </div>
    </div>

    <!-- Languages -->
    <div>
      <div class="sidebar-heading">{title_langs}</div>
      <div class="lang-list">
        <div>{lang1}</div>
        <div>{lang2}</div>
      </div>
    </div>
  </aside>
</div>
</body>
</html>
"""
    return html_doc


def generate_ats_html(
    candidate: Dict[str, Any],
    language: str = "en",
    target_role: Optional[str] = None
) -> str:
    """
    Generate 1-column linear ATS companion HTML with identical factual content.
    """
    is_en = (language == "en")
    name = candidate.get("name", "NGÔ VĂN HIỀN").upper()
    role = target_role.upper() if target_role else "CLOUD & DEVOPS INTERN"
    is_cloud_devops = any(k in role.lower() for k in ["cloud", "devops", "aws", "infrastructure", "sre"])

    contact = candidate.get("contact", {})
    email = contact.get("email", "hienngo090800@gmail.com")
    phone = contact.get("phone", "0393492064")
    loc = contact.get("location", "Đà Nẵng, Việt Nam")
    if is_en:
        loc = "Da Nang, Vietnam"
    github_url = contact.get("github", "https://github.com/hien23ns")
    linkedin_url = contact.get("linkedin", "https://www.linkedin.com/in/ngovanhien")
    website_url = contact.get("website", "https://ngovanhien.id.vn")

    if is_en:
        title_summary = "PROFESSIONAL SUMMARY"
        title_skills = "TECHNICAL SKILLS"
        title_projects = "TECHNICAL PROJECTS"
        title_edu = "EDUCATION"
        title_certs = "CERTIFICATIONS"
        title_langs = "LANGUAGES"

        if is_cloud_devops:
            summary_text = (
                "Undergraduate student in Network and Information Security at Vietnam - Korea University of "
                "Information and Communication Technology (VKU), graduating in 2028. Foundational knowledge "
                "in computer networking (OSI, TCP/IP), Linux/Bash administration, Python, Java, and basic AWS cloud "
                "services (IAM, EC2, S3, Shared Responsibility Model). Seeking a Cloud & DevOps Internship to "
                "acquire practical experience in cloud infrastructure and automation."
            )
        else:
            summary_text = (
                "Undergraduate student in Network and Information Security at Vietnam - Korea University of "
                "Information and Communication Technology (VKU), graduating in 2028. Foundational knowledge "
                "in network protocols (OSI, TCP/IP), network analysis tools (Wireshark, Nmap, Firewall), Linux administration, "
                "and programming with Python and Java. Seeking an Information Security & SOC Analyst Internship to apply "
                "technical skills in security monitoring and network traffic analysis."
            )

        p1_title = "P2P Screen Sharing using WebRTC"
        p1_tech = "WebRTC, P2P"
        p1_desc = "Developed a peer-to-peer screen sharing and data transmission mechanism between devices using WebRTC."

        p2_title = "Android Social Networking Application"
        p2_tech = "Android"
        p2_desc = "Developed a mobile social networking application on the Android platform."

        edu_degree = "Undergraduate Engineering Program in Network & Information Security"
        edu_school = "Vietnam - Korea University of Information and Communication Technology (VKU)"
        edu_time = "2023 – 2028 (Expected Graduation)"
        edu_gpa = ""

        cert1_name = "Gemini Certified Student (2025)"
        cert2_name = "Building a Personal Project to International Standards — Rikkei Education (2025)"

        lang1 = "Vietnamese: Native"
        lang2 = "English: Technical reading; basic conversational English"

        if is_cloud_devops:
            skills_content = """
        <ul>
          <li><strong>Cloud &amp; Infrastructure (Foundational):</strong> AWS IAM, Amazon EC2, Amazon S3, Shared Responsibility Model</li>
          <li><strong>Systems &amp; Scripting:</strong> Linux (Ubuntu), Bash Shell</li>
          <li><strong>Programming Languages:</strong> Python, Java</li>
          <li><strong>Networking &amp; Security:</strong> OSI Model, TCP/IP, Wireshark, Nmap, Firewall fundamentals, WebRTC, P2P</li>
        </ul>
        """
        else:
            skills_content = """
        <ul>
          <li><strong>Networking &amp; Security:</strong> OSI Model, TCP/IP, Wireshark, Nmap, Firewall fundamentals, WebRTC, P2P</li>
          <li><strong>Systems &amp; Scripting:</strong> Linux (Ubuntu), Bash Shell</li>
          <li><strong>Programming Languages:</strong> Python, Java</li>
          <li><strong>Cloud &amp; Infrastructure (Foundational):</strong> AWS IAM, Amazon EC2, Amazon S3, Shared Responsibility Model</li>
        </ul>
        """
    else:
        title_summary = "TÓM TẮT CHUYÊN MÔN"
        title_skills = "KỸ NĂNG KỸ THUẬT"
        title_projects = "DỰ ÁN KỸ THUẬT"
        title_edu = "HỌC VẤN"
        title_certs = "CHỨNG CHỈ &amp; BẰNG CẤP"
        title_langs = "NGOẠI NGỮ"

        if is_cloud_devops:
            summary_text = (
                "Sinh viên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông "
                "Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Có kiến thức nền tảng về mạng máy tính (OSI, "
                "TCP/IP), Linux/Bash, lập trình Python/Java và các dịch vụ đám mây AWS cơ bản (IAM, EC2, S3, "
                "Shared Responsibility Model). Mong muốn thực tập vị trí Cloud & DevOps để tích lũy kinh nghiệm "
                "thực hành hạ tầng đám mây và tự động hóa."
            )
        else:
            summary_text = (
                "Sinh viên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông "
                "Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Có kiến thức nền tảng về mô hình OSI, TCP/IP, "
                "công cụ phân tích mạng (Wireshark, Nmap, Firewall), quản trị Linux và lập trình Python/Java. "
                "Mong muốn thực tập vị trí An toàn thông tin / SOC Analyst để phát triển kỹ năng giám sát an ninh "
                "mạng và phân tích lưu lượng thực tế."
            )

        p1_title = "Chia sẻ màn hình P2P sử dụng WebRTC"
        p1_tech = "WebRTC, P2P"
        p1_desc = "Phát triển cơ chế chia sẻ màn hình và truyền dữ liệu giữa các thiết bị theo mô hình P2P sử dụng WebRTC."

        p2_title = "Ứng dụng mạng xã hội Android"
        p2_tech = "Android"
        p2_desc = "Thực hiện dự án ứng dụng mạng xã hội trên nền tảng Android."

        edu_degree = "Chương trình Kỹ sư ngành Mạng và An toàn thông tin"
        edu_school = "Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU)"
        edu_time = "2023 – 2028 (Dự kiến tốt nghiệp)"
        edu_gpa = ""

        cert1_name = "Gemini Certified Student (2025)"
        cert2_name = "Xây dựng Dự án Cá nhân theo Tiêu chuẩn Quốc tế — Rikkei Education (2025)"

        lang1 = "Tiếng Việt: Bản ngữ"
        lang2 = "Tiếng Anh: Technical reading; basic conversational English"

        if is_cloud_devops:
            skills_content = """
        <ul>
          <li><strong>Điện toán Đám mây (Cơ bản):</strong> AWS IAM, Amazon EC2, Amazon S3, Shared Responsibility Model</li>
          <li><strong>Hệ thống &amp; Scripting:</strong> Linux (Ubuntu), Bash Shell</li>
          <li><strong>Ngôn ngữ Lập trình:</strong> Python, Java</li>
          <li><strong>Mạng &amp; An toàn Thông tin:</strong> Mô hình OSI, TCP/IP, Wireshark, Nmap, Firewall, WebRTC, P2P</li>
        </ul>
        """
        else:
            skills_content = """
        <ul>
          <li><strong>Mạng &amp; An toàn Thông tin:</strong> Mô hình OSI, TCP/IP, Wireshark, Nmap, Firewall, WebRTC, P2P</li>
          <li><strong>Hệ thống &amp; Scripting:</strong> Linux (Ubuntu), Bash Shell</li>
          <li><strong>Ngôn ngữ Lập trình:</strong> Python, Java</li>
          <li><strong>Điện toán Đám mây (Cơ bản):</strong> AWS IAM, Amazon EC2, Amazon S3, Shared Responsibility Model</li>
        </ul>
        """

    html = f"""<!DOCTYPE html>
<html lang="{language}">
<head>
<meta charset="UTF-8">
<title>{name} - {role} ATS Resume</title>
<style>
@page {{
  size: A4 portrait;
  margin: 15mm 18mm;
}}
body {{
  font-family: Arial, "Helvetica Neue", Helvetica, sans-serif;
  color: #111827;
  font-size: 10.5pt;
  line-height: 1.45;
  margin: 0;
  padding: 0;
}}
h1 {{
  font-size: 18pt;
  margin: 0 0 2px 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.role {{
  font-size: 11pt;
  font-weight: bold;
  color: #0369a1;
  margin-bottom: 6px;
}}
.contact-line {{
  font-size: 9.5pt;
  color: #374151;
  margin-bottom: 12px;
}}
.contact-line a {{
  color: #111827;
  text-decoration: none;
}}
hr {{
  border: 0;
  border-top: 1px solid #d1d5db;
  margin: 10px 0;
}}
h2 {{
  font-size: 11.5pt;
  margin: 12px 0 6px 0;
  text-transform: uppercase;
  border-bottom: 1px solid #111827;
  padding-bottom: 2px;
  letter-spacing: 0.5px;
}}
p {{
  margin: 0 0 6px 0;
  text-align: left;
}}
ul {{
  margin: 0 0 8px 0;
  padding-left: 20px;
}}
li {{
  margin-bottom: 3px;
}}
.item-header {{
  display: flex;
  justify-content: space-between;
  font-weight: bold;
  margin-top: 6px;
}}
.item-sub {{
  color: #4b5563;
  font-size: 9.75pt;
  margin-bottom: 3px;
}}
</style>
</head>
<body>
  <h1>{name}</h1>
  <div class="role">{role}</div>
  <div class="contact-line">
    {loc} | {phone} | <a href="mailto:{email}">{email}</a> | <a href="{github_url}">{github_url}</a> | <a href="{linkedin_url}">{linkedin_url}</a> | <a href="{website_url}">{website_url}</a>
  </div>

  <h2>{title_summary}</h2>
  <p>{summary_text}</p>

  <h2>{title_skills}</h2>
  {skills_content}

  <h2>{title_projects}</h2>
  <div class="item-header">
    <span>{p1_title}</span>
    <span>{p1_tech}</span>
  </div>
  <p>{p1_desc}</p>

  <div class="item-header">
    <span>{p2_title}</span>
    <span>{p2_tech}</span>
  </div>
  <p>{p2_desc}</p>

  <h2>{title_edu}</h2>
  <div class="item-header">
    <span>{edu_degree}</span>
    <span>{edu_time}</span>
  </div>
  <div class="item-sub">{edu_school}</div>

  <h2>{title_certs}</h2>
  <ul>
    <li>{cert1_name}</li>
    <li>{cert2_name}</li>
  </ul>

  <h2>{title_langs}</h2>
  <ul>
    <li>{lang1}</li>
    <li>{lang2}</li>
  </ul>
</body>
</html>
"""
    return html


def generate_job_cover_letter(
    candidate: Dict[str, Any],
    company: str,
    target_role: str,
    language: str = "en",
    eval_result: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a job-tailored Cover Letter specifically addressed to the company and role.
    Strictly factual: quotes candidate's education at VKU (class 2023-2028, GPA 2.9/4.0),
    highlights verified skills, and addresses internship arrangement honestly.
    """
    is_en = (language == "en")
    name = candidate.get("name", "Ngô Văn Hiền")
    contact = candidate.get("contact", {})
    email = contact.get("email", "hienngo090800@gmail.com")
    phone = contact.get("phone", "0393492064")
    loc = "Da Nang, Vietnam" if is_en else "Đà Nẵng, Việt Nam"
    today = datetime.now().strftime("%B %d, %Y" if is_en else "%d/%m/%Y")
    
    is_cloud_devops = any(k in target_role.lower() for k in ["cloud", "devops", "aws", "infrastructure", "sre"])

    if is_en:
        if is_cloud_devops:
            body = f"""Dear Hiring Team at {company},

I am writing to express my strong interest in the {target_role} position at {company}. As an undergraduate student majoring in Network and Information Security at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I have developed a solid foundation in Linux system administration, computer networking (OSI, TCP/IP), and programming with Python and Java.

Throughout my academic coursework and personal projects, I have familiarized myself with foundational cloud concepts on AWS, including IAM, EC2, S3, and the AWS Shared Responsibility Model. Additionally, I have developed academic projects including a peer-to-peer screen sharing tool using WebRTC and an Android mobile application. These projects have given me opportunities to apply programming and networking concepts.

I am particularly excited about the opportunity to intern at {company} because of your commitment to technological innovation and engineering excellence. I am eager to apply my foundational skills in scripting, networking, and cloud services under the guidance of your team, while acquiring practical hands-on experience in cloud infrastructure, automation, and system reliability.

Thank you very much for your time and consideration. I welcome the opportunity to discuss how my academic background and dedication to continuous learning can contribute to your team.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        else:
            body = f"""Dear Hiring Team at {company},

I am writing to enthusiastically apply for the {target_role} position at {company}. Currently pursuing my degree in Network and Information Security at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I have focused my studies on network architecture, packet analysis, and system security fundamentals.

My academic foundation includes practical work with Linux environments (Ubuntu), Bash scripting, and programming in Python and Java. I have practical familiarity with network tools such as Wireshark and Nmap to analyze traffic and investigate packet flows, alongside core concepts of firewall rules. These projects have given me opportunities to apply programming and networking concepts.

Joining {company} as an intern would provide an invaluable opportunity to contribute to security operations and threat monitoring. I am eager to learn from your security professionals, support daily monitoring workflows, and apply my technical skills with discipline and integrity.

Thank you for reviewing my application. I look forward to the possibility of discussing my background in greater detail.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
    else:
        if is_cloud_devops:
            body = f"""Kính gửi: Bộ phận Tuyển dụng {company},

Tôi viết thư này để bày tỏ nguyện vọng ứng tuyển vào vị trí {target_role} tại {company}. Hiện tôi là sinh viên chuyên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Trong quá trình học tập, tôi đã xây dựng nền tảng vững chắc về hệ điều hành Linux (Ubuntu), Bash script, lập trình Python/Java và kiến thức mạng máy tính (OSI, TCP/IP).

Về mảng điện toán đám mây, tôi đã chủ động tìm hiểu và nắm vững các khái niệm cơ bản trên nền tảng AWS như IAM, Amazon EC2, Amazon S3 và Mô hình trách nhiệm chia sẻ (Shared Responsibility Model). Đồng thời, tôi đã thực hiện các đồ án học thuật bao gồm chia sẻ màn hình P2P qua WebRTC và ứng dụng di động Android. Các dự án này đã mang lại cho tôi cơ hội vận dụng các kiến thức lập trình và mạng máy tính vào thực tế.

Tôi rất ấn tượng với môi trường kỹ thuật và các giải pháp chuyển đổi số của {company}. Tôi mong muốn có cơ hội thực tập tại công ty để đóng góp sự nhiệt huyết, tinh thần kỷ luật và tiếp thu kinh nghiệm thực tế về tự động hóa hạ tầng và vận hành hệ thống đám mây từ các kỹ sư đi trước.

Xin chân thành cảm ơn Quý công ty đã dành thời gian xem xét hồ sơ của tôi. Tôi rất mong có cơ hội được trao đổi trực tiếp trong buổi phỏng vấn.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        else:
            body = f"""Kính gửi: Bộ phận Tuyển dụng {company},

Tôi viết thư này để bày tỏ mong muốn được ứng tuyển vào vị trí {target_role} tại {company}. Tôi hiện đang theo học chuyên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp vào năm 2028.

Trong chương trình đào tạo kỹ sư, tôi đã trang bị kiến thức bài bản về mô hình mạng OSI, bộ giao thức TCP/IP, cấu trúc gói tin, cùng kỹ năng sử dụng các công cụ phân tích lưu lượng mạng như Wireshark, Nmap và nguyên lý hoạt động của Firewall. Bên cạnh đó, tôi có kỹ năng thực hành tốt với thao tác dòng lệnh trên Linux (Ubuntu) và viết script Python/Bash để đọc hiểu, xử lý log và tự động hóa tác vụ cơ bản. Các dự án này đã mang lại cho tôi cơ hội vận dụng các kiến thức lập trình và mạng máy tính vào thực tế.

Tôi mong muốn được tham gia thực tập tại {company} để áp dụng kiến thức phân tích mạng và an toàn thông tin vào thực tiễn giám sát an ninh mạng, đồng thời rèn luyện tính kỷ luật và bảo mật thông tin theo chuẩn doanh nghiệp.

Tôi xin chân thành cảm ơn Quý công ty đã quan tâm đến hồ sơ ứng tuyển. Rất mong có cơ hội được tham gia trao đổi sâu hơn về vị trí thực tập này.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    title_header = "# COVER LETTER" if is_en else "# THƯ ỨNG TUYỂN"
    cand_label = "**Candidate:**" if is_en else "**Ứng viên:**"
    comp_label = "**Company:**" if is_en else "**Công ty:**"
    role_label = "**Target Role:**" if is_en else "**Vị trí ứng tuyển:**"

    return f"""{title_header}
**Date:** {today}
{cand_label} {name}
{comp_label} {company}
{role_label} {target_role}

---

{body}
"""


def create_job_application_package(
    candidate: Dict[str, Any],
    eval_result: Dict[str, Any],
    jd_data: Dict[str, Any],
    template: str = "modern_tech",
    base_output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Generate and save a dedicated, job-tailored application package:
    Directory structure:
      <base_output_dir>/<company>_<role>_<job_id>/<version>/
    Saved files:
      - source_jd.txt (raw JD + metadata header)
      - manifest.json (hashes, metadata, artifact list)
      - internal_evaluation.json (met/unmet/unknown conditions, strictly private)
      - cv_en.html & cv_en.pdf (1-page Modern Tech CV)
      - cv_vi.html & cv_vi.pdf (1-page Modern Tech CV)
      - cover_letter_en.md (tailored Cover Letter)
      - cover_letter_vi.md (tailored Cover Letter)
      - cv_en_preview.png & cv_vi_preview.png (rendered directly from PDF via PyMuPDF at 150 DPI)
      - cv_ats_en.pdf & cv_ats_vi.pdf (1-column ATS companion)
    """
    company = jd_data.get("company", "Company")
    role = eval_result.get("title", jd_data.get("title", "Intern"))
    job_id = str(jd_data.get("job_id", eval_result.get("id", "job_custom")))
    
    # Sanitize naming
    c_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', company.lower()).strip('_')[:25]
    r_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', role.lower()).strip('_')[:35]
    j_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', job_id.lower()).strip('_')[:20]
    folder_name = f"{c_clean}_{r_clean}_{j_clean}".strip('_')
    
    if base_output_dir is None:
        base_dir = OUTPUT_DIR / "applications" / folder_name
    else:
        base_dir = base_output_dir / folder_name
        
    base_dir = ensure_within_project(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine non-overwriting version (v1, v2, ...)
    version_idx = 1
    while (base_dir / f"v{version_idx}").exists():
        version_idx += 1
    version_dir = ensure_within_project(base_dir / f"v{version_idx}")
    version_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Save source_jd.txt
    jd_text = jd_data.get("text", jd_data.get("raw_jd", ""))
    jd_url = jd_data.get("source", eval_result.get("source", ""))
    fetched_at = jd_data.get("fetched_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    source_jd_content = f"""======================================================================
 SOURCE JOB POSTING
======================================================================
Company:    {company}
Title:      {role}
Job ID:     {job_id}
URL:        {jd_url}
Fetched At: {fetched_at}
Market:     {eval_result.get('market', 'vietnam')}
======================================================================
--- RAW JD CONTENT ---
{jd_text}
"""
    source_jd_path = version_dir / "source_jd.txt"
    source_jd_path.write_text(source_jd_content, encoding="utf-8")
    
    # 2. Build internal_evaluation.json (strictly private)
    internal_eval = {
        "job_id": job_id,
        "company": company,
        "title": role,
        "evaluated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "match_score": eval_result.get("match_score"),
        "score_status": eval_result.get("score_status"),
        "recommendation": eval_result.get("recommendation"),
        "rationale": eval_result.get("rationale"),
        "mandatory_conditions": {
            "met": eval_result.get("hard_requirements", []),
            "unmet": eval_result.get("unmet_requirements", []),
            "unknown": eval_result.get("unclear_items", [])
        },
        "disqualifiers": eval_result.get("disqualifiers", []),
        "matched_skills": [m.get("skill") for m in eval_result.get("matched_skills", [])],
        "missing_skills": eval_result.get("missing_skills", []),
        "clarification_questions": eval_result.get("clarification_questions", []),
        "private_audit_notes": []
    }
    
    # Special audit check for Hitachi or similar requirements
    if "hitachi" in company.lower() or "4481162663" in job_id:
        internal_eval["private_audit_notes"].append(
            "Lịch thực tập: JD ghi 'flexible arrangements' nhưng không nêu rõ số buổi/tuần. Cần xác nhận trực tiếp với HR để đối chiếu lịch học tại VKU; không tự suy đoán là part-time."
        )
        
    internal_eval_path = version_dir / "internal_evaluation.json"
    internal_eval_path.write_text(json.dumps(internal_eval, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # 3. Generate HTMLs
    html_en = generate_modern_tech_html(candidate, language="en", target_role=role, company=company, eval_result=eval_result)
    html_vi = generate_modern_tech_html(candidate, language="vi", target_role=role, company=company, eval_result=eval_result)
    
    html_ats_en = generate_ats_html(candidate, language="en", target_role=role)
    html_ats_vi = generate_ats_html(candidate, language="vi", target_role=role)
    
    cv_en_html_path = version_dir / "cv_en.html"
    cv_vi_html_path = version_dir / "cv_vi.html"
    cv_ats_en_html_path = version_dir / "cv_ats_en.html"
    cv_ats_vi_html_path = version_dir / "cv_ats_vi.html"
    
    cv_en_html_path.write_text(html_en, encoding="utf-8")
    cv_vi_html_path.write_text(html_vi, encoding="utf-8")
    cv_ats_en_html_path.write_text(html_ats_en, encoding="utf-8")
    cv_ats_vi_html_path.write_text(html_ats_vi, encoding="utf-8")
    
    # 4. Generate Cover Letters
    cl_en = generate_job_cover_letter(candidate, company=company, target_role=role, language="en", eval_result=eval_result)
    cl_vi = generate_job_cover_letter(candidate, company=company, target_role=role, language="vi", eval_result=eval_result)
    
    cl_en_path = version_dir / "cover_letter_en.md"
    cl_vi_path = version_dir / "cover_letter_vi.md"
    cl_en_path.write_text(cl_en, encoding="utf-8")
    cl_vi_path.write_text(cl_vi, encoding="utf-8")
    
    # 5. Render PDFs via Playwright
    from playwright.sync_api import sync_playwright
    
    cv_en_pdf_path = version_dir / "cv_en.pdf"
    cv_vi_pdf_path = version_dir / "cv_vi.pdf"
    cv_ats_en_pdf_path = version_dir / "cv_ats_en.pdf"
    cv_ats_vi_pdf_path = version_dir / "cv_ats_vi.pdf"
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        
        # English Modern Tech
        p_en = browser.new_page(viewport={"width": 794, "height": 1123})
        p_en.goto(f"file:///{cv_en_html_path.resolve().as_posix()}", wait_until="networkidle")
        p_en.pdf(
            path=str(cv_en_pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
            prefer_css_page_size=True
        )
        p_en.close()
        
        # Vietnamese Modern Tech
        p_vi = browser.new_page(viewport={"width": 794, "height": 1123})
        p_vi.goto(f"file:///{cv_vi_html_path.resolve().as_posix()}", wait_until="networkidle")
        p_vi.pdf(
            path=str(cv_vi_pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
            prefer_css_page_size=True
        )
        p_vi.close()

        # English ATS
        p_ats_en = browser.new_page(viewport={"width": 794, "height": 1123})
        p_ats_en.goto(f"file:///{cv_ats_en_html_path.resolve().as_posix()}", wait_until="networkidle")
        p_ats_en.pdf(
            path=str(cv_ats_en_pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
            prefer_css_page_size=True
        )
        p_ats_en.close()

        # Vietnamese ATS
        p_ats_vi = browser.new_page(viewport={"width": 794, "height": 1123})
        p_ats_vi.goto(f"file:///{cv_ats_vi_html_path.resolve().as_posix()}", wait_until="networkidle")
        p_ats_vi.pdf(
            path=str(cv_ats_vi_pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
            prefer_css_page_size=True
        )
        p_ats_vi.close()
        
        browser.close()
        
    # 6. Render Previews directly from PDF using PyMuPDF (fitz) at 150 DPI
    prev_en_imgs = render_pdf_to_images(cv_en_pdf_path, version_dir / "cv_en_preview")
    prev_vi_imgs = render_pdf_to_images(cv_vi_pdf_path, version_dir / "cv_vi_preview")
    
    # 7. PDF Text & Layout Verification using pypdf
    verify_en = verify_pdf_with_pypdf(cv_en_pdf_path)
    verify_vi = verify_pdf_with_pypdf(cv_vi_pdf_path)
    
    # 8. Create Application Bundle (email drafts, preview, application.json, draft .eml)
    from src.application_sender import create_application_bundle
    app_res = create_application_bundle(
        package_dir=version_dir,
        candidate=candidate,
        company=company,
        role=role,
        job_id=job_id,
        jd_data=jd_data,
        eval_result=eval_result,
        language="en"
    )

    # 9. Save manifest.json
    manifest = {
        "company": company,
        "role": role,
        "job_id": job_id,
        "version": f"v{version_idx}",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "template": template,
        "candidate": candidate.get("name", "Ngô Văn Hiền"),
        "artifacts": [
            "source_jd.txt",
            "internal_evaluation.json",
            "cv_en.html",
            "cv_en.pdf",
            "cv_vi.html",
            "cv_vi.pdf",
            "cv_ats_en.html",
            "cv_ats_en.pdf",
            "cv_ats_vi.html",
            "cv_ats_vi.pdf",
            "cover_letter_en.md",
            "cover_letter_vi.md",
            "cv_en_preview.png",
            "cv_vi_preview.png",
            "email_subject.txt",
            "email_body.txt",
            "email_preview.html",
            "application.json",
            "draft_application.eml"
        ],
        "pdf_verification": {
            "english": {
                "pages": verify_en["num_pages"],
                "single_page_verified": verify_en["is_single_page"],
                "text_extracted_chars": verify_en["text_length"],
                "has_contact_info": verify_en["has_email"] and verify_en["has_phone"]
            },
            "vietnamese": {
                "pages": verify_vi["num_pages"],
                "single_page_verified": verify_vi["is_single_page"],
                "text_extracted_chars": verify_vi["text_length"],
                "has_contact_info": verify_vi["has_email"] and verify_vi["has_phone"]
            }
        }
    }
    manifest_path = version_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {
        "version_dir": version_dir,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "cv_en_pdf": cv_en_pdf_path,
        "cv_vi_pdf": cv_vi_pdf_path,
        "preview_en": prev_en_imgs[0] if prev_en_imgs else None,
        "preview_vi": prev_vi_imgs[0] if prev_vi_imgs else None,
        "internal_eval_path": internal_eval_path,
        "verification_en": verify_en,
        "verification_vi": verify_vi,
        "application_meta": app_res["app_meta"],
        "eml_path": app_res["eml_path"],
        "email_preview_path": app_res["preview_html_path"]
    }


def generate_modern_tech_bundle(candidate_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Build standalone Modern Tech bundle in output/ directory for direct review.
    """
    if candidate_path is None:
        candidate_path = PROJECT_ROOT / "data" / "candidates" / "my_profile.json"
    
    cand_data = json.loads(candidate_path.read_text(encoding="utf-8"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    html_en_path = OUTPUT_DIR / "NgoVanHien_ModernTech_EN.html"
    pdf_en_path = OUTPUT_DIR / "NgoVanHien_ModernTech_EN.pdf"
    prev_en_path = OUTPUT_DIR / "NgoVanHien_ModernTech_EN_preview"
    
    html_vi_path = OUTPUT_DIR / "NgoVanHien_ModernTech_VI.html"
    pdf_vi_path = OUTPUT_DIR / "NgoVanHien_ModernTech_VI.pdf"
    prev_vi_path = OUTPUT_DIR / "NgoVanHien_ModernTech_VI_preview"
    
    html_en = generate_modern_tech_html(cand_data, language="en")
    html_vi = generate_modern_tech_html(cand_data, language="vi")
    
    html_en_path.write_text(html_en, encoding="utf-8")
    html_vi_path.write_text(html_vi, encoding="utf-8")
    
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        
        # English
        page_en = browser.new_page(viewport={"width": 794, "height": 1123})
        page_en.goto(f"file:///{html_en_path.resolve().as_posix()}", wait_until="networkidle")
        page_en.pdf(
            path=str(pdf_en_path),
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
            prefer_css_page_size=True
        )
        page_en.close()
        
        # Vietnamese
        page_vi = browser.new_page(viewport={"width": 794, "height": 1123})
        page_vi.goto(f"file:///{html_vi_path.resolve().as_posix()}", wait_until="networkidle")
        page_vi.pdf(
            path=str(pdf_vi_path),
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
            prefer_css_page_size=True
        )
        page_vi.close()
        browser.close()
        
    # Render previews directly from PDF with fitz
    render_pdf_to_images(pdf_en_path, prev_en_path)
    render_pdf_to_images(pdf_vi_path, prev_vi_path)
    
    return {
        "html_en": html_en_path,
        "pdf_en": pdf_en_path,
        "preview_en": OUTPUT_DIR / "NgoVanHien_ModernTech_EN_preview.png",
        "html_vi": html_vi_path,
        "pdf_vi": pdf_vi_path,
        "preview_vi": OUTPUT_DIR / "NgoVanHien_ModernTech_VI_preview.png"
    }


if __name__ == "__main__":
    res = generate_modern_tech_bundle()
    for k, v in res.items():
        print(f"{k}: {v}")
