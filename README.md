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
# 1. Chạy 37 ca kiểm thử toàn diện & kiểm thử hồi quy (tests.test_all)
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

### Bước 1: Tạo hồ sơ ứng viên cá nhân
Tạo hoặc chỉnh sửa hồ sơ của bạn tại `data/candidates/my_profile.json` theo mẫu chuẩn (file này đã được `.gitignore` bảo vệ tuyệt đối):
```powershell
# Xem mẫu hồ sơ chuẩn tại data/candidates/candidate_mock.json
Get-Content data/candidates/candidate_mock.json
```

### Bước 2: Đánh giá mô tả công việc (JD Evaluation) & Sinh tài liệu ứng tuyển
```powershell
# 1. Đánh giá JD thị trường Việt Nam (tự động tạo CV, Thư ứng tuyển, Bộ luyện phỏng vấn và lưu Tracker)
python -m src.cli evaluate --file data/my_jd.txt --candidate data/candidates/my_profile.json --market vietnam --save-track --generate-docs

# 2. Đánh giá JD thị trường Hàn Quốc
python -m src.cli evaluate --file tests/fixtures/jd_korea_security.txt --market korea --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs

# 3. Đánh giá dự án Freelance
python -m src.cli evaluate --file tests/fixtures/jd_freelance_python.txt --market freelance --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs

# 4. Đánh giá trực tiếp từ đoạn văn bản (nhập nhanh)
python -m src.cli evaluate --text "Tuyển thực tập sinh SOC..." --market vietnam

# 5. Chế độ AI với Gemini (yêu cầu GEMINI_API_KEY)
python -m src.cli evaluate --file data/my_jd.txt --market vietnam --mode ai --provider gemini
```

### Bước 3: Xem và quản lý tiến độ ứng tuyển (Tracker)
```powershell
# Xem danh sách các công việc đã lưu
python -m src.cli tracker list

# Cập nhật trạng thái sau khi nộp đơn hoặc phỏng vấn
python -m src.cli tracker update --id <JOB_ID> --status "Đã nộp" --notes "Đã gửi CV qua email"

# Xuất dữ liệu tracker ra file CSV
python -m src.cli tracker export
```

### Bước 4: Xem tài liệu ứng tuyển
Các tài liệu Markdown và HTML độc lập được lưu trong thư mục `output/`:
- `output/*_cv.md` & `output/*_cv.html`: CV được may đo theo JD (mở file HTML bằng trình duyệt để xem và in PDF Ctrl+P).
- `output/*_cover_letter.md`: Thư ứng tuyển (Cover Letter) trung thực với hồ sơ.
- `output/*_interview_prep.md`: Bộ câu hỏi phỏng vấn kỹ thuật và gợi ý trả lời dựa trên kỹ năng thực tế của bạn.

---

## 4. BẢNG TRẠNG THÁI NGHIỆM THU & TÍNH NĂNG MINH BẠCH

| Thành phần | Trạng thái | Ghi chú minh bạch |
|---|:---:|---|
| **Bộ kiểm thử dự án (37 tests)** | **PASS** | Chạy đạt 37/37 trong ~0.5s, 0 fail, 0 error |
| **Cầu nối Upstream (job_key & guards)** | **PASS** | Tích hợp thành công trong `src/upstream_bridge.py` |
| **Bảo mật dữ liệu cá nhân & Secret** | **PASS** | `.gitignore` loại trừ hoàn toàn `my_profile.json`, `my_jd.txt`, `jobs_tracker.*`, `output/*` |
| **Cơ chế cách ly Demo Tracker** | **PASS** | Thử nghiệm fixture tự động cô lập qua `--tracker-file` hoặc vào `.local/` |
| **Bảo toàn trạng thái khi đánh giá lại** | **PASS** | Giữ nguyên trạng thái đã nộp, ngày nộp, ghi chú; ghi JSON an toàn nguyên tử |
| **Phân loại cấu trúc JD & Trích dẫn** | **PASS** | Phân định Bắt buộc / Ưu tiên / Công việc / Đào tạo kèm trích dẫn văn bản gốc |
| **Xử lý JD đào tạo thiếu yêu cầu** | **PASS** | Gán `match_score=null`, đề xuất `CÂN NHẮC ỨNG TUYỂN / CẦN LÀM RÕ THÊM` |
| **Chuẩn hóa quan hệ kỹ năng (Taxonomy)** | **PASS** | Nhận diện quan hệ TCP/IP $\subset$ Network, Wireshark $\subset$ Packet Analysis |
| **Trung thực hồ sơ sinh tài liệu** | **PASS** | Gắn placeholder khi thiếu dữ liệu; không tự bịa đặt năng lực |
| **Chống đè tên file đầu ra** | **PASS** | Tiền tố file kết hợp slug công ty và vị trí (`{company}_{role}`) |
| **Phân định rõ Rules vs AI mode** | **PASS** | Mặc định `--mode rules` 100% offline; `--mode ai` opt-in với Google Gemini |
| **Cào tự động cổng việc làm công khai** | **BLOCKED** | Các cổng tuyển dụng (TopCV, Saramin, LinkedIn) chặn bot qua WAF/Cloudflare. Luồng nhập thủ công (`--text` / `--file`) hoạt động 100% tin cậy |

