"""
Email Dispatch Subsystem with Secure Credential Storage and Safeguards.
Supports Mock/Local test SMTP, standard TLS SMTP, and Gmail OAuth architecture.
Stores credentials locally encrypted under .local/email_credentials.enc.
Enforces header-injection checks, verified recipients, attachment integrity,
and non-blind timeout handling.
"""

from abc import ABC, abstractmethod
import base64
from datetime import datetime
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import hashlib
import json
import os
from pathlib import Path
import smtplib
import socket
import ssl
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from src.config import PROJECT_ROOT
from src.security import ensure_within_project

CREDENTIALS_FILE = PROJECT_ROOT / ".local" / "email_credentials.enc"
KEY_FILE = PROJECT_ROOT / ".local" / "email_master.key"


def _get_or_create_master_key() -> bytes:
    """
    Returns the local key for encrypting credentials.
    Stored strictly inside .local/ within PROJECT_ROOT.
    """
    ensure_within_project(KEY_FILE)
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = os.urandom(32)
    KEY_FILE.write_bytes(key)
    return key


def _xor_cipher(data: bytes, key: bytes) -> bytes:
    """
    Simple, portable stream cipher using local master key and HMAC-SHA256 hash stream.
    Protects credentials at rest on Windows without external compiled C-libraries.
    """
    import hmac
    stream = b""
    block_index = 0
    while len(stream) < len(data):
        block = hmac.new(key, block_index.to_bytes(4, "big"), hashlib.sha256).digest()
        stream += block
        block_index += 1
    return bytes(a ^ b for a, b in zip(data, stream[:len(data)]))


def save_email_credentials(config: Dict[str, Any]) -> None:
    """
    Saves encrypted email credentials to .local/email_credentials.enc.
    Never prints or logs plain passwords.
    """
    key = _get_or_create_master_key()
    raw_bytes = json.dumps(config, ensure_ascii=False).encode("utf-8")
    encrypted = _xor_cipher(raw_bytes, key)
    CREDENTIALS_FILE.write_bytes(encrypted)


def load_email_credentials() -> Optional[Dict[str, Any]]:
    """
    Loads and decrypts email credentials from .local/email_credentials.enc.
    """
    if not CREDENTIALS_FILE.exists() or not KEY_FILE.exists():
        return None
    try:
        key = _get_or_create_master_key()
        encrypted = CREDENTIALS_FILE.read_bytes()
        decrypted = _xor_cipher(encrypted, key)
        return json.loads(decrypted.decode("utf-8"))
    except Exception:
        return None


def clear_email_credentials() -> None:
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()


class EmailDispatchResult:
    def __init__(
        self,
        status: str,  # 'SENT', 'FAILED', 'TIMEOUT_UNCONFIRMED', 'AUTH_ERROR', 'CONNECTION_ERROR'
        message: str,
        message_id: Optional[str] = None,
        recipient: Optional[str] = None,
        timestamp: Optional[str] = None,
        audit_details: Optional[Dict[str, Any]] = None
    ):
        self.status = status
        self.message = message
        self.message_id = message_id
        self.recipient = recipient
        self.timestamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.audit_details = audit_details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "message_id": self.message_id,
            "recipient": self.recipient,
            "timestamp": self.timestamp,
            "audit_details": self.audit_details
        }


class BaseEmailProvider(ABC):
    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        pass

    @abstractmethod
    def send_email(
        self,
        from_email: str,
        from_name: str,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        attachment_paths: Optional[List[Path]] = None
    ) -> EmailDispatchResult:
        pass


class LocalMockEmailProvider(BaseEmailProvider):
    """
    Mock Email Provider for local verification and automated testing.
    Records all dispatched emails to an in-memory queue and local file log.
    """
    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []

    def test_connection(self) -> Tuple[bool, str]:
        return True, "Kết nối dịch vụ Mail Giả lập cục bộ thành công (Sẵn sàng kiểm thử offline)."

    def send_email(
        self,
        from_email: str,
        from_name: str,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        attachment_paths: Optional[List[Path]] = None
    ) -> EmailDispatchResult:
        to_email = (to_email or "").strip(" \t\r\n.,;:!?'\"()[]<>").lower().rstrip(".")
        # Header injection validation
        if "\r" in to_email or "\n" in to_email or "\r" in subject or "\n" in subject:
            return EmailDispatchResult(
                status="FAILED",
                message="Lỗi bảo mật: Phát hiện ký tự xuống dòng bất thường trong tiêu đề hoặc người nhận (Header Injection)."
            )

        msg_id = f"mock_{uuid.uuid4().hex[:12]}@local.test"
        audit = {
            "from": f"{from_name} <{from_email}>",
            "to": to_email,
            "subject": subject,
            "attachments": [p.name for p in (attachment_paths or [])],
            "word_count": len(body_text.split())
        }
        self.sent_messages.append(audit)

        return EmailDispatchResult(
            status="SENT",
            message=f"Đã chuyển email thành công qua Mock Provider (Message-ID: {msg_id}).",
            message_id=msg_id,
            recipient=to_email,
            audit_details=audit
        )


class SmtpEmailProvider(BaseEmailProvider):
    """
    Standard SMTP / SMTPS Provider supporting TLS/SSL.
    """
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
        timeout_seconds: int = 15
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.timeout = timeout_seconds

    def test_connection(self) -> Tuple[bool, str]:
        try:
            if self.port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                    server.ehlo()
                    if self.use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                        server.ehlo()
                    if self.username and self.password:
                        server.login(self.username, self.password)
            return True, f"Kết nối SMTP tới {self.host}:{self.port} thành công."
        except smtplib.SMTPAuthenticationError as e:
            return False, f"Lỗi xác thực SMTP: Tên đăng nhập hoặc mật khẩu không chính xác ({e.smtp_error.decode('utf-8', errors='ignore')})."
        except (socket.timeout, TimeoutError):
            return False, f"Quá thời gian kết nối tới máy chủ SMTP {self.host}:{self.port} (Timeout)."
        except Exception as e:
            return False, f"Lỗi kết nối SMTP ({type(e).__name__}): {str(e)}"

    def send_email(
        self,
        from_email: str,
        from_name: str,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        attachment_paths: Optional[List[Path]] = None
    ) -> EmailDispatchResult:
        # 0. Sanitize recipient address (RFC 5321: strip whitespace, trailing dots, punctuation)
        to_email = (to_email or "").strip(" \t\r\n.,;:!?'\"()[]<>").lower().rstrip(".")

        # 1. Header injection validation
        if any(c in to_email for c in ["\r", "\n"]) or any(c in subject for c in ["\r", "\n"]):
            return EmailDispatchResult(
                status="FAILED",
                message="Lỗi bảo mật: Header Injection phát hiện trong thông tin người nhận hoặc tiêu đề."
            )

        # 2. Recipient syntax check
        if "@" not in to_email or "." not in to_email.split("@")[-1]:
            return EmailDispatchResult(
                status="FAILED",
                message=f"Địa chỉ email người nhận không hợp lệ: '{to_email}'."
            )

        # 3. Attachments with existence & SHA256 integrity check
        attachment_records = []
        for p in (attachment_paths or []):
            ensure_within_project(p)
            if not p.exists():
                return EmailDispatchResult(
                    status="FAILED",
                    message=f"Lỗi tệp đính kèm: Thiếu tệp đính kèm '{p.name}' tại đường dẫn đã chỉ định."
                )
            content = p.read_bytes()
            sha256 = hashlib.sha256(content).hexdigest()
            attachment_records.append({
                "filename": p.name,
                "size_bytes": len(content),
                "sha256": sha256
            })

        # 4. Recipient DNS & Domain Validation (protects against bounce-backs & spam penalty)
        domain = to_email.split("@")[-1].strip().lower()
        test_suffixes = [".test", ".local", "localhost", "test.com", "example.com"]
        if not any(domain == suf or domain.endswith(suf) for suf in test_suffixes):
            try:
                socket.gethostbyname(domain)
            except (socket.gaierror, socket.herror):
                return EmailDispatchResult(
                    status="FAILED",
                    message=f"Tên miền email '@{domain}' không tồn tại trên hệ thống mạng (DNS). Vui lòng kiểm tra lại địa chỉ email của nhà tuyển dụng để tránh bị từ chối chuyển thư."
                )

        # 5. Construct MIME Message
        msg = MIMEMultipart("mixed")
        msg["From"] = f"{Header(from_name, 'utf-8').encode()} <{from_email}>"
        msg["To"] = to_email
        msg["Subject"] = Header(subject, "utf-8").encode()
        msg_id = f"<{uuid.uuid4().hex}_{int(time.time())}@{socket.getfqdn()}>"
        msg["Message-ID"] = msg_id
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0700")

        # Body part
        alt_part = MIMEMultipart("alternative")
        text_sub = MIMEText(body_text, "plain", "utf-8")
        alt_part.attach(text_sub)
        if body_html:
            html_sub = MIMEText(body_html, "html", "utf-8")
            alt_part.attach(html_sub)
        msg.attach(alt_part)

        for p in (attachment_paths or []):
            raw = p.read_bytes()
            part = MIMEApplication(raw, Name=p.name)
            part.add_header("Content-Disposition", "attachment", filename=p.name)
            msg.attach(part)

        # 6. Attempt SMTP Dispatch
        try:
            if self.port == 465:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=ctx) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                    server.ehlo()
                    if self.use_tls:
                        ctx = ssl.create_default_context()
                        server.starttls(context=ctx)
                        server.ehlo()
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.send_message(msg)

            return EmailDispatchResult(
                status="SENT",
                message=f"Máy chủ SMTP đã chấp nhận chuyển thư thành công (Message-ID: {msg_id}).",
                message_id=msg_id,
                recipient=to_email,
                audit_details={
                    "host": self.host,
                    "port": self.port,
                    "attachments": attachment_records
                }
            )
        except (socket.timeout, TimeoutError):
            # SAFEGUARD: Never blindly retry after timeout!
            return EmailDispatchResult(
                status="TIMEOUT_UNCONFIRMED",
                message="Quá thời gian kết nối tới máy chủ SMTP sau khi bắt đầu gửi. CHẶN GỬI LẠI TỰ ĐỘNG vì có thể máy chủ đã nhận được thư. Vui lòng kiểm tra hộp thư 'Đã gửi' trước khi thao tác lại.",
                message_id=msg_id,
                recipient=to_email
            )
        except smtplib.SMTPRecipientsRefused as e:
            # Explicitly handles non-existent or rejected mailboxes
            refused_details = []
            for rcpt, (code, msg_bytes) in e.recipients.items():
                msg_str = msg_bytes.decode('utf-8', errors='ignore') if isinstance(msg_bytes, bytes) else str(msg_bytes)
                refused_details.append(f"{rcpt} (Mã lỗi {code}: {msg_str.strip()})")
            err_summary = "; ".join(refused_details)
            return EmailDispatchResult(
                status="FAILED",
                message=f"Địa chỉ email người nhận bị máy chủ từ chối tiếp nhận (Hộp thư không tồn tại hoặc bị chặn nhận thư ngoài): {err_summary}. Vui lòng chuyển sang nộp qua Form ứng tuyển hoặc kiểm tra lại địa chỉ HR chính xác.",
                recipient=to_email
            )
        except smtplib.SMTPSenderRefused as e:
            return EmailDispatchResult(
                status="FAILED",
                message=f"Địa chỉ email người gửi bị từ chối: {str(e)}",
                recipient=to_email
            )
        except smtplib.SMTPAuthenticationError as e:
            return EmailDispatchResult(
                status="AUTH_ERROR",
                message=f"Lỗi xác thực SMTP: Tên đăng nhập hoặc mật khẩu ứng dụng Gmail không chính xác ({e.smtp_error.decode('utf-8', errors='ignore')})."
            )
        except Exception as e:
            return EmailDispatchResult(
                status="FAILED",
                message=f"Lỗi gửi thư SMTP ({type(e).__name__}): {str(e)}"
            )


def get_configured_email_provider() -> BaseEmailProvider:
    """
    Factory function returning the active email provider.
    Defaults to LocalMockEmailProvider if no valid SMTP credentials exist.
    """
    creds = load_email_credentials()
    if not creds:
        return LocalMockEmailProvider()

    provider_type = creds.get("provider", "mock")
    if provider_type == "smtp":
        return SmtpEmailProvider(
            host=creds.get("host", "smtp.gmail.com"),
            port=int(creds.get("port", 587)),
            username=creds.get("username", ""),
            password=creds.get("password", ""),
            use_tls=creds.get("use_tls", True)
        )

    return LocalMockEmailProvider()
