# ai-job-search (ai-find-job)

Trợ lý thông minh hỗ trợ tìm kiếm, đánh giá và chuẩn bị hồ sơ ứng tuyển việc làm an ninh mạng (Việt Nam, Hàn Quốc, Freelance) trên Windows 11 với Google Antigravity.

---

## 1. NGUYÊN TẮC KIẾN TRÚC & TÍCH HỢP UPSTREAM

- **Kho mã nguồn gốc (Canonical Upstream):** `ai-job-search-dev/ai-job-search` (`https://github.com/ai-job-search-dev/ai-job-search.git`).
- **Thư mục upstream:** Lưu trữ cách ly tại [`upstream/`](upstream/) (Commit: `e16acee3abdaae57f8026789338a3c6eebf4608b`, Giấy phép MIT).
- **Mã nguồn tích hợp trực tiếp:**
  - [`src/upstream_bridge.py`](src/upstream_bridge.py): Gọi hàm `make_key` từ `upstream/tools/job_key.py` để sinh canonical deduplication slug chuẩn hóa; gọi `upstream/tools/security_guards.py` để kiểm tra toàn vẹn chuỗi cung ứng.
  - [`src/tracker.py`](src/tracker.py): Lưu canonical key upstream vào bản ghi tracker, hỗ trợ ghi file nguyên tử (atomic write) và bảo toàn trạng thái khi đánh giá lại.
  - Định dạng hồ sơ Thin-Pointer theo chuẩn `upstream/CLAUDE.md`.
- **Giới hạn thư mục:** Mọi thao tác file, dependency, log và cache đều nằm 100% trong `PROJECT_ROOT`. Không ghi file ra ngoài, không sửa Registry/PATH hệ thống.
- **Bảo vệ quyền riêng tư & Secret:**
  - Mặc định `--mode rules` hoạt động 100% offline, zero network calls.
  - Chế độ `--mode ai` yêu cầu người dùng chủ động chọn, có cảnh báo quyền riêng tư trước khi truyền dữ liệu.
  - Hàm `mask_secrets()` che dấu token, key-value secrets trong mọi log và thông báo lỗi.

---

## 2. BỘ KIỂM THỬ TỰ ĐỘNG

Dự án tách bạch hoàn toàn giữa bộ test mở rộng của dự án và bộ test của kho nguồn upstream:

```powershell
# 1. Chạy 30 ca kiểm thử toàn diện & kiểm thử hồi quy (tests.test_all)
python -m unittest tests.test_all
# Hoặc dùng launcher PowerShell (truyền đúng exit code ra ngoài):
.\run.ps1 test

# 2. Chạy 836 ca kiểm thử của kho gốc Upstream (805 passed, 31 skipped, 0 failed)
python -m unittest discover -s upstream/tests -p "test_*.py"

# 3. Kiểm tra an toàn chuỗi cung ứng upstream
python -m src.cli upstream-verify
```

---

## 3. HƯỚNG DẪN SỬ DỤNG DÒNG LỆNH (CLI)

### Đánh giá mô tả công việc (JD Evaluation)
```powershell
# Thị trường Việt Nam (Lưu ý: Luôn truyền --tracker-file khi thử nghiệm fixture để bảo vệ tracker thật)
python -m src.cli evaluate --file tests/fixtures/jd_vietnam_soc.txt --market vietnam --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs

# Thị trường Hàn Quốc (Xử lý phủ định tiếng Hàn/Anh và trích dẫn bằng chứng)
python -m src.cli evaluate --file tests/fixtures/jd_korea_security.txt --market korea --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs

# Dự án Freelance
python -m src.cli evaluate --file tests/fixtures/jd_freelance_python.txt --market freelance --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs
```

### Đánh giá từ file JD mẫu (Fixtures)
```powershell
# Fixture Thực tập sinh An toàn thông tin CyStack (Hà Nội, Việt Nam)
python -m src.cli evaluate --file data/live_jds/vietnam_sun_cybersec_intern.txt --market vietnam --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs

# Fixture Toss Security Analyst (Seoul, Hàn Quốc)
python -m src.cli evaluate --file data/live_jds/korea_soc_intern.txt --market korea --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs

# Fixture Đề xuất kỹ thuật Python Log Parser (Freelance synthetic fixture)
python -m src.cli evaluate --file data/live_jds/freelance_log_parser.txt --market freelance --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs
```

### Quản lý Tracker ứng tuyển
```powershell
# Xem danh sách
python -m src.cli tracker list

# Cập nhật trạng thái
python -m src.cli tracker update --id <JOB_ID> --status "Đã nộp" --notes "Đã gửi qua email"

# Xuất ra CSV (Mặc định xuất file CSV tương ứng với file JSON theo dõi)
python -m src.cli tracker export
```

---

## 4. BẢNG TRẠNG THÁI NGHIỆM THU & TÍNH NĂNG MINH BẠCH

| Thành phần | Trạng thái | Ghi chú minh bạch |
|---|:---:|---|
| **Bộ kiểm thử dự án (30 tests)** | **PASS** | Chạy đạt 30/30 trong ~0.5s, 0 fail, 0 error |
| **Cầu nối Upstream (job_key & guards)** | **PASS** | Tích hợp thành công trong `src/upstream_bridge.py` |
| **Cơ chế cách ly Demo Tracker** | **PASS** | Không làm biến đổi `data/tracker/jobs_tracker.json` (0 jobs) |
| **Bảo toàn trạng thái khi đánh giá lại** | **PASS** | Giữ nguyên trạng thái đã nộp, ngày nộp, ghi chú; ghi JSON an toàn nguyên tử |
| **Xử lý phủ định JD Hàn Quốc** | **PASS** | Nhận diện đúng phủ định theo câu, trích dẫn bằng chứng, áp dụng điều kiện loại trừ |
| **Trung thực hồ sơ sinh tài liệu** | **PASS** | Gắn placeholder khi thiếu dữ liệu; không tự nhận năng lực chuyên sâu; gắn badge mock |
| **Chống đè tên file đầu ra** | **PASS** | Tiền tố file kết hợp slug công ty và vị trí (`{company}_{role}`) |
| **Phân định rõ Rules vs AI mode** | **PASS** | Mặc định `--mode rules` 100% offline; `--mode ai` opt-in với Google Gemini |
| **Cào tự động cổng việc làm công khai** | **BLOCKED** | Các cổng tuyển dụng (TopCV, Saramin, LinkedIn) chặn bot qua WAF/Cloudflare. Luồng nhập thủ công (`--text` / `--file`) hoạt động 100% tin cậy |
| **Kết nối AI API trực tuyến** | **UNVERIFIED_LIVE** | Mock test PASS. Live test BLOCKED nếu người dùng chưa cung cấp `GEMINI_API_KEY` |
| **Bản in trực quan / PDF nhị phân** | **NOT TESTED** | Xuất HTML chuẩn in `@media print`. Chưa kiểm tra thẩm mỹ bản in PDF bằng mắt người |
