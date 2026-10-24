# KẾ HOẠCH TRIỂN KHAI VÀ CHECKLIST NGHIỆM THU (IMPLEMENTATION PLAN)

Dự án: **ai-job-search (ai-find-job)**  
Môi trường thực thi: **Windows 11 / PowerShell / Antigravity IDE**  
Thư mục gốc chuẩn hóa (`PROJECT_ROOT`): `C:\Users\Lenovo\Downloads\ai-find-job`  
Runtime: **Python 3.11.9** (Standard Library, Zero-external-dependency core)  
Upstream Repository: `https://github.com/ai-job-search-dev/ai-job-search.git` lưu tại [`upstream/`](../upstream/) (Commit `e16acee3abdaae57f8026789338a3c6eebf4608b`, Giấy phép MIT)

---

## 1. MỤC TIÊU VÀ PHẠM VI DỰ ÁN

Hệ thống được thiết kế để hoạt động hoàn toàn cục bộ trong `PROJECT_ROOT`, không xâm lấn hệ thống, tuân thủ nghiêm ngặt các nguyên tắc bảo mật, quyền riêng tư và tính trung thực học thuật/hồ sơ:
1. **Liên kết và tuân thủ Upstream:** Tích hợp mã nguồn upstream vào thư mục `upstream/`, bảo toàn quy tắc bảo mật chuỗi cung ứng `tools/security_guards.py` và kiến trúc Thin-Pointer `AGENTS.md`.
2. **Ba phân hệ thị trường:**
   - **Việt Nam:** Vị trí Security Intern, SOC Intern, SOC Analyst L1, Network Security Intern, Network Engineer Junior; tiền tệ VND.
   - **Hàn Quốc:** Vị trí 정보보안, 정보보호, 보안관제, 취약점 진단, 모의해킹; bóc tách độc lập ngôn ngữ, visa cư trú (nếu không nêu thì ghi "Chưa rõ", không suy diễn); tiền tệ KRW.
   - **Freelance:** Dự án mạng, quản trị Linux, xử lý log bằng Python, giám sát an ninh có ủy quyền; đánh giá rủi ro pháp lý/thẩm quyền, mốc giao hàng; tiền tệ USD.
3. **Sinh tài liệu & Luyện phỏng vấn:** CV Markdown, Thư ứng tuyển, Đề xuất Freelance, Kịch bản phỏng vấn kỹ thuật và xuất file HTML độc lập có CSS in ấn chuẩn.
4. **Theo dõi (Tracker):** Quản lý trạng thái ứng tuyển JSON/CSV; phân tách rạch ròi dữ liệu kiểm thử và dữ liệu người dùng thật.
5. **Tương thích Antigravity:** Tích hợp kỹ năng [`.agents/skills/ai-job-search/SKILL.md`](../.agents/skills/ai-job-search/SKILL.md) và thực thi kiểm chứng đầu-cuối qua Antigravity tools.

---

## 2. BẢNG NGHIỆM THU TRUNG THỰC (ACCEPTANCE MATRIX)

*Quy ước trạng thái đơn nhất:*
- **PASS:** Đã chạy thực tế trong môi trường và có file bằng chứng (`docs/evidence/`).
- **FAIL:** Đã phát hiện lỗi và chưa khắc phục.
- **BLOCKED:** Bị chặn do điều kiện bên ngoài (WAF/Anti-bot trang web, thiếu API key của bên thứ ba).
- **NOT TESTED:** Chưa được kiểm chứng trong phạm vi phiên làm việc hiện tại.

| Hạng mục kiểm tra | Chế độ / Phạm vi | Trạng thái | Bằng chứng thực tế tại repo |
|---|---|:---:|---|
| **1. Xác minh Upstream Repository** | Kiểm tra mã nguồn, commit, license | **PASS** | [`docs/evidence/upstream_verification.txt`](evidence/upstream_verification.txt) |
| **2. Upstream Security Guards** | `python upstream/tools/security_guards.py` | **PASS** | [`docs/evidence/upstream_verification.txt`](evidence/upstream_verification.txt) |
| **3. Upstream Test Suite (836 tests)** | `python -m unittest discover` | **PASS** | [`docs/evidence/upstream_verification.txt`](evidence/upstream_verification.txt) (805 OK, 31 skip, 0 fail) |
| **4. Bộ Test tự động Dự án (21 tests)** | Khởi chạy qua Python 3.11 Windows | **PASS** | `python -m unittest tests.test_all` (21/21 OK, 0.524s) |
| **5. Cầu nối Upstream (job_key & guards)** | `src/upstream_bridge.py` | **PASS** | `test_19`, `test_20`, `test_21` PASS; sinh canonical key chuẩn hóa |
| **6. Đánh giá JD Việt Nam (CyStack Live)** | Động cơ quy tắc cục bộ (0-100) | **PASS** | [`docs/evidence/e2e_integration_run.txt`](evidence/e2e_integration_run.txt) (95/100, NÊN ỨNG TUYỂN) |
| **7. Đánh giá JD Hàn Quốc (Toss Live)** | Bóc tách Visa/Ngôn ngữ ("Chưa rõ") | **PASS** | [`docs/evidence/e2e_integration_run.txt`](evidence/e2e_integration_run.txt) (73/100, NÊN ỨNG TUYỂN) |
| **8. Đánh giá JD Freelance (Task #710 Live)** | Rủi ro thẩm quyền & Đề xuất mốc | **PASS** | [`docs/evidence/e2e_integration_run.txt`](evidence/e2e_integration_run.txt) (100/100, NÊN ỨNG TUYỂN) |
| **9. Lọc trùng tin tuyển dụng (Deduplication)** | Băm SHA-256 + canonical slug | **PASS** | `test_09` PASS, lệnh `python -m src.cli deduplicate` |
| **10. Tải URL tuyển dụng công ty (CyStack/Toss)** | Endpoint công khai có thể đối chiếu | **PASS** | `fetch_jd_url` thành công tải 3.947 ký tự (CyStack) và dữ liệu Toss |
| **11. Tải URL qua cổng việc làm (TopCV/Saramin)** | Cổng việc làm có chống bot / WAF | **BLOCKED** | HTTP 403 Forbidden / 404 (Hệ thống an toàn chuyển nhập tay) |
| **12. Kết nối AI LLM trực tuyến (Gemini/OpenAI)** | Gọi API bên ngoài qua mạng | **UNVERIFIED_OPTIONAL** | Tùy chọn chưa cấu hình API key; Fallback Offline 100% |
| **13. Antigravity Native AI Workflow** | Phân tích & sinh tài liệu trực tiếp | **PASS** | Agent thực thi luồng qua `.agents/skills/ai-job-search/` |
| **14. Sinh hồ sơ Markdown (CV, Letter, Prop)** | Không bịa đặt kinh nghiệm/chứng chỉ | **PASS** | Đã tạo và đối soát trực tiếp các file tại [`output/`](../output/) |
| **15. Xuất HTML độc lập (In PDF qua browser)** | Mở bằng trình duyệt để in (Ctrl+P) | **PASS** | Đã xuất các file `.html` có CSS `@media print` |
| **16. Kiểm tra bố cục in trực quan / PDF nhị phân** | Kiểm tra trực quan bằng mắt người | **NOT TESTED** | Chưa kiểm tra trực quan bố cục trang in; không cam kết bố cục đẹp |
| **17. Quản lý Tracker ứng tuyển (JSON/CSV)** | Cách ly dữ liệu test và dữ liệu thật | **PASS** | `data/tracker/jobs_tracker.json` giữ sạch 0 jobs; test dùng file riêng |
| **18. Chống Path Traversal & Prompt Injection** | Bảo vệ filesystem & làm sạch dữ liệu | **PASS** | Test 12, 13, 16 PASS; trung hòa chỉ thị injection và path traversal |
