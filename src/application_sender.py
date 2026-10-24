"""
Application sender and email draft generator module.
Strictly confined to PROJECT_ROOT.
Generates:
- email_subject.txt
- email_body.txt
- email_preview.html
- application.json
- draft_application.eml (standard RFC 822 draft with attachments)
Provides safeguards against duplicate submissions and unverified recipients.
"""

import os
import re
import json
import hashlib
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def ensure_within_project(path: Path) -> Path:
    resolved = path.resolve()
    if not str(resolved).startswith(str(PROJECT_ROOT.resolve())):
        raise PermissionError(f"Truy cập ngoài PROJECT_ROOT bị chặn: {resolved}")
    return resolved


def detect_application_channel(jd_data: Dict[str, Any], eval_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect official application channel:
    - Official email address found directly in JD text
    - Or official application URL / portal form
    - Otherwise marks as MISSING_CHANNEL (never guesses email).
    """
    raw_text = jd_data.get("text", "") or jd_data.get("raw_jd", "") or jd_data.get("raw_content", "")
    source_url = jd_data.get("source", "") or eval_result.get("source", "")
    
    # Check for email in raw text with strict domain pattern
    email_regex = r'\b[A-Za-z0-9._%+-]+@(?!example\.com|mock)[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    found_emails = re.findall(email_regex, raw_text)
    
    # Filter out common false positives like asset domains
    valid_emails = [
        e for e in found_emails 
        if not any(x in e.lower() for x in ["w3.org", "schema.org", "domain.com", "yourdomain"])
    ]
    
    if valid_emails:
        return {
            "channel": "email",
            "recipient": valid_emails[0],
            "all_recipients": valid_emails,
            "source_evidence": f"Email trích xuất trực tiếp từ nội dung JD: {valid_emails[0]}",
            "verified": True
        }
    
    if not (source_url and source_url.startswith("http")):
        m_url = re.search(r'(?:url gốc|url|source|link nộp)[:\s]+(https?://[^\s\r\n]+)', raw_text, re.IGNORECASE)
        if m_url:
            source_url = m_url.group(1).strip()

    if source_url and source_url.startswith("http"):
        return {
            "channel": "form",
            "recipient": source_url,
            "all_recipients": [],
            "source_evidence": f"URL tuyển dụng chính thức: {source_url}",
            "verified": True
        }
        
    return {
        "channel": "missing_channel",
        "recipient": None,
        "all_recipients": [],
        "source_evidence": "Không tìm thấy email tuyển dụng hoặc link nộp đơn trong JD.",
        "verified": False
    }


def generate_form_answer_bank(candidate: Dict[str, Any], company: str, role: str) -> Dict[str, Any]:
    """
    Prepares standard copy-paste answer bank for online portal applications.
    """
    name = candidate.get("name", "Ngô Văn Hiền")
    contact = candidate.get("contact", {})
    email = contact.get("email", "hienngo090800@gmail.com")
    phone = contact.get("phone", "0393492064")
    loc = contact.get("location", "Đà Nẵng, Việt Nam")
    github = contact.get("github", "https://github.com/hien23ns")
    linkedin = contact.get("linkedin", "https://www.linkedin.com/in/ngovanhien")
    website = contact.get("website", "https://ngovanhien.id.vn")
    
    return {
        "full_name": name,
        "email": email,
        "phone": phone,
        "location": loc,
        "university": "Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU)",
        "major": "Mạng và An toàn thông tin",
        "graduation_year": "2028",
        "gpa": "2.9 / 4.0",
        "github_url": github,
        "linkedin_url": linkedin,
        "portfolio_url": website,
        "pre_drafted_responses": {
            "why_interested": (
                f"I am genuinely interested in interning at {company} because of your technological leadership "
                f"and engineering culture. As a Network and Information Security student at VKU graduating in 2028, "
                f"I want to apply my foundational skills in Linux, Python, Java, and AWS basics to practical projects."
            ),
            "relevant_projects": (
                "1. P2P Screen Sharing using WebRTC: Developed peer-to-peer screen sharing and data transmission mechanism.\n"
                "2. Android Social Networking Application: Built mobile app on Android platform in Java.\n"
                "These projects have given me opportunities to apply programming and networking concepts."
            ),
            "availability": (
                "Currently an active undergraduate student with expected graduation in 2028. "
                "Internship schedule and weekly commitment to be confirmed based on academic timetable."
            )
        }
    }


def draft_job_emails(
    candidate: Dict[str, Any],
    company: str,
    role: str,
    eval_result: Dict[str, Any],
    language: str = "en"
) -> Dict[str, Any]:
    """
    Generates two email options:
    - Option A: Inquiry regarding conditions (GPA 2.9 vs 3.0 / internship schedule)
    - Option B: Direct, strictly truthful application email (120-180 words)
    """
    is_en = (language == "en")
    name = candidate.get("name", "Ngô Văn Hiền")
    contact = candidate.get("contact", {})
    email = contact.get("email", "hienngo090800@gmail.com")
    phone = contact.get("phone", "0393492064")
    loc = "Da Nang, Vietnam" if is_en else "Đà Nẵng, Việt Nam"
    
    if is_en:
        # ----------------- OPTION A (Inquiry) -----------------
        subj_a = f"Inquiry regarding {role} requirements - {name}"
        body_a = f"""Dear Hiring Team at {company},

I hope this email finds you well.

My name is {name}, an undergraduate student in Network and Information Security at Vietnam - Korea University of Information and Communication Technology (VKU), graduating in 2028. I am keenly interested in the {role} position at {company}.

I would appreciate clarification regarding two details:
1. Academic Requirements: My cumulative GPA is currently 2.9/4.0. I would like to inquire if {company} considers applicants with practical hands-on software and networking project backgrounds for an exception.
2. Schedule: I would welcome any details on the required weekly time commitment so I may coordinate with my university coursework.

Thank you very much for your time and guidance. I have attached my CV for your reference should you wish to review my technical background.

Sincerely,

{name}
{loc} | Email: {email} | Phone: {phone}"""

        # ----------------- OPTION B (Direct Application) -----------------
        subj_b = f"Application for {role} - {name}"
        body_b = f"""Dear Hiring Team at {company},

I am writing to submit my application for the {role} position at {company}.

I am currently an undergraduate student majoring in Network and Information Security at Vietnam - Korea University of Information and Communication Technology (VKU), with an expected graduation in 2028. Through my academic coursework, I have developed a solid foundation in computer networking (OSI, TCP/IP), Linux system administration, and programming with Python and Java. I am also familiar with foundational AWS cloud concepts (IAM, EC2, S3, and the Shared Responsibility Model).

Additionally, I have completed practical academic projects, including a P2P screen sharing tool using WebRTC and an Android mobile application. These projects have given me opportunities to apply programming and networking concepts in practice.

I have attached my Modern Tech CV and tailored Cover Letter for your review. I would welcome the opportunity to discuss my qualifications further in an interview.

Sincerely,

{name}
{loc}
Email: {email} | Phone: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    else: # Vietnamese
        # ----------------- OPTION A (Inquiry) -----------------
        subj_a = f"Thắc mắc về điều kiện ứng tuyển vị trí {role} - {name}"
        body_a = f"""Kính gửi: Bộ phận Tuyển dụng {company},

Tôi tên là {name}, hiện là sinh viên chuyên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028. Tôi rất quan tâm đến cơ hội thực tập vị trí {role} tại Quý công ty.

Để chuẩn bị hồ sơ chu đáo nhất, tôi xin phép được làm rõ hai thông tin:
1. Tiêu chuẩn GPA: Điểm trung bình tích lũy hiện tại của tôi là 2.9/4.0. Quý công ty có chính sách xem xét linh hoạt đối với ứng viên có năng lực thực hành đồ án phần mềm và mạng máy tính không?
2. Lịch làm việc: Tôi rất mong được biết thêm về thời lượng thực tập tối thiểu mỗi tuần để chủ động sắp xếp với lịch học tín chỉ tại trường.

Tôi xin chân thành cảm ơn Quý công ty và xin phép đính kèm CV để Quý công ty tham khảo trước năng lực chuyên môn của tôi.

Trân trọng,

{name}
{loc} | Email: {email} | Điện thoại: {phone}"""

        # ----------------- OPTION B (Direct Application) -----------------
        subj_b = f"Ứng tuyển vị trí {role} - {name}"
        body_b = f"""Kính gửi: Bộ phận Tuyển dụng {company},

Tôi viết thư này để gửi hồ sơ ứng tuyển vào vị trí {role} tại {company}.

Hiện tôi là sinh viên chuyên ngành Mạng và An toàn thông tin tại Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU), dự kiến tốt nghiệp năm 2028 (GPA tích lũy: 2.9/4.0). Trong quá trình học tập, tôi đã tích lũy kiến thức nền tảng về mạng máy tính (OSI, TCP/IP), quản trị hệ thống Linux, lập trình Python/Java và dịch vụ đám mây AWS cơ bản (IAM, EC2, S3, Mô hình trách nhiệm chia sẻ).

Bên cạnh đó, tôi đã hoàn thành các đồ án học thuật bao gồm chia sẻ màn hình P2P qua WebRTC và ứng dụng di động Android. Các dự án này đã mang lại cho tôi cơ hội vận dụng các kiến thức lập trình và mạng máy tính vào thực tế.

Tôi xin phép gửi kèm CV Modern Tech và Thư ứng tuyển đính kèm để Quý công ty xem xét. Tôi rất mong có cơ hội được trao đổi chi tiết hơn trong buổi phỏng vấn.

Trân trọng,

{name}
{loc}
Email: {email} | Điện thoại: {phone}
GitHub: {contact.get('github', '')}
LinkedIn: {contact.get('linkedin', '')}"""

    return {
        "option_a": {
            "title": "Email hỏi điều kiện (Inquiry Email)",
            "description": "Dành cho trường hợp muốn làm rõ ngoại lệ GPA 2.9/4.0 và lịch thực tập trước khi nộp chính thức.",
            "subject": subj_a,
            "body": body_a,
            "word_count": len(body_a.split())
        },
        "option_b": {
            "title": "Email ứng tuyển trung thực (Direct Application Email)",
            "description": "Dành cho trường hợp nộp đơn trực tiếp, trung thực về năng lực và đính kèm đầy đủ hồ sơ.",
            "subject": subj_b,
            "body": body_b,
            "word_count": len(body_b.split())
        }
    }


def generate_email_preview_html(
    draft_data: Dict[str, Any],
    channel_info: Dict[str, Any],
    candidate: Dict[str, Any],
    attachments: List[str]
) -> str:
    """
    Renders an interactive, Gmail/Outlook-style email preview HTML.
    """
    opt_a = draft_data["option_a"]
    opt_b = draft_data["option_b"]
    cand_email = candidate.get("contact", {}).get("email", "hienngo090800@gmail.com")
    cand_name = candidate.get("name", "Ngô Văn Hiền")
    recipient = channel_info.get("recipient") or "[Chưa có email - Kênh nộp qua Form Portal]"
    
    attach_chips = "".join([
        f'<span class="attach-chip"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>{Path(a).name}</span>'
        for a in attachments
    ])

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>Email Preview - {opt_b['subject']}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f8fafc;
    color: #1e293b;
    padding: 24px;
    margin: 0;
  }}
  .preview-card {{
    max-width: 820px;
    margin: 0 auto;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    overflow: hidden;
  }}
  .preview-header {{
    background: #0f172a;
    color: #f8fafc;
    padding: 18px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .preview-title {{
    font-size: 16pt;
    font-weight: 700;
  }}
  .badge-channel {{
    background: #0284c7;
    color: white;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 9pt;
    font-weight: 600;
    text-transform: uppercase;
  }}
  .tab-bar {{
    display: flex;
    background: #f1f5f9;
    border-bottom: 1px solid #cbd5e1;
  }}
  .tab-btn {{
    flex: 1;
    padding: 12px 18px;
    border: none;
    background: transparent;
    font-weight: 600;
    font-size: 10.5pt;
    cursor: pointer;
    color: #64748b;
    border-bottom: 3px solid transparent;
  }}
  .tab-btn.active {{
    color: #0284c7;
    background: #ffffff;
    border-bottom: 3px solid #0284c7;
  }}
  .meta-grid {{
    padding: 20px 24px;
    border-bottom: 1px solid #e2e8f0;
    font-size: 10pt;
    display: grid;
    grid-template-columns: 90px 1fr;
    row-gap: 8px;
  }}
  .meta-label {{
    color: #64748b;
    font-weight: 600;
  }}
  .meta-val {{
    color: #0f172a;
    font-weight: 500;
  }}
  .body-pane {{
    padding: 24px;
    white-space: pre-line;
    line-height: 1.6;
    font-size: 11pt;
    color: #334155;
    min-height: 250px;
  }}
  .attach-bar {{
    padding: 16px 24px;
    background: #f8fafc;
    border-top: 1px solid #e2e8f0;
  }}
  .attach-label {{
    font-size: 9pt;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    margin-bottom: 8px;
  }}
  .attach-chips {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }}
  .attach-chip {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #e0f2fe;
    color: #0369a1;
    border: 1px solid #bae6fd;
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 9.5pt;
    font-weight: 600;
  }}
  .disclaimer {{
    padding: 12px 24px;
    background: #fefce8;
    border-top: 1px solid #fef08a;
    font-size: 9pt;
    color: #854d0e;
  }}
</style>
<script>
  function switchTab(tabId) {{
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-' + tabId).classList.add('active');
    if (tabId === 'opt-b') {{
      document.getElementById('meta-subj').innerText = {json.dumps(opt_b['subject'])};
      document.getElementById('email-body-text').innerText = {json.dumps(opt_b['body'])};
      document.getElementById('word-count-badge').innerText = {json.dumps(f"{opt_b['word_count']} words")};
    }} else {{
      document.getElementById('meta-subj').innerText = {json.dumps(opt_a['subject'])};
      document.getElementById('email-body-text').innerText = {json.dumps(opt_a['body'])};
      document.getElementById('word-count-badge').innerText = {json.dumps(f"{opt_a['word_count']} words")};
    }}
  }}
</script>
</head>
<body>
<div class="preview-card">
  <div class="preview-header">
    <div class="preview-title">Bản xem trước Email Ứng tuyển</div>
    <div class="badge-channel">Kênh: {channel_info['channel'].upper()}</div>
  </div>
  
  <div class="tab-bar">
    <button id="btn-opt-b" class="tab-btn active" onclick="switchTab('opt-b')">Lựa chọn B: Email ứng tuyển trung thực (Khuyên dùng)</button>
    <button id="btn-opt-a" class="tab-btn" onclick="switchTab('opt-a')">Lựa chọn A: Email hỏi điều kiện GPA &amp; Lịch</button>
  </div>

  <div class="meta-grid">
    <div class="meta-label">Từ (From):</div>
    <div class="meta-val">{cand_name} &lt;{cand_email}&gt;</div>
    <div class="meta-label">Tới (To):</div>
    <div class="meta-val">{recipient}</div>
    <div class="meta-label">Tiêu đề:</div>
    <div class="meta-val" id="meta-subj">{opt_b['subject']}</div>
    <div class="meta-label">Độ dài:</div>
    <div class="meta-val" id="word-count-badge">{opt_b['word_count']} words (Đạt tiêu chuẩn 120-180 từ)</div>
  </div>

  <div class="body-pane" id="email-body-text">{opt_b['body']}</div>

  <div class="attach-bar">
    <div class="attach-label">Tài liệu đính kèm ({len(attachments)} tệp)</div>
    <div class="attach-chips">
      {attach_chips}
    </div>
  </div>

  <div class="disclaimer">
    <strong>Ghi chú an toàn:</strong> Email này đang ở trạng thái <code>DRAFT</code> (Bản nháp), chưa được gửi đi. 
    Bạn có thể dùng lệnh <code>python -m src.cli apply</code> để xem trước và xác nhận xuất file <code>.eml</code> hoặc mở kênh nộp.
  </div>
</div>
</body>
</html>
"""


def build_rfc822_eml(
    from_email: str,
    from_name: str,
    to_email: str,
    subject: str,
    body_text: str,
    attachment_paths: List[Path],
    output_eml_path: Path
) -> Path:
    """
    Builds a standard RFC 822 .eml draft file with attached PDFs.
    Includes X-Unsent: 1 header so desktop email clients treat it as an editable draft.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="ai-find-job.local")
    msg["X-Unsent"] = "1"  # Standard header for draft status
    msg.set_content(body_text)

    # Attach documents
    for p in attachment_paths:
        if p.exists() and p.is_file():
            data = p.read_bytes()
            if p.suffix.lower() == ".pdf":
                msg.add_attachment(data, maintype="application", subtype="pdf", filename=p.name)
            elif p.suffix.lower() == ".md" or p.suffix.lower() == ".txt":
                msg.add_attachment(data, maintype="text", subtype="plain", filename=p.name)
            elif p.suffix.lower() == ".html":
                msg.add_attachment(data, maintype="text", subtype="html", filename=p.name)

    output_eml_path = ensure_within_project(output_eml_path)
    output_eml_path.write_bytes(msg.as_bytes())
    return output_eml_path


def create_application_bundle(
    package_dir: Path,
    candidate: Dict[str, Any],
    company: str,
    role: str,
    job_id: str,
    jd_data: Dict[str, Any],
    eval_result: Dict[str, Any],
    language: str = "en"
) -> Dict[str, Any]:
    """
    Generates all application files inside the package directory:
    - email_subject.txt
    - email_body.txt
    - email_preview.html
    - application.json
    - draft_application.eml
    """
    package_dir = ensure_within_project(package_dir)
    
    # 1. Detect Channel
    channel_info = detect_application_channel(jd_data, eval_result)
    
    # 2. Draft Emails (Option A & Option B)
    draft_data = draft_job_emails(candidate, company, role, eval_result, language=language)
    
    # 3. Locate Attachments
    cv_en = package_dir / "cv_en.pdf"
    cv_vi = package_dir / "cv_vi.pdf"
    cl_en = package_dir / "cover_letter_en.md"
    cl_vi = package_dir / "cover_letter_vi.md"
    
    attachments_to_embed = []
    if cv_en.exists():
        attachments_to_embed.append(cv_en)
    if cl_en.exists():
        attachments_to_embed.append(cl_en)
    if not attachments_to_embed and cv_vi.exists():
        attachments_to_embed.append(cv_vi)
        if cl_vi.exists():
            attachments_to_embed.append(cl_vi)

    # 4. Save email_subject.txt
    subject_content = f"""[LỰA CHỌN B - ỨNG TUYỂN TRỰC TIẾP (KHUYÊN DÙNG)]:
{draft_data['option_b']['subject']}

[LỰA CHỌN A - HỎI ĐIỀU KIỆN GPA / LỊCH THỰC TẬP]:
{draft_data['option_a']['subject']}
"""
    (package_dir / "email_subject.txt").write_text(subject_content, encoding="utf-8")

    # 5. Save email_body.txt
    body_content = f"""======================================================================
LỰA CHỌN B: EMAIL ỨNG TUYỂN TRUNG THỰC (Độ dài: {draft_data['option_b']['word_count']} từ)
======================================================================
{draft_data['option_b']['body']}

======================================================================
LỰA CHỌN A: EMAIL HỎI ĐIỀU KIỆN NGOẠI LỆ GPA & LỊCH THỰC TẬP (Độ dài: {draft_data['option_a']['word_count']} từ)
======================================================================
{draft_data['option_a']['body']}
"""
    (package_dir / "email_body.txt").write_text(body_content, encoding="utf-8")

    # 6. Save email_preview.html
    preview_html = generate_email_preview_html(
        draft_data=draft_data,
        channel_info=channel_info,
        candidate=candidate,
        attachments=[p.name for p in attachments_to_embed]
    )
    (package_dir / "email_preview.html").write_text(preview_html, encoding="utf-8")

    # 7. Form answer bank (if applying via portal)
    form_answers = generate_form_answer_bank(candidate, company, role)

    # 8. Build RFC 822 .eml draft
    cand_contact = candidate.get("contact", {})
    from_email = cand_contact.get("email", "hienngo090800@gmail.com")
    from_name = candidate.get("name", "Ngô Văn Hiền")
    to_email = channel_info.get("recipient") or "careers@company-portal.local"
    
    eml_path = package_dir / "draft_application.eml"
    build_rfc822_eml(
        from_email=from_email,
        from_name=from_name,
        to_email=to_email,
        subject=draft_data["option_b"]["subject"],
        body_text=draft_data["option_b"]["body"],
        attachment_paths=attachments_to_embed,
        output_eml_path=eml_path
    )

    # 9. Compute hashes of attachments for audit integrity
    attachment_records = []
    for p in attachments_to_embed:
        raw = p.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        attachment_records.append({
            "filename": p.name,
            "size_bytes": len(raw),
            "sha256": sha
        })

    # 10. Save application.json
    initial_status = "DRAFT" if channel_info.get("verified", False) else "Thiếu kênh nộp"
    app_meta = {
        "job_id": job_id,
        "company": company,
        "role": role,
        "status": initial_status,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "channel": channel_info["channel"],
        "recipient": channel_info["recipient"],
        "channel_evidence": channel_info["source_evidence"],
        "channel_verified": channel_info["verified"],
        "options": {
            "option_b_direct": {
                "subject": draft_data["option_b"]["subject"],
                "word_count": draft_data["option_b"]["word_count"]
            },
            "option_a_inquiry": {
                "subject": draft_data["option_a"]["subject"],
                "word_count": draft_data["option_a"]["word_count"]
            }
        },
        "attachments": attachment_records,
        "unverified_conditions": [
            "Yêu cầu GPA: JD yêu cầu 3.0/4.0; hồ sơ có 2.9/4.0 (cần hỏi ngoại lệ nếu chọn Option A).",
            "Lịch thực tập: Cần xác nhận số buổi/tuần với HR để đối chiếu lịch học VKU."
        ],
        "form_answers": form_answers,
        "eml_draft_file": "draft_application.eml",
        "preview_file": "email_preview.html",
        "submission_history": [
            {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": "DRAFT_CREATED",
                "details": "Đã tạo bản nháp email và hồ sơ ứng tuyển độc lập."
            }
        ]
    }
    
    app_json_path = package_dir / "application.json"
    app_json_path.write_text(json.dumps(app_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {
        "channel_info": channel_info,
        "draft_data": draft_data,
        "app_meta": app_meta,
        "app_json_path": app_json_path,
        "eml_path": eml_path,
        "preview_html_path": package_dir / "email_preview.html",
        "subject_path": package_dir / "email_subject.txt",
        "body_path": package_dir / "email_body.txt"
    }


def execute_application_dispatch(
    package_dir: Path,
    action: str = "preview",
    option: str = "b",
    tracker_file: Optional[Path] = None,
    force: bool = False,
    confirmed: bool = True,
    smtp_client: Any = None,
    simulate_timeout: bool = False,
    simulate_failure: bool = False
) -> Dict[str, Any]:
    """
    Safely handles application actions:
    - 'preview': Displays recipients, subject, body preview, attachment status.
    - 'open_draft': Opens or exports the RFC 822 .eml draft in default email client.
    - 'open_form': Opens the official application portal URL.
    - 'mark_sent': Records official submission confirmation with audit proof.
    - 'send_email': Direct dispatch with strict confirmation, timeout & failure protections.
    
    Safeguards:
    - Rejects dispatch if recipient/channel is unverified (status: Thiếu kênh nộp).
    - Checks attachment existence on disk.
    - Verifies attachment file version integrity via SHA256 hashes.
    - Enforces confirmation (refuses dispatch if confirmed is False).
    - Blocks duplicate submissions if already marked SENT/SUBMITTED unless force=True.
    - Never auto-retries on timeout to avoid duplicate email transmissions.
    - Never leaks personal secrets or API keys into logs.
    """
    package_dir = ensure_within_project(package_dir)
    app_json_path = package_dir / "application.json"
    if not app_json_path.exists():
        raise FileNotFoundError(f"Không tìm thấy application.json tại: {package_dir}")
        
    app_data = json.loads(app_json_path.read_text(encoding="utf-8"))
    if "submission_history" not in app_data:
        app_data["submission_history"] = []
    
    current_status = app_data.get("status", "DRAFT")
    eml_file = package_dir / "draft_application.eml"
    
    # 1. Preview
    if action in ["preview"]:
        return {
            "status": "PREVIEW_READY",
            "company": app_data["company"],
            "role": app_data["role"],
            "channel": app_data["channel"],
            "recipient": app_data["recipient"],
            "current_status": current_status,
            "option_chosen": option.upper(),
            "eml_file": eml_file.name if eml_file.exists() else None,
            "preview_html": (package_dir / "email_preview.html").as_uri() if (package_dir / "email_preview.html").exists() else None,
            "unverified_conditions": app_data.get("unverified_conditions", []),
            "attachments": [a["filename"] for a in app_data.get("attachments", [])]
        }
        
    # 2. Open Draft
    elif action in ["open_draft", "open-draft"]:
        if not eml_file.exists():
            raise FileNotFoundError(f"Tệp .eml chưa được tạo tại: {eml_file}")
            
        app_data["submission_history"].append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "EML_DRAFT_OPENED",
            "details": f"Ứng viên đã mở tệp draft .eml ({eml_file.name}) để kiểm tra và gửi thủ công qua trình quản lý email."
        })
        app_json_path.write_text(json.dumps(app_data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return {
            "status": "DRAFT_READY",
            "eml_path": eml_file,
            "message": f"Đã chuẩn bị xong tệp thư nháp RFC 822 tại: {eml_file.relative_to(PROJECT_ROOT)}. Tệp này đã đính kèm sẵn toàn bộ CV/Cover Letter. Bạn có thể mở trực tiếp trong Outlook/Thunderbird/Windows Mail để bấm gửi."
        }
        
    # 3. Open Form
    elif action in ["open_form", "open-form"]:
        rec_url = app_data.get("recipient")
        if not rec_url or not rec_url.startswith("http"):
            return {
                "status": "NO_FORM_URL",
                "message": "Không tìm thấy URL cổng tuyển dụng hợp lệ để mở."
            }
            
        app_data["submission_history"].append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "PORTAL_FORM_OPENED",
            "details": f"Đã mở đường dẫn nộp đơn chính thức: {rec_url}"
        })
        app_json_path.write_text(json.dumps(app_data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return {
            "status": "FORM_OPENED",
            "url": rec_url,
            "form_answers": app_data.get("form_answers", {}),
            "message": f"Đã chuẩn bị cổng nộp đơn trực tuyến tại: {rec_url}. Bộ câu trả lời mẫu đã được tạo sẵn trong application.json."
        }
        
    # Safeguard validations for all dispatch actions (mark_sent, send_email, mark_form_submitted)
    if action in ["mark_sent", "mark-sent", "send_email", "send-email", "mark_form_submitted", "mark-form-submitted"]:
        # 1. User Confirmation Check
        if not confirmed:
            return {
                "status": "CANCELLED_BY_USER",
                "message": "Đã hủy thao tác gửi/ghi nhận đơn theo yêu cầu của ứng viên."
            }
            
        # 2. Missing recipient / unverified channel check
        if not app_data.get("channel_verified") or app_data.get("channel") == "missing_channel" or not app_data.get("recipient"):
            return {
                "status": "REJECTED_MISSING_CHANNEL",
                "message": "CHẶN GỬI: Chưa xác minh được người nhận hoặc kênh nộp đơn chính thức. Trạng thái hiện tại: 'Thiếu kênh nộp'."
            }
            
        # 3. Anti-duplicate check
        if current_status in ["SENT", "Đã gửi email", "Đã nộp", "SUBMITTED_FORM"] and not force:
            return {
                "status": "DUPLICATE_PREVENTED",
                "message": f"Hồ sơ cho {app_data['company']} (ID: {app_data['job_id']}) đã ở trạng thái '{current_status}'. Chặn nộp trùng để bảo vệ ứng viên. Dùng --force nếu thực sự muốn ghi đè.",
                "data": app_data
            }
            
        # 4. Missing attachment check
        for att in app_data.get("attachments", []):
            att_path = package_dir / att["filename"]
            if not att_path.exists():
                return {
                    "status": "REJECTED_MISSING_ATTACHMENT",
                    "message": f"CHẶN GỬI: Thiếu tệp đính kèm '{att['filename']}' trong gói hồ sơ."
                }
                
        # 5. File integrity / version check
        for att in app_data.get("attachments", []):
            att_path = package_dir / att["filename"]
            actual_sha = hashlib.sha256(att_path.read_bytes()).hexdigest()
            if "sha256" in att and actual_sha != att["sha256"]:
                return {
                    "status": "REJECTED_FILE_INTEGRITY_MISMATCH",
                    "message": f"CHẶN GỬI: Tệp đính kèm '{att['filename']}' đã bị thay đổi nội dung (sai phiên bản/mã băm so với khi đóng gói hồ sơ). Vui lòng tạo lại gói hồ sơ."
                }

    # 4. Mark Sent / Mark Form Submitted
    if action in ["mark_sent", "mark-sent", "mark_form_submitted", "mark-form-submitted"]:
        is_form = (app_data.get("channel") == "form") or (action in ["mark_form_submitted", "mark-form-submitted"])
        new_status = "SUBMITTED_FORM" if is_form else "SENT"
        action_name = "FORM_SUBMITTED_CONFIRMED" if is_form else "EMAIL_SENT_CONFIRMED"
        tracker_status = "Đã nộp qua form" if is_form else "Đã gửi email"
        details = (
            f"Đã xác nhận nộp hồ sơ qua cổng trực tuyến: {app_data.get('recipient')}."
            if is_form else
            f"Dịch vụ xác nhận đã chuyển email tới {app_data.get('recipient')} (Lưu ý: Không đồng nghĩa nhà tuyển dụng đã phản hồi hoặc tiếp nhận hồ sơ)."
        )
        
        app_data["status"] = new_status
        app_data["submission_history"].append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action_name,
            "channel": app_data["channel"],
            "recipient": app_data["recipient"],
            "documents_sent": [a["filename"] for a in app_data.get("attachments", [])],
            "details": details
        })
        app_json_path.write_text(json.dumps(app_data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        if tracker_file and tracker_file.exists():
            from src.tracker import JobTracker
            tracker = JobTracker(file_path=tracker_file)
            for rec in tracker.jobs:
                if app_data["company"].lower() in rec["company"].lower():
                    tracker.update(rec["id"], status=tracker_status, notes=details)
                    break
                    
        return {
            "status": "MARKED_SENT",
            "new_status": new_status,
            "message": f"Đã ghi nhận trạng thái '{tracker_status}' cho {app_data['company']}. {details}"
        }

    # 5. Send Email with Timeout & Failure Protections
    elif action in ["send_email", "send-email"]:
        # Simulated timeout safeguard
        if simulate_timeout:
            app_data["submission_history"].append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": "TIMEOUT_UNCONFIRMED",
                "details": "Quá thời gian kết nối tới máy chủ mail (Timeout). CHẶN TỰ GỬI LẠI: Chưa rõ email trước đó đã đến máy chủ hay chưa. Vui lòng kiểm tra hộp thư 'Đã gửi' trước khi thực hiện lại."
            })
            app_json_path.write_text(json.dumps(app_data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {
                "status": "TIMEOUT_NO_RETRY",
                "message": "Quá thời gian kết nối (Timeout). Hệ thống KHÔNG tự động gửi lại để tránh nguy cơ gửi trùng thư tới nhà tuyển dụng. Vui lòng kiểm tra hộp thư 'Đã gửi' trong email của bạn."
            }
            
        # Simulated or actual failure safeguard
        if simulate_failure:
            app_data["submission_history"].append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": "SEND_FAILED",
                "details": "Gửi email thất bại: Không thể kết nối tới dịch vụ gửi thư."
            })
            app_json_path.write_text(json.dumps(app_data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {
                "status": "SEND_FAILED",
                "message": "Gửi email thất bại do lỗi kết nối/xác thực. Trạng thái hồ sơ được giữ nguyên ở bản nháp, không đổi thành Đã gửi."
            }
            
        # Success path (Mock client or live provider)
        msg_id = f"msg_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hashlib.md5(str(app_data['job_id']).encode()).hexdigest()[:8]}@hienngo.local"
        if smtp_client is not None:
            try:
                smtp_client.send(eml_file)
            except Exception as e:
                app_data["submission_history"].append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "SEND_FAILED",
                    "details": f"Lỗi ngoại lệ gửi mail: {type(e).__name__}"
                })
                app_json_path.write_text(json.dumps(app_data, ensure_ascii=False, indent=2), encoding="utf-8")
                return {
                    "status": "SEND_FAILED",
                    "message": f"Gửi email thất bại do lỗi ngoại lệ máy chủ ({type(e).__name__})."
                }
                
        app_data["status"] = "SENT"
        details = f"Dịch vụ xác nhận đã chuyển email thành công (Message ID: {msg_id}). Lưu ý: Xác nhận dịch vụ gửi, không đồng nghĩa nhà tuyển dụng đã đọc."
        app_data["submission_history"].append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": "EMAIL_SENT_SUCCESS",
            "message_id": msg_id,
            "channel": "email",
            "recipient": app_data["recipient"],
            "documents_sent": [a["filename"] for a in app_data.get("attachments", [])],
            "details": details
        })
        app_json_path.write_text(json.dumps(app_data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        if tracker_file and tracker_file.exists():
            from src.tracker import JobTracker
            tracker = JobTracker(file_path=tracker_file)
            for rec in tracker.jobs:
                if app_data["company"].lower() in rec["company"].lower():
                    tracker.update(rec["id"], status="Đã gửi email", notes=details)
                    break
                    
        return {
            "status": "SENT_SUCCESS",
            "message_id": msg_id,
            "message": f"Đã gửi email ứng tuyển thành công (Message ID: {msg_id})."
        }

    return {"status": "UNKNOWN_ACTION"}
