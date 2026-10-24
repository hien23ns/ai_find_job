# HƯỚNG DẪN VẬN HÀNH DỰ ÁN TRÊN WINDOWS (WINDOWS OPERATION GUIDE)

Dự án: **ai-job-search (ai-find-job)**  
Môi trường kiểm chứng: **Windows 11 / Windows PowerShell / Antigravity IDE**  
Thư mục dự án (`PROJECT_ROOT`): `C:\Users\Lenovo\Downloads\ai-find-job`  
Mã nguồn Upstream: [`upstream/`](../upstream/) (`ai-job-search-dev/ai-job-search`, Commit `e16acee3abdaae57f8026789338a3c6eebf4608b`, Giấy phép MIT)  

---

## 1. YÊU CẦU CÔNG CỤ & RUNTIME

### Công cụ Bắt buộc (Required)
- **Python 3.10+** (Hệ thống đã có sẵn **Python 3.11.9**).
- **Thư viện chuẩn (Standard Library):** Hệ thống được thiết kế với triết lý **Zero-External-Dependency** cho phần lõi, không cần cài đặt thêm gói `pip` toàn cục nào, không làm ô nhiễm môi trường máy, không cần quyền Administrator.
- **Windows PowerShell** hoặc Windows Terminal.

### Công cụ Tùy chọn (Optional)
- **Node.js (v26.4.0) / Bun (1.3.14):** Tùy chọn dùng thêm cho các CLI portal search của upstream.
  - *Lưu ý về PowerShell Execution Policy:* Trên Windows, việc chạy script `.ps1` chưa ký (như `bun.ps1`) có thể bị chặn bởi Execution Policy mặc định. Hãy dùng lệnh `bun.cmd` hoặc dùng trực tiếp Python có sẵn.
- **LaTeX / MiKTeX:** Tùy chọn để biên dịch template LaTeX upstream. Khi thiếu công cụ này, hệ thống **tự động kích hoạt cơ chế fallback**: xuất ra file **Markdown chuẩn** và file **HTML độc lập**, người dùng chỉ cần mở bằng trình duyệt (Edge/Chrome) và chọn `In / Save as PDF` (Ctrl + P).
- **Khóa API AI trực tuyến (Gemini / OpenAI):** Tùy chọn. Khi không có API key hoặc mất mạng, hệ thống chạy **100% Offline** bằng động cơ quy tắc cục bộ (Deterministic Local Rule Engine).

---

## 2. KHỞI CHẠY BẰNG POWERSHELL

Mở PowerShell tại thư mục dự án `C:\Users\Lenovo\Downloads\ai-find-job`:

### Cách 1: Sử dụng launcher tiện ích `run.ps1`
Launcher này tự động cấu hình biến môi trường `$env:PYTHONPYCACHEPREFIX` và `$env:TEMP` vào trong thư mục `PROJECT_ROOT\.local` để đảm bảo không ghi rác ra hệ thống:
```powershell
# Chạy bộ 21 bài test tự động của dự án
powershell -ExecutionPolicy Bypass -File .\run.ps1 test

# Đánh giá JD thị trường Việt Nam (tự động chuyển sang tracker demo khi chạy fixture)
powershell -ExecutionPolicy Bypass -File .\run.ps1 eval --file tests/fixtures/jd_vietnam_soc.txt --market vietnam --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs

# Xem danh sách ứng tuyển trong tracker
powershell -ExecutionPolicy Bypass -File .\run.ps1 tracker list

# Xuất dữ liệu tracker ra CSV
powershell -ExecutionPolicy Bypass -File .\run.ps1 tracker export

# Lọc trùng tin tuyển dụng
powershell -ExecutionPolicy Bypass -File .\run.ps1 dedup --file tests/fixtures/jd_duplicates.json
```

### Cách 2: Gọi trực tiếp qua Python module
```powershell
# Chạy bộ test suite mở rộng của dự án (21 tests)
python -m unittest tests.test_all

# Chạy test upstream gốc (836 tests)
python -m unittest discover -s upstream/tests -p "test_*.py"

# Đánh giá JD thị trường (sử dụng --tracker-file .local/temp/demo_tracker.json khi chạy mẫu)
python -m src.cli evaluate --file tests/fixtures/jd_vietnam_soc.txt --market vietnam --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs

# Kiểm tra tích hợp upstream
python -m src.cli upstream-info
python -m src.cli upstream-key --company "CyStack" --title "SOC Analyst Intern"
python -m src.cli upstream-verify
```

---

## 3. HƯỚNG DẪN SỬ DỤNG CHO 3 NHÓM THỊ TRƯỜNG

### A. Thị trường Việt Nam (Thực tập / Fresher / Junior An ninh mạng)
- **Vị trí mục tiêu:** Security Intern, SOC Intern, SOC Analyst L1, Network Security Intern, Network Engineer Junior.
- **Kỹ năng trọng tâm:** Wireshark, TCP/IP, Linux, Python, Snort, Suricata, SIEM/Splunk/ELK, Firewall, Nmap, Phân tích log.
- **Tiền tệ:** VND.
- **Lệnh thực hiện:**
```powershell
python -m src.cli evaluate --file tests/fixtures/jd_vietnam_soc.txt --market vietnam --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs
```

### B. Thị trường Hàn Quốc (Hàn Quốc - 신입/인턴 정보보안)
- **Vị trí mục tiêu:** 정보보안, 정보보호, 보안관제, 네트워크 보안, 취약점 진단, 모의해킹, 신입, 인턴.
- **Tiền tệ:** KRW.
- **Lệnh thực hiện:**
```powershell
python -m src.cli evaluate --file tests/fixtures/jd_korea_security.txt --market korea --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs
```
- **Quy tắc bất di bất dịch:** Nếu thông tin về visa, ngoại ngữ, nơi cư trú hoặc việc nhận người nước ngoài không được nêu rõ trong bài đăng, hệ thống sẽ trả về **"Chưa rõ"**, tuyệt đối không tự suy đoán.
- Luôn kèm cảnh báo: *Bắt buộc phải có người có năng lực ngôn ngữ tiếng Hàn rà soát ngữ pháp và thuật ngữ trước khi nộp hồ sơ.*

### C. Thị trường Freelance (Mạng, Linux, Python, Giám sát an ninh)
- **Phạm vi công việc:** Tự động hóa xử lý log bằng Python, tài liệu mô tả kiến trúc mạng, cấu hình hardening máy chủ Linux, thiết lập rules giám sát.
- **Tiền tệ:** USD / VND.
- **Lệnh thực hiện:**
```powershell
python -m src.cli evaluate --file tests/fixtures/jd_freelance_python.txt --market freelance --save-track --tracker-file .local/temp/demo_tracker.json --generate-docs
```
- **Quy tắc mốc thanh toán:** Không tự ý gán tỷ lệ % thanh toán (như 30%-40%-30%) như thể khách hàng đã đồng ý. Nếu JD không nêu, hệ thống ghi rõ: *Chưa rõ trong JD / Chỉ là đề xuất thương lượng từ phía ứng viên cần khách hàng phê duyệt.*
- **Cảnh báo thẩm quyền pháp lý (Bắt buộc):** Chỉ thực hiện kiểm thử an toàn thông tin khi có văn bản ủy quyền chính thức (Letter of Authorization).

---

## 4. BẢO MẬT DỮ LIỆU & QUYỀN RIÊNG TƯ

- **Tracker:** Tách riêng file kiểm thử (`.local/temp/demo_tracker.json`) khỏi file tracker thật ([`data/tracker/jobs_tracker.json`](../data/tracker/jobs_tracker.json)). Không tạo hồ sơ "Đã nộp" giả mạo trong tracker chính thức.
- **Chống Prompt Injection:** Mọi văn bản JD tải về hoặc người dùng dán vào đều là *untrusted input*. Động cơ [`src/security.py`](../src/security.py) sẽ trung hòa các chỉ thị điều khiển độc hại.
- **Xuất PDF:** Hệ thống không giả mạo là đã biên dịch PDF khi thiếu LaTeX, mà xuất ra file HTML có CSS `@media print` để người dùng mở bằng trình duyệt và chọn in ra PDF. Tình trạng kiểm chứng: **NOT TESTED** (Bố cục in thực tế của file PDF chưa được kiểm chứng trực quan bằng mắt người; không khẳng định bố cục in đẹp khi chưa kiểm tra).
- **Dịch vụ AI trực tuyến:** Mặc định chạy 100% bằng quy tắc cục bộ. Nếu người dùng cấu hình `GEMINI_API_KEY`, hệ thống mới gọi API qua HTTPS và luôn thông báo rằng dữ liệu tóm tắt được gửi qua mạng Internet. Tình trạng kiểm chứng: **UNVERIFIED_OPTIONAL** (Tùy chọn chưa kiểm chứng).
