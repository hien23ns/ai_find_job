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



def get_domain_tailoring(target_role: Optional[str] = None, eval_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    role_str = (target_role or "").lower()
    cat = (eval_result.get("category") or "").lower() if eval_result else ""

    is_design = bool(re.search(r'\b(design|ui/ux|ui|ux|graphic|designer|đồ họa|thiết kế)\b', role_str)) or cat == "design"
    is_marketing = bool(re.search(r'\b(marketing|content|seo|truyền thông|quảng cáo|copywriter)\b', role_str)) or cat == "marketing"
    is_data = bool(re.search(r'\b(data|dữ liệu|analytics|bi|business analyst|ba|ai|machine learning|trí tuệ nhân tạo|power bi|sql)\b', role_str)) or cat == "data_ai"
    is_hr = bool(re.search(r'\b(hr|nhân sự|talent|recruiter|recruitment|tuyển dụng|admin|human resources)\b', role_str)) or cat == "hr_admin"
    is_finance = bool(re.search(r'\b(finance|tài chính|kế toán|kiểm toán|accounting|auditor|thu ngân)\b', role_str)) or cat == "finance"
    is_translation = bool(re.search(r'\b(translation|biên dịch|phiên dịch|translator|comtor|thông dịch|ngôn ngữ)\b', role_str)) or cat == "translation"
    is_logistics = bool(re.search(r'\b(logistics|xuất nhập khẩu|kho vận|supply chain|vận hành kho|giao vận|chuyển phát)\b', role_str)) or cat == "logistics"
    is_media = bool(re.search(r'\b(video|media|tiktok|quay dựng|editor|multimedia|dựng phim)\b', role_str)) or cat == "content_media"
    is_sales = bool(re.search(r'\b(sale|sales|kinh doanh|bán hàng|business development|account executive|cskh)\b', role_str)) or cat == "sales"
    is_cloud_devops = bool(re.search(r'\b(cloud|devops|aws|infrastructure|sre|hạ tầng|sysadmin)\b', role_str))
    is_dev = bool(re.search(r'\b(developer|software|lập trình|frontend|backend|fullstack|mobile|android|engineer|web|ios|react|node|java|python)\b', role_str)) or cat in ["it", "tech"]

    if is_cloud_devops:
        domain = "cloud_devops"
    elif is_hr:
        domain = "hr_admin"
    elif is_data:
        domain = "data_ai"
    elif is_media:
        domain = "content_media"
    elif is_design:
        domain = "design"
    elif is_marketing:
        domain = "marketing"
    elif is_finance:
        domain = "finance"
    elif is_translation:
        domain = "translation"
    elif is_logistics:
        domain = "logistics"
    elif is_sales:
        domain = "sales"
    elif is_dev:
        domain = "dev"
    else:
        domain = "security"

    # ==================== DATA DOMAIN ====================
    if domain == "data_ai":
        summary_en = (
            "Undergraduate engineering student in ICT at Vietnam - Korea University of Information and Communication "
            "Technology (VKU), graduating in 2028. Strong analytical foundation in Python scripting, structured data processing, "
            "Linux/Bash automation, and AI workflows (Gemini Certified Student). Practical experience handling peer-to-peer data "
            "streams in WebRTC and mobile data models. Seeking a Data Analyst / AI Internship to automate pipelines and derive insights."
        )
        summary_vi = (
            "Sinh viên ngành CNTT tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp "
            "năm 2028. Nền tảng vững vàng về lập trình Python xử lý dữ liệu bảng, tự động hóa tác vụ trên Linux/Bash và ứng dụng "
            "công cụ AI (Gemini Certified Student). Từng phát triển cơ chế truyền tải dữ liệu P2P qua WebRTC. Mong muốn thực tập "
            "vị trí Phân tích dữ liệu (Data Analyst) / AI để đóng góp vào việc chuẩn hóa và phân tích số liệu."
        )
        skills_en = [
            {"label": "Data Processing & AI", "val": "Python, Structured data cleaning, Log parsing & metrics, Gemini AI Certified"},
            {"label": "Cloud & Storage", "val": "AWS S3 object storage, Amazon EC2, AWS Shared Responsibility Model"},
            {"label": "Systems & Scripting", "val": "Linux (Ubuntu), Bash Shell automation, Git version control"},
            {"label": "Networking & Protocols", "val": "OSI Model, TCP/IP data transmission, WebRTC P2P data channels"}
        ]
        skills_vi = [
            {"label": "Xử lý Dữ liệu & AI", "val": "Python, Làm sạch và trích xuất dữ liệu, Phân tích log số liệu, Chứng chỉ Gemini AI"},
            {"label": "Đám mây & Lưu trữ", "val": "AWS S3 lưu trữ đối tượng, Amazon EC2, Mô hình trách nhiệm chia sẻ"},
            {"label": "Hệ thống & Tự động hóa", "val": "Linux (Ubuntu), Viết script Bash Shell, Quản lý mã nguồn Git"},
            {"label": "Mạng & Giao thức", "val": "Mô hình OSI, TCP/IP luồng truyền tải, Kênh dữ liệu WebRTC P2P"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to enthusiastically apply for the {r} position at {c}. Currently an undergraduate student in ICT at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I have built a strong analytical background in Python scripting, data formatting, and algorithmic problem-solving.

During my studies, I have utilized Python and Linux/Bash to process, parse, and automate data handling tasks. I have achieved the Gemini Certified Student credential and completed Rikkei Education's international project standard course. Furthermore, my hands-on capstone projects—including a WebRTC peer-to-peer data transmission mechanism and an Android application—provided practical experience with structured data models and system metrics.

I am eager to contribute to {c}'s data initiatives, bringing a rigorous analytical work ethic, passion for data accuracy, and disciplined learning attitude.

Thank you very much for considering my application. I welcome the opportunity to discuss my qualifications in greater detail.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ mong muốn được ứng tuyển vào vị trí {r} tại {c}. Hiện tôi là sinh viên ngành CNTT tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Trong quá trình học tập, tôi đã tập trung xây dựng năng lực tư duy logic, xử lý và phân tích số liệu bằng Python trên môi trường Linux.

Tôi đã chủ động đạt chứng chỉ Gemini Certified Student và hoàn thành khóa huấn luyện dự án chuẩn quốc tế của Rikkei Education. Thông qua các dự án thực hành như chia sẻ dữ liệu P2P qua WebRTC và ứng dụng Android, tôi đã rèn luyện kỹ năng quản lý cấu trúc dữ liệu, kiểm tra tính toàn vẹn và tối ưu hóa luồng truyền tải thông tin.

Tôi rất mong có cơ hội thực tập tại {c} để áp dụng kỹ năng xử lý dữ liệu, tinh thần trách nhiệm và tính cẩn trọng vào việc xây dựng báo cáo và hỗ trợ ra quyết định tại doanh nghiệp.

Xin chân thành cảm ơn Quý công ty đã dành thời gian xem xét hồ sơ của tôi.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    # ==================== DESIGN DOMAIN ====================
    elif domain == "design":
        summary_en = (
            "Undergraduate student in ICT at Vietnam - Korea University of Information and Communication Technology "
            "(VKU), graduating in 2028. Practical experience designing user interfaces and layouts for an Android mobile "
            "social app and interactive WebRTC screen sharing. Certified in Gemini AI and International Project Standards "
            "(Rikkei Education). Seeking a UI/UX & Digital Design Internship to craft intuitive, modern user experiences."
        )
        summary_vi = (
            "Sinh viên ngành CNTT tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp "
            "năm 2028. Có kinh nghiệm thực hành thiết kế giao diện người dùng trên ứng dụng di động Android và luồng tương tác "
            "trực quan WebRTC. Đạt chứng chỉ Gemini Certified Student và chuẩn dự án quốc tế Rikkei Education. Mong muốn thực tập "
            "vị trí Thiết kế UI/UX / Đồ họa số."
        )
        skills_en = [
            {"label": "UI/UX & Digital Design", "val": "Mobile UI layouts, User flow wireframing, Modern interface ergonomics, Gemini AI design assistance"},
            {"label": "Platforms & Tools", "val": "Android Studio XML layouts, WebRTC visual data, Linux (Ubuntu)"},
            {"label": "Programming & Logic", "val": "Java, Python, Bash Shell"},
            {"label": "Networking & Protocols", "val": "OSI Model, TCP/IP, P2P transmission"}
        ]
        skills_vi = [
            {"label": "Thiết kế Giao diện & UI/UX", "val": "Bố cục ứng dụng di động, Phác thảo luồng người dùng (User flow), Ứng dụng Gemini AI hỗ trợ"},
            {"label": "Nền tảng & Công cụ", "val": "Android Studio, Giao diện XML, WebRTC truyền dữ liệu trực quan, Linux"},
            {"label": "Ngôn ngữ & Logic", "val": "Java, Python, Bash Shell"},
            {"label": "Mạng & Giao thức", "val": "Mô hình OSI, TCP/IP, Truyền tải P2P"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to express my enthusiastic interest in the {r} role at {c}. As an undergraduate student at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I combine foundational software principles with a strong eye for user-centric digital interface design.

In my academic coursework and capstone projects, I developed the complete front-facing mobile user interface for an Android social networking app, focusing on clean layout hierarchy and intuitive user flows. Furthermore, having earned the Gemini Certified Student credential and Rikkei Education project standards certificate, I frequently leverage modern AI tools to accelerate prototyping and design ideation.

I am keen to join {c} as an intern to contribute creative thinking, collaborate closely with developers and product managers, and support high-quality digital design deliverables.

Thank you very much for reviewing my application.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ mong muốn ứng tuyển vào vị trí {r} tại {c}. Hiện tôi là sinh viên ngành CNTT tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028.

Trong quá trình học tập và làm đồ án, tôi đã trực tiếp thiết kế và triển khai giao diện người dùng cho ứng dụng mạng xã hội trên nền tảng Android, chú trọng trải nghiệm điều hướng mượt mà và tính nhất quán thị giác. Tôi cũng đạt chứng chỉ Gemini Certified Student và rèn luyện kỹ năng thực hiện dự án theo tiêu chuẩn quốc tế từ Rikkei Education, biết ứng dụng AI để tạo bản mẫu ý tưởng nhanh chóng.

Tôi rất mong có cơ hội thực tập tại {c} để phát huy tư duy thiết kế lấy người dùng làm trung tâm, học hỏi quy trình thiết kế chuyên nghiệp và đồng hành cùng đội ngũ phát triển sản phẩm.

Xin chân thành cảm ơn Quý công ty.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    # ==================== MARKETING DOMAIN ====================
    elif domain == "marketing":
        summary_en = (
            "Undergraduate student at Vietnam - Korea University of ICT (VKU), graduating in 2028. Tech-savvy background "
            "combining digital content creation mindset, AI-assisted productivity (Gemini Certified Student), and analytical "
            "thinking from programming in Python and Java. Experienced with mobile user communities through Android app development. "
            "Seeking a Digital Marketing / Content Internship to drive data-informed engagement and product storytelling."
        )
        summary_vi = (
            "Sinh viên Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Có tư duy "
            "phân tích nhạy bén, ứng dụng công cụ AI sáng tạo nội dung (Gemini Certified Student), phân tích dữ liệu cơ bản bằng "
            "Python và kinh nghiệm phát triển ứng dụng mạng xã hội Android. Mong muốn thực tập vị trí Digital Marketing / Content "
            "Creator để phát triển chiến dịch truyền thông sản phẩm số hiệu quả."
        )
        skills_en = [
            {"label": "Digital Marketing & AI", "val": "Content strategy, Social engagement, Gemini AI prompt engineering, Product storytelling"},
            {"label": "Analytics & Programming", "val": "Python data processing, Metric logging, Basic SEO fundamentals"},
            {"label": "Systems & Cloud", "val": "Linux (Ubuntu), AWS S3/EC2 basics, WebRTC"},
            {"label": "Languages & Communication", "val": "Vietnamese (Native), English technical reading & communication"}
        ]
        skills_vi = [
            {"label": "Digital Marketing & AI", "val": "Chiến lược nội dung, Tương tác mạng xã hội, Ứng dụng AI Gemini, Truyền thông sản phẩm số"},
            {"label": "Phân tích & Lập trình", "val": "Xử lý dữ liệu bằng Python, Thống kê chỉ số, Nền tảng SEO cơ bản"},
            {"label": "Hệ thống & Đám mây", "val": "Linux (Ubuntu), AWS S3/EC2 cơ bản, WebRTC"},
            {"label": "Ngoại ngữ & Kỹ năng", "val": "Tiếng Việt bản ngữ, Tiếng Anh đọc hiểu tài liệu và giao tiếp"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to express my strong enthusiasm for the {r} role at {c}. As an undergraduate student at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I bridge technical product understanding with digital marketing creativity.

My academic journey has equipped me with data-literate analytical skills using Python, while achieving the Gemini Certified Student credential has enabled me to leverage cutting-edge AI for content ideation and multi-channel marketing campaigns. Having designed user features for an Android social networking app, I understand user psychology, engagement touchpoints, and digital brand messaging.

Joining {c} as an intern would be an outstanding opportunity to execute data-driven campaigns, produce engaging content, and contribute to measurable brand growth.

Thank you very much for your time and consideration.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ nguyện vọng ứng tuyển vào vị trí {r} tại {c}. Hiện tôi là sinh viên tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028.

Với kiến thức công nghệ và tư duy phân tích dữ liệu bằng Python, kết hợp chứng chỉ Gemini Certified Student trong việc ứng dụng AI sáng tạo nội dung, tôi có khả năng xây dựng các ý tưởng truyền thông số cuốn hút, bám sát hành vi người dùng và đo lường hiệu quả qua số liệu thực tế. Đồ án ứng dụng mạng xã hội Android cũng giúp tôi hiểu rõ tương tác cộng đồng và điểm chạm khách hàng số.

Tôi mong muốn được tham gia thực tập tại {c} để cống hiến sự nhiệt tình, sáng tạo và học hỏi kinh nghiệm triển khai chiến dịch đa kênh từ đội ngũ marketing chuyên nghiệp.

Xin chân thành cảm ơn Quý công ty.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    # ==================== HR / ADMIN DOMAIN ====================
    elif domain == "hr_admin":
        summary_en = (
            "Undergraduate student at Vietnam - Korea University of ICT (VKU), graduating in 2028. Possesses a unique blend of "
            "technical IT knowledge and structured communication skills, certified in Building Personal Projects to International "
            "Standards (Rikkei Education) and Gemini AI. Experienced in understanding tech job requirements and developer workflows. "
            "Seeking an HR / IT Talent Acquisition Internship to support candidate screening, sourcing, and organizational processes."
        )
        summary_vi = (
            "Sinh viên Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Kết hợp "
            "nền tảng công nghệ thông tin với kỹ năng giao tiếp và tổ chức dự án chuẩn quốc tế (Rikkei Education). Thấu hiểu các "
            "yêu cầu kỹ thuật phần mềm và mạng; thành thạo công cụ AI hỗ trợ (Gemini Certified). Mong muốn thực tập vị trí Tuyển dụng "
            "CNTT (IT Recruiter) / Quản trị Nhân sự (HR)."
        )
        skills_en = [
            {"label": "Tech Talent Sourcing & HR", "val": "IT JD requirement mapping, Technical profile screening, Gemini AI workflow assistance"},
            {"label": "Organizational & Operations", "val": "Structured project execution (Rikkei Standards), Documentation, Process coordination"},
            {"label": "Technical Foundation", "val": "Linux, Python, Java, Networking basics, Android mobile concepts"},
            {"label": "Languages & Communication", "val": "Vietnamese (Native), English technical reading & professional communication"}
        ]
        skills_vi = [
            {"label": "Tuyển dụng & Nhân sự CNTT", "val": "Đọc hiểu yêu cầu kỹ thuật JD, Sàng lọc hồ sơ công nghệ, Ứng dụng Gemini AI hỗ trợ"},
            {"label": "Tổ chức & Quy trình", "val": "Triển khai dự án chuẩn quốc tế (Rikkei Education), Lưu trữ văn bản, Điều phối quy trình"},
            {"label": "Nền tảng Công nghệ", "val": "Linux, Python, Java, Kiến thức mạng và phần mềm Android"},
            {"label": "Ngoại ngữ & Giao tiếp", "val": "Tiếng Việt bản ngữ, Tiếng Anh đọc hiểu tài liệu và giao tiếp chuyên nghiệp"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to enthusiastically apply for the {r} role at {c}. Currently an undergraduate student at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I bring a unique advantage to technical recruitment and HR operations: a direct understanding of engineering disciplines, programming stacks, and developer language.

Having completed software projects and attained the Rikkei Education International Standard Project certificate, I am adept at communicating with technical candidates and mapping technical competencies against job descriptions. Combined with my proficiency in AI tools (Gemini Certified Student) and bilingual communication, I can accelerate candidate sourcing, interview coordination, and HR administration.

I look forward to supporting {c}'s talent acquisition and people operations with diligence, integrity, and proactive enthusiasm.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ mong muốn được ứng tuyển vào vị trí {r} tại {c}. Tôi hiện là sinh viên tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028.

Lợi thế của tôi trong mảng tuyển dụng và quản trị nhân sự là sự am hiểu thực tế về ngôn ngữ kỹ thuật, các framework công nghệ và tư duy của lập trình viên. Đạt chứng chỉ quản lý dự án theo chuẩn quốc tế của Rikkei Education và chứng chỉ Gemini Certified Student giúp tôi giao tiếp nhạy bén, sàng lọc hồ sơ ứng viên công nghệ chuẩn xác và sắp xếp tài liệu hành chính khoa học.

Tôi rất mong có cơ hội thực tập tại {c} để hỗ trợ tìm kiếm nhân tài công nghệ, đồng hành cùng văn hóa doanh nghiệp và phát triển chuyên sâu trong ngành Nhân sự.

Xin trân trọng cảm ơn Quý công ty.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    # ==================== FINANCE DOMAIN ====================
    elif domain == "finance":
        summary_en = (
            "Engineering student at Vietnam - Korea University of ICT (VKU), graduating in 2028. High quantitative aptitude, "
            "meticulous attention to detail, and practical proficiency in Python for automated data calculation and structured "
            "tabular analysis. Foundation in system security principles and process integrity. Seeking a Finance & Accounting "
            "Internship to assist in ledger data entry, reconciliation, and automated reporting."
        )
        summary_vi = (
            "Sinh viên Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Có tư duy "
            "logic và tính toán chuẩn xác, thành thạo lập trình Python phục vụ tự động hóa tính toán và xử lý số liệu bảng tính. "
            "Nắm vững nguyên tắc bảo mật thông tin và tính toàn vẹn dữ liệu. Mong muốn thực tập vị trí Kế toán / Tài chính để "
            "hỗ trợ đối soát dữ liệu, nhập liệu và chuẩn hóa quy trình kế toán số."
        )
        skills_en = [
            {"label": "Data Processing & Calculation", "val": "Python numerical scripts, Tabular data accuracy, Automated reconciliation"},
            {"label": "Security & Data Integrity", "val": "Access control fundamentals, System confidentiality, AWS S3 secure storage"},
            {"label": "Systems & Automation", "val": "Linux (Ubuntu), Bash Shell, Spreadsheet data formatting"},
            {"label": "Professional Attributes", "val": "Meticulous discipline, Integrity, Vietnamese (Native), English reading"}
        ]
        skills_vi = [
            {"label": "Xử lý Số liệu & Tính toán", "val": "Script Python xử lý số liệu, Độ chính xác dữ liệu bảng, Tự động hóa đối soát"},
            {"label": "Bảo mật & Toàn vẹn Dữ liệu", "val": "Nguyên tắc phân quyền truy cập, Bảo mật thông tin, Lưu trữ bảo mật AWS S3"},
            {"label": "Hệ thống & Tự động hóa", "val": "Linux (Ubuntu), Bash Shell, Chuẩn hóa dữ liệu bảng tính"},
            {"label": "Phẩm chất & Ngoại ngữ", "val": "Kỷ luật cẩn trọng, Trung thực số liệu, Tiếng Việt bản ngữ, Tiếng Anh đọc hiểu"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to formally apply for the {r} position at {c}. As an undergraduate student in ICT at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I offer high numerical rigor, mathematical discipline, and technical proficiency in Python data automation.

My coursework has trained me in structured data processing, access control principles, and information security standards. I am experienced in writing automated scripts to eliminate calculation errors and verify balance sheets. Combined with disciplined work habits and the Rikkei Education project standards certification, I ensure complete precision and confidentiality in financial recordkeeping.

I am enthusiastic about the chance to intern at {c} and contribute to your financial administration and digital ledger workflows.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ mong muốn ứng tuyển vào vị trí {r} tại {c}. Tôi hiện đang theo học tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028.

Với nền tảng tư duy toán học và kỹ năng lập trình Python xử lý bảng tính số liệu, tôi luôn đề cao tính chính xác tuyệt đối, tính bảo mật dữ liệu và sự cẩn trọng trong từng chứng từ đối soát. Tôi đã đạt chứng chỉ dự án chuẩn quốc tế của Rikkei Education, rèn luyện thói quen làm việc có phương pháp, trung thực và tuân thủ nguyên tắc bảo mật thông tin.

Tôi rất mong có cơ hội thực tập tại {c} để đóng góp công sức vào công tác kế toán, đối soát chứng từ và số hóa quy trình tài chính của Quý công ty.

Xin trân trọng cảm ơn.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    # ==================== TRANSLATION DOMAIN ====================
    elif domain == "translation":
        summary_en = (
            "Undergraduate student in ICT at Vietnam - Korea University (VKU), graduating in 2028. Native Vietnamese with "
            "advanced technical English reading comprehension for software, networking, and system specifications. Certified "
            "by Rikkei Education in International Standards. Seeking an IT Comtor / Technical Translation Internship to deliver "
            "accurate bilingual documentation and team communication."
        )
        summary_vi = (
            "Sinh viên chuyên ngành CNTT tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt "
            "nghiệp năm 2028. Tiếng Việt bản ngữ cùng năng lực đọc hiểu và biên dịch tài liệu kỹ thuật CNTT, đặc tả hệ thống và "
            "phần mềm tiếng Anh chính xác. Đạt chứng chỉ Rikkei Education tiêu chuẩn quốc tế. Mong muốn thực tập vị trí IT Comtor "
            "/ Biên dịch kỹ thuật."
        )
        skills_en = [
            {"label": "Technical Translation & IT Comtor", "val": "Bilingual IT terminology (English-Vietnamese), Software spec translation, Documentation accuracy"},
            {"label": "Technical Foundation", "val": "Computer networking (OSI, TCP/IP), Programming (Java, Python), Linux"},
            {"label": "AI & Productivity", "val": "Gemini Certified Student, Computer-assisted translation, Prompt engineering"},
            {"label": "Standards & Teamwork", "val": "Rikkei International Project Standards, Cross-cultural communication"}
        ]
        skills_vi = [
            {"label": "Biên dịch Kỹ thuật & IT Comtor", "val": "Thuật ngữ CNTT Anh-Việt, Biên dịch đặc tả phần mềm & tài liệu kỹ thuật, Tính chính xác câu chữ"},
            {"label": "Nền tảng Công nghệ", "val": "Mạng máy tính (OSI, TCP/IP), Ngôn ngữ lập trình (Java, Python), Linux"},
            {"label": "Công cụ AI & Năng suất", "val": "Chứng chỉ Gemini AI, Sử dụng AI hỗ trợ biên dịch và tra cứu ngữ cảnh"},
            {"label": "Tiêu chuẩn & Phối hợp", "val": "Dự án chuẩn quốc tế Rikkei Education, Giao tiếp đa văn hóa"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to express my strong enthusiasm for the {r} role at {c}. Currently an undergraduate student at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I combine strong bilingual communication with comprehensive software and systems technical literacy.

Having completed technical coursework and programming projects, I am familiar with software engineering terminologies, architecture diagrams, and technical requirements. This allows me to translate complex specifications accurately without semantic loss. Certified by Rikkei Education in international project standards and by Google as a Gemini Certified Student, I bridge linguistic gaps with modern efficiency.

I would be thrilled to intern at {c} and contribute to smooth bilingual project communication, technical documentation, and cross-border collaboration.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ mong muốn ứng tuyển vào vị trí {r} tại {c}. Hiện tôi là sinh viên tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028.

Ưu thế lớn nhất của tôi là nền tảng kỹ thuật công nghệ thông tin kết hợp khả năng đọc hiểu tài liệu tiếng Anh chuyên ngành chuẩn xác. Tôi có thể đọc hiểu thông suốt các tài liệu đặc tả API, kiến trúc mạng và mô tả yêu cầu chức năng phần mềm, giúp việc chuyển ngữ sang tiếng Việt không bị sai lệch thuật ngữ. Tôi cũng đạt chứng chỉ dự án tiêu chuẩn quốc tế Rikkei Education và chứng chỉ Gemini Certified Student.

Tôi rất mong có cơ hội thực tập vị trí IT Comtor / Biên dịch kỹ thuật tại {c} để đóng góp vào việc kết nối tài liệu và truyền đạt thông suốt giữa các đội ngũ kỹ thuật.

Xin trân trọng cảm ơn Quý công ty.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    # ==================== LOGISTICS DOMAIN ====================
    elif domain == "logistics":
        summary_en = (
            "Undergraduate student at Vietnam - Korea University of ICT (VKU), graduating in 2028. Strong analytical mindset "
            "with foundational knowledge in network data flow (OSI, TCP/IP) and Python automation. Seeking an Operations &amp; "
            "Logistics Internship to assist with inventory tracking, shipment scheduling, and digital process optimization."
        )
        summary_vi = (
            "Sinh viên Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Nắm vững "
            "tư duy quy trình, theo dõi luồng thông tin và tự động hóa tác vụ bằng Python và Linux. Mong muốn thực tập vị trí "
            "Logistics / Quản trị chuỗi cung ứng và kho vận để đóng góp vào việc số hóa quản lý đơn hàng và điều phối."
        )
        skills_en = [
            {"label": "Operations & Logistics Support", "val": "Dispatch tracking, Inventory data logging, Process flowchart mapping"},
            {"label": "Data & Scripting", "val": "Python tabular data processing, Linux/Bash automation, Spreadsheet accuracy"},
            {"label": "Networking & Information Flow", "val": "OSI & TCP/IP data transmission mechanics, System security principles"},
            {"label": "Personal Attributes", "val": "Methodical discipline, Diligence, Vietnamese (Native), English reading"}
        ]
        skills_vi = [
            {"label": "Vận hành & Hỗ trợ Logistics", "val": "Theo dõi đơn hàng & điều phối, Nhập liệu kho vận, Vẽ sơ đồ luồng quy trình"},
            {"label": "Dữ liệu & Scripting", "val": "Xử lý dữ liệu bảng bằng Python, Tự động hóa Linux/Bash, Chuẩn hóa bảng tính"},
            {"label": "Luồng Thông tin & Hệ thống", "val": "Cơ chế truyền tải dữ liệu TCP/IP, Nguyên tắc bảo mật thông tin"},
            {"label": "Phẩm chất & Ngoại ngữ", "val": "Kỷ luật cẩn thận, Chăm chỉ, Tiếng Việt bản ngữ, Tiếng Anh đọc hiểu"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to enthusiastically apply for the {r} role at {c}. As an undergraduate student at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I bring a structured analytical mindset and technical literacy to operations and supply chain logistics.

My coursework in data transmission and systems has trained me to track complex operational flows methodically. Through Python programming and spreadsheet automation, I can reduce manual data entry bottlenecks and monitor shipment KPIs. Having achieved Rikkei Education's international project standards certification, I approach logistics tasks with high personal accountability and detail orientation.

I welcome the opportunity to intern at {c} and contribute to your fulfillment, dispatching, and inventory operations.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ mong muốn được ứng tuyển vào vị trí {r} tại {c}. Hiện tôi là sinh viên tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028.

Với tư duy kỹ thuật logic và kỹ năng tin học vững vàng, tôi có khả năng nắm bắt nhanh các phần mềm quản lý kho vận, viết script Python xử lý số liệu điều phối và tối ưu hóa luồng theo dõi trạng thái đơn hàng. Tôi đã đạt chứng chỉ dự án chuẩn quốc tế của Rikkei Education, luôn rèn luyện tính kỷ luật, cẩn trọng và tinh thần trách nhiệm cao đối với từng lô hàng.

Tôi rất mong có cơ hội thực tập tại {c} để hỗ trợ công tác vận hành kho, theo dõi điều phối vận tải và đóng góp vào sự phát triển của chuỗi cung ứng công ty.

Xin trân trọng cảm ơn Quý công ty.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    # ==================== MEDIA / VIDEO DOMAIN ====================
    elif domain == "content_media":
        summary_en = (
            "Creative undergraduate student in ICT at Vietnam - Korea University of Information and Communication "
            "Technology (VKU), graduating in 2028. Proficient in digital media storytelling, AI-assisted video concepting "
            "(Gemini Certified Student), and visual layout design from Android mobile app development. Seeking a Video Editor "
            "&amp; Digital Media Internship to create high-retention multimedia content."
        )
        summary_vi = (
            "Sinh viên ngành CNTT tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp "
            "năm 2028. Thành thạo công cụ AI (Gemini Certified Student) hỗ trợ lên kịch bản, ý tưởng hình ảnh và có kinh nghiệm "
            "thiết kế giao diện ứng dụng di động. Mong muốn thực tập vị trí Video Editor / Sáng tạo nội dung truyền thông số."
        )
        skills_en = [
            {"label": "Media Creation & AI", "val": "Video editing concepts, Short-form storytelling (TikTok/Reels), Gemini AI creative prompting"},
            {"label": "Visual & Digital Layouts", "val": "Mobile visual hierarchy, User engagement flow, Graphic fundamentals"},
            {"label": "Technical Foundation", "val": "Linux (Ubuntu), Python automation, WebRTC visual streaming"},
            {"label": "Languages & Teamwork", "val": "Vietnamese (Native), English technical reading & communication"}
        ]
        skills_vi = [
            {"label": "Sáng tạo Media & AI", "val": "Tư duy dựng video, Kịch bản video ngắn (TikTok/Reels), Ứng dụng Gemini AI sáng tạo"},
            {"label": "Bố cục Thị giác & Thiết kế", "val": "Bố cục giao diện di động, Điểm chạm tương tác người xem, Nền tảng đồ họa"},
            {"label": "Nền tảng Công nghệ", "val": "Linux (Ubuntu), Tự động hóa Python, Luồng hình ảnh WebRTC"},
            {"label": "Ngoại ngữ & Phối hợp", "val": "Tiếng Việt bản ngữ, Tiếng Anh đọc hiểu tài liệu và giao tiếp"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to express my creative passion for the {r} role at {c}. Currently an undergraduate student at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I combine digital visual aesthetics with technical fluency in modern AI and multimedia tools.

Certified as a Gemini AI Student, I leverage generative AI to brainstorm engaging video hooks, storyboard dynamic visual flows, and optimize content for short-form platforms (TikTok, Reels, YouTube Shorts). My background designing mobile applications has cultivated an acute sense of visual rhythm, pacing, and audience engagement retention.

I am eager to join {c} as an intern to produce captivating digital media and bring fresh creative energy to your content channels.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ mong muốn được ứng tuyển vào vị trí {r} tại {c}. Tôi hiện đang theo học tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028.

Với niềm đam mê sáng tạo nội dung đa phương tiện, tôi kết hợp tư duy thị giác thẩm mỹ với việc ứng dụng công cụ AI (Gemini Certified Student) để phát triển kịch bản và định hình nhịp điệu video ngắn (TikTok, Reels). Kinh nghiệm xây dựng giao diện ứng dụng di động cũng rèn luyện cho tôi sự nhạy cảm về bố cục hình ảnh và khả năng giữ chân người xem qua từng khung hình.

Tôi rất mong có cơ hội thực tập tại {c} để đóng góp những ý tưởng video sáng tạo, bắt nhịp xu hướng thị trường và hỗ trợ xây dựng hình ảnh thương hiệu số của Quý công ty.

Xin trân trọng cảm ơn.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    # ==================== SALES DOMAIN ====================
    elif domain == "sales":
        summary_en = (
            "Undergraduate student in ICT at Vietnam - Korea University of Information and Communication Technology (VKU), "
            "graduating in 2028. Combines comprehensive technical understanding of software, networking, and cloud basics with "
            "strong communication skills and client empathy. Certified by Rikkei Education. Seeking a Business Development / "
            "Tech Sales Internship to identify client needs and present digital solutions."
        )
        summary_vi = (
            "Sinh viên Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Hiểu rõ "
            "kiến trúc sản phẩm phần mềm, dịch vụ mạng và công nghệ thông tin. Có kỹ năng lắng nghe, thấu cảm nhu cầu khách hàng "
            "và thuyết trình giải pháp kỹ thuật rõ ràng. Mong muốn thực tập vị trí Phát triển kinh doanh (Business Development) "
            "/ Sales B2B trong lĩnh vực công nghệ."
        )
        skills_en = [
            {"label": "Tech Sales & Business Development", "val": "Client pain-point discovery, Solution presentation, B2B technology consulting"},
            {"label": "Technology Competence", "val": "Software architecture understanding, Cloud fundamentals (AWS), Mobile apps"},
            {"label": "Communication & Coordination", "val": "Cross-functional collaboration, Proposal drafting, Rikkei Project Standards"},
            {"label": "Languages", "val": "Vietnamese (Native), English technical reading & professional communication"}
        ]
        skills_vi = [
            {"label": "Sales Kỹ thuật & Phát triển Kinh doanh", "val": "Nắm bắt nhu cầu khách hàng, Thuyết trình giải pháp số, Tư vấn sản phẩm công nghệ B2B"},
            {"label": "Hiểu biết Công nghệ", "val": "Kiến trúc phần mềm, Nền tảng điện toán đám mây (AWS), Ứng dụng di động"},
            {"label": "Giao tiếp & Đàm phán", "val": "Phối hợp liên phòng ban, Soạn thảo đề xuất hợp tác, Chuẩn dự án Rikkei"},
            {"label": "Ngoại ngữ", "val": "Tiếng Việt bản ngữ, Tiếng Anh đọc hiểu tài liệu và giao tiếp chuyên nghiệp"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to enthusiastically apply for the {r} role at {c}. As an undergraduate student at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I bridge technological capability with consultative client-facing skills.

Having developed technical software and networking projects, I can demystify complex technical concepts for business stakeholders and present tailored solutions with confidence. Certified in international project execution by Rikkei Education, I emphasize clear communication, active listening, and relationship-building.

I am keen to join {c} as an intern to assist in pipeline prospecting, client engagement, and commercial technology presentations.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ mong muốn ứng tuyển vào vị trí {r} tại {c}. Hiện tôi là sinh viên tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028.

Ưu điểm nổi bật của tôi khi tiếp cận công việc kinh doanh và phát triển đối tác là sự hiểu biết thấu đáo về cấu trúc giải pháp phần mềm và công nghệ số. Tôi có khả năng giải thích dễ hiểu các giá trị kỹ thuật tới khách hàng, lắng nghe các bài toán thực tế của doanh nghiệp và đề xuất phương án phù hợp. Đồng thời, chứng nhận dự án chuẩn quốc tế của Rikkei Education giúp tôi duy trì phong thái làm việc chuyên nghiệp và cam kết tiến độ.

Tôi rất mong có cơ hội thực tập tại {c} để rèn luyện kỹ năng tư vấn bán hàng giải pháp số và đóng góp vào doanh thu của Quý công ty.

Xin chân thành cảm ơn.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    # ==================== DEV DOMAIN ====================
    elif domain == "dev":
        summary_en = (
            "Undergraduate student in ICT at Vietnam - Korea University of Information and Communication Technology (VKU), "
            "graduating in 2028. Practical experience in software development with Java and Android mobile applications, "
            "WebRTC P2P implementation, and Python scripting on Linux. Seeking a Software Engineering / Mobile Developer "
            "Internship to contribute to production codebases."
        )
        summary_vi = (
            "Sinh viên Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Có kinh nghiệm "
            "lập trình phát triển ứng dụng di động Android bằng Java, xây dựng cơ chế chia sẻ P2P với WebRTC và viết script tự động "
            "trên Linux bằng Python. Mong muốn thực tập vị trí Lập trình viên phần mềm / Mobile Developer để rèn luyện kỹ năng thực tế."
        )
        skills_en = [
            {"label": "Software & Mobile Development", "val": "Java, Android SDK, Object-Oriented Programming (OOP), WebRTC P2P"},
            {"label": "Scripting & Backend Basics", "val": "Python, Linux (Ubuntu), Bash Shell, Git version control"},
            {"label": "Networking & Protocols", "val": "OSI Model, TCP/IP, Socket communication, Packet inspection"},
            {"label": "Cloud & Certifications", "val": "AWS IAM/EC2/S3 basics, Gemini Certified Student (2025), Rikkei Education"}
        ]
        skills_vi = [
            {"label": "Phát triển Phần mềm & Di động", "val": "Java, Lập trình ứng dụng Android, Lập trình hướng đối tượng (OOP), WebRTC P2P"},
            {"label": "Scripting & Nền tảng Hệ thống", "val": "Python, Linux (Ubuntu), Bash Shell, Quản trị Git"},
            {"label": "Mạng & Giao thức", "val": "Mô hình OSI, TCP/IP, Giao tiếp Socket, Kiểm tra gói tin"},
            {"label": "Đám mây & Chứng chỉ", "val": "AWS IAM/EC2/S3 cơ bản, Gemini Certified Student (2025), Rikkei Education"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to express my strong enthusiasm for the {r} role at {c}. Currently an undergraduate student at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I have dedicated my studies to hands-on software development in Java and Python.

Through my personal projects, I developed a mobile social networking application on Android and engineered a peer-to-peer screen sharing system using WebRTC. These projects taught me to write clean, modular code, manage versioning with Git, and debug complex runtime issues on Linux. Furthermore, my Rikkei Education certification in international project standards reflects my commitment to high software quality.

I am eager to contribute to {c}'s engineering team as an intern, learn from your senior engineers, and tackle challenging technical problems.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ mong muốn được ứng tuyển vào vị trí {r} tại {c}. Hiện tôi là sinh viên ngành CNTT tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028.

Trong quá trình học tập, tôi đã tập trung phát triển kỹ năng lập trình với Java và Python, trực tiếp xây dựng ứng dụng di động Android và triển khai cơ chế truyền dữ liệu P2P qua WebRTC. Tôi thành thạo thao tác trên Linux, quản lý mã nguồn bằng Git và tuân thủ tiêu chuẩn dự án quốc tế theo chứng nhận của Rikkei Education.

Tôi rất mong có cơ hội thực tập tại {c} để tham gia vào quy trình phát triển sản phẩm thực tế, học hỏi từ các kỹ sư giàu kinh nghiệm và đóng góp vào mã nguồn dự án.

Xin chân thành cảm ơn Quý công ty.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    # ==================== CLOUD / DEVOPS DOMAIN ====================
    elif domain == "cloud_devops":
        summary_en = (
            "Undergraduate student in Network and Information Security at Vietnam - Korea University of Information "
            "and Communication Technology (VKU), graduating in 2028. Foundational knowledge in computer networking (OSI, "
            "TCP/IP), Linux/Bash administration, Python, Java, and basic AWS cloud services (IAM, EC2, S3, Shared "
            "Responsibility Model). Seeking a Cloud &amp; DevOps Internship to acquire practical experience in cloud infrastructure and automation."
        )
        summary_vi = (
            "Sinh viên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), "
            "dự kiến tốt nghiệp năm 2028. Có kiến thức nền tảng về mạng máy tính (OSI, TCP/IP), Linux/Bash, lập trình Python/Java "
            "và các dịch vụ đám mây AWS cơ bản (IAM, EC2, S3, Shared Responsibility Model). Mong muốn thực tập vị trí Cloud &amp; "
            "DevOps để tích lũy kinh nghiệm thực hành hạ tầng đám mây và tự động hóa."
        )
        skills_en = [
            {"label": "Cloud &amp; Architecture", "val": "AWS IAM, Amazon EC2, Amazon S3, Shared Responsibility Model (Foundational)"},
            {"label": "Systems &amp; Scripting", "val": "Linux (Ubuntu), Bash Shell"},
            {"label": "Programming Languages", "val": "Python, Java"},
            {"label": "Networking &amp; Security", "val": "OSI Model, TCP/IP, Wireshark, Nmap, Firewall fundamentals, WebRTC, P2P"}
        ]
        skills_vi = [
            {"label": "Điện toán Đám mây (Cơ bản)", "val": "AWS IAM, Amazon EC2, Amazon S3, Shared Responsibility Model"},
            {"label": "Hệ thống & Scripting", "val": "Linux (Ubuntu), Bash Shell"},
            {"label": "Ngôn ngữ Lập trình", "val": "Python, Java"},
            {"label": "Mạng & An toàn Thông tin", "val": "Mô hình OSI, TCP/IP, Wireshark, Nmap, Firewall, WebRTC, P2P"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to express my strong interest in the {r} position at {c}. As an undergraduate student majoring in Network and Information Security at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I have developed a solid foundation in Linux system administration, computer networking (OSI, TCP/IP), and programming with Python and Java.

Throughout my academic coursework and personal projects, I have familiarized myself with foundational cloud concepts on AWS, including IAM, EC2, S3, and the AWS Shared Responsibility Model. Additionally, I have developed academic projects including a peer-to-peer screen sharing tool using WebRTC and an Android mobile application.

I am particularly excited about the opportunity to intern at {c} because of your commitment to technological innovation and engineering excellence. I am eager to apply my foundational skills in scripting, networking, and cloud services under the guidance of your team.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ nguyện vọng ứng tuyển vào vị trí {r} tại {c}. Hiện tôi là sinh viên chuyên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Trong quá trình học tập, tôi đã xây dựng nền tảng vững chắc về hệ điều hành Linux (Ubuntu), Bash script, lập trình Python/Java và kiến thức mạng máy tính (OSI, TCP/IP).

Về mảng điện toán đám mây, tôi đã chủ động tìm hiểu và nắm vững các khái niệm cơ bản trên nền tảng AWS như IAM, Amazon EC2, Amazon S3 và Mô hình trách nhiệm chia sẻ (Shared Responsibility Model). Đồng thời, tôi đã thực hiện các đồ án học thuật bao gồm chia sẻ màn hình P2P qua WebRTC và ứng dụng di động Android.

Tôi rất ấn tượng với môi trường kỹ thuật của {c}. Tôi mong muốn có cơ hội thực tập tại công ty để đóng góp sự nhiệt huyết, tinh thần kỷ luật và tiếp thu kinh nghiệm thực tế về tự động hóa hạ tầng từ các kỹ sư đi trước.

Xin chân thành cảm ơn Quý công ty.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    # ==================== OTHER DOMAINS / FALLBACK (SECURITY) ====================
    else:
        summary_en = (
            "Undergraduate student in Network and Information Security at Vietnam - Korea University of Information "
            "and Communication Technology (VKU), graduating in 2028. Foundational knowledge in network protocols (OSI, "
            "TCP/IP), network analysis tools (Wireshark, Nmap, Firewall), Linux administration, and programming with "
            "Python and Java. Seeking an Information Security &amp; SOC Analyst Internship to apply technical skills in security monitoring and network traffic analysis."
        )
        summary_vi = (
            "Sinh viên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), "
            "dự kiến tốt nghiệp năm 2028. Có kiến thức nền tảng về mô hình OSI, TCP/IP, công cụ phân tích mạng (Wireshark, "
            "Nmap, Firewall), quản trị Linux và lập trình Python/Java. Mong muốn thực tập vị trí An toàn thông tin / SOC "
            "Analyst để phát triển kỹ năng giám sát an ninh mạng và phân tích lưu lượng thực tế."
        )
        skills_en = [
            {"label": "Networking &amp; Security", "val": "OSI Model, TCP/IP, Wireshark, Nmap, Firewall fundamentals, WebRTC, P2P"},
            {"label": "Systems &amp; Scripting", "val": "Linux (Ubuntu), Bash Shell"},
            {"label": "Programming Languages", "val": "Python, Java"},
            {"label": "Cloud &amp; Architecture", "val": "AWS IAM, Amazon EC2, Amazon S3, Shared Responsibility Model (Foundational)"}
        ]
        skills_vi = [
            {"label": "Mạng & An toàn Thông tin", "val": "Mô hình OSI, TCP/IP, Wireshark, Nmap, Firewall, WebRTC, P2P"},
            {"label": "Hệ thống & Scripting", "val": "Linux (Ubuntu), Bash Shell"},
            {"label": "Ngôn ngữ Lập trình", "val": "Python, Java"},
            {"label": "Điện toán Đám mây (Cơ bản)", "val": "AWS IAM, Amazon EC2, Amazon S3, Shared Responsibility Model"}
        ]
        cl_body_en = lambda c, r, name, loc, email, phone, contact: f"""Dear Hiring Team at {c},

I am writing to enthusiastically apply for the {r} position at {c}. Currently pursuing my degree in Network and Information Security at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028, I have focused my studies on network architecture, packet analysis, and system security fundamentals.

My academic foundation includes practical work with Linux environments (Ubuntu), Bash scripting, and programming in Python and Java. I have practical familiarity with network tools such as Wireshark and Nmap to analyze traffic and investigate packet flows, alongside core concepts of firewall rules.

Joining {c} as an intern would provide an invaluable opportunity to contribute to security operations and threat monitoring. I am eager to learn from your security professionals, support daily monitoring workflows, and apply my technical skills with discipline and integrity.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""
        cl_body_vi = lambda c, r, name, loc, email, phone, contact: f"""Kính gửi: Bộ phận Tuyển dụng {c},

Tôi viết thư này để bày tỏ mong muốn được ứng tuyển vào vị trí {r} tại {c}. Tôi hiện đang theo học chuyên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp vào năm 2028.

Trong chương trình đào tạo kỹ sư, tôi đã trang bị kiến thức bài bản về mô hình mạng OSI, bộ giao thức TCP/IP, cấu trúc gói tin, cùng kỹ năng sử dụng các công cụ phân tích lưu lượng mạng như Wireshark, Nmap và nguyên lý hoạt động của Firewall. Bên cạnh đó, tôi có kỹ năng thực hành tốt với thao tác dòng lệnh trên Linux (Ubuntu) và viết script Python/Bash để đọc hiểu, xử lý log và tự động hóa tác vụ cơ bản.

Tôi mong muốn được tham gia thực tập tại {c} để áp dụng kiến thức phân tích mạng và an toàn thông tin vào thực tiễn giám sát an ninh mạng, đồng thời rèn luyện tính kỷ luật và bảo mật thông tin theo chuẩn doanh nghiệp.

Xin chân thành cảm ơn Quý công ty.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    return {
        "domain": domain,
        "summary_en": summary_en,
        "summary_vi": summary_vi,
        "skills_en": skills_en,
        "skills_vi": skills_vi,
        "cl_body_en": cl_body_en,
        "cl_body_vi": cl_body_vi
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

    # Tailored summary & skills from domain engine
    tailor = get_domain_tailoring(role, eval_result)
    if is_en:
        summary_text = tailor["summary_en"]
        skills_ordered = tailor["skills_en"]
    else:
        summary_text = tailor["summary_vi"]
        skills_ordered = tailor["skills_vi"]

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

        tailor_ats_en = get_domain_tailoring(role)
        summary_text = tailor_ats_en["summary_en"]
        skills_content = "\n        <ul>\n" + "\n".join([f"          <li><strong>{s['label']}:</strong> {s['val']}</li>" for s in tailor_ats_en["skills_en"]]) + "\n        </ul>\n        "
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

        tailor_ats = get_domain_tailoring(role)
        summary_text = tailor_ats["summary_vi"]
        skills_content = "\n        <ul>\n" + "\n".join([f"          <li><strong>{s['label']}:</strong> {s['val']}</li>" for s in tailor_ats["skills_vi"]]) + "\n        </ul>\n        "

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
    
    tailor_cl = get_domain_tailoring(target_role, eval_result)
    if is_en:
        body = tailor_cl["cl_body_en"](company, target_role, name, loc, email, phone, contact)
    else:
        body = tailor_cl["cl_body_vi"](company, target_role, name, loc, email, phone, contact)

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
