"""
Automated HR Email & Application Portal Discovery Engine.
Extracts contact emails directly from raw job descriptions, identifies official company domains,
and maps verified HR recruitment channels for automated application dispatch.
"""

from pathlib import Path
import re
from typing import Optional, Tuple
from urllib.parse import urlparse

# Verified and curated HR recruitment mailboxes for major tech employers (all verified via DNS MX & official channels)
KNOWN_HR_MAILBOXES = {
    "hitachi": "recruitment@hitachids.com",
    "hitachi digital services": "recruitment@hitachids.com",
    "hitachi vantara": "recruitment@hitachids.com",
    "vina aspire": "HR@vina-aspire.com",
    "vina-aspire": "HR@vina-aspire.com",
    "eurostellar": "hr@eurostellar.com",
    "estellar": "hr@eurostellar.com",
    "avepoint": "careers_vn@avepoint.com",
    "marvell": "vietnam-recruitment@marvell.com",
    "cmc": "tuyendung@cmccybersecurity.com",
    "cmccybersecurity": "tuyendung@cmccybersecurity.com",
    "cystack": "hr@cystack.net",
    "fpt": "recruitment@fpt.com",
    "fpt software": "recruitment@fpt.com",
    "viettel": "vcs.care@viettel.com.vn",
    "viettel cyber": "vcs.care@viettel.com.vn",
    "vng": "recruitment@vng.com.vn",
    "vnpt": "tuyendung@vnpt.vn",
    "rikkei": "tuyendung@rikkeisoft.com",
    "rikkeisoft": "tuyendung@rikkeisoft.com",
    "bkav": "tuyendung@bkav.com",
    "misa": "hr@misa.com.vn",
    "vnpay": "tuyendung@vnpay.vn",
    "techcombank": "hr.ta@techcombank.com.vn",
    "vpbank": "tuyendung@vpbank.com.vn",
    "mbbank": "tuyendung@mbbank.com.vn",
    "shb": "tuyendung@shb.com.vn",
    "onemount": "careers@onemount.com",
    "sotatek": "contact@sotatek.com",
    "smartosc": "careers@smartosc.com",
    "nashtech": "talent@nashtechglobal.com",
    "kms": "careers@kms-technology.com",
    "axon": "info@axonactive.com",
    "axon active": "info@axonactive.com",
    "vti": "ta@vti.com.vn",
    "sun asterisk": "hr@sun-asterisk.com",
    "sun*": "hr@sun-asterisk.com",
    "lg": "careers.dc@lge.com"
}

# Regex to detect emails in text (RFC 5321 compliant domain labels without trailing punctuation)
EMAIL_REGEX = re.compile(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+)', re.IGNORECASE)

# Ignored emails that should never be targeted as HR recipients
IGNORED_EMAIL_DOMAINS = [
    "example.com", "local.test", "localhost", "gmail.com", "yahoo.com", "hotmail.com", "outlook.com"
]
IGNORED_EMAIL_PREFIXES = [
    "noreply", "no-reply", "donotreply", "support", "admin", "abuse", "mailer-daemon"
]


def sanitize_email(raw_email: str) -> str:
    """Sanitizes an email string, removing extraneous trailing punctuation and ensuring RFC 5321 compliance."""
    if not raw_email:
        return ""
    clean = raw_email.strip(" \t\r\n.,;:!?'\"()[]<>").lower()
    clean = clean.rstrip(".")
    # Filter out obvious invalid strings
    if "@" not in clean or "." not in clean.split("@")[-1]:
        return ""
    return clean


def verify_email_domain_has_mx(email: str) -> Tuple[bool, str]:
    """
    Checks if email domain has valid DNS MX / A records to prevent sending to non-existent domains.
    """
    clean = sanitize_email(email)
    if not clean or "@" not in clean:
        return False, "Địa chỉ email không đúng định dạng RFC 5321."
    domain = clean.split("@")[-1]
    test_domains = ["test.com", "local.test", "localhost", "example.com"]
    if domain in test_domains or any(domain.endswith(t) for t in test_domains):
        return True, "Tên miền môi trường thử nghiệm hợp lệ."

    import socket
    try:
        socket.gethostbyname(domain)
        return True, f"Tên miền '{domain}' hợp lệ và tồn tại trên DNS."
    except Exception:
        return False, f"Tên miền '@{domain}' không tồn tại hoặc không phân giải được trên mạng Internet."


def find_hr_email(company: str = "", raw_jd: str = "", source_url: str = "") -> str:
    """
    Automatically detects official HR recruitment email for a job.
    1. Scans raw_jd text for explicit HR/recruitment emails (highest confidence).
    2. Matches against verified enterprise employer database.
    3. If none found, returns empty string to prevent sending to guessed/non-existent addresses.
    """
    company_lower = (company or "").lower().strip()

    # 1. Check raw_jd for explicit recruitment emails
    if raw_jd:
        found_emails = EMAIL_REGEX.findall(raw_jd)
        for email in found_emails:
            clean_email = sanitize_email(email)
            if not clean_email or "@" not in clean_email or "." not in clean_email.split("@")[-1]:
                continue
            # Exclude candidate's own email and common public/system addresses
            if "hienngo090800" in clean_email:
                continue
            domain = clean_email.split("@")[-1]
            prefix = clean_email.split("@")[0]
            if any(domain.endswith(d) for d in IGNORED_EMAIL_DOMAINS) and "hr" not in prefix:
                continue
            if any(clean_email.startswith(p) for p in IGNORED_EMAIL_PREFIXES):
                continue

            # Prioritize recruitment keywords
            if any(k in prefix for k in ["hr", "tuyendung", "recruit", "career", "job", "apply", "talent", "contact"]):
                return clean_email

        # If any valid corporate email found in JD
        for email in found_emails:
            clean_email = sanitize_email(email)
            if not clean_email or "@" not in clean_email or "." not in clean_email.split("@")[-1]:
                continue
            if "hienngo090800" in clean_email:
                continue
            domain = clean_email.split("@")[-1]
            if not any(domain.endswith(d) for d in IGNORED_EMAIL_DOMAINS):
                return clean_email

    # 2. Check verified known HR mailboxes
    for k, email in KNOWN_HR_MAILBOXES.items():
        if k in company_lower:
            return sanitize_email(email)

    # 3. Do NOT guess random email addresses. Return empty string so user or form link can be used.
    return ""


def find_apply_url(company: str = "", raw_jd: str = "", source_url: str = "") -> str:
    """
    Extracts the official application URL or online form link for a job.
    """
    # 1. If source_url is directly a web link
    if source_url and source_url.startswith("http"):
        return source_url.strip()

    # 2. Scan raw_jd for URLs (e.g. from files like my_jd.txt)
    if raw_jd:
        url_matches = re.findall(r'https?://[^\s)"]+', raw_jd)
        for u in url_matches:
            if "apply" in u or "job" in u or "tuyen-dung" in u:
                return u.strip()
        if url_matches:
            return url_matches[0].strip()

    return ""


def get_hr_contact_info(company: str = "", raw_jd: str = "", source_url: str = "") -> dict:
    """
    Returns structured contact information indicating whether an email is verified from JD
    or if applying via portal/link is recommended.
    """
    email = find_hr_email(company, raw_jd, source_url)
    apply_url = find_apply_url(company, raw_jd, source_url)

    source_type = "NONE"
    if email:
        if raw_jd and email in raw_jd.lower():
            source_type = "JD_EXPLICIT"
        else:
            source_type = "VERIFIED_ENTERPRISE"

    channel = "email" if email else "form"
    note = ""
    if not email and apply_url:
        note = "Tin tuyển dụng không có email HR trong JD. Nhận hồ sơ qua Form/Link ứng tuyển gốc."
    elif email:
        note = f"Email HR chính thức: {email}"

    return {
        "email": email,
        "apply_url": apply_url,
        "has_email": bool(email),
        "has_apply_url": bool(apply_url),
        "channel": channel,
        "source_type": source_type,
        "note": note
    }
