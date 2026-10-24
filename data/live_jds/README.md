# QUẢN LÝ DỮ LIỆU JD & QUY CHUẨN XÁC MINH NGUỒN TIN (DATA INTEGRITY)

Thư mục này chứa các tài liệu mô tả công việc (JD) mẫu dùng cho quá trình kiểm thử, minh họa và đối chiếu kết quả đánh giá hệ thống.

---

## 1. PHÂN BIỆT DỮ LIỆU MẪU (FIXTURE) VÀ TIN TUYỂN DỤNG THẬT (LIVE JD)

Theo nguyên tắc trung thực tuyệt đối về dữ liệu (Factual Integrity) và bảo vệ an toàn hệ thống:
1. **Dữ liệu mẫu (Synthetic / Demo Fixtures):**
   - Các file trong thư mục này được phân loại rõ ràng là fixture mẫu.
   - Tuyệt đối không tự suy diễn ngân sách, thời hạn dự án hoặc tự bịa ra mã công việc ("Task Specification #710", "$300-$600") khi không có bằng chứng từ nguồn công bố.
   - Nếu đề bài kỹ thuật không nêu ngân sách/thời hạn, hệ thống bắt buộc phải ghi `[Chưa xác định - Cần làm rõ / Báo giá]` thay vì tự điền số liệu.

2. **Tin tuyển dụng thực tế (Live JDs):**
   - Đối với tin tuyển dụng trực tiếp của doanh nghiệp, mỗi tin phải có:
     - URL cụ thể đến đúng bài đăng tuyển dụng (không dùng link trang chủ cổng nghề nghiệp chung chung để khẳng định một vị trí đơn lẻ).
     - Thời điểm truy cập và thu thập.
     - Nội dung văn bản nguyên bản đối chiếu được.
   - **Tình trạng cào dữ liệu tự động từ các cổng việc làm (Web Scraping Status):**
     - Đa số các cổng tuyển dụng trực tuyến (LinkedIn, VietnamWorks, TopCV, Saramin, Wanted Korea, v.v.) hiện đều triển khai hệ thống tường lửa ứng dụng web (WAF / Cloudflare Anti-bot), yêu cầu xác thực đăng nhập hoặc hiển thị nội dung động qua SPA (React/Next.js).
     - Việc tải tự động qua HTTP đơn giản đối với các trang này sẽ bị chặn (`403 Forbidden`, `Challenge Page`) và được hệ thống phân loại đúng trạng thái là **`BLOCKED (WAF / Anti-Bot Protected)`**.
     - **Giải pháp an toàn và đáng tin cậy nhất:** Người dùng sao chép văn bản JD thực tế và nạp trực tiếp vào hệ thống qua lệnh CLI bằng `--file` hoặc `--text`. Luồng nạp thủ công luôn hoạt động ổn định và chính xác 100%.

---

## 2. DANH MỤC CÁC FILE TRONG THƯ MỤC

| Tên File | Thị trường | Phân loại | Mục đích kiểm thử |
|---|---|---|---|
| `vietnam_sun_cybersec_intern.txt` | Việt Nam | Demo Fixture | Đối sánh kỹ năng SOC Intern & sinh hồ sơ tiếng Việt |
| `korea_soc_intern.txt` | Hàn Quốc | Demo Fixture | Kiểm thử điều kiện visa, ngôn ngữ & văn hóa làm việc |
| `freelance_log_parser.txt` | Freelance | Synthetic Fixture | Kiểm thử tính điểm dự án, cảnh báo rủi ro & sinh proposal |

---

## 3. LỆNH CHẠY THỬ NGHIỆM ĐẢM BẢO CÁCH LY

Khi thử nghiệm đánh giá các file fixture, luôn sử dụng tham số `--tracker-file` để không làm thay đổi tracker chính:

```powershell
# Đánh giá fixture Việt Nam
python -m src.cli evaluate --file data/live_jds/vietnam_sun_cybersec_intern.txt --market vietnam --save-track --tracker-file .local/temp/demo_tracker.json

# Đánh giá fixture Hàn Quốc
python -m src.cli evaluate --file data/live_jds/korea_soc_intern.txt --market korea --save-track --tracker-file .local/temp/demo_tracker.json

# Đánh giá fixture Freelance
python -m src.cli evaluate --file data/live_jds/freelance_log_parser.txt --market freelance --save-track --tracker-file .local/temp/demo_tracker.json
```
