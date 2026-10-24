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

MOCK_BADGE = "> [!NOTE]\n> **HỒ SƠ MẪU (MOCK PROFILE)** - Dữ liệu dùng cho mục đích kiểm thử và minh họa hệ thống.\n"

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
        Never hallucinates experience, skills or credentials.
        Emits clear placeholders when candidate data is missing.
        """
        cand = self.candidate
        name = cand.get("name", "[Chưa cập nhật tên ứng viên / Cần bổ sung]")
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
            lines.append("*[Chưa cập nhật thông tin liên hệ / Cần bổ sung]*\n")
            
        lines.append(f"**Vị trí mục tiêu / Target Role:** {target_role}\n")
        lines.append("---\n")

        # 1. Summary / Objective
        lines.append("## Tóm tắt chuyên môn (Professional Summary)")
        summary = cand.get("summary")
        if summary:
            lines.append(summary)
        else:
            lines.append(f"*[Chưa cập nhật tóm tắt chuyên môn / Cần bổ sung mục tiêu nghề nghiệp cho vị trí {target_role}]*")
        lines.append("")

        # 2. Education
        lines.append("## Học vấn (Education)")
        education = cand.get("education")
        if education and isinstance(education, list) and len(education) > 0:
            for edu in education:
                school = edu.get("institution", "[Chưa rõ cơ sở đào tạo]")
                degree = edu.get("degree", "[Bằng cấp]")
                major = edu.get("major", "[Chuyên ngành]")
                year = edu.get("year", "")
                gpa = edu.get("gpa", "")
                gpa_str = f" - GPA: {gpa}" if gpa else ""
                lines.append(f"- **{degree} ngành {major}** | {school} ({year}){gpa_str}")
        else:
            lines.append("*[Chưa cập nhật thông tin học vấn / Cần bổ sung]*")
        lines.append("")

        # 3. Technical Skills
        lines.append("## Kỹ năng chuyên môn (Technical Skills)")
        skills = cand.get("skills")
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
            lines.append("## Môn học chuyên ngành tiêu biểu (Relevant Coursework)")
            for cw in coursework:
                c_name = cw.get("course_name", "")
                topics = cw.get("topics", "")
                lines.append(f"- **{c_name}:** {topics}")
            lines.append("")

        # 5. Hands-on Labs & Simulations (Distinguished from Work Experience)
        labs = cand.get("labs_and_simulations", [])
        if labs:
            lines.append("## Thực hành Phòng Lab & Giả lập (Hands-on Labs & Simulations)")
            for lab in labs:
                l_name = lab.get("name", "")
                tools = ", ".join(lab.get("tools", []))
                desc = lab.get("description", "")
                lines.append(f"### {l_name}")
                if tools:
                    lines.append(f"**Công cụ:** {tools}")
                lines.append(f"- {desc}\n")

        # 6. Personal Projects (Distinguished from Work Experience)
        projects = cand.get("personal_projects", [])
        if projects:
            lines.append("## Dự án cá nhân & Đồ án (Personal Projects & Capstones)")
            for proj in projects:
                p_name = proj.get("name", "")
                tech = ", ".join(proj.get("technologies", []))
                desc = proj.get("description", "")
                repo = proj.get("repo_url", "")
                lines.append(f"### {p_name}")
                if tech:
                    lines.append(f"**Công nghệ:** {tech}")
                lines.append(f"- {desc}")
                if repo:
                    lines.append(f"- Repository: {repo}")
                lines.append("")

        # 7. Work Experience (Strict differentiation: unrecorded vs verified none)
        lines.append("## Kinh nghiệm làm việc thực tế (Work Experience)")
        if "work_experience" in cand:
            work = cand.get("work_experience")
            if work and isinstance(work, list) and len(work) > 0:
                for w in work:
                    role = w.get("role", "")
                    company = w.get("company", "")
                    period = w.get("period", "")
                    desc = w.get("description", "")
                    lines.append(f"### {role} - {company} ({period})")
                    lines.append(f"- {desc}\n")
            else:
                lines.append("*Chưa có kinh nghiệm chính thức (Fresher / Mới tốt nghiệp - Chưa ghi nhận kinh nghiệm làm việc trước đây)*\n")
        else:
            lines.append("*[Chưa cập nhật dữ liệu kinh nghiệm làm việc / Cần bổ sung]*\n")

        # 8. Certifications & Languages
        lines.append("## Chứng chỉ & Ngoại ngữ (Certifications & Languages)")
        certs = cand.get("certifications")
        if certs and isinstance(certs, list) and len(certs) > 0:
            for cert in certs:
                lines.append(f"- Chứng chỉ: **{cert.get('name')}** - {cert.get('issuer', '')} ({cert.get('year', '')})")
        else:
            lines.append("- Chứng chỉ: *[Chưa cập nhật / Cần bổ sung]*")

        langs = cand.get("languages")
        if langs and isinstance(langs, dict) and any(langs.values()):
            for lang_k, level in langs.items():
                lines.append(f"- Ngoại ngữ ({lang_k.capitalize()}): {level}")
        else:
            lines.append("- Ngoại ngữ: *[Chưa cập nhật / Cần bổ sung]*")

        if market == "korea":
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
        
        # Pick top 3 matched evidences
        top_evidences = []
        for m in matched[:3]:
            top_evidences.append(f"{m['skill']} ({m['evidence_type']}: {m['evidence_details']})")

        has_verified_evidence = len(top_evidences) > 0

        if language == "en":
            evidence_section = (
                f"Specifically, my background includes demonstrable evidence in:\n"
                + "\n".join(f"- {e}" for e in top_evidences)
                if has_verified_evidence
                else "*[Note: Candidate profile does not currently list verified skills or project evidence matching this position. Please add relevant coursework or lab experience before submitting.]*"
            )
            content = f"""{badge}# Cover Letter: {job_title}

**Applicant:** {name}  
**Date:** {evaluation.get('collection_time', datetime.now().strftime('%Y-%m-%d'))}  
**Target Organization:** {company}  

Dear Hiring Team,

I am writing to express my interest in the **{job_title}** position at **{company}**. 

{evidence_section}

I am motivated to apply my technical foundation, discipline, and commitment to continuous learning to support your engineering operations.

Thank you for your time and consideration.

Sincerely,  
**{name}**
"""
        else: # Vietnamese
            evidence_section = (
                f"Qua quá trình học tập và rèn luyện, tôi đã tích lũy kỹ năng thực hành phù hợp với yêu cầu của vị trí qua các minh chứng cụ thể:\n"
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

Tôi hiểu rằng vị trí {job_title} đòi hỏi tính cẩn trọng, kỷ luật và tinh thần sẵn sàng học hỏi liên tục. Với tinh thần trách nhiệm và cam kết kỹ thuật trung thực, tôi mong muốn được đóng góp vào các hoạt động vận hành của Quý công ty.

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

    def export_to_html(self, markdown_content: str, output_path: Path) -> Path:
        """
        Convert Markdown to standalone styled HTML.
        Provides zero-dependency printable document when LaTeX/Bun is missing.
        """
        safe_out = ensure_within_project(output_path)
        
        lines = markdown_content.splitlines()
        html_body = []
        in_code_block = False
        in_list = False
        
        for line in lines:
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
                html_body.append(f"<h1>{html.escape(line[2:])}</h1>")
            elif line.startswith("## "):
                html_body.append(f"<h2>{html.escape(line[3:])}</h2>")
            elif line.startswith("### "):
                html_body.append(f"<h3>{html.escape(line[4:])}</h3>")
            elif line.startswith("> "):
                html_body.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
            elif line.startswith("- "):
                if not in_list:
                    html_body.append("<ul>")
                    in_list = True
                html_body.append(f"<li>{html.escape(line[2:])}</li>")
            elif line.strip() == "---":
                html_body.append("<hr/>")
            elif not line.strip():
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
                html_body.append("<br/>")
            else:
                if in_list:
                    html_body.append("</ul>")
                    in_list = False
                html_body.append(f"<p>{html.escape(line)}</p>")
                
        if in_list:
            html_body.append("</ul>")
            
        full_html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>Generated Document - ai-job-search</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 860px; margin: 40px auto; padding: 0 20px; color: #1a202c; }}
h1 {{ color: #2b6cb0; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
h2 {{ color: #2d3748; margin-top: 24px; border-bottom: 1px solid #edf2f7; padding-bottom: 4px; }}
h3 {{ color: #4a5568; }}
blockquote {{ background: #ebf8ff; border-left: 4px solid #3182ce; padding: 12px 16px; margin: 16px 0; }}
code, pre {{ background: #edf2f7; border-radius: 4px; font-family: Consolas, monospace; }}
pre {{ padding: 12px; overflow-x: auto; }}
ul {{ padding-left: 24px; }}
hr {{ border: 0; border-top: 1px solid #cbd5e0; margin: 24px 0; }}
@media print {{ body {{ max-width: 100%; margin: 0; padding: 15mm; }} }}
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
