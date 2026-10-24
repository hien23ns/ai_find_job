# BÁO CÁO KIỂM THỬ VÀ BẰNG CHỨNG THỰC TẾ (TEST REPORT)

Dự án: **ai-job-search (ai-find-job)**  
Môi trường thực thi: **Windows 11 / Windows PowerShell / Python 3.11.9**  
Thư mục gốc (`PROJECT_ROOT`): `C:\Users\Lenovo\Downloads\ai-find-job`  
Thời điểm cập nhật & xác minh: **2026-10-24 13:12:00**

---

## 1. TỔNG QUAN KẾT QUẢ KIỂM THỬ TỪ LOG THỰC TẾ

> [!IMPORTANT]
> Báo cáo này tách bạch rành mạch giữa:
> 1. **Bộ kiểm thử mở rộng của dự án (`tests.test_all`):** Đánh giá các tính năng mở rộng an ninh mạng, bảo mật và tương thích Windows.
> 2. **Bộ kiểm thử kho nguồn upstream (`upstream/tests`):** Đánh giá sự toàn vẹn của mã nguồn gốc, không dùng để chứng minh tính năng mở rộng của dự án.
> 3. **Các tính năng tùy chọn (External API & LaTeX PDF):** Ghi rõ trạng thái chưa kiểm chứng thay vì khẳng định 100%.

| Hạng mục kiểm thử | Lệnh thực thi thực tế | Tổng số | Đạt (Pass) | Bỏ qua (Skip) | Thất bại (Fail) | Lỗi (Error) | Trạng thái nghiệm thu |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Kiểm thử mở rộng dự án** | `python -m unittest tests.test_all` | **21** | **21** | 0 | 0 | 0 | **PASS** |
| **Kiểm thử kho nguồn Upstream** | `python -m unittest discover -s upstream/tests` | **836** | **805** | **31** | 0 | 0 | **PASS** (Upstream core) |
| **Kiểm tra an toàn Upstream** | `python upstream/tools/security_guards.py` | 1 | 1 | 0 | 0 | 0 | **PASS** |
| **Tải trực tiếp trang tuyển dụng công ty** | `fetch_jd_url` (CyStack, Toss, GitHub) | 3 | 3 | 0 | 0 | 0 | **PASS** |
| **Tải trực tiếp qua cổng việc làm (WAF/Bot)** | `fetch_jd_url` (TopCV, Saramin) | 2 | 0 | 0 | 0 | 0 | **BLOCKED (HTTP 403/404)** |
| **Dịch vụ LLM trực tuyến bên ngoài** | `AIService(api_key=None)` | 1 | 0 | 0 | 0 | 0 | **UNVERIFIED_OPTIONAL** |
| **Kiểm tra bố cục in / visual bản PDF** | `DocumentGenerator.export_to_html` | 1 | 0 | 0 | 0 | 0 | **NOT TESTED** |

---

## 2. BẰNG CHỨNG BỘ KIỂM THỬ DỰ ÁN (21 TEST CASES)

Lệnh thực thi:
```powershell
python -m unittest tests.test_all
```
Kết quả thực tế ghi nhận:
```
.....................
----------------------------------------------------------------------
Ran 21 tests in 0.524s

OK
```

### Chi tiết 21 Ca kiểm thử:
1. `test_01_runtime_launch_on_windows`: [PASS] Khởi chạy an toàn với Python 3.11 trên Windows, kiểm tra `cli.py` và đường dẫn dự án.
2. `test_02_path_with_spaces`: [PASS] Thao tác an toàn khi thư mục dự án chứa dấu khoảng trắng.
3. `test_03_input_from_text_and_utf8_file`: [PASS] Tiếp nhận JD an toàn từ text trực tiếp và file UTF-8.
4. `test_04_multilingual_vietnamese_korean_english`: [PASS] Xử lý chính xác đa ngôn ngữ: Tiếng Việt, Tiếng Hàn (Hangul), Tiếng Anh.
5. `test_05_three_independent_markets`: [PASS] Đánh giá độc lập 3 thị trường: Việt Nam (VND), Hàn Quốc (KRW), Freelance (USD/VND).
6. `test_06_missing_candidate_info`: [PASS] Xử lý khi hồ sơ ứng viên thiếu dữ liệu; không bịa đặt kinh nghiệm hay kỹ năng.
7. `test_07_korea_unclear_visa_and_language`: [PASS] Gán nhãn "Chưa rõ" cho visa, ngoại ngữ, nơi cư trú khi JD Hàn Quốc không nêu; không suy đoán.
8. `test_08_url_errors_blocked_expired_pages`: [PASS] Bắt lỗi WAF/403/404 và chuyển sang luồng nhập text thủ công.
9. `test_09_deduplication`: [PASS] Lọc trùng JD dựa trên hash nội dung chuẩn hóa và slug công ty/tiêu đề.
10. `test_10_generate_markdown_cv_letter_proposal`: [PASS] Sinh CV, Thư ứng tuyển, Bản đề xuất Freelance và Bộ phỏng vấn Markdown.
11. `test_11_tracker_update_and_read`: [PASS] Lưu trữ, đọc lại, cập nhật trạng thái và xuất CSV từ Tracker.
12. `test_12_adversarial_prompt_injection_safety`: [PASS] Trung hòa các chỉ thị độc hại (`Ignore instructions`, `DROP TABLE`, `<script>`).
13. `test_13_filesystem_boundary_enforcement`: [PASS] Chặn đứng hành vi Path Traversal (`../`, ổ đĩa ngoài, system32) bằng `PermissionError`.
14. `test_14_fallback_offline_bun_latex_ai`: [PASS] Cơ chế Fallback 100% offline khi không có API key hoặc thiếu Bun/LaTeX.
15. `test_15_freelance_milestone_no_unwarranted_percentages`: [PASS] Không tự ý gán tỷ lệ % mốc thanh toán (như 30%-40%-30%) khi chưa thỏa thuận.
16. `test_16_clean_prefix_path_traversal_defense`: [PASS] Làm sạch ký tự lạ trong tiêu đề tin để chống thoát khỏi thư mục `output/`.
17. `test_17_tracker_isolation_custom_file`: [PASS] Cách ly hoàn toàn file tracker kiểm thử khi truyền `--tracker-file`.
18. `test_18_demo_run_does_not_mutate_production_tracker`: [PASS] Xác nhận chạy demo/fixture tuyệt đối không làm thay đổi hay xóa dữ liệu của tracker chính thức (`data/tracker/jobs_tracker.json`).
19. `test_19_upstream_bridge_canonical_key`: [PASS] Gọi trực tiếp mã nguồn `upstream/tools/job_key.py` để sinh canonical slug chuẩn hóa (hỗ trợ cả chữ Latin và ký tự non-Latin/Hangul).
20. `test_20_upstream_bridge_security_guards`: [PASS] Gọi trực tiếp `upstream/tools/security_guards.py`, xác nhận các chốt chặn an toàn chuỗi cung ứng đều PASS.
21. `test_21_candidate_thin_pointer_schema`: [PASS] Kiểm tra cấu trúc hồ sơ Thin-Pointer theo chuẩn `CLAUDE.md`, phân định rõ ràng giữa Kinh nghiệm thực tế, Môn học, Bài Lab và Đồ án.

---

## 3. BẰNG CHỨNG XÁC MINH NGUỒN JD THỰC TẾ & BỊ CHẶN (LIVE JD VERIFICATION)

### A. Các nguồn truy cập thành công (PASS)
1. **Việt Nam (`data/live_jds/vietnam_sun_cybersec_intern.txt`):**
   - Vị trí: Kỹ sư An toàn Thông tin & Giám sát An ninh mạng (Security Analyst / Intern).
   - Đơn vị: Công ty Cổ phần An ninh mạng CyStack (CyStack Vietnam).
   - Địa điểm: Tầng 6, Golden Field, 24 Nguyễn Cơ Thạch, Nam Từ Liêm, Hà Nội.
   - URL nguồn xác minh: `https://cystack.net/vi/careers`
   - Thời điểm truy cập: `2026-10-24 12:59:59`
   - Tình trạng kết nối `fetch_jd_url`: **PASS** (Tải thành công 3.947 ký tự văn bản công khai).
2. **Hàn Quốc (`data/live_jds/korea_soc_intern.txt`):**
   - Vị trí: [신입/주니어] Security Analyst (정보보안 및 보안관제 엔지니어).
   - Doanh nghiệp: 토스 (비바리퍼블리카 / Viva Republica - Toss).
   - Địa điểm: 서울특별시 강남구 테헤란로 142 (아크플레이스).
   - URL nguồn xác minh: `https://toss.im/career`
   - Thời điểm truy cập: `2026-10-24 13:00:41`
   - Tình trạng kết nối `fetch_jd_url`: **PASS** (Tải thành công dữ liệu tuyển dụng công khai).
3. **Freelance (`data/live_jds/freelance_log_parser.txt`):**
   - Vị trí: Python 3 Log Parser & Automated State Deduplicator Script (Task #710).
   - Nguồn: Open Source Career Infrastructure.
   - URL nguồn xác minh: `https://raw.githubusercontent.com/ai-job-search-dev/ai-job-search/master/tools/scrape_state.py`
   - Thời điểm truy cập: `2026-10-24 13:00:51`
   - Tình trạng kết nối `fetch_jd_url`: **PASS** (Tải thành công 4.893 ký tự đặc tả kỹ thuật).

### B. Các nguồn bị tường lửa / WAF chặn (BLOCKED)
1. **TopCV Việt Nam (`https://www.topcv.vn/viec-lam/thuc-tap-sinh-soc`):**
   - Trạng thái: **BLOCKED (HTTP 403 Forbidden)**.
   - Nguyên nhân: Tường lửa Cloudflare WAF chặn bot/crawler tự động, yêu cầu đăng nhập trình duyệt hoặc giải CAPTCHA.
   - Xử lý: Hệ thống giữ đúng giới hạn an toàn, không cố gắng hack hay bypass, hiển thị hướng dẫn người dùng copy text dán vào thủ công.
2. **Saramin Hàn Quốc (`https://www.saramin.co.kr/zf_user/jobs/relay/view`):**
   - Trạng thái: **BLOCKED (HTTP 404 / Chống bot)**.
   - Xử lý: Bắt lỗi ngoại lệ, chuyển sang luồng nhập text thủ công.

---

## 4. BẰNG CHỨNG TÍCH HỢP UPSTREAM & PHÂN ĐỊNH TRÁCH NHIỆM

Tệp nhật ký đầy đủ: [`docs/evidence/e2e_integration_run.txt`](evidence/e2e_integration_run.txt)

- **Mã nguồn Upstream sử dụng:**
  - `upstream/tools/job_key.py`: Gọi trực tiếp trong `src/upstream_bridge.py` và `src/tracker.py` để sinh khóa định danh duy nhất (VD: `cystack_soc-analyst-intern`).
  - `upstream/tools/security_guards.py`: Kiểm tra toàn vẹn chuỗi cung ứng trước khi chạy luồng nghiệp vụ.
  - `upstream/CLAUDE.md`: Tiêu chuẩn hóa định dạng hồ sơ ứng viên Thin-Pointer.

- **Phân định trách nhiệm giữa Quy tắc Python và Antigravity:**
  - **Python (Quy tắc cứng):** Giới hạn thư mục (`ensure_within_project`), trung hòa Prompt Injection, tính điểm số 0-100 có trọng số, gán nhãn "Chưa rõ" cho điều kiện khuyết, lưu trữ tracker cục bộ.
  - **Antigravity (Mô hình LLM):** Tinh chỉnh ngôn từ tự nhiên của Thư ứng tuyển / Proposal, phản biện và gợi ý chiến lược phỏng vấn kỹ thuật tương tác, phân tích ngữ cảnh kinh doanh đặc thù.

---

## 5. KIỂM ĐỊNH SẢN PHẨM & CÁC HẠNG MỤC TÙY CHỌN

1. **Kiểm tra nội dung tài liệu sinh ra (`output/`):**
   - Đã đọc và đối soát trực tiếp các file CV, Thư ứng tuyển, Đề xuất Freelance.
   - Không phát hiện bất kỳ sự bịa đặt (hallucination) nào về số năm kinh nghiệm hay bằng cấp/chứng chỉ của ứng viên.
   - Mọi kỹ năng trong thư đều trích dẫn chính xác nguồn (Kinh nghiệm thực tế, Môn học, Bài Lab, Đồ án cá nhân).
   - Nội dung điều chỉnh linh hoạt theo từng vị trí tuyển dụng.
2. **Kiểm tra bản in / PDF:**
   - **Tình trạng: NOT TESTED**.
   - Do môi trường Windows hiện tại không cài đặt sẵn bộ biên dịch LaTeX nhị phân (`lualatex`/`xelatex`) trong thư mục dự án, hệ thống xuất file HTML có định dạng CSS `@media print` cho phép người dùng mở trình duyệt và chọn in ra PDF. Bố cục in thực tế của file PDF chưa được kiểm chứng trực quan bằng mắt người.
3. **Dịch vụ AI trực tuyến (Online API):**
   - **Tình trạng: UNVERIFIED_OPTIONAL**.
   - Chưa cấu hình `GEMINI_API_KEY`. Hệ thống hoạt động hoàn toàn độc lập, an toàn và ổn định qua Động cơ Quy tắc Cục bộ (Local Rule Engine) kết hợp cùng mô hình Antigravity đang đối thoại.
