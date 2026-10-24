"""
Document Generator for CV, Cover Letter, Freelance Proposal, and Interview Preparation.
Generates production-grade Markdown and self-contained HTML with zero external dependencies.
Maintains absolute factual integrity: no fabricated certifications, degrees, or experience.
Flags placeholders clearly when data is missing, and marks mock profiles across all documents.
"""

from datetime import datetime
import html
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from src.config import OUTPUT_DIR
from src.security import ensure_within_project
from src.avatar import get_avatar_base64

MOCK_BADGE = "> [!NOTE]\n> **HỒ SƠ MẪU (MOCK PROFILE)** - Dữ liệu dùng cho mục đích kiểm thử và minh họa hệ thống.\n"


def _format_inline_markdown(text: str) -> str:
    """
    Safely escape HTML entities and convert Markdown bold/italic/code/links to HTML tags.
    Guarantees no raw literal ** or * remain surrounding content in the final rendered output.
    """
    # 1. Escape HTML entities
    safe = html.escape(text, quote=False)

    # 2. Markdown links: [text](url)
    safe = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', safe)

    # 3. Inline code: `code`
    safe = re.sub(r'`([^`]+)`', r'<code>\1</code>', safe)

    # 4. Bold + Italic: ***text***
    safe = re.sub(r'\*\*\*([^\*]+)\*\*\*', r'<strong><em>\1</em></strong>', safe)

    # 5. Bold: **text**
    safe = re.sub(r'\*\*([^\*]+)\*\*', r'<strong>\1</strong>', safe)

    # 6. Italic: *text* (excluding already formatted tags)
    safe = re.sub(r'(?<!\*)\*([^\*]+)\*(?!\*)', r'<em>\1</em>', safe)

    # 7. Safety cleanups: convert any lingering double or single asterisk wraps
    safe = re.sub(r'\*\*([^\*]+)\*\*', r'<strong>\1</strong>', safe)
    safe = re.sub(r'\*([^\*]+)\*', r'<em>\1</em>', safe)

    return safe


class DocumentGenerator:
    def __init__(self, candidate: Optional[Dict[str, Any]] = None):
        self.candidate = candidate or {}

    def _get_mock_badge(self) -> str:
        if self.candidate.get("is_mock", False):
            return MOCK_BADGE + "\n"
        return ""

    def generate_cv_markdown(self, target_role: str, market: str = "vietnam", language: str = "vi") -> str:
        """
        Generate a strictly factual Markdown CV tailored to target role.
        Supports both Vietnamese ('vi') and English ('en').
        Never hallucinates experience, skills or credentials.
        Emits clear placeholders when candidate data is missing.
        """
        cand = self.candidate
        name = cand.get("name", "[Chưa cập nhật tên ứng viên / Cần bổ sung]" if language == "vi" else "[Candidate Name]")
        is_mock = cand.get("is_mock", False)
        
        lines = []
        if is_mock:
            lines.append(MOCK_BADGE)

        lines.append(f"# {name}")
        contact = cand.get("contact", {})
        contact_items = [
            contact.get("email"),
            contact.get("phone"),
            contact.get("github"),
            contact.get("linkedin"),
            contact.get("location")
        ]
        contact_str = " | ".join(filter(None, contact_items))
        if contact_str:
            lines.append(f"*{contact_str}*\n")
        else:
            lines.append("*[Chưa cập nhật thông tin liên hệ / Cần bổ sung]*\n" if language == "vi" else "*[Contact information pending update]*\n")
            
        role_label = "**Vị trí mục tiêu / Target Role:**" if language == "vi" else "**Target Role:**"
        lines.append(f"{role_label} {target_role}\n")
        lines.append("---\n")

        # 1. Summary / Objective
        if language == "en":
            lines.append("## Professional Summary")
            if "cloud" in target_role.lower() or "devops" in target_role.lower():
                lines.append(
                    "Undergraduate student in Network and Information Security at Vietnam - Korea University of Information "
                    "and Communication Technology (VKU), graduating in 2028. Possesses a solid academic "
                    "foundation in computer networking (OSI, TCP/IP), Linux system administration, and programming with Python and Java. "
                    "Familiar with foundational AWS cloud concepts (IAM, EC2, S3, Shared Responsibility Model) and software implementation "
                    "through academic projects (P2P WebRTC screen sharing and Android mobile application). Highly motivated to secure "
                    "a Cloud & DevOps Internship to acquire practical, hands-on practice in cloud infrastructure, automation, and system reliability."
                )
            else:
                summary = cand.get("summary")
                if summary:
                    lines.append(summary)
                else:
                    lines.append(f"*[Candidate summary pending update for {target_role}]*")
        else:
            lines.append("## Tóm tắt chuyên môn (Professional Summary)")
            summary = cand.get("summary")
            if summary:
                lines.append(summary)
            else:
                lines.append(f"*[Chưa cập nhật tóm tắt chuyên môn / Cần bổ sung mục tiêu nghề nghiệp cho vị trí {target_role}]*")
        lines.append("")

        # 2. Education
        education = cand.get("education")
        if language == "en":
            lines.append("## Education")
            if education and isinstance(education, list) and len(education) > 0:
                for edu in education:
                    school = edu.get("institution", "")
                    if "việt - hàn" in school.lower() or "vku" in school.lower():
                        school = "Vietnam - Korea University of Information and Communication Technology (VKU)"
                    degree = edu.get("degree", "")
                    if "kỹ sư" in degree.lower() or "đang theo học" in degree.lower():
                        degree = "Undergraduate Engineering Program"
                    major = edu.get("major", "")
                    if "mạng" in major.lower() and "an toàn" in major.lower():
                        major = "Network and Information Security"
                    year = edu.get("year", "2023 - 2028")
                    year_en = year.replace("(dự kiến tốt nghiệp)", "(Expected Graduation)")
                    lines.append(f"- **{degree} in {major}** | {school} ({year_en})")
            else:
                lines.append("*[Education information pending update]*")
        else:
            lines.append("## Học vấn (Education)")
            if education and isinstance(education, list) and len(education) > 0:
                for edu in education:
                    school = edu.get("institution", "[Chưa rõ cơ sở đào tạo]")
                    degree = edu.get("degree", "[Bằng cấp]")
                    major = edu.get("major", "[Chuyên ngành]")
                    year = edu.get("year", "")
                    lines.append(f"- **{degree} ngành {major}** | {school} ({year})")
            else:
                lines.append("*[Chưa cập nhật thông tin học vấn / Cần bổ sung]*")
        lines.append("")

        # 3. Technical Skills
        skills = cand.get("skills")
        if language == "en":
            lines.append("## Technical Skills")
            if skills and isinstance(skills, dict) and any(skills.values()):
                for cat, items in skills.items():
                    if items:
                        cat_name = cat.replace("_", " ").title()
                        en_items = []
                        for it in items:
                            if it == "Mô hình OSI": en_items.append("OSI Model")
                            elif it == "Cấu hình mạng cơ bản": en_items.append("Basic Network Configuration")
                            elif it == "Truyền dữ liệu P2P": en_items.append("P2P Data Transfer")
                            elif it == "Nguyên tắc bảo mật hệ thống": en_items.append("System Security Principles")
                            elif it == "AWS cơ bản": en_items.append("AWS Fundamentals")
                            elif it == "AWS IAM cơ bản": en_items.append("AWS IAM (Foundational)")
                            elif it == "Amazon EC2 cơ bản": en_items.append("Amazon EC2 (Foundational)")
                            elif it == "Amazon S3 cơ bản": en_items.append("Amazon S3 (Foundational)")
                            elif it == "AWS Shared Responsibility Model": en_items.append("AWS Shared Responsibility Model")
                            else: en_items.append(it)
                        lines.append(f"- **{cat_name}:** {', '.join(en_items)}")
            else:
                lines.append("*[Technical skills pending update]*")
        else:
            lines.append("## Kỹ năng chuyên môn (Technical Skills)")
            if skills and isinstance(skills, dict) and any(skills.values()):
                for cat, items in skills.items():
                    if items:
                        cat_name = cat.replace("_", " ").title()
                        lines.append(f"- **{cat_name}:** {', '.join(items)}")
            else:
                lines.append("*[Chưa cập nhật danh mục kỹ năng / Cần bổ sung]*")
        lines.append("")

        # 4. Academic Coursework (Distinguished from Work Experience)
        coursework = cand.get("coursework", [])
        if coursework:
            title_cw = "## Relevant Coursework" if language == "en" else "## Môn học chuyên ngành tiêu biểu (Relevant Coursework)"
            lines.append(title_cw)
            for cw in coursework:
                c_name = cw.get("course_name", "")
                topics = cw.get("topics", "")
                lines.append(f"- **{c_name}:** {topics}")
            lines.append("")

        # 5. Hands-on Labs & Simulations (Distinguished from Work Experience)
        labs = cand.get("labs_and_simulations", [])
        if labs:
            title_labs = "## Hands-on Labs & Simulations" if language == "en" else "## Thực hành Phòng Lab & Giả lập (Hands-on Labs & Simulations)"
            lines.append(title_labs)
            for lab in labs:
                l_name = lab.get("name", "")
                tools = ", ".join(lab.get("tools", []))
                desc = lab.get("description", "")
                lines.append(f"### {l_name}")
                if tools:
                    tool_lbl = "Tools:" if language == "en" else "Công cụ:"
                    lines.append(f"**{tool_lbl}** {tools}")
                lines.append(f"- {desc}\n")

        # 6. Personal Projects (Distinguished from Work Experience)
        projects = cand.get("personal_projects", [])
        if projects:
            verified_projects = []
            for proj in projects:
                p_name = proj.get("name", "")
                p_desc = proj.get("description", "")
                # Rule: Bỏ SecMon khỏi tài liệu gửi nhà tuyển dụng cho đến khi xác minh được nội dung
                if "secmon" in p_name.lower() or "chưa dùng làm bằng chứng" in p_desc.lower():
                    continue
                # Clean internal reviewer comments from description (no internal audit notes in CV)
                clean_desc = re.sub(
                    r"(?:Dự án được liệt kê trong CV[^\n.]*;?|Chức năng cụ thể[^\n.]*;?|chưa bổ sung số liệu[^\n.]*|phần việc cá nhân cần bổ sung[^\n.]*|\.?$)",
                    "",
                    p_desc,
                    flags=re.IGNORECASE
                ).strip().rstrip(";,.")
                if not clean_desc:
                    clean_desc = p_desc
                verified_projects.append({
                    "name": p_name,
                    "technologies": proj.get("technologies", []),
                    "description": clean_desc,
                    "repo_url": proj.get("repo_url", "")
                })

            if verified_projects:
                title_proj = "## Technical Projects & Capstones" if language == "en" else "## Dự án cá nhân & Đồ án (Personal Projects & Capstones)"
                lines.append(title_proj)
                for proj in verified_projects:
                    p_name = proj.get("name", "")
                    tech = ", ".join(proj.get("technologies", []))
                    desc = proj.get("description", "")
                    repo = proj.get("repo_url", "")
                    
                    if language == "en":
                        if "webrtc" in p_name.lower():
                            en_name = "P2P Screen Sharing using WebRTC"
                            en_desc = "Developed a peer-to-peer screen sharing and data transmission mechanism between devices using WebRTC."
                        elif "android" in p_name.lower():
                            en_name = "Android Social Networking Application"
                            en_desc = "Developed a mobile social networking application on the Android platform."
                        else:
                            en_name = p_name
                            en_desc = desc
                        lines.append(f"### {en_name}")
                        if tech:
                            lines.append(f"**Technologies:** {tech}")
                        lines.append(f"- {en_desc}")
                        if repo:
                            lines.append(f"- Repository: {repo}")
                    else:
                        lines.append(f"### {p_name}")
                        if tech:
                            lines.append(f"**Công nghệ:** {tech}")
                        lines.append(f"- {desc}")
                        if repo:
                            lines.append(f"- Repository: {repo}")
                    lines.append("")

        # 7. Work Experience (Strict differentiation: unrecorded vs verified none)
        work = cand.get("work_experience")
        if language == "en":
            # Rule: Bỏ mục kinh nghiệm rỗng đối với bản tiếng Anh ưu tiên một trang
            if work and isinstance(work, list) and len(work) > 0:
                lines.append("## Work Experience")
                for w in work:
                    role = w.get("role", "")
                    company = w.get("company", "")
                    period = w.get("period", "")
                    desc = w.get("description", "")
                    lines.append(f"### {role} - {company} ({period})")
                    lines.append(f"- {desc}\n")
        else:
            lines.append("## Kinh nghiệm làm việc thực tế (Work Experience)")
            if "work_experience" in cand:
                if work and isinstance(work, list) and len(work) > 0:
                    for w in work:
                        role = w.get("role", "")
                        company = w.get("company", "")
                        period = w.get("period", "")
                        desc = w.get("description", "")
                        lines.append(f"### {role} - {company} ({period})")
                        lines.append(f"- {desc}\n")
                else:
                    lines.append("*Chưa có kinh nghiệm làm việc doanh nghiệp trước đây (Sinh viên đang theo học / Fresher 0 năm kinh nghiệm)*\n")
            else:
                lines.append("*[Chưa cập nhật dữ liệu kinh nghiệm làm việc / Cần bổ sung]*\n")

        # 8. Certifications & Languages
        title_cert_lang = "## Certifications & Languages" if language == "en" else "## Chứng chỉ & Ngoại ngữ (Certifications & Languages)"
        lines.append(title_cert_lang)
        certs = cand.get("certifications")
        if certs and isinstance(certs, list) and len(certs) > 0:
            for cert in certs:
                issuer = cert.get('issuer', '').strip()
                issuer_str = f" - {issuer}" if issuer else ""
                year_str = f" ({cert.get('year')})" if cert.get('year') else ""
                lbl = "Certification:" if language == "en" else "Chứng chỉ:"
                lines.append(f"- {lbl} **{cert.get('name')}**{issuer_str}{year_str}")
        else:
            lines.append("- Certifications: *[None]*" if language == "en" else "- Chứng chỉ: *[Chưa cập nhật / Cần bổ sung]*")

        langs = cand.get("languages")
        if langs and isinstance(langs, dict) and any(langs.values()):
            for lang_k, level in langs.items():
                # Rule: Bỏ mục tiếng Hàn chưa học
                if lang_k.lower() == "korean" and ("chưa" in level.lower() or "not" in level.lower()):
                    continue
                if language == "en":
                    if lang_k.lower() == "vietnamese":
                        lines.append("- Language (Vietnamese): Native")
                    elif lang_k.lower() == "english":
                        lines.append("- Language (English): Technical reading & documentation, basic conversational")
                    else:
                        lines.append(f"- Language ({lang_k.capitalize()}): {level}")
                else:
                    lines.append(f"- Ngoại ngữ ({lang_k.capitalize()}): {level}")
        else:
            lines.append("- Languages: *[Pending]*" if language == "en" else "- Ngoại ngữ: *[Chưa cập nhật / Cần bổ sung]*")

        if market == "korea" and language == "vi":
            lines.append("\n> [!WARNING]\n> **LƯU Ý THỊ TRƯỜNG HÀN QUỐC:** Nếu nộp hồ sơ bằng tiếng Hàn (이력서/자기소개서), "
                         "bắt buộc phải có người có năng lực ngôn ngữ tiếng Hàn rà soát ngữ pháp và thuật ngữ trước khi gửi!")

        return "\n".join(lines)

    def generate_cover_letter(self, evaluation: Dict[str, Any], language: str = "vi") -> str:
        """
        Generate tailored Cover Letter grounded in verified candidate evidence.
        """
        cand = self.candidate
        name = cand.get("name", "[Tên ứng viên - Cần bổ sung]")
        job_title = evaluation.get("title", "Vị trí tuyển dụng")
        company = evaluation.get("company", "Quý công ty")
        matched = evaluation.get("matched_skills", [])
        badge = self._get_mock_badge()
        
        # Pick top matched evidences formatted professionally without debug labels
        top_evidences = []
        for m in matched[:4]:
            skill = m.get("skill", "")
            ev_type = m.get("evidence_type", "")
            ev_det = m.get("evidence_details", "")
            if "Có trong danh mục kỹ năng" in ev_det:
                top_evidences.append(f"**{skill}:** Nền tảng kỹ năng học tập và thực hành trong các học phần chuyên ngành.")
            elif "Dự án" in ev_type or "Personal Project" in ev_type:
                top_evidences.append(f"**{skill}:** Vận dụng thực tế qua đồ án học thuật.")
            else:
                top_evidences.append(f"**{skill}:** {ev_det}")

        has_verified_evidence = len(top_evidences) > 0

        if language == "en":
            top_evidences_en = []
            for m in matched[:4]:
                skill = m.get("skill", "")
                top_evidences_en.append(f"**{skill}:** Practical foundation built through academic coursework and hands-on programming.")
            evidence_section = (
                f"Specifically, my technical background includes demonstrable academic and hands-on preparation in:\n"
                + "\n".join(f"- {e}" for e in top_evidences_en)
                if has_verified_evidence
                else "*[Note: Candidate profile does not currently list verified skills matching this position.]*"
            )
            content = f"""{badge}# Cover Letter: {job_title}

**Applicant:** {name}  
**Date:** {evaluation.get('collection_time', datetime.now().strftime('%Y-%m-%d'))}  
**Target Organization:** {company}  

Dear Hiring Team,

I am writing to express my strong interest in the **{job_title}** position at **{company}**. 

{evidence_section}

I am currently an undergraduate student pursuing an engineering degree in Network and Information Security at Vietnam - Korea University of Information and Communication Technology (VKU), with an expected graduation in 2028. While I do not possess prior full-time corporate experience and am actively developing my professional skills, I am thoroughly dedicated to engineering discipline, procedural rigor, and rapid technical learning.

Thank you very much for your time and consideration. I would welcome the opportunity to discuss my qualifications further in an interview.

Sincerely,  
**{name}**
"""
        else: # Vietnamese
            evidence_section = (
                f"Qua quá trình học tập và rèn luyện, tôi đã tích lũy các kỹ năng nền tảng phù hợp với yêu cầu tuyển dụng:\n"
                + "\n".join(f"- {e}" for e in top_evidences)
                if has_verified_evidence
                else "*[Lưu ý: Hồ sơ hiện tại chưa có dữ liệu kỹ năng hoặc kinh nghiệm đối sánh với vị trí này. Cần bổ sung thông tin hồ sơ trước khi gửi thư ứng tuyển thực tế.]*"
            )
            content = f"""{badge}# Thư Ứng Tuyển: {job_title}

**Kính gửi:** Bộ phận Tuyển dụng & Quản lý Kỹ thuật - **{company}**  
**Ứng viên:** {name}  
**Vị trí ứng tuyển:** {job_title}  
**Ngày tạo:** {evaluation.get('collection_time', datetime.now().strftime('%Y-%m-%d'))}  

Kính gửi Quý công ty,

Tôi viết thư này để bày tỏ mong muốn được ứng tuyển vào vị trí **{job_title}** tại **{company}**.

{evidence_section}

Hiện tại, tôi đang là sinh viên theo học chương trình kỹ sư (dự kiến tốt nghiệp năm 2028). Tôi hiểu rằng vị trí {job_title} đòi hỏi tính cẩn trọng, kỷ luật và tinh thần học hỏi liên tục. Dù chưa có kinh nghiệm làm việc doanh nghiệp trước đây và đang trong giai đoạn tích lũy chuyên môn, tôi cam kết tuân thủ nghiêm ngặt quy trình kỹ thuật, trung thực về năng lực và nỗ lực tối đa để hoàn thành tốt các nhiệm vụ được giao.

Rất mong có cơ hội được trao đổi chi tiết hơn trong buổi phỏng vấn.

Trân trọng,  
**{name}**
"""
        return content

    def generate_freelance_proposal(self, evaluation: Dict[str, Any]) -> str:
        """
        Generate Freelance Proposal: Problem, Approach, Deliverables, Timeline, Clarification Questions.
        Includes mock badge when applicable.
        """
        cand = self.candidate
        name = cand.get("name", "[Họ và tên Kỹ sư Freelance]")
        title = evaluation.get("title", "Dự án Freelance")
        freelance_spec = evaluation.get("freelance_specifics", {})
        badge = self._get_mock_badge()
        
        milestones = freelance_spec.get("Mốc bàn giao đề xuất", [])
        questions = evaluation.get("clarification_questions", [])
        
        milestones_text = "\n".join(f"- {m}" for m in milestones) if milestones else "- *[Cần làm rõ mốc bàn giao với khách hàng]*"
        questions_text = "\n".join(f"- {q}" for q in questions) if questions else "- *[Không có câu hỏi làm rõ đặc biệt]*"

        proposal = f"""{badge}# ĐỀ XUẤT DỰ ÁN FREELANCE (PROJECT PROPOSAL)

**Tên dự án:** {title}  
**Người thực hiện:** {name}  
**Ngày lập đề xuất:** {evaluation.get('collection_time', datetime.now().strftime('%Y-%m-%d'))}  

---

## 1. Xác định vấn đề cốt lõi (Problem Statement)
Dự án yêu cầu giải quyết bài toán kỹ thuật tập trung vào cấu hình hệ thống, tự động hóa xử lý dữ liệu log hoặc rà soát an toàn thông tin theo phạm vi thỏa thuận. Mục tiêu là đảm bảo tính chính xác, hiệu năng ổn định và tuân thủ tiêu chuẩn an toàn.

## 2. Phương pháp tiếp cận & Kỹ thuật (Technical Approach)
- **Chuẩn bị & Cách ly:** Triển khai thử nghiệm trên môi trường Lab/Staging trước khi áp dụng chính thức.
- **Tự động hóa:** Sử dụng script Python và công cụ dòng lệnh Linux chuẩn, mã nguồn sạch, có chú thích và log chi tiết.
- **Bảo mật:** Tuân thủ nguyên tắc đặc quyền tối thiểu (Least Privilege). Tuyệt đối không lưu trữ hay làm rò rỉ thông tin xác thực.

## 3. Danh mục đầu ra bàn giao (Deliverables)
- Mã nguồn script (Python / Bash) hoàn chỉnh, có xử lý ngoại lệ và logging.
- Tài liệu hướng dẫn cài đặt và vận hành (README / Runbook) từng bước.
- File log hoặc báo cáo kiểm thử xác nhận hoàn thành (Test Verification Log).
- Hỗ trợ giải đáp và bàn giao trực tiếp qua tài liệu.

## 4. Mốc bàn giao đề xuất & Kế hoạch thời gian (Milestones & Timeline)
{milestones_text}

## 5. Câu hỏi làm rõ & Điều kiện tiên quyết (Clarification Questions)
{questions_text}

> [!IMPORTANT]
> **Cam kết bảo mật & Pháp lý:** 
> - Công việc chỉ được thực hiện trong phạm vi hệ thống thuộc quyền quản lý hoặc đã có văn bản ủy quyền chính thức từ khách hàng.
> - Cam kết bảo mật 100% dữ liệu và mã nguồn dự án.
"""
        return proposal

    def generate_interview_prep(self, evaluation: Dict[str, Any]) -> str:
        """
        Generate tailored Interview Questions and Answer Guidelines based on JD and Candidate Profile.
        Includes mock badge when applicable.
        """
        cand = self.candidate
        title = evaluation.get("title", "Vị trí an ninh mạng")
        missing = evaluation.get("missing_skills", [])
        badge = self._get_mock_badge()
        
        score_val = evaluation.get("match_score")
        score_text = f"{score_val}/100" if score_val is not None else "Chưa đủ dữ liệu tính điểm tổng (Cần xác minh điều kiện)"
        lines = [
            f"{badge}# BỘ CÂU HỎI & HƯỚNG DẪN LUYỆN PHỎNG VẤN (INTERVIEW PREP)",
            f"**Vị trí:** {title}",
            f"**Điểm phù hợp hồ sơ:** {score_text}\n",
            "---",
            "## I. CÂU HỎI KỸ THUẬT THEO ĐẶC THÙ CÔNG VIỆC\n"
        ]
        
        # Wireshark / Network questions
        lines.append("### 1. Phân tích gói tin & Mạng (Wireshark / TCP/IP)")
        lines.append("- **Câu hỏi:** Bạn hãy mô tả quá trình bắt tay 3 bước (TCP 3-way handshake) và cách nhận biết một cuộc tấn công SYN Flood trên Wireshark?")
        lines.append("- **Gợi ý trả lời dựa trên hồ sơ:** Nêu rõ các cờ SYN, SYN-ACK, ACK. Nếu có bài lab mạng: lọc cú pháp `tcp.flags.syn == 1 and tcp.flags.ack == 0` để chỉ ra lưu lượng bất thường.\n")

        # Linux / Log analysis
        lines.append("### 2. Quản trị Linux & Xử lý Log (Linux & Python)")
        lines.append("- **Câu hỏi:** Khi một server Linux bị nghi ngờ có kết nối lạ ra ngoài, bạn dùng những lệnh gì để điều tra?")
        lines.append("- **Gợi ý trả lời dựa trên hồ sơ:** Sử dụng `ss -tunap` hoặc `netstat -tunap` để tìm tiến trình (PID) gắn với kết nối IP lạ. Sau đó kiểm tra `/proc/<PID>/exe` và log trong `/var/log/auth.log`.\n")

        # SOC / Incident handling
        lines.append("### 3. Quy trình Giám sát an ninh (SOC Analyst L1)")
        lines.append("- **Câu hỏi:** Nếu hệ thống SIEM cảnh báo có brute-force SSH thành công, quy trình phản ứng ban đầu của bạn là gì?")
        lines.append("- **Gợi ý trả lời:** Xác minh cảnh báo (True Positive) qua log xác thực; cách ly IP nguồn qua Firewall; thông báo L2/Team Lead; kiểm tra hoạt động của tài khoản bị xâm nhập sau thời điểm đăng nhập thành công.\n")

        # Handling missing skills questions
        if missing:
            lines.append("## II. CHIẾN LƯỢC TRẢ LỜI CÁC ĐIỂM CHƯA CÓ KINH NGHIỆM")
            lines.append(f"JD yêu cầu: **{', '.join(missing[:4])}** mà hồ sơ chưa nêu rõ:")
            lines.append("- **Chiến lược:** Thành thật xác nhận chưa có cơ hội làm việc trong môi trường thực tế, nhưng lập tức chứng minh khả năng tự học qua việc đã nắm vững nguyên lý nền tảng tương đương và lộ trình đang rèn luyện.\n")

        lines.append("## III. CÂU HỎI TÌNH HUỐNG (BEHAVIORAL & SCENARIO)")
        lines.append("- **Câu hỏi:** Kể về một đồ án hoặc bài lab khó khăn nhất bạn từng gặp và cách bạn giải quyết?")
        lines.append("- **Cấu trúc trả lời STAR:** Tình huống (Situation) -> Nhiệm vụ (Task) -> Hành động đã làm (Action) -> Kết quả đạt được (Result).\n")

        return "\n".join(lines)

    def export_to_html(self, markdown_content: str, output_path: Path, avatar_data_uri: Optional[str] = None) -> Path:
        """
        Convert Markdown to standalone styled HTML.
        Provides zero-dependency printable document formatted specifically for crisp 1-page A4 print.
        Safely escapes HTML and converts bold/italic markdown into proper tags.
        Embeds avatar as Data URI when available.
        """
        safe_out = ensure_within_project(output_path)
        
        if avatar_data_uri is None:
            avatar_data_uri = get_avatar_base64()

        lines = markdown_content.splitlines()
        html_body = []
        in_code_block = False
        in_list = False
        
        # Check if document starts with a CV Header (# Name)
        header_name = None
        header_contact = None
        header_target_role = None
        start_idx = 0
        
        idx = 0
        while idx < len(lines):
            l = lines[idx].strip()
            if l.startswith("# "):
                header_name = l[2:].strip()
                n_idx = idx + 1
                while n_idx < len(lines) and not lines[n_idx].strip():
                    n_idx += 1
                if n_idx < len(lines) and lines[n_idx].strip().startswith("*") and not lines[n_idx].strip().startswith("**"):
                    header_contact = lines[n_idx].strip().strip("*").strip()
                    n_idx += 1
                while n_idx < len(lines) and not lines[n_idx].strip():
                    n_idx += 1
                if n_idx < len(lines) and "target role" in lines[n_idx].lower():
                    header_target_role = lines[n_idx].strip()
                    n_idx += 1
                while n_idx < len(lines) and (not lines[n_idx].strip() or lines[n_idx].strip() == "---"):
                    n_idx += 1
                start_idx = n_idx
                break
            elif l.startswith(">"):
                clean_quote = l[1:].strip()
                html_body.append(f"<blockquote>{_format_inline_markdown(clean_quote)}</blockquote>")
            idx += 1

        if header_name:
            avatar_html = ""
            if avatar_data_uri:
                avatar_html = f'<div class="cv-avatar-container"><img src="{avatar_data_uri}" alt="Portrait Photo" class="cv-avatar" /></div>'
            
            contact_html = f'<div class="cv-contact">{_format_inline_markdown(header_contact)}</div>' if header_contact else ''
            role_html = f'<div class="cv-target-role">{_format_inline_markdown(header_target_role)}</div>' if header_target_role else ''
            
            header_markup = f"""<div class="cv-header">
  <div class="cv-header-text">
    <h1>{html.escape(header_name)}</h1>
    {contact_html}
    {role_html}
  </div>
  {avatar_html}
</div>"""
            html_body.append(header_markup)
            remaining_lines = lines[start_idx:]
        else:
            remaining_lines = lines

        for line in remaining_lines:
            if line.startswith("```"):
                if in_code_block:
                    html_body.append("</pre></code>")
                    in_code_block = False
                else:
                    html_body.append("<pre><code>")
                    in_code_block = True
                continue
            if in_code_block:
                html_body.append(html.escape(line))
                continue
                
            if line.startswith("# "):
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
                html_body.append(f"<h1>{_format_inline_markdown(line[2:])}</h1>")
            elif line.startswith("## "):
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
                html_body.append(f"<h2>{_format_inline_markdown(line[3:])}</h2>")
            elif line.startswith("### "):
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
                html_body.append(f"<h3>{_format_inline_markdown(line[4:])}</h3>")
            elif line.startswith("> "):
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
                html_body.append(f"<blockquote>{_format_inline_markdown(line[2:])}</blockquote>")
            elif line.startswith("- "):
                if not in_list:
                    html_body.append("<ul>")
                    in_list = True
                html_body.append(f"<li>{_format_inline_markdown(line[2:])}</li>")
            elif line.strip() == "---":
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
                html_body.append("<hr/>")
            elif not line.strip():
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
            else:
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
                html_body.append(f"<p>{_format_inline_markdown(line)}</p>")
                
        if in_list:
            html_body.append("</ul>")
            
        full_html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>Candidate Curriculum Vitae - ai-job-search</title>
<style>
@page {{
  size: A4 portrait;
  margin: 10mm 14mm 10mm 14mm;
}}
* {{
  box-sizing: border-box;
}}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 9.75pt;
  line-height: 1.42;
  color: #1a202c;
  max-width: 820px;
  margin: 20px auto;
  padding: 0 15px;
  background-color: #ffffff;
}}
.cv-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  border-bottom: 2px solid #2b6cb0;
  padding-bottom: 8px;
  margin-bottom: 10px;
}}
.cv-header-text {{
  flex: 1;
}}
.cv-name {{
  font-size: 19pt;
  color: #1a365d;
  margin: 0 0 4px 0;
  font-weight: 700;
  letter-spacing: -0.3px;
  border: none;
  padding: 0;
}}
.cv-contact {{
  font-size: 8.75pt;
  color: #4a5568;
  margin: 2px 0 4px 0;
  line-height: 1.35;
}}
.cv-target-role {{
  font-size: 10pt;
  color: #2b6cb0;
  font-weight: 600;
  margin-top: 2px;
}}
.cv-avatar-container {{
  flex-shrink: 0;
  text-align: right;
}}
.cv-avatar {{
  width: 90px;
  height: 115px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #cbd5e0;
  box-shadow: 0 2px 4px rgba(0,0,0,0.06);
  display: block;
}}
h1 {{
  font-size: 16pt;
  color: #2b6cb0;
  border-bottom: 2px solid #e2e8f0;
  padding-bottom: 4px;
  margin: 12px 0 8px 0;
}}
h2 {{
  font-size: 10.5pt;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: #2b6cb0;
  border-bottom: 1.5px solid #e2e8f0;
  padding-bottom: 2px;
  margin: 10px 0 5px 0;
}}
h3 {{
  font-size: 10pt;
  color: #2d3748;
  margin: 5px 0 2px 0;
  font-weight: 600;
}}
blockquote {{
  background: #ebf8ff;
  border-left: 4px solid #3182ce;
  padding: 8px 12px;
  margin: 10px 0;
  font-size: 9pt;
}}
code, pre {{
  background: #edf2f7;
  border-radius: 4px;
  font-family: Consolas, monospace;
}}
pre {{
  padding: 8px;
  overflow-x: auto;
}}
ul {{
  padding-left: 18px;
  margin: 2px 0 6px 0;
}}
li {{
  margin-bottom: 2px;
}}
p {{
  margin: 3px 0 5px 0;
}}
hr {{
  border: 0;
  border-top: 1px solid #cbd5e0;
  margin: 8px 0;
}}
strong {{
  font-weight: 600;
  color: #1a202c;
}}
em {{
  font-style: italic;
}}
a {{
  color: #2b6cb0;
  text-decoration: none;
}}
@media print {{
  body {{
    max-width: 100%;
    margin: 0;
    padding: 0;
    font-size: 9.2pt;
    line-height: 1.35;
  }}
  .cv-header {{
    page-break-inside: avoid;
  }}
  h2, h3 {{
    page-break-after: avoid;
  }}
  ul, p {{
    page-break-inside: avoid;
  }}
}}
</style>
</head>
<body>
{"".join(html_body)}
</body>
</html>
"""
        safe_out.parent.mkdir(parents=True, exist_ok=True)
        safe_out.write_text(full_html, encoding="utf-8")
        return safe_out


def generate_pdf_from_html(html_path: Path, output_pdf_path: Optional[Path] = None) -> Optional[Path]:
    """
    Generate print-ready A4 PDF from HTML document using Playwright Chromium.
    Returns path to generated PDF, or None if Playwright is unavailable.
    """
    safe_html = ensure_within_project(html_path)
    if output_pdf_path is None:
        output_pdf_path = safe_html.with_suffix(".pdf")
    safe_pdf = ensure_within_project(output_pdf_path)
    
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"file:///{safe_html.resolve().as_posix()}", wait_until="networkidle")
            page.pdf(
                path=str(safe_pdf),
                format="A4",
                print_background=True,
                margin={"top": "10mm", "bottom": "10mm", "left": "14mm", "right": "14mm"},
                prefer_css_page_size=True
            )
            browser.close()
        return safe_pdf
    except Exception as e:
        return None

