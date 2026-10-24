# TÍCH HỢP UPSTREAM VÀ THAY ĐỔI MÃ NGUỒN (UPSTREAM INTEGRATION)

Dự án: **ai-job-search (ai-find-job)**  
Phiên bản: **1.0.0-windows-antigravity**  
Ngày cập nhật: **2026-10-24 13:14:00**

---

## 1. THÔNG TIN KHO NGUỒN GỐC (CANONICAL UPSTREAM)

- **Kho nguồn (Repository):** `https://github.com/ai-job-search-dev/ai-job-search.git`
- **Commit được ghim (Pinned Commit):** `e16acee3abdaae57f8026789338a3c6eebf4608b`
- **Giấy phép (License):** MIT License
- **Vị trí lưu trữ trong dự án:** `PROJECT_ROOT/upstream/`
- **Tình trạng kiểm thử upstream:**
  - `python -m unittest discover -s upstream/tests -p "test_*.py"`: **836 tests** (805 passed, 31 skipped, 0 failed, thời gian: 94.8s).
  - `python upstream/tools/security_guards.py`: **PASS** (`security_guards: OK (permissions allowlist, hooks allowlist, gitignore rules, package manifests, no tracked node_modules, skill/command allowed-tools, agent tools)`).

---

## 2. KIẾN TRÚC THIN-POINTER VÀ DANH SÁCH THAY ĐỔI / TÍCH HỢP

Nhằm ngăn chặn sự phân mảnh giữa các môi trường runtime (Antigravity, Claude Code, Cursor) và đảm bảo tính an toàn chuỗi cung ứng, dự án triển khai mô hình **Thin-Pointer Architecture**:

### A. Tích hợp trực tiếp mã nguồn Upstream:
1. **`src/upstream_bridge.py`:**
   - Kết nối trực tiếp vào `upstream/tools/job_key.py`: Sử dụng hàm `make_key(company, title, url)` để tạo slug chuẩn hóa chống trùng lặp dữ liệu (Deduplication Key). Thuật toán xử lý an toàn cả tên công ty/vị trí bằng tiếng Latin lẫn tiếng Hàn (Hangul) hoặc các bảng mã đặc thù thông qua băm SHA-1 fallback.
   - Kết nối vào `upstream/tools/security_guards.py`: Tự động gọi kiểm tra bảo vệ chuỗi cung ứng trước khi phân tích hồ sơ.
   - Đối chiếu cấu trúc hồ sơ Thin-Pointer theo chuẩn `upstream/CLAUDE.md`.
2. **`src/tracker.py`:**
   - Tích hợp `get_canonical_job_key()` để gán nhãn `canonical_key` thống nhất cho mọi bản ghi theo dõi, đảm bảo tương thích 100% với định dạng dữ liệu `seen_jobs.json` của upstream.
3. **`src/cli.py`:**
   - Bổ sung 3 lệnh CLI quản lý upstream:
     * `python -m src.cli upstream-info`: Xem thông tin tích hợp và commit ghim.
     * `python -m src.cli upstream-key --company <C> --title <T>`: Sinh khóa canonical.
     * `python -m src.cli upstream-verify`: Chạy kiểm tra an toàn chuỗi cung ứng.
4. **`tests/test_all.py`:**
   - Bổ sung 3 ca kiểm thử tự động xác minh upstream: `test_19_upstream_bridge_canonical_key`, `test_20_upstream_bridge_security_guards`, `test_21_candidate_thin_pointer_schema`.

### B. Lớp mở rộng chuyên biệt cho An ninh mạng (Security Extension):
1. **Động cơ đánh giá 3 thị trường (`src/evaluator.py`):**
   - **Việt Nam:** Vị trí SOC Analyst Intern, Security Intern, Network Engineer Junior (Tiền tệ: VND).
   - **Hàn Quốc:** Vị trí 신입/인턴 정보보안, 보안관제; phân lập nghiêm ngặt điều kiện Visa/Ngôn ngữ (Tiền tệ: KRW; nếu JD không nêu thì trả về "Chưa rõ", không tự suy đoán).
   - **Freelance:** Dự án mạng, quản trị Linux, xử lý log bằng Python, giám sát an ninh (Tiền tệ: USD/VND; yêu cầu ủy quyền chính thức; không tự áp đặt % thanh toán khi chưa thỏa thuận).
2. **Động cơ chống tấn công & Bảo vệ dữ liệu (`src/security.py`):**
   - Giới hạn cứng filesystem boundary (`ensure_within_project`).
   - Trung hòa Prompt Injection (`sanitize_untrusted_text`).
3. **Sinh hồ sơ & Kịch bản phỏng vấn (`src/generator.py`):**
   - Sinh CV Markdown, Thư ứng tuyển, Đề xuất Freelance, Kịch bản câu hỏi phỏng vấn kỹ thuật.
   - Xuất file HTML độc lập có CSS `@media print` sẵn sàng in ấn từ trình duyệt.
4. **Cách ly dữ liệu kiểm thử & Dữ liệu thật (`src/tracker.py`, `src/cli.py`):**
   - Toàn bộ lệnh demo/fixture được định tuyến vào `.local/temp/demo_tracker.json`.
   - File tracker thật `data/tracker/jobs_tracker.json` giữ nguyên trạng thái sạch (0 jobs).
