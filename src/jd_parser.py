"""
Job Description (JD) Parser, Fetcher, and Deduplicator.
Strictly handles UTF-8 files, direct text, and public URL fetching with strict safety.
"""

from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request

from src.security import ensure_within_project, sanitize_untrusted_text

class HTMLTextExtractor(HTMLParser):
    """Clean HTML to plain text without external dependencies."""
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text_parts = []
        self.in_script_or_style = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ["script", "style", "noscript"]:
            self.in_script_or_style = True
        elif tag.lower() in ["p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"]:
            self.text_parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in ["script", "style", "noscript"]:
            self.in_script_or_style = False
        elif tag.lower() in ["p", "div", "li"]:
            self.text_parts.append("\n")

    def handle_data(self, data):
        if not self.in_script_or_style:
            self.text_parts.append(data)

    def get_text(self) -> str:
        raw_text = "".join(self.text_parts)
        # Normalize multiple spaces and blank lines
        lines = [line.strip() for line in raw_text.splitlines()]
        return "\n".join(line for line in lines if line)

def compute_jd_hash(title: str, company: str, content: str) -> str:
    """Compute a normalized SHA256 hash for deduplication."""
    norm_title = re.sub(r"\s+", " ", title.strip().lower())
    norm_company = re.sub(r"\s+", " ", company.strip().lower())
    # Normalized content without punctuation
    norm_content = re.sub(r"[^\w\s]", "", content.lower())
    norm_content = re.sub(r"\s+", " ", norm_content)
    # Take first 500 chars of normalized content + title + company
    digest_source = f"{norm_company}::{norm_title}::{norm_content[:500]}"
    return hashlib.sha256(digest_source.encode("utf-8")).hexdigest()

def parse_jd_text(text: str, source: str = "manual_text", metadata: Optional[Dict] = None) -> Dict:
    """
    Parse JD text safely with sanitization.
    Extracts structured fields without hallucinating nonexistent details.
    """
    sanitized = sanitize_untrusted_text(text)
    meta = metadata or {}
    
    # Intelligent heuristic extraction for title and company if not provided
    title = meta.get("title", "")
    company = meta.get("company", "")
    
    first_lines = [line.strip() for line in sanitized.splitlines() if line.strip()][:12]
    if not title:
        for line in first_lines:
            if line.startswith("[") and line.endswith("]"):
                continue
            for prefix in ["vị trí tuyển dụng:", "vị trí:", "tiêu đề:", "job title:", "title:", "project title:", "채용 공고:", "채용:"]:
                if line.lower().startswith(prefix):
                    title = line[len(prefix):].strip()
                    break
            if title:
                break
        if not title and first_lines:
            for line in first_lines:
                if not (line.startswith("[") and line.endswith("]")):
                    title = line[:120]
                    break
            if not title:
                title = first_lines[0][:120]

    if not company:
        for line in first_lines:
            if line.startswith("[") and line.endswith("]"):
                continue
            for prefix in ["đơn vị tuyển dụng:", "công ty:", "doanh nghiệp:", "company:", "client / organization:", "client:", "기업명:"]:
                if line.lower().startswith(prefix):
                    company = line[len(prefix):].strip()
                    break
            if company:
                break
        if not company and len(first_lines) > 1:
            for line in first_lines[1:]:
                if not (line.startswith("[") and line.endswith("]")) and line != title:
                    company = line[:80]
                    break
    # Extract job_id if present
    job_id = meta.get("job_id", "")
    if not job_id:
        m_id = re.search(r'(?:job[-_ ]?id|id tin|mã tin|view)/?[:\s]+([0-9a-zA-Z_-]{5,30})', sanitized, re.IGNORECASE)
        if m_id:
            job_id = m_id.group(1).strip()

    jd_hash = compute_jd_hash(title, company, sanitized)
    
    return {
        "title": title or "Chưa rõ tiêu đề",
        "company": company or "Chưa rõ công ty",
        "job_id": job_id,
        "source": source,
        "raw_content": sanitized,
        "hash": jd_hash,
        "market": meta.get("market", "vietnam")
    }

def read_jd_file(file_path: Union[str, Path]) -> Dict:
    """
    Read JD from a local UTF-8 file inside PROJECT_ROOT.
    """
    safe_path = ensure_within_project(file_path)
    if not safe_path.exists():
        raise FileNotFoundError(f"Tập tin JD không tồn tại: {safe_path}")
        
    try:
        content = safe_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback to utf-8 with replacement
        content = safe_path.read_text(encoding="utf-8", errors="replace")

    meta = {"source": f"file://{safe_path.name}"}
    m_url = re.search(r'(?:url gốc|url|source)[:\s]+(https?://[^\s\r\n]+)', content, re.IGNORECASE)
    if m_url:
        meta["source"] = m_url.group(1).strip()
    m_fn = re.search(r'(\d{6,20})', safe_path.name)
    if m_fn:
        meta["job_id"] = m_fn.group(1)
        
    return parse_jd_text(content, source=meta.get("source", f"file://{safe_path.name}"), metadata=meta)

def fetch_jd_url(url: str, timeout: int = 10) -> Dict:
    """
    Fetch JD from a public URL safely without bypassing authentication, captcha, or rate limits.
    Returns clear errors and falls back to manual entry if blocked/login/expired.
    """
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or parsed.scheme not in ["http", "https"]:
        raise ValueError(f"URL không hợp lệ: {url}. Chỉ hỗ trợ giao thức http/https.")
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ai-job-search/1.0 (Job Matching Research)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi,en,ko;q=0.8"
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            html_bytes = response.read(1024 * 512) # Cap at 512KB for safety
            html_content = html_bytes.decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in [401, 403]:
            raise PermissionError(
                f"Truy cập bị chặn (HTTP {e.code}) bởi trang web: {url}. "
                f"Trang web yêu cầu đăng nhập, cookie hoặc có hệ thống chống bot/CAPTCHA. "
                f"Vui lòng copy nội dung JD và sử dụng luồng nhập trực tiếp (manual text hoặc file UTF-8)."
            )
        elif e.code == 404:
            raise FileNotFoundError(f"Trang tin tuyển dụng không tồn tại (HTTP 404): {url}")
        else:
            raise ConnectionError(f"Lỗi máy chủ máy chủ web (HTTP {e.code}) khi tải {url}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise ConnectionError(f"Không thể kết nối đến URL {url}: {e}. Vui lòng kiểm tra lại mạng hoặc chuyển sang nhập thủ công.")

    # Check for login walls, captcha pages, or expired postings
    lower_html = html_content.lower()
    
    # 1. Login wall check
    if any(sig in lower_html for sig in ["sign in to continue", "log in to continue", "đăng nhập để xem", "로그인이 필요합니다"]):
        raise ValueError(
            f"Trang web yêu cầu ĐĂNG NHẬP: Không coi trang đăng nhập là tin tuyển dụng hợp lệ. "
            f"Vui lòng dùng luồng nhập trực tiếp JD."
        )
        
    # 2. CAPTCHA / Bot check
    if any(sig in lower_html for sig in ["cf-browser-verification", "g-recaptcha", "cloudflare-static", "hcaptcha"]):
        raise PermissionError(
            f"Trang web kích hoạt kiểm tra BOT / CAPTCHA: Tuân thủ quy định không né CAPTCHA. "
            f"Vui lòng copy văn bản JD vào file UTF-8 để phân tích."
        )
        
    # 3. Expired job check
    if any(sig in lower_html for sig in ["job expired", "tin tuyển dụng đã hết hạn", "채용마감", "마감된 공고", "this job is closed"]):
        raise ValueError(f"Tin tuyển dụng ĐÃ HẾT HẠN hoặc đã đóng: Không coi tin hết hạn là kết quả hợp lệ.")

    # Clean HTML to plain text
    extractor = HTMLTextExtractor()
    extractor.feed(html_content)
    plain_text = extractor.get_text()
    
    if len(plain_text.strip()) < 50:
        raise ValueError("Nội dung tải về quá ngắn hoặc không chứa mô tả công việc rõ ràng. Vui lòng sử dụng luồng nhập trực tiếp.")
        
    return parse_jd_text(plain_text, source=url)

def deduplicate_jds(jd_list: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Deduplicate a list of JDs based on content hash and (company, title) signature.
    Returns (unique_jds, duplicate_jds).
    """
    seen_hashes = set()
    seen_signatures = set()
    unique_jds = []
    duplicate_jds = []
    
    for jd in jd_list:
        title = jd.get("title", "").strip().lower()
        company = jd.get("company", "").strip().lower()
        
        h = jd.get("hash")
        if not h:
            h = compute_jd_hash(jd.get("title", ""), jd.get("company", ""), jd.get("raw_content", ""))
            jd["hash"] = h
            
        # Signature based on company + title
        has_specific_info = bool(company and title and "chưa rõ" not in company and "chưa rõ" not in title)
        sig = f"{company}:::{title}" if has_specific_info else None
        
        is_dup = (h in seen_hashes) or (sig and sig in seen_signatures)
        
        if is_dup:
            duplicate_jds.append(jd)
        else:
            seen_hashes.add(h)
            if sig:
                seen_signatures.add(sig)
            unique_jds.append(jd)
            
    return unique_jds, duplicate_jds
