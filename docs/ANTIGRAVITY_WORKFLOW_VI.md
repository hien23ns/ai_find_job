# QUY TRÌNH LÀM VIỆC VỚI ANTIGRAVITY (ANTIGRAVITY WORKFLOW)

Dự án: **ai-job-search (ai-find-job)**  
Môi trường: **Google Antigravity IDE / Agentic AI Workflow**  
Đường dẫn dự án: `C:\Users\Lenovo\Downloads\ai-find-job`  
Mã nguồn Upstream: [`upstream/`](../upstream/) (`ai-job-search-dev/ai-job-search`)

---

## 1. NGUYÊN TẮC HOẠT ĐỘNG TRONG ANTIGRAVITY

1. **Khả năng tự nhiên của Antigravity (Native Agent Capability):**
   - Không giả định các slash command riêng của Claude Code (như `/setup`, `/scrape`, `/apply`) tự động chạy trong Antigravity.
   - Antigravity hoạt động dựa trên các công cụ chuẩn (`run_command`, `view_file`, `write_to_file`, `ask_question`) cùng hệ thống kỹ năng định nghĩa tại `.agents/skills/<skill_name>/SKILL.md`.
   - Trong phiên làm việc Antigravity, **mô hình AI của Agent trực tiếp đóng vai trò là động cơ phân tích ngữ cảnh, tư vấn phỏng vấn và sinh tài liệu**, do đó người dùng có thể sử dụng trọn vẹn luồng công việc mà không bắt buộc phải mua thêm khóa API đám mây bên ngoài.

2. **Cấu trúc kỹ năng chuẩn (Skill Discovery):**
   - Kỹ năng chính của dự án: [`.agents/skills/ai-job-search/SKILL.md`](../.agents/skills/ai-job-search/SKILL.md).
   - Các kỹ năng tìm kiếm của upstream: [`upstream/.agents/skills/`](../upstream/.agents/skills/) (bao gồm `jobindex-search`, `linkedin-search`, `jobbank-search`, `jobnet-search`...).
   - Quy tắc ứng xử chung: [`AGENTS.md`](../AGENTS.md) đóng vai trò Thin-Pointer kết nối thống nhất toàn bộ repo.

---

## 2. QUY TRÌNH ĐẦU-CUỐI THỰC TẾ (END-TO-END WORKFLOW)

Quy trình chuẩn gồm 5 bước được kiểm chứng thực tế:

```
[1. Đọc Hồ sơ Ứng viên]
       │
       ▼
[2. Tiếp nhận Mô tả Công việc (JD)] ──> [Làm sạch dữ liệu / Chống Injection]
       │
       ▼
[3. Đánh giá Mức độ Phù hợp (Evaluation)]
   - Tính điểm 0-100 minh bạch
   - Bóc tách bằng chứng từ Môn học/Lab/Dự án/Kinh nghiệm
   - Nhận diện điều kiện loại trừ & điểm chưa rõ (Visa/Ngôn ngữ/Thẩm quyền)
       │
       ▼
[4. Sinh Hồ sơ Ứng tuyển & Kịch bản Phỏng vấn]
   - CV Markdown & Cover Letter / Đề xuất Freelance
   - Bộ câu hỏi phỏng vấn kỹ thuật bám sát JD & hồ sơ
   - File HTML độc lập có CSS in ấn chuẩn
       │
       ▼
[5. Lưu & Cập nhật Trạng thái Ứng tuyển (Tracker)]
   - Lưu trữ có cấu trúc JSON / CSV
   - Tách biệt dữ liệu kiểm thử và dữ liệu thật
```

---

## 3. KIỂM CHỨNG TÁC VỤ MẪU VỚI BẰNG CHỨNG THỰC TẾ

Tệp bằng chứng đầy đủ: [`docs/evidence/e2e_integration_run.txt`](evidence/e2e_integration_run.txt)

### Bước 1: Tiếp nhận và đánh giá JD (Thị trường Việt Nam)
Lệnh PowerShell thực thi:
```powershell
python -m src.cli evaluate --file data/live_jds/vietnam_sun_cybersec_intern.txt --market vietnam --candidate data/candidates/candidate_mock.json --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs
```

### Bước 2: Đánh giá kết quả thực tế
- Điểm phù hợp: **95/100** (Khuyến nghị: **NÊN ỨNG TUYỂN**).
- Vị trí: Kỹ sư An toàn Thông tin & Giám sát An ninh mạng (Security Analyst / Intern) tại Công ty Cổ phần An ninh mạng CyStack.
- Bằng chứng kỹ năng tìm thấy:
  - TCP/IP: Kinh nghiệm thực tế tại Mock Company (Hỗ trợ cấu hình VLAN Cisco).
  - Wireshark: Đồ án `Home Lab Network Security Monitoring`.
  - Linux & Bash: Bài Lab `Hardening máy chủ Linux Ubuntu`.
  - Python: Đồ án `Python Log Parser & Anomaly Detection`.
  - Nmap: Bài Lab `Phân tích gói tin mạng và phát hiện tấn công`.
- Kỹ năng còn thiếu: Không phát hiện thiếu sót trọng tâm.

### Bước 3: Kiểm tra tài liệu được sinh tại `output/`
- CV Markdown: [`output/kỹ_sư_an_toàn_thông_tin__giám_cv.md`](../output/kỹ_sư_an_toàn_thông_tin__giám_cv.md).
- Thư ứng tuyển: [`output/kỹ_sư_an_toàn_thông_tin__giám_cover_letter.md`](../output/kỹ_sư_an_toàn_thông_tin__giám_cover_letter.md).
- Bộ câu hỏi phỏng vấn: [`output/kỹ_sư_an_toàn_thông_tin__giám_interview_prep.md`](../output/kỹ_sư_an_toàn_thông_tin__giám_interview_prep.md).
- File HTML in ấn độc lập: [`output/kỹ_sư_an_toàn_thông_tin__giám_cv.html`](../output/kỹ_sư_an_toàn_thông_tin__giám_cv.html) *(Tình trạng kiểm tra bản in PDF trực quan: **NOT TESTED**)*.

### Bước 4: Kiểm tra và xuất Tracker
```powershell
python -m src.cli tracker --tracker-file .local/temp/demo_tracker.json list
python -m src.cli tracker --tracker-file .local/temp/demo_tracker.json export
```
File tracker chính thức [`data/tracker/jobs_tracker.json`](../data/tracker/jobs_tracker.json) được bảo vệ hoàn toàn sạch (0 jobs), không có bản ghi giả mạo từ các bài demo.

---

## 4. AN TOÀN VÀ GIỚI HẠN THỰC TẾ

1. **Giới hạn thư mục tuyệt đối:** Toàn bộ file đọc, ghi, log và cache đều nằm trong `C:\Users\Lenovo\Downloads\ai-find-job`.
2. **Không tự động nộp đơn:** Antigravity chỉ chuẩn bị tài liệu và kịch bản; người dùng là người duy nhất quyết định thời điểm và cách thức gửi hồ sơ cho nhà tuyển dụng.
3. **Cơ chế Fallback trung thực:** Nếu không có kết nối API đám mây, hệ thống hoạt động bằng quy tắc cục bộ rõ ràng, không giả mạo trạng thái trực tuyến.
