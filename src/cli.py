"""
Command Line Interface (CLI) for ai-job-search.
Supports evaluating JDs, tracking applications, deduplicating posts, and generating tailored documents.
Works natively on Windows with full UTF-8 support.
Provides strict separation between offline rules mode and opt-in AI mode.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict

# Ensure stdout handles UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.ai_service import AIService
from src.config import CANDIDATES_DIR, LOCAL_DIR, OUTPUT_DIR, PROJECT_ROOT, TEMP_DIR
from src.evaluator import JobEvaluator
from src.generator import DocumentGenerator
from src.jd_parser import deduplicate_jds, fetch_jd_url, parse_jd_text, read_jd_file
from src.security import ensure_within_project
from src.tracker import JobTracker
from src.upstream_bridge import get_canonical_job_key, get_upstream_info, run_upstream_security_guards

def load_candidate_profile(candidate_path: Path) -> Dict[str, Any]:
    safe_path = ensure_within_project(candidate_path)
    if not safe_path.exists():
        raise FileNotFoundError(f"Không tìm thấy hồ sơ ứng viên tại: {safe_path}")
    return json.loads(safe_path.read_text(encoding="utf-8"))

def cmd_evaluate(args):
    # 1. Load candidate profile
    candidate_path = Path(args.candidate) if args.candidate else (CANDIDATES_DIR / "candidate_mock.json")
    candidate = load_candidate_profile(candidate_path)

    # 2. Get JD data
    if args.text:
        jd_data = parse_jd_text(args.text, source="manual_input")
    elif args.file:
        jd_data = read_jd_file(Path(args.file))
    elif args.url:
        print(f"[*] Đang tải dữ liệu từ URL: {args.url} ...")
        jd_data = fetch_jd_url(args.url)
    else:
        print("[!] Lỗi: Bạn phải cung cấp --text, --file hoặc --url.", file=sys.stderr)
        sys.exit(1)

    mode = getattr(args, "mode", "rules")
    ai_result = None

    # 3. AI Mode handling (Strict opt-in with explicit user notice)
    if mode == "ai":
        print("\n" + "!" * 70)
        print(" [!] CẢNH BÁO QUYỀN RIÊNG TƯ & BẢO MẬT (CHẾ ĐỘ AI):")
        print("     Bạn đã chọn --mode ai. Hệ thống chuẩn bị gửi tóm tắt hồ sơ và")
        print(f"     trích đoạn nội dung JD qua kết nối Internet tới {args.provider} API.")
        print("     [Lưu ý: Luồng CLI này độc lập với việc Antigravity Agent suy luận trong IDE]")
        print("!" * 70 + "\n")

        ai_svc = AIService(api_key=getattr(args, "api_key", None), provider=args.provider)
        cand_summary = candidate.get("summary", "") or f"Ứng viên chuyên ngành ATTT/CNTT ({candidate.get('name', 'N/A')})"
        jd_text = jd_data.get("raw_content", "") or jd_data.get("content", "")
        ai_result = ai_svc.analyze_job(jd_text, cand_summary, market=args.market)
    else:
        # Default rules mode: Strictly 0 network calls
        pass

    # 4. Evaluate using deterministic local rule engine
    evaluator = JobEvaluator(candidate)
    eval_result = evaluator.evaluate(jd_data, market=args.market)

    # 5. Print Summary Report
    source_label = "RULES (Động cơ quy tắc cục bộ - 100% Offline)"
    if mode == "ai" and ai_result:
        source_label = ai_result.get("source", "AI Mode")

    print("\n" + "="*70)
    print(f" BÁO CÁO ĐÁNH GIÁ MỨC ĐỘ PHÙ HỢP CÔNG VIỆC ({eval_result['market_name']})")
    print("="*70)
    print(f"Chế độ phân tích:   {mode.upper()}")
    print(f"Nguồn đánh giá:     {source_label}")
    print(f"Vị trí:              {eval_result['title']}")
    print(f"Công ty:             {jd_data.get('company', 'Quý công ty')}")
    print(f"Nguồn JD:            {eval_result['source']}")
    print(f"Thời điểm thu thập:  {eval_result['collection_time']}")
    score_str = f"{eval_result['match_score']}/100" if eval_result.get('match_score') is not None else f"Chưa đủ căn cứ tính điểm tổng ({eval_result.get('score_status', 'JD thiếu yêu cầu kỹ thuật cụ thể')})"
    print(f"Điểm phù hợp:        {score_str}")
    print(f"Khuyến nghị:         {eval_result['recommendation']}")
    print(f"Lý do:               {eval_result['rationale']}")
    
    print("\n--- PHÂN LOẠI CẤU TRÚC JD (KÈM TRÍCH DẪN BẰNG CHỨNG) ---")
    sections = eval_result.get("jd_sections", {})
    if sections.get("mandatory_requirements"):
        print(" [1] Điều kiện bắt buộc (Mandatory):")
        for m in sections["mandatory_requirements"]:
            print(f"     - {m['text']} [Trích dẫn JD: '{m['raw_quote']}']")
    if sections.get("preferred_requirements"):
        print(" [2] Điều kiện ưu tiên (Preferred):")
        for p in sections["preferred_requirements"]:
            print(f"     - {p['text']} [Trích dẫn JD: '{p['raw_quote']}']")
    if sections.get("responsibilities"):
        print(" [3] Công việc sẽ thực hiện (Responsibilities):")
        for r in sections["responsibilities"]:
            print(f"     - {r['text']} [Trích dẫn JD: '{r['raw_quote']}']")
    if sections.get("training_offerings"):
        print(" [4] Nội dung được đào tạo / Học việc (Training Offerings):")
        for t in sections["training_offerings"]:
            print(f"     - {t['text']} [Trích dẫn JD: '{t['raw_quote']}']")
    if sections.get("work_conditions"):
        print(" [5] Địa điểm & Lịch làm việc (Work Conditions):")
        for w in sections["work_conditions"]:
            print(f"     - {w['text']} [Trích dẫn JD: '{w['raw_quote']}']")

    print("\n--- CHI TIẾT CÁCH TÍNH ĐIỂM ---")
    for k, v in eval_result['score_calculation'].items():
        print(f" - {k}: {v}")

    print("\n--- ĐIỀU KIỆN BẮT BUỘC & LOẠI TRỪ ---")
    for req in eval_result['hard_requirements']:
        print(f" [v] Bắt buộc: {req}")
    if eval_result['disqualifiers']:
        for d in eval_result['disqualifiers']:
            print(f" [!] ĐIỀU KIỆN LOẠI TRỪ: {d}")
    else:
        print(" [OK] Không phát hiện điều kiện loại trừ vi phạm.")

    print("\n--- KỸ NĂNG PHÙ HỢP (KÈM BẰNG CHỨNG HỒ SƠ) ---")
    if eval_result.get("skill_status") == "Chưa đủ dữ liệu để đánh giá kỹ năng":
        print(" [i] Trạng thái: Chưa đủ dữ liệu để đánh giá kỹ năng kỹ thuật cụ thể từ JD.")
        print(f"     Ghi chú: {eval_result.get('skill_note', '')}")
    elif eval_result['matched_skills']:
        for m in eval_result['matched_skills']:
            print(f" [+] {m['skill']}")
            print(f"     Nguồn: {m['evidence_type']}")
            print(f"     Chi tiết: {m['evidence_details']}")
    else:
        print(" [!] Chưa tìm thấy kỹ năng khớp trực tiếp.")

    print("\n--- KỸ NĂNG CÒN THIẾU CẦN BỔ SUNG ---")
    if eval_result['missing_skills']:
        print(" [-] " + ", ".join(eval_result['missing_skills']))
    elif eval_result.get("skill_status") == "Chưa đủ dữ liệu để đánh giá kỹ năng":
        print(" [i] Không có kỹ năng tiên quyết bị đánh dấu thiếu (JD có nội dung đào tạo, chưa nêu đủ yêu cầu kỹ thuật cụ thể).")
    else:
        print(" [OK] Đáp ứng đầy đủ các kỹ năng cốt lõi được liệt kê.")

    # Market specifics
    if eval_result.get('korea_specifics'):
        print("\n--- THÔNG TIN ĐẶC THÙ THỊ TRƯỜNG HÀN QUỐC ---")
        ks = eval_result['korea_specifics']
        for k in ["Yêu cầu tiếng Hàn", "Yêu cầu tiếng Anh", "Chấp nhận ứng viên nước ngoài", "Yêu cầu nơi cư trú", "Hỗ trợ giấy phép làm việc / Visa"]:
            if k in ks:
                ev_key = f"Bằng chứng {k.lower().replace('yêu cầu ', '').replace('hỗ trợ ', '')}"
                ev_val = ks.get(ev_key, "")
                ev_str = f" [Bằng chứng: '{ev_val}']" if ev_val and ev_val != "Không đề cập trong nội dung JD" else ""
                print(f" - {k}: {ks[k]}{ev_str}")

    if eval_result.get('freelance_specifics'):
        print("\n--- ĐÁNH GIÁ DỰ ÁN FREELANCE & RỦI RO ---")
        fs = eval_result['freelance_specifics']
        print(f" - Phạm vi & Đầu ra:      {fs.get('Phạm vi & Đầu ra')}")
        print(f" - Tiêu chí nghiệm thu:   {fs.get('Tiêu chí nghiệm thu')}")
        print(f" - Ngân sách & Thời hạn:  {fs.get('Ngân sách & Thời hạn')}")
        print(f" - Quyền truy cập:        {fs.get('Quyền truy cập cần thiết')}")
        if fs.get('risks'):
            print(" [!] RỦI RO PHÁT HIỆN:")
            for r in fs['risks']:
                print(f"     * {r}")

    if eval_result.get('unclear_items'):
        print("\n--- ĐIỀU KIỆN THỰC TẾ CẦN XÁC MINH ---")
        for u in eval_result['unclear_items']:
            print(f" [!] {u}")

    if eval_result['clarification_questions']:
        print("\n--- CÂU HỎI CẦN LÀM RÕ VỚI NHÀ TUYỂN DỤNG / KHÁCH HÀNG ---")
        for q in eval_result['clarification_questions']:
            print(f" [?] {q}")

    # Display AI Advice if in AI mode
    if mode == "ai" and ai_result:
        print("\n" + "="*70)
        print(f" LỜI KHUYÊN KỸ THUẬT TỪ AI TƯ VẤN ({ai_result.get('provider', 'AI')})")
        print("="*70)
        if ai_result.get("status") == "PASS_ONLINE_AI":
            print(f"[Trạng thái]: KẾT NỐI LIVE AI THÀNH CÔNG (Model: {ai_result.get('model')})")
            print(f"\n{ai_result.get('ai_advice')}\n")
            print(f"Lưu ý truyền dữ liệu: {ai_result.get('sent_data_summary')}")
            print(f"{ai_result.get('privacy_note')}")
        elif ai_result.get("status") == "FAILED_AI_FALLBACK":
            print(f"[!] TRẠNG THÁI: GỌI AI THẤT BẠI - ĐÃ CHUYỂN VỀ QUY TẮC CỤC BỘ")
            print(f"    Lỗi: {ai_result.get('error')}")
            print(f"    {ai_result.get('notice')}")
        elif ai_result.get("status") == "BLOCKED_NO_API_KEY":
            print(f"[!] TRẠNG THÁI: AI BỊ CHẶN (Thiếu API Key)")
            print(f"    {ai_result.get('notice')}")
        print("="*70)

    # 6. Save to tracker if requested
    if args.save_track:
        tracker_file = Path(args.tracker_file) if getattr(args, "tracker_file", None) else None
        # Safeguard: If reading from fixture/test paths and no custom tracker file is passed,
        # redirect to demo_tracker.json in .local/temp to protect the production tracker
        if tracker_file is None and args.file and ("fixtures" in str(args.file) or "tests" in str(args.file)):
            tracker_file = TEMP_DIR / "demo_tracker.json"
        tracker = JobTracker(file_path=tracker_file) if tracker_file else JobTracker()

        # Compute job ID to check if existing (prevents overwriting application status on re-evaluation)
        company_name = jd_data.get('company', 'Chưa rõ')
        canonical_key = get_canonical_job_key(company_name, eval_result['title'], eval_result['source'] if eval_result['source'].startswith("http") else "")
        raw_hash = hashlib.sha1(f"{args.market}_{canonical_key}".encode("utf-8")).hexdigest()[:6]
        calc_id = f"job_{raw_hash}"
        existing_record = tracker.get(calc_id)

        is_favorable = (eval_result.get('match_score') is not None and eval_result['match_score'] >= 50) or ("NÊN ỨNG TUYỂN" in eval_result['recommendation'] or "CÂN NHẮC" in eval_result['recommendation'])
        rec = tracker.add_or_update(
            title=eval_result['title'],
            company=company_name,
            market=args.market,
            source=eval_result['source'],
            match_score=eval_result['match_score'],
            status=None if existing_record else ("Đang chuẩn bị hồ sơ" if is_favorable else "Chưa nộp"),
            notes=None if existing_record else eval_result['rationale'],
            next_step=None if existing_record else ("Xác minh điều kiện & Chuẩn bị phỏng vấn" if is_favorable else "Lưu trữ tham khảo"),
            job_id=calc_id
        )
        print(f"\n[+] Đã lưu vào Tracker thành công (ID: {rec['id']}, Tracker: {tracker.file_path.name}).")

    # 7. Generate docs if requested
    if args.generate_docs:
        target_output_dir = OUTPUT_DIR
        if getattr(args, "output_dir", None):
            target_output_dir = Path(args.output_dir)
        elif args.tracker_file and (".local" in str(args.tracker_file) or "temp" in str(args.tracker_file)):
            target_output_dir = LOCAL_DIR / "test_outputs"
        elif args.file and ("fixtures" in str(args.file) or "tests" in str(args.file)):
            target_output_dir = LOCAL_DIR / "test_outputs"

        target_output_dir = ensure_within_project(target_output_dir)
        target_output_dir.mkdir(parents=True, exist_ok=True)

        gen = DocumentGenerator(candidate)
        company_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', jd_data.get('company', 'company').lower()).strip('_')[:20]
        role_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', eval_result['title'].lower()).strip('_')[:30]
        clean_prefix = f"{company_clean}_{role_clean}".strip('_')
        if not clean_prefix or clean_prefix == "_":
            clean_prefix = f"job_{args.market}_eval"

        cv_md = gen.generate_cv_markdown(target_role=eval_result['title'], market=args.market)
        cv_path = ensure_within_project(target_output_dir / f"{clean_prefix}_cv.md")
        cv_path.write_text(cv_md, encoding="utf-8")
        print(f"[+] Đã tạo CV Markdown: {cv_path.name} (tại {target_output_dir.name})")

        if args.market == "freelance":
            prop_md = gen.generate_freelance_proposal(eval_result)
            prop_path = ensure_within_project(target_output_dir / f"{clean_prefix}_proposal.md")
            prop_path.write_text(prop_md, encoding="utf-8")
            print(f"[+] Đã tạo Proposal Markdown: {prop_path.name} (tại {target_output_dir.name})")
        else:
            cl_md = gen.generate_cover_letter(eval_result, language="vi")
            cl_path = ensure_within_project(target_output_dir / f"{clean_prefix}_cover_letter.md")
            cl_path.write_text(cl_md, encoding="utf-8")
            print(f"[+] Đã tạo Thư ứng tuyển Markdown: {cl_path.name} (tại {target_output_dir.name})")

        prep_md = gen.generate_interview_prep(eval_result)
        prep_path = ensure_within_project(target_output_dir / f"{clean_prefix}_interview_prep.md")
        prep_path.write_text(prep_md, encoding="utf-8")
        print(f"[+] Đã tạo Bộ luyện phỏng vấn Markdown: {prep_path.name} (tại {target_output_dir.name})")

        # Also export standalone HTML (printable via browser)
        raw_html_path = ensure_within_project(target_output_dir / f"{clean_prefix}_cv.html")
        html_path = gen.export_to_html(cv_md, raw_html_path)
        print(f"[+] Đã xuất file HTML độc lập (mở trình duyệt để in PDF): {html_path.name} (tại {target_output_dir.name})")

    print("="*70 + "\n")

def cmd_tracker(args):
    tracker_file = Path(args.tracker_file) if getattr(args, "tracker_file", None) else None
    tracker = JobTracker(file_path=tracker_file) if tracker_file else JobTracker()
    if args.subaction == "list":
        jobs = tracker.list_all(filter_market=args.market, filter_status=args.status)
        print("\n" + "="*80)
        print(f" DANH SÁCH THEO DÕI ỨNG TUYỂN (Tổng: {len(jobs)} vị trí)")
        print("="*80)
        print(f"{'ID':<12} | {'Thị trường':<10} | {'Điểm':<5} | {'Trạng thái':<18} | {'Vị trí & Công ty'}")
        print("-" * 80)
        for j in jobs:
            score_disp = str(j['match_score']) if j.get('match_score') is not None else "N/A"
            print(f"{j['id']:<12} | {j['market']:<10} | {score_disp:<5} | {j['status']:<18} | {j['title']} ({j['company']})")
        print("="*80 + "\n")
    elif args.subaction == "update":
        if not args.id:
            print("[!] Lỗi: Vui lòng cung cấp --id để cập nhật.", file=sys.stderr)
            sys.exit(1)
        existing = tracker.get(args.id)
        if not existing:
            print(f"[!] Không tìm thấy job có ID {args.id}", file=sys.stderr)
            sys.exit(1)
        updated = tracker.update_status(
            job_id=args.id,
            status=args.status or existing['status'],
            application_date=args.date,
            notes=args.notes,
            next_step=args.next_step
        )
        print(f"[+] Đã cập nhật thành công ID {updated['id']}: Trạng thái '{updated['status']}'")
    elif args.subaction == "export":
        out_path = Path(args.output) if getattr(args, "output", None) else None
        out = tracker.export_csv(output_path=out_path)
        print(f"[+] Đã xuất toàn bộ dữ liệu tracker ra CSV: {out.name}")

def cmd_deduplicate(args):
    safe_path = ensure_within_project(Path(args.file))
    data = json.loads(safe_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        data = data.get("jobs", [])
    unique, duplicates = deduplicate_jds(data)
    print(f"\n[*] Tổng số tin đưa vào: {len(data)}")
    print(f"[+] Số tin duy nhất (Unique): {len(unique)}")
    print(f"[-] Số tin trùng lặp bị loại bỏ: {len(duplicates)}")
    if duplicates:
        print("\nChi tiết các tin trùng lặp:")
        for dup in duplicates:
            print(f" - {dup.get('title')} ({dup.get('company')}) - Lý do: Trùng canonical key [{dup.get('canonical_key')}]")
    print()

def cmd_upstream_info(args):
    info = get_upstream_info()
    print("=" * 65)
    print(" THÔNG TIN KHO NGUỒN UPSTREAM (ai-job-search-dev/ai-job-search)")
    print("=" * 65)
    print(f"URL Kho gốc:       {info['canonical_upstream']}")
    print(f"Thư mục cục bộ:    {info['upstream_dir']}")
    print(f"Commit Ref:        {info['upstream_commit']}")
    print(f"Giấy phép:         {info['license']}")
    print("\nCác công cụ upstream khả dụng:")
    for tool_name, desc in info['tools_available'].items():
        print(f" - {tool_name:<20}: {desc}")
    print("=" * 65)

def cmd_upstream_key(args):
    key = get_canonical_job_key(args.company, args.title, args.url)
    print(f"Canonical Upstream Key: {key}")

def cmd_upstream_verify(args):
    res = run_upstream_security_guards()
    print("=" * 65)
    print(" KIỂM TRA BẢO MẬT CHUỖI CUNG ỨNG UPSTREAM (security_guards.py)")
    print("=" * 65)
    print(f"Trạng thái: {res['status']}")
    print(f"Kết quả:    {res.get('output', res.get('message', ''))}")
    print("=" * 65)

def main():
    parser = argparse.ArgumentParser(description="ai-job-search - Nền tảng tìm kiếm, đánh giá và ứng tuyển việc an ninh mạng")
    subparsers = parser.add_subparsers(dest="command")

    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Đánh giá mô tả công việc (JD)")
    eval_parser.add_argument("--text", help="Nội dung JD trực tiếp")
    eval_parser.add_argument("--file", help="Đường dẫn file JD (UTF-8) trong dự án")
    eval_parser.add_argument("--url", help="URL công khai của tin tuyển dụng")
    eval_parser.add_argument("--market", choices=["vietnam", "korea", "freelance"], default="vietnam", help="Thị trường mục tiêu")
    eval_parser.add_argument("--candidate", help="Đường dẫn file hồ sơ ứng viên (JSON)")
    eval_parser.add_argument("--mode", choices=["rules", "ai"], default="rules", help="Chế độ phân tích: rules (cục bộ 100% offline) hoặc ai (gọi Google Gemini qua mạng)")
    eval_parser.add_argument("--provider", choices=["gemini"], default="gemini", help="Nhà cung cấp AI (mặc định: gemini)")
    eval_parser.add_argument("--api-key", help="API Key tùy chọn cho AI (không in ra log/màn hình)")
    eval_parser.add_argument("--save-track", action="store_true", help="Lưu kết quả vào Tracker")
    eval_parser.add_argument("--tracker-file", help="Đường dẫn file tracker tùy chọn (dùng cho test/cách ly)")
    eval_parser.add_argument("--output-dir", help="Thư mục xuất tài liệu (Mặc định: output/; kiểm thử tự động lưu vào .local/test_outputs)")
    eval_parser.add_argument("--generate-docs", action="store_true", help="Tự động tạo CV, Cover Letter/Proposal, Bộ phỏng vấn")

    # Tracker command
    track_parser = subparsers.add_parser("tracker", help="Quản lý theo dõi ứng tuyển")
    track_parser.add_argument("--tracker-file", help="Đường dẫn file tracker tùy chọn")
    track_sub = track_parser.add_subparsers(dest="subaction")
    
    # tracker list
    t_list = track_sub.add_parser("list", help="Liệt kê các công việc đang theo dõi")
    t_list.add_argument("--market", choices=["vietnam", "korea", "freelance"])
    t_list.add_argument("--status", help="Lọc theo trạng thái")
    
    # tracker update
    t_update = track_sub.add_parser("update", help="Cập nhật trạng thái công việc")
    t_update.add_argument("--id", required=True, help="ID của công việc")
    t_update.add_argument("--status", help="Trạng thái mới")
    t_update.add_argument("--date", help="Ngày ứng tuyển (YYYY-MM-DD)")
    t_update.add_argument("--notes", help="Ghi chú thêm")
    t_update.add_argument("--next-step", help="Bước tiếp theo")
    
    # tracker export
    t_export = track_sub.add_parser("export", help="Xuất dữ liệu tracker ra file CSV")
    t_export.add_argument("--output", help="Đường dẫn file CSV xuất ra")

    # Deduplicate command
    dedup_parser = subparsers.add_parser("deduplicate", help="Lọc trùng danh sách tin tuyển dụng")
    dedup_parser.add_argument("--file", required=True, help="File JSON chứa danh sách JDs")

    # Upstream integration commands
    subparsers.add_parser("upstream-info", help="Xem thông tin và công cụ upstream tích hợp")

    up_key = subparsers.add_parser("upstream-key", help="Tạo canonical deduplication key qua upstream tools/job_key.py")
    up_key.add_argument("--company", required=True, help="Tên công ty")
    up_key.add_argument("--title", required=True, help="Tiêu đề vị trí tuyển dụng")
    up_key.add_argument("--url", default="", help="URL tin tuyển dụng")

    subparsers.add_parser("upstream-verify", help="Kiểm tra an toàn chuỗi cung ứng upstream qua tools/security_guards.py")

    args = parser.parse_args()

    if args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "tracker":
        cmd_tracker(args)
    elif args.command == "deduplicate":
        cmd_deduplicate(args)
    elif args.command == "upstream-info":
        cmd_upstream_info(args)
    elif args.command == "upstream-key":
        cmd_upstream_key(args)
    elif args.command == "upstream-verify":
        cmd_upstream_verify(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
