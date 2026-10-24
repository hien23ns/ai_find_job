"""
AI Service with Strict Separation between Rules and AI Modes.
Supports Google Gemini API via official REST endpoint using Python standard urllib.
Strictly offline when in rules mode; never transmits OpenAI keys to Google endpoints;
never falsely claims AI success on network error or fallback.
"""

import json
import os
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

from src.security import mask_secrets

SUPPORTED_PROVIDERS = ["gemini"]
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

class AIService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "gemini",
        model: str = DEFAULT_GEMINI_MODEL
    ):
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Provider '{provider}' không được hỗ trợ. Các provider hiện có: {SUPPORTED_PROVIDERS}. "
                f"Tuyệt đối không sử dụng khóa OpenAI hoặc provider khác để gửi sang Google."
            )
        self.provider = provider
        self.model = model
        # Only accept GEMINI_API_KEY for provider 'gemini', never cross-read OPENAI_API_KEY
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.is_configured = bool(self.api_key and self.api_key.strip())

    def analyze_job(
        self,
        jd_text: str,
        candidate_summary: str,
        market: str = "vietnam"
    ) -> Dict[str, Any]:
        """
        Execute AI analysis when explicitly requested and configured.
        Returns explicit status, source, and privacy notification.
        """
        if not self.is_configured:
            return {
                "status": "BLOCKED_NO_API_KEY",
                "mode": "ai_requested_but_blocked",
                "source": "BLOCKED (Thiếu GEMINI_API_KEY)",
                "provider": self.provider,
                "notice": "Chưa cấu hình GEMINI_API_KEY trong môi trường dự án. "
                          "Yêu cầu AI bị chặn để bảo vệ quyền riêng tư và tránh gửi dữ liệu không an toàn.",
                "privacy_note": "100% dữ liệu được giữ an toàn trong PROJECT_ROOT.",
                "antigravity_note": "Trong Antigravity IDE, agent suy luận trực tiếp trong phiên làm việc mà không cần gọi API ngoài."
            }

        try:
            return self._call_online_ai(jd_text, candidate_summary, market)
        except urllib.error.HTTPError as http_err:
            masked_err = mask_secrets(f"HTTPError {http_err.code}: {http_err.reason}")
            return {
                "status": "FAILED_AI_FALLBACK",
                "mode": "fallback_to_rules",
                "source": "Fallback to Rules Engine (Lỗi API AI)",
                "provider": self.provider,
                "error": masked_err,
                "notice": f"Gọi API AI thất bại ({masked_err}). Đã chuyển sang phân tích quy tắc cục bộ.",
                "privacy_note": "Dữ liệu được xử lý cục bộ sau lỗi kết nối."
            }
        except urllib.error.URLError as url_err:
            masked_err = mask_secrets(f"URLError: {url_err.reason}")
            return {
                "status": "FAILED_AI_FALLBACK",
                "mode": "fallback_to_rules",
                "source": "Fallback to Rules Engine (Lỗi kết nối mạng)",
                "provider": self.provider,
                "error": masked_err,
                "notice": f"Kết nối tới máy chủ AI thất bại ({masked_err}). Đã chuyển sang phân tích quy tắc cục bộ.",
                "privacy_note": "Dữ liệu được xử lý cục bộ."
            }
        except Exception as e:
            masked_err = mask_secrets(str(e))
            return {
                "status": "FAILED_AI_FALLBACK",
                "mode": "fallback_to_rules",
                "source": "Fallback to Rules Engine (Lỗi không xác định)",
                "provider": self.provider,
                "error": masked_err,
                "notice": f"Lỗi ngoại lệ khi gọi AI ({masked_err}). Đã chuyển sang phân tích quy tắc cục bộ.",
                "privacy_note": "Dữ liệu được xử lý cục bộ."
            }

    def _call_online_ai(self, jd_text: str, candidate_summary: str, market: str) -> Dict[str, Any]:
        """
        Execute HTTPS POST to Google Gemini REST endpoint.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        prompt = (
            f"Bạn là chuyên gia tư vấn tuyển dụng an ninh mạng tại thị trường {market}.\n"
            f"Tóm tắt ứng viên: {candidate_summary}\n\n"
            f"Nội dung JD: {jd_text[:3000]}\n\n"
            f"Hãy đưa ra 3 lời khuyên kỹ thuật trọng tâm cho ứng viên."
        )
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if not candidates or "content" not in candidates[0]:
                raise ValueError("Phản hồi từ Gemini API không có cấu trúc nội dung hợp lệ.")
            text = candidates[0]["content"]["parts"][0]["text"]
            return {
                "status": "PASS_ONLINE_AI",
                "mode": "ai",
                "source": f"AI (Google Gemini - {self.model})",
                "provider": self.provider,
                "model": self.model,
                "ai_advice": text,
                "sent_data_summary": f"Tóm tắt hồ sơ ({len(candidate_summary)} ký tự), Trích đoạn JD ({min(len(jd_text), 3000)} ký tự)",
                "privacy_note": "CẢNH BÁO QUYỀN RIÊNG TƯ: Dữ liệu tóm tắt hồ sơ và JD đã được gửi qua HTTPS tới máy chủ Google Gemini."
            }
