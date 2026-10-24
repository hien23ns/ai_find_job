"""
Security controls and constraints.
- Path Traversal prevention (strictly confined to PROJECT_ROOT)
- Platform-aware boundary checking (Windows & POSIX)
- Untrusted content sanitization (Prompt Injection neutralization)
- Secret masking in logs without regex group reference errors
"""

import os
from pathlib import Path
import re
import sys
from typing import Union
from src.config import PROJECT_ROOT

PROMPT_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous|above)\s+instructions",
    r"(?i)disregard\s+(all\s+)?(previous|above)\s+instructions",
    r"(?i)you\s+are\s+now\s+(an?\s+)?unrestricted",
    r"(?i)system\s*:\s*you\s+must",
    r"(?i)system\s+prompt\s+override",
    r"(?i)<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
    r"(?i)curl\s+https?://",
    r"(?i)powershell\s+-enc",
    r"(?i)rmdir\s+/s\s+/q",
    r"(?i)drop\s+table\b",
]

def ensure_within_project(target_path: Union[str, Path], root: Path = PROJECT_ROOT) -> Path:
    """
    Ensure the path is strictly within root (PROJECT_ROOT).
    Raises PermissionError if path attempts to escape or points outside.
    Supports both Windows and POSIX path semantics safely.
    """
    resolved_root = root.resolve()
    
    if isinstance(target_path, str):
        # Platform-aware check: Windows drive on non-Windows, or absolute POSIX path on Windows
        if re.match(r"^[a-zA-Z]:[/\\]", target_path):
            if sys.platform != "win32":
                raise PermissionError(
                    f"BẢO MẬT: Đường dẫn ổ đĩa Windows '{target_path}' nằm ngoài phạm vi PROJECT_ROOT ('{resolved_root}')."
                )
        elif target_path.startswith("/") and sys.platform == "win32":
            raise PermissionError(
                f"BẢO MẬT: Đường dẫn POSIX tuyệt đối '{target_path}' nằm ngoài phạm vi PROJECT_ROOT ('{resolved_root}')."
            )
        target_path = Path(target_path)
    
    # If path is relative, resolve it relative to root
    if not target_path.is_absolute():
        resolved = (root / target_path).resolve()
    else:
        resolved = target_path.resolve()
        
    # Check if resolved path is root or inside root
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        raise PermissionError(
            f"BẢO MẬT: Đường dẫn '{resolved}' nằm ngoài phạm vi PROJECT_ROOT ('{resolved_root}'). "
            f"Mọi thao tác ngoài thư mục dự án bị nghiêm cấm!"
        )
        
    return resolved

def sanitize_untrusted_text(text: str) -> str:
    """
    Sanitize text input from external JDs or untrusted files.
    Neutralizes prompt injection directives and cleans hazardous control characters.
    """
    if not text:
        return ""
        
    # Remove null bytes and non-printable terminal control sequences (except standard whitespace/newlines)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    
    # Detect and neutralize prompt injection attempts
    neutralized = cleaned
    for pattern in PROMPT_INJECTION_PATTERNS:
        matches = re.findall(pattern, neutralized)
        if matches:
            neutralized = re.sub(
                pattern,
                lambda m: f"[NEUTRALIZED_UNTRUSTED_INSTRUCTION: {m.group(0)}]",
                neutralized
            )
            
    return neutralized

def mask_secrets(text: str) -> str:
    """
    Mask potential secrets, API keys, and credentials in log outputs.
    Ensures safe handling without invalid regex group references (\1 errors).
    """
    if not text:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return "[UNMASKABLE_CONTENT]"

    masked = text

    # 1. Key-value assignment patterns: (key_name)(separator)(quote?)(value)(closing_quote?)
    kv_pattern = r"(?i)\b(api[_-]?key|secret|token|password|bearer|auth[_-]?token)\s*([:=])\s*(['\"]?)([a-zA-Z0-9_\-\.]{8,})(\3)"
    def _mask_kv(m):
        prefix = m.group(1)
        sep = m.group(2)
        quote = m.group(3)
        closing_quote = m.group(5)
        return f"{prefix}{sep} {quote}[PROTECTED_SECRET]{closing_quote}"

    try:
        masked = re.sub(kv_pattern, _mask_kv, masked)
    except Exception:
        pass

    # 2. Standalone tokens with known prefixes (never uses backreferences in replacement)
    # GitHub personal access tokens
    masked = re.sub(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b", "[PROTECTED_TOKEN]", masked)
    # Generic sk- tokens (OpenAI, etc.)
    masked = re.sub(r"\bsk-[a-zA-Z0-9]{16,}\b", "[PROTECTED_TOKEN]", masked)
    # Google API keys (AIza...)
    masked = re.sub(r"\bAIza[0-9A-Za-z\-_]{30,}\b", "[PROTECTED_TOKEN]", masked)
    # Bearer tokens: Bearer <token>
    masked = re.sub(r"(?i)\b(bearer\s+)([a-zA-Z0-9_\-\.]{12,})\b", r"\g<1>[PROTECTED_TOKEN]", masked)

    return masked
