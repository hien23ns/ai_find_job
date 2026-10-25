"""
Local Web Server and REST API (FastAPI + Uvicorn).
Binds strictly to loopback (127.0.0.1).
Implements Host validation, CSRF protection, path traversal defenses,
Vietnamese localized data, and background worker coordination.
"""

import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from src.config import PROJECT_ROOT, TRACKER_DIR
from src.db import DatabaseManager, sync_db_to_tracker_json
from src.email_sender import (
    load_email_credentials,
    save_email_credentials,
    get_configured_email_provider,
    clear_email_credentials,
    EmailDispatchResult,
    SmtpEmailProvider,
    LocalMockEmailProvider
)
from src.evaluator import JobEvaluator
from src.form_automation import FormAutomationManager, FormAutomationResult
from src.hr_finder import find_hr_email, find_apply_url, sanitize_email, verify_email_domain_has_mx
from src.job_searcher import JobSearcher
from src.modern_tech_cv import create_job_application_package
from src.security import ensure_within_project
from src.worker import ApplicationWorker

SERVER_INFO_FILE = PROJECT_ROOT / ".local" / "server_info.json"
STATIC_DIR = PROJECT_ROOT / "src" / "web_ui"
CANDIDATE_FILE = PROJECT_ROOT / "data" / "candidates" / "my_profile.json"

app = FastAPI(title="ai-find-job - Trợ lý Tìm việc & Ứng tuyển Tự động", docs_url=None, redoc_url=None)

# Initialize Session CSRF Token
CSRF_TOKEN = secrets.token_hex(24)

# Global Worker Instance
_WORKER_INSTANCE: Optional[ApplicationWorker] = None


def get_worker() -> ApplicationWorker:
    global _WORKER_INSTANCE
    if _WORKER_INSTANCE is None:
        _WORKER_INSTANCE = ApplicationWorker()
        _WORKER_INSTANCE.start()
    return _WORKER_INSTANCE


@app.middleware("http")
async def security_and_csrf_middleware(request: Request, call_next):
    # 1. Host Validation (Prevent DNS Rebinding)
    host = request.headers.get("host", "")
    if not (host.startswith("127.0.0.1") or host.startswith("localhost") or host.startswith("testserver")):
        return Response(content="Lỗi bảo mật: Truy cập bị từ chối (Chỉ chấp nhận kết nối loopback cục bộ).", status_code=403)

    # 2. CSRF Validation for State-Mutating Requests
    if request.method in ["POST", "PUT", "DELETE"]:
        # Skip CSRF check for health / csrf-token endpoints
        if not (request.url.path in ["/api/csrf-token", "/api/health"]):
            client_csrf = request.headers.get("X-CSRF-Token")
            if not client_csrf or client_csrf != CSRF_TOKEN:
                return JSONResponse(
                    status_code=403,
                    content={"error": "Mã xác thực CSRF không hợp lệ hoặc đã hết hạn. Vui lòng tải lại trang."}
                )

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


# --- Static Files & SPA Route ---
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Giao diện web chưa được cài đặt.")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


@app.get("/style.css")
async def serve_css():
    css_file = STATIC_DIR / "style.css"
    if not css_file.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp CSS.")
    return Response(content=css_file.read_text(encoding="utf-8"), media_type="text/css; charset=utf-8")


@app.get("/app.js")
async def serve_js():
    js_file = STATIC_DIR / "app.js"
    if not js_file.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp JS.")
    return Response(content=js_file.read_text(encoding="utf-8"), media_type="application/javascript; charset=utf-8")


@app.get("/api/profile/avatar")
async def get_candidate_avatar():
    avatar_file = PROJECT_ROOT / "data" / "private" / "assets" / "avatar.png"
    if avatar_file.exists():
        return FileResponse(path=str(avatar_file), media_type="image/png")
    # Fallback to high-quality SVG avatar
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="130" height="150" viewBox="0 0 130 150">
      <rect width="130" height="150" fill="#0f172a"/>
      <circle cx="65" cy="55" r="28" fill="#0284c7"/>
      <path d="M 22 135 C 22 98, 108 98, 108 135 Z" fill="#0284c7"/>
      <text x="65" y="142" font-size="11" fill="#94a3b8" text-anchor="middle" font-family="sans-serif">Ứng viên</text>
    </svg>'''
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


@app.get("/api/csrf-token")
async def get_csrf():
    return {"csrf_token": CSRF_TOKEN}


# --- Dashboard Endpoint ---
@app.get("/api/dashboard")
async def get_dashboard():
    db = DatabaseManager()
    summary = db.get_dashboard_summary()
    worker = get_worker()

    # Browser check
    profile_dir = PROJECT_ROOT / ".local" / "browser_profile"
    browser_ready = profile_dir.exists()

    # Email provider check
    creds = load_email_credentials()
    email_status = "Đã cấu hình SMTP" if creds else "Dùng Mock Provider cục bộ"

    return {
        "summary": summary,
        "worker_status": "Đang chạy" if worker.is_running else "Đã dừng",
        "browser_status": "Sẵn sàng" if browser_ready else "Khởi tạo lần đầu",
        "email_status": email_status
    }


# --- Candidate Profile Endpoints ---
@app.get("/api/profile")
async def get_profile():
    ensure_within_project(CANDIDATE_FILE)
    if not CANDIDATE_FILE.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy file hồ sơ ứng viên.")
    data = json.loads(CANDIDATE_FILE.read_text(encoding="utf-8"))
    return data


@app.put("/api/profile")
async def update_profile(request: Request):
    ensure_within_project(CANDIDATE_FILE)
    new_data = await request.json()

    # Create backup before edit
    backup_dir = PROJECT_ROOT / "data" / "candidates" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"my_profile_backup_{ts}.json"
    if CANDIDATE_FILE.exists():
        backup_file.write_text(CANDIDATE_FILE.read_text(encoding="utf-8"), encoding="utf-8")

    # Atomic write
    tmp_file = CANDIDATE_FILE.with_suffix(".tmp")
    tmp_file.write_text(json.dumps(new_data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_file, CANDIDATE_FILE)

    return {"status": "success", "message": "Đã lưu cập nhật hồ sơ cá nhân an toàn."}


# --- Jobs Search and Evaluation Endpoints ---
@app.get("/api/jobs")
async def list_jobs(
    market: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    location: Optional[str] = None,
    work_mode: Optional[str] = None,
    employment_type: Optional[str] = None,
    q: Optional[str] = None,
    only_email: bool = False
):
    db = DatabaseManager()
    raw_jobs = db.list_jobs(
        market=market,
        status=status,
        category=category,
        location=location,
        work_mode=work_mode,
        employment_type=employment_type,
        search_query=q
    )
    enriched = []
    app_records = db.list_applications()
    app_job_ids = {a.get("job_id") for a in app_records if a.get("job_id") and a.get("package_dir")}

    for j in raw_jobs:
        hr_email = sanitize_email(find_hr_email(company=j.get("company", ""), raw_jd=j.get("raw_jd", ""), source_url=j.get("source", "")))
        apply_url = find_apply_url(company=j.get("company", ""), raw_jd=j.get("raw_jd", ""), source_url=j.get("source", ""))
        has_email = bool(hr_email and "@" in hr_email and "." in hr_email.split("@")[-1])
        if only_email and not has_email:
            continue
        j_copy = dict(j)
        j_copy["hr_email"] = hr_email
        j_copy["has_hr_email"] = has_email
        j_copy["apply_url"] = apply_url
        j_copy["preferred_channel"] = "email" if has_email else "form"
        j_copy["has_package"] = j.get("id") in app_job_ids
        enriched.append(j_copy)

    # Sort: Prioritize jobs with verified HR email first, then match_score descending, then updated_at
    enriched.sort(key=lambda x: (1 if x["has_hr_email"] else 0, x.get("match_score", 0), x.get("updated_at", "")), reverse=True)
    return enriched


@app.get("/api/candidate/form-assist")
async def get_candidate_form_assist():
    candidate_data = {}
    if CANDIDATE_FILE.exists():
        candidate_data = json.loads(CANDIDATE_FILE.read_text(encoding="utf-8"))

    edu = candidate_data.get("education", [{}])[0] if candidate_data.get("education") else {}
    contact = candidate_data.get("contact", {})
    return {
        "full_name": candidate_data.get("name", "Ngô Văn Hiền"),
        "email": contact.get("email", "hienngo090800@gmail.com"),
        "phone": contact.get("phone", "0393492064"),
        "university": edu.get("institution", "Trường Đại học Công nghệ thông tin và Truyền thông Việt - Hàn (VKU)"),
        "major": edu.get("major", "Mạng và An toàn thông tin"),
        "graduation_year": "2028 (Dự kiến)",
        "location": contact.get("location", "Ngũ Hành Sơn, Đà Nẵng, Việt Nam"),
        "github": contact.get("github", "https://github.com/hien23ns"),
        "linkedin": contact.get("linkedin", "https://www.linkedin.com/in/ngovanhien"),
        "website": contact.get("website", "https://ngovanhien.id.vn"),
        "summary": candidate_data.get("summary", "")
    }


@app.post("/api/jobs/{job_id}/mark-form-submitted")
async def mark_job_form_submitted(job_id: str, request: Request):
    db = DatabaseManager()
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy việc làm")

    now_date = datetime.now().strftime("%Y-%m-%d")
    job["status"] = "Đã nộp qua form"
    job["application_date"] = now_date
    job["apply_channel"] = "form"
    db.save_job(job)

    app_record = db.get_application_by_job_id(job_id)
    if app_record:
        worker = get_worker()
        worker.transition_state(
            app_record["id"], "SUBMITTED",
            action="MANUAL_FORM_SUBMISSION_CONFIRMED",
            details="Ứng viên đã điền form tuyển dụng và xác nhận nộp thành công."
        )

    return {
        "status": "success",
        "message": f"🎉 Đã ghi nhận nộp form thành công cho '{job['company']} - {job['title']}'!"
    }


@app.post("/api/applications/{app_id}/mark-form-submitted")
async def mark_app_form_submitted(app_id: str, request: Request):
    db = DatabaseManager()
    app_record = db.get_application(app_id) or db.get_application_by_job_id(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ ứng tuyển")
    return await mark_job_form_submitted(app_record["job_id"], request)


@app.get("/api/jobs/{job_id}")
async def get_job_detail(job_id: str):
    db = DatabaseManager()
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy công việc {job_id}")
    app_record = db.get_application_by_job_id(job_id)
    auto_hr_email = find_hr_email(company=job.get("company", ""), raw_jd=job.get("raw_jd", ""), source_url=job.get("source", ""))
    auto_apply_url = find_apply_url(company=job.get("company", ""), raw_jd=job.get("raw_jd", ""), source_url=job.get("source", ""))
    return {
        "job": job,
        "application": app_record,
        "auto_hr_email": auto_hr_email,
        "auto_apply_url": auto_apply_url
    }


@app.post("/api/jobs/search")
async def execute_job_search(request: Request):
    payload = await request.json()
    keywords = (payload.get("keywords") or "").strip()
    market = payload.get("market", "vietnam")
    limit = int(payload.get("limit", 15))
    category = payload.get("category", "all")
    loc_filter = payload.get("location", "all")
    work_mode = payload.get("work_mode", "all")
    employment_type = payload.get("employment_type", "all")

    db = DatabaseManager()
    searcher = JobSearcher()

    # Determine default keywords if user left it blank
    effective_keywords = keywords
    if not effective_keywords:
        if category == "design":
            effective_keywords = "UI/UX Graphic Designer"
        elif category == "marketing":
            effective_keywords = "Digital Marketing Content Creator"
        elif category == "it":
            effective_keywords = "Software Developer CNTT"
        elif category == "security":
            effective_keywords = "Cyber Security SOC Analyst"
        elif category == "sales":
            effective_keywords = "Business Development Sales"
        else:
            effective_keywords = "Thực tập sinh Intern"

    # Geo location for live search
    location_str = "Vietnam"
    if loc_filter == "danang":
        location_str = "Da Nang, Vietnam"
    elif loc_filter == "hanoi":
        location_str = "Hanoi, Vietnam"
    elif loc_filter == "hcm":
        location_str = "Ho Chi Minh City, Vietnam"
    elif loc_filter == "cantho":
        location_str = "Can Tho, Vietnam"
    elif loc_filter == "haiphong":
        location_str = "Hai Phong, Vietnam"
    elif loc_filter == "remote" or work_mode == "remote":
        location_str = "Remote"
    elif market == "korea" or loc_filter == "korea":
        location_str = "South Korea"
    elif market == "freelance":
        location_str = "Remote"

    live_query = effective_keywords
    if work_mode == "remote" and "remote" not in live_query.lower():
        live_query += " Remote"
    if employment_type == "parttime" and "part" not in live_query.lower():
        live_query += " Part-time"

    candidate_profile = CANDIDATE_FILE if CANDIDATE_FILE.exists() else (PROJECT_ROOT / "data" / "candidates" / "candidate_mock.json")

    # 1. Multi-Platform Search Aggregation
    aggregated_jobs = []

    # Source A: Live Active Search (LinkedIn Guest API - Verifying isActive == True)
    try:
        live_linkedin = searcher.search_live_active_jobs(
            query=live_query,
            location=location_str,
            limit=limit,
            market=market,
            candidate_profile_path=candidate_profile
        )
        for j in live_linkedin:
            j["source_platform"] = "LinkedIn (Live & Đang mở tuyển)"
            aggregated_jobs.append(j)
    except Exception as e:
        print(f"Notice: LinkedIn live search: {e}")

    # Source B: Multi-Platform Tech Catalog (TopCV, ITviec, VietnamWorks, CareerViet, Direct Enterprise Portals)
    try:
        from src.multi_platform_searcher import get_all_multi_platform_jobs
        platform_jobs = get_all_multi_platform_jobs(
            category=category,
            location=loc_filter,
            work_mode=work_mode,
            employment_type=employment_type,
            query=keywords if keywords else None
        )
        for pj in platform_jobs:
            pj_copy = dict(pj)
            pj_copy["source_platform"] = pj.get("platform_source", "TopCV / ITviec / Doanh nghiệp")
            pj_copy["description"] = pj.get("raw_jd", "")
            pj_copy["url"] = pj.get("source", "")
            pj_copy["is_live"] = True
            pj_copy["is_active"] = True
            aggregated_jobs.append(pj_copy)
    except Exception as e:
        print(f"Notice: Multi-platform catalog: {e}")

    # Source C: Freehire (if market is freelance or remote requested)
    if market == "freelance" or work_mode == "remote" or loc_filter == "remote" or "remote" in effective_keywords.lower():
        try:
            freehire_jobs = searcher.search_freehire(query=effective_keywords, region="apac", limit=limit, remote="remote")
            for fj in freehire_jobs:
                fj["source_platform"] = "Freehire (Remote / APAC)"
                aggregated_jobs.append(fj)
        except Exception as e:
            print(f"Notice: Freehire search: {e}")

    # 2. Collision-resistant deduplication across platforms using canonical keys
    from src.upstream_bridge import get_canonical_job_key
    seen_keys = set()
    unique_to_import = []
    for j in aggregated_jobs:
        company = (j.get("company") or "Chưa rõ").strip()
        title = (j.get("title") or effective_keywords).strip()
        url = (j.get("url") or j.get("source") or "").strip()
        ck = get_canonical_job_key(company, title, url)
        if ck not in seen_keys:
            seen_keys.add(ck)
            j["canonical_key"] = ck
            unique_to_import.append(j)

    # 3. Read & understand job + resolve verified HR email & MX
    for j in unique_to_import:
        desc = j.get("description") or j.get("raw_jd") or ""
        email = sanitize_email(j.get("hr_email") or find_hr_email(company=j.get("company", ""), raw_jd=desc, source_url=j.get("url", "")))
        mx_ok, _ = verify_email_domain_has_mx(email) if email else (False, "")
        j["has_hr_email"] = bool(email and mx_ok)
        j["hr_email"] = email if (email and mx_ok) else ""
        j["apply_url"] = find_apply_url(company=j.get("company", ""), raw_jd=desc, source_url=j.get("url", ""))

    # Prioritize: Verified HR email first, then ATS match_score descending
    unique_to_import.sort(key=lambda x: (1 if x["has_hr_email"] else 0, x.get("match_score", 80)), reverse=True)

    imported_count = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 4. Save into Database with atomic collision-resistant deduplication
    for j in unique_to_import:
        j_id = j.get("id") or f"job_{secrets.token_hex(4)}"
        company = j.get("company", "Công ty chưa rõ")
        title = j.get("title", effective_keywords)
        desc = j.get("description") or j.get("raw_jd") or ""
        j_cat = j.get("category") or (category if category != "all" else None)
        j["id"] = j_id
        j["category"] = j_cat

        db.save_job({
            "id": j_id,
            "title": title,
            "company": company,
            "market": market,
            "source": j.get("url") or j.get("source") or "",
            "match_score": int(j.get("match_score", 85)),
            "status": "Chưa nộp",
            "notes": f"🟢 Tin tuyển dụng thực tế đang tuyển | Nguồn: {j.get('source_platform', 'Đa nền tảng')}",
            "canonical_key": j.get("canonical_key", f"{company}_{title}".lower().replace(" ", "_")),
            "raw_jd": desc,
            "category": j_cat,
            "location": j.get("location"),
            "work_mode": j.get("work_mode"),
            "employment_type": j.get("employment_type"),
            "created_at": now,
            "updated_at": now
        })
        imported_count += 1

    return {
        "imported_count": imported_count,
        "total_found": len(unique_to_import),
        "is_live": True,
        "message": f"🎉 Đã quét đa nền tảng (LinkedIn, TopCV, ITviec, Enterprise)! Tìm thấy {len(unique_to_import)} tin tuyển dụng thực tế không trùng lặp.",
        "jobs": unique_to_import
    }


# --- Application Package & Generation Endpoints ---
@app.post("/api/jobs/{job_id}/prepare-package")
async def prepare_package(job_id: str):
    db = DatabaseManager()
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy việc làm")

    candidate_data = json.loads(CANDIDATE_FILE.read_text(encoding="utf-8"))

    # Generate complete Modern Tech package in a worker thread to avoid Playwright sync API inside asyncio loop
    pkg_res = await asyncio.to_thread(
        create_job_application_package,
        candidate=candidate_data,
        eval_result={"match_score": job.get("match_score", 85), "hard_requirements": [], "category": job.get("category")},
        jd_data={"company": job["company"], "title": job["title"], "text": job.get("raw_jd", ""), "id": job_id, "category": job.get("category")}
    )

    pkg_dir = pkg_res.get("version_dir") or pkg_res.get("package_dir")
    app_id = f"app_{job_id}_{secrets.token_hex(2)}"

    # Automatically discover HR email and apply URL
    auto_hr_email = find_hr_email(company=job.get("company", ""), raw_jd=job.get("raw_jd", ""), source_url=job.get("source", ""))
    auto_apply_url = find_apply_url(company=job.get("company", ""), raw_jd=job.get("raw_jd", ""), source_url=job.get("source", ""))

    # Determine default channel & recipient
    if auto_hr_email:
        channel = "email"
        recipient = auto_hr_email
    elif auto_apply_url:
        channel = "form"
        recipient = auto_apply_url
    elif "http" in job.get("source", ""):
        channel = "form"
        recipient = job.get("source")
    else:
        channel = "email"
        recipient = auto_hr_email or ""

    initial_status = "READY" if channel == "email" else "NEEDS_REVIEW"

    app_data = {
        "id": app_id,
        "job_id": job_id,
        "company": job["company"],
        "role": job["title"],
        "package_dir": str(pkg_dir),
        "status": initial_status,
        "channel": channel,
        "recipient": recipient,
        "eml_draft_file": "draft_application.eml",
        "preview_file": "email_preview.html",
        "form_answers": {
            "full_name": candidate_data.get("name"),
            "email": candidate_data.get("contact", {}).get("email"),
            "phone": candidate_data.get("contact", {}).get("phone"),
            "university": "VKU"
        },
        "unverified_conditions": [],
        "attachments": [{"filename": "cv_en.pdf"}, {"filename": "cover_letter_en.md"}],
        "current_step": "PREPARED",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    db.save_application(app_data)
    db.add_history(
        application_id=app_id,
        action="PACKAGE_PREPARED",
        status=initial_status,
        details=f"Đã tạo thành công bộ hồ sơ Modern Tech và bản nháp ứng tuyển tại {pkg_dir.name}."
    )

    return {
        "status": "success",
        "application_id": app_id,
        "package_dir": str(pkg_dir),
        "auto_hr_email": auto_hr_email,
        "auto_apply_url": auto_apply_url
    }


@app.post("/api/jobs/batch-prepare-packages")
async def batch_prepare_packages(request: Request):
    payload = await request.json()
    job_ids = payload.get("job_ids", [])
    if not job_ids:
        raise HTTPException(status_code=400, detail="Danh sách job_ids không được để trống")

    results = []
    for jid in job_ids:
        try:
            res = await prepare_package(jid)
            results.append({"job_id": jid, "status": "success", "package": res})
        except Exception as e:
            results.append({"job_id": jid, "status": "error", "error": str(e)})

    return {
        "status": "success",
        "total_requested": len(job_ids),
        "success_count": sum(1 for r in results if r["status"] == "success"),
        "results": results
    }


@app.get("/api/packages/{job_id}")
async def get_package_details(job_id: str):
    db = DatabaseManager()
    app_record = db.get_application_by_job_id(job_id) or db.get_application(job_id)
    if not app_record or not app_record.get("package_dir"):
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Chưa có gói hồ sơ cho công việc này.")
        pkg_res = await prepare_package(job_id)
        app_record = db.get_application(pkg_res["application_id"])

    pkg_dir = Path(app_record["package_dir"])
    ensure_within_project(pkg_dir)

    job = db.get_job(app_record.get("job_id", job_id)) or {}
    auto_hr_email = find_hr_email(company=job.get("company", app_record.get("company", "")), raw_jd=job.get("raw_jd", ""), source_url=job.get("source", ""))
    auto_apply_url = find_apply_url(company=job.get("company", app_record.get("company", "")), raw_jd=job.get("raw_jd", ""), source_url=job.get("source", ""))

    # Auto-populate recipient if blank
    if not app_record.get("recipient"):
        if app_record.get("channel") == "email":
            app_record["recipient"] = auto_hr_email
        else:
            app_record["recipient"] = auto_apply_url or auto_hr_email
        db.save_application(app_record)

    # Read cover letter & email body for live editor
    cl_text = ""
    if (pkg_dir / "cover_letter_en.md").exists():
        cl_text = (pkg_dir / "cover_letter_en.md").read_text(encoding="utf-8")

    from src.application_sender import extract_clean_email_components
    _, email_text, _ = extract_clean_email_components(
        pkg_dir=pkg_dir,
        role=app_record.get("role", ""),
        company=app_record.get("company", "")
    )

    pdf_url = f"/files/{pkg_dir.relative_to(PROJECT_ROOT).as_posix()}/cv_en.pdf"
    preview_html_url = f"/files/{pkg_dir.relative_to(PROJECT_ROOT).as_posix()}/email_preview.html"

    return {
        "application": app_record,
        "cover_letter_text": cl_text,
        "email_body_text": email_text,
        "pdf_url": pdf_url,
        "preview_html_url": preview_html_url,
        "history": db.get_history(app_record["id"]),
        "auto_hr_email": auto_hr_email,
        "auto_apply_url": auto_apply_url
    }


@app.put("/api/packages/{job_id}/documents")
async def update_package_documents(job_id: str, request: Request):
    db = DatabaseManager()
    app_record = db.get_application_by_job_id(job_id) or db.get_application(job_id)
    if not app_record or not app_record.get("package_dir"):
        raise HTTPException(status_code=404, detail="Không tìm thấy gói hồ sơ.")

    pkg_dir = Path(app_record["package_dir"])
    ensure_within_project(pkg_dir)
    payload = await request.json()

    if "cover_letter_text" in payload:
        (pkg_dir / "cover_letter_en.md").write_text(payload["cover_letter_text"], encoding="utf-8")

    if "email_body_text" in payload:
        clean_text = payload["email_body_text"]
        (pkg_dir / "email_clean_body.txt").write_text(clean_text, encoding="utf-8")
        (pkg_dir / "email_body.txt").write_text(clean_text, encoding="utf-8")
        from src.application_sender import build_corporate_email_html
        (pkg_dir / "email_clean_body.html").write_text(
            build_corporate_email_html(clean_text, candidate_name="Ngô Văn Hiền"),
            encoding="utf-8"
        )

    db.add_history(
        application_id=app_record["id"],
        action="DOCUMENTS_EDITED",
        status=app_record["status"],
        details="Ứng viên đã chỉnh sửa nội dung thư ứng tuyển / email trên giao diện."
    )

    return {"status": "success", "message": "Đã lưu thay đổi tài liệu ứng tuyển."}


@app.put("/api/applications/{app_id}/channel")
async def update_application_channel(app_id: str, request: Request):
    payload = await request.json()
    channel = payload.get("channel", "form")
    recipient = payload.get("recipient", "").strip()

    db = DatabaseManager()
    app_record = db.get_application(app_id) or db.get_application_by_job_id(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ ứng tuyển.")

    app_record["channel"] = channel
    app_record["recipient"] = recipient
    db.save_application(app_record)

    job_id = app_record.get("job_id")
    if job_id:
        job = db.get_job(job_id)
        if job:
            job["apply_channel"] = channel
            job["recipient"] = recipient
            db.save_job(job)

    db.add_history(
        application_id=app_record["id"],
        action="CHANNEL_CONFIGURED",
        status=app_record["status"],
        details=f"Đã cập nhật kênh nộp: {channel} - Người nhận: {recipient}"
    )

    return {"status": "success", "message": "Đã lưu kênh ứng tuyển và thông tin người nhận."}


@app.post("/api/applications/{app_id}/direct-fill")
async def direct_form_fill(app_id: str, request: Request):
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        pass

    db = DatabaseManager()
    app_record = db.get_application(app_id) or db.get_application_by_job_id(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ ứng tuyển.")

    # Anti-duplicate lock
    if app_record.get("status") in ["SUBMITTED", "Đã nộp", "Đã nộp qua form"] and not payload.get("force"):
        raise HTTPException(status_code=400, detail=f"Công việc này đã nộp thành công trước đó ({app_record['status']}). Chặn nộp trùng để bảo vệ an toàn.")

    if "recipient" in payload and payload["recipient"]:
        app_record["recipient"] = payload["recipient"].strip()
        app_record["channel"] = "form"
        db.save_application(app_record)

    recipient_url = app_record.get("recipient", "").strip()
    if not recipient_url or not recipient_url.startswith("http"):
        job_id = app_record.get("job_id")
        job = db.get_job(job_id) if job_id else None
        if job:
            found_url = find_apply_url(
                company=job.get("company", ""),
                raw_jd=job.get("raw_jd", ""),
                source_url=job.get("source", "")
            )
            if found_url and found_url.startswith("http"):
                recipient_url = found_url
                app_record["recipient"] = recipient_url
                app_record["channel"] = "form"
                db.save_application(app_record)

    if not recipient_url or not recipient_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Vui lòng nhập đường dẫn URL hợp lệ của trang Form tuyển dụng (bắt đầu bằng http:// hoặc https://).")

    pkg_dir = Path(app_record.get("package_dir", ""))
    cv_path = pkg_dir / "cv_en.pdf"
    if not cv_path.exists():
        cv_path = None

    dry_run = payload.get("dry_run", False)

    def _execute_fill():
        automator = FormAutomationManager(headless=False)
        try:
            res = automator.process_application_form(
                url=recipient_url,
                app_data=app_record,
                cv_path=cv_path,
                dry_run=dry_run
            )
            return res
        finally:
            automator.close()

    result: FormAutomationResult = await asyncio.to_thread(_execute_fill)

    worker = get_worker()
    if result.status == "SUCCESS":
        worker.transition_state(
            app_record["id"], "SUBMITTED",
            action="DIRECT_FORM_SUBMISSION_SUCCESS",
            details=result.message,
            proof_data={"proof_path": result.proof_path}
        )
    elif result.status == "NEEDS_REVIEW":
        worker.transition_state(
            app_record["id"], "NEEDS_REVIEW",
            action="DIRECT_FORM_FILLED",
            details=result.message,
            proof_data={"proof_path": result.proof_path}
        )
    elif result.status == "AWAITING_USER":
        worker.transition_state(
            app_record["id"], "AWAITING_USER",
            action="DIRECT_FORM_USER_INTERVENTION",
            details=result.message,
            proof_data=result.question_prompt
        )
    else:
        worker.transition_state(
            app_record["id"], "FAILED",
            action="DIRECT_FORM_FAILED",
            details=result.message
        )

    return {
        "status": result.status,
        "message": result.message,
        "proof_path": result.proof_path,
        "current_step": result.current_step
    }


@app.post("/api/applications/{app_id}/direct-send-email")
async def direct_send_email(app_id: str, request: Request):
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        pass

    db = DatabaseManager()
    app_record = db.get_application(app_id) or db.get_application_by_job_id(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ ứng tuyển.")

    # Anti-duplicate lock
    if app_record.get("status") in ["SUBMITTED", "Đã nộp", "Đã gửi email"] and not payload.get("force"):
        raise HTTPException(status_code=400, detail=f"Công việc này đã nộp thành công trước đó ({app_record['status']}). Chặn gửi trùng để bảo vệ an toàn.")

    if "recipient" in payload and payload["recipient"]:
        app_record["recipient"] = sanitize_email(payload["recipient"])
        app_record["channel"] = "email"
        db.save_application(app_record)

    to_email = sanitize_email(app_record.get("recipient", ""))
    if not to_email:
        job_id = app_record.get("job_id")
        job = db.get_job(job_id) if job_id else None
        if job:
            found_email = sanitize_email(find_hr_email(
                company=job.get("company", ""),
                raw_jd=job.get("raw_jd", ""),
                source_url=job.get("source", "")
            ))
            if found_email and "@" in found_email:
                to_email = found_email
                app_record["recipient"] = to_email
                app_record["channel"] = "email"
                db.save_application(app_record)

    to_email = sanitize_email(to_email)
    if not to_email or "@" not in to_email or "." not in to_email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Vui lòng nhập địa chỉ email người nhận hợp lệ (ví dụ: hr@company.com).")

    # Domain MX safeguard: verify email domain resolves before sending
    is_valid_domain, domain_msg = verify_email_domain_has_mx(to_email)
    if not is_valid_domain:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể gửi email tới '{to_email}': {domain_msg}. Vui lòng kiểm tra lại địa chỉ email hoặc chọn phương thức nộp qua Form."
        )

    pkg_dir = Path(app_record.get("package_dir", ""))
    ensure_within_project(pkg_dir)

    from src.application_sender import extract_clean_email_components
    subject, body_text, body_html = extract_clean_email_components(
        pkg_dir=pkg_dir,
        role=app_record.get("role", ""),
        company=app_record.get("company", ""),
        candidate_name="Ngô Văn Hiền"
    )

    cv_file = pkg_dir / "cv_en.pdf"
    if not cv_file.exists():
        cv_file = pkg_dir / "cv_vi.pdf"

    attachments = []
    if cv_file.exists():
        attachments.append(cv_file)

    worker = get_worker()
    worker.transition_state(
        app_record["id"], "SUBMITTING",
        action="DIRECT_EMAIL_DISPATCH_STARTED",
        details=f"Đang tiến hành gửi email trực tiếp tới {to_email}..."
    )

    provider = get_configured_email_provider()

    def _execute_send():
        return provider.send_email(
            from_email="hienngo090800@gmail.com",
            from_name="Ngô Văn Hiền",
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachment_paths=attachments
        )

    res: EmailDispatchResult = await asyncio.to_thread(_execute_send)
    is_mock = isinstance(provider, LocalMockEmailProvider)

    if res.status == "SENT":
        mode_note = "[CHẾ ĐỘ THỬ NGHIỆM MOCK: Thư chỉ ghi nhận cục bộ, chưa gửi thật vì chưa cài đặt Gmail App Password trong Cài đặt]" if is_mock else "[GỬI THẬT 100% qua Gmail SMTP - Vui lòng kiểm tra mục Thư đã gửi]"
        worker.transition_state(
            app_record["id"], "SUBMITTED",
            action="DIRECT_EMAIL_SUCCESS",
            details=f"Đã gửi email thành công tới {to_email}. {mode_note} Message-ID: {res.message_id}",
            proof_data={"message_id": res.message_id, "recipient": to_email, "is_mock": is_mock}
        )
        return {
            "status": "success",
            "is_mock": is_mock,
            "message": f"Đã gửi email ứng tuyển thành công tới {to_email}! {mode_note}",
            "message_id": res.message_id
        }
    else:
        worker.transition_state(
            app_record["id"], "FAILED",
            action="DIRECT_EMAIL_FAILED",
            details=res.message
        )
        raise HTTPException(status_code=500, detail=f"Không thể gửi email: {res.message}")


@app.post("/api/jobs/{job_id}/auto-apply-email")
async def auto_apply_email_by_job(job_id: str, request: Request):
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        pass

    db = DatabaseManager()
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy việc làm")

    # Anti-duplicate safeguard
    if job.get("status") in ["Đã nộp", "Đã gửi email", "Đã nộp qua form", "SUBMITTED"] and not payload.get("force"):
        raise HTTPException(status_code=400, detail=f"Việc làm '{job['company']} - {job['title']}' đã nộp thành công trước đó ({job['status']}). Chặn gửi trùng để bảo vệ an toàn.")

    # 1. Ensure package is ready
    app_record = db.get_application_by_job_id(job_id)
    if not app_record or not app_record.get("package_dir"):
        pkg_res = await prepare_package(job_id)
        app_record = db.get_application(pkg_res["application_id"])

    # 2. Automatically find HR email
    to_email = sanitize_email(payload.get("recipient", ""))
    if not to_email:
        to_email = sanitize_email(find_hr_email(company=job.get("company", ""), raw_jd=job.get("raw_jd", ""), source_url=job.get("source", "")))

    if not to_email or "@" not in to_email or "." not in to_email.split("@")[-1]:
        apply_url = find_apply_url(company=job.get("company", ""), raw_jd=job.get("raw_jd", ""), source_url=job.get("source", ""))
        url_hint = f" ({apply_url})" if apply_url else ""
        raise HTTPException(
            status_code=400,
            detail=f"Tin tuyển dụng của '{job.get('company')}' không có email HR trực tiếp trong JD mà tiếp nhận hồ sơ qua link ứng tuyển{url_hint}. Vui lòng bấm '📝 Điền & Nộp Form' hoặc nhập email HR chính xác vào ô Người nhận nếu bạn có."
        )

    # Domain MX safeguard: verify email domain resolves before sending
    is_valid_domain, domain_msg = verify_email_domain_has_mx(to_email)
    if not is_valid_domain:
        raise HTTPException(
            status_code=400,
            detail=f"Email HR '{to_email}' không hợp lệ hoặc không có máy chủ nhận thư: {domain_msg}. Vui lòng kiểm tra lại địa chỉ email hoặc chọn nộp qua Form."
        )

    app_record["recipient"] = to_email
    app_record["channel"] = "email"
    db.save_application(app_record)

    pkg_dir = Path(app_record.get("package_dir", ""))
    ensure_within_project(pkg_dir)

    from src.application_sender import extract_clean_email_components
    subject, body_text, body_html = extract_clean_email_components(
        pkg_dir=pkg_dir,
        role=job.get("title", ""),
        company=job.get("company", ""),
        candidate_name="Ngô Văn Hiền"
    )

    cv_file = pkg_dir / "cv_en.pdf"
    if not cv_file.exists():
        cv_file = pkg_dir / "cv_vi.pdf"

    attachments = [cv_file] if cv_file.exists() else []

    worker = get_worker()
    worker.transition_state(
        app_record["id"], "SUBMITTING",
        action="AUTO_EMAIL_DISPATCH_STARTED",
        details=f"Đang tự động gửi email ứng tuyển tới HR ({to_email})..."
    )

    provider = get_configured_email_provider()

    def _execute_send():
        return provider.send_email(
            from_email="hienngo090800@gmail.com",
            from_name="Ngô Văn Hiền",
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachment_paths=attachments
        )

    res: EmailDispatchResult = await asyncio.to_thread(_execute_send)
    is_mock = isinstance(provider, LocalMockEmailProvider)

    if res.status == "SENT":
        mode_note = "[CHẾ ĐỘ THỬ NGHIỆM MOCK: Thư chỉ ghi nhận cục bộ, chưa gửi thật vì chưa cài đặt Gmail App Password trong Cài đặt]" if is_mock else "[GỬI THẬT 100% qua Gmail SMTP - Vui lòng kiểm tra mục Thư đã gửi]"
        worker.transition_state(
            app_record["id"], "SUBMITTED",
            action="AUTO_EMAIL_DISPATCH_SUCCESS",
            details=f"Đã tự động gửi email ứng tuyển tới HR ({to_email}) thành công. {mode_note} Message-ID: {res.message_id}",
            proof_data={"message_id": res.message_id, "recipient": to_email, "is_mock": is_mock}
        )
        job = db.get_job(job_id)
        if job:
            job["status"] = "Đã gửi email"
            job["application_date"] = datetime.now().strftime("%Y-%m-%d")
            job["recipient"] = to_email
            job["apply_channel"] = "email"
            db.save_job(job)

        return {
            "status": "success",
            "hr_email": to_email,
            "is_mock": is_mock,
            "message": f"🚀 Đã tự động tìm thấy email HR ({to_email}) và gửi hồ sơ ứng tuyển kèm CV thành công! {mode_note}",
            "message_id": res.message_id
        }
    else:
        worker.transition_state(
            app_record["id"], "FAILED",
            action="AUTO_EMAIL_DISPATCH_FAILED",
            details=res.message
        )
        raise HTTPException(status_code=500, detail=f"Không thể gửi email tới {to_email}: {res.message}")


@app.post("/api/applications/{app_id}/auto-apply-email")
async def auto_apply_email_by_app(app_id: str, request: Request):
    db = DatabaseManager()
    app_record = db.get_application(app_id) or db.get_application_by_job_id(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ ứng tuyển")
    return await auto_apply_email_by_job(app_record["job_id"], request)


# --- Queue & Dispatch Center Endpoints ---
@app.get("/api/queue")
async def get_queue():
    db = DatabaseManager()
    return db.list_applications()


@app.post("/api/queue/dispatch")
async def dispatch_queue_action(request: Request):
    payload = await request.json()
    app_id = payload.get("application_id")
    action = payload.get("action")  # "queue", "submit", "pause", "cancel"

    db = DatabaseManager()
    app_record = db.get_application(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ ứng tuyển.")

    worker = get_worker()

    if action == "queue":
        worker.transition_state(app_id, "QUEUED", action="QUEUED_BY_USER", details="Đưa vào hàng đợi ứng tuyển.")
    elif action == "pause":
        worker.transition_state(app_id, "NEEDS_REVIEW", action="PAUSED_BY_USER", details="Tạm dừng tiến trình.")
    elif action == "cancel":
        worker.transition_state(app_id, "CANCELLED", action="CANCELLED_BY_USER", details="Hủy đơn trong hàng đợi.")
    elif action == "submit":
        # Direct user approval: trigger execution
        threading.Thread(target=worker.process_application, args=(app_id, False), daemon=True).start()

    return {"status": "success", "message": f"Đã thực hiện hành động {action} cho hồ sơ {app_id}"}


@app.post("/api/queue/stop-all")
async def stop_all_queue():
    db = DatabaseManager()
    db.set_setting("kill_switch_activated", "1")
    worker = get_worker()
    apps = db.list_applications(status="QUEUED")
    for a in apps:
        worker.transition_state(
            a["id"], "CANCELLED",
            action="KILL_SWITCH_HALT",
            details="Dừng khẩn cấp toàn bộ hàng đợi."
        )
    return {"status": "success", "message": "ĐÃ KÍCH HOẠT DỪNG TOÀN BỘ HÀNG ĐỢI ỨNG TUYỂN."}


@app.post("/api/user-interaction/answer")
async def submit_user_answer(request: Request):
    payload = await request.json()
    app_id = payload.get("application_id")
    field_id = payload.get("field_id")
    answer = payload.get("answer")

    db = DatabaseManager()
    app_record = db.get_application(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn ứng tuyển.")

    # Save answer to form_answers
    form_answers = app_record.get("form_answers", {})
    form_answers[field_id] = answer
    app_record["form_answers"] = form_answers
    db.save_application(app_record)

    worker = get_worker()
    worker.transition_state(
        app_id, "QUEUED",
        action="USER_PROVIDED_ANSWER",
        details=f"Ứng viên đã trả lời câu hỏi '{field_id}'. Tiếp tục hàng đợi."
    )
    return {"status": "success", "message": "Đã lưu câu trả lời và khôi phục hàng đợi."}


# --- Settings & Hardware/Connection Check Endpoints ---
@app.get("/api/settings")
async def get_settings():
    db = DatabaseManager()
    creds = load_email_credentials()
    is_smtp = creds is not None and creds.get("provider") == "smtp"
    username = creds.get("username", "") if creds else ""
    return {
        "automation_mode": db.get_setting("automation_mode", "review"),
        "daily_limit": int(db.get_setting("daily_limit", "5")),
        "email_provider": "smtp" if is_smtp else "mock",
        "is_mock": not is_smtp,
        "email_username": username or "hienngo090800@gmail.com",
        "has_smtp_password": bool(creds.get("password")) if creds else False
    }


@app.put("/api/settings")
async def update_settings(request: Request):
    payload = await request.json()
    db = DatabaseManager()
    for k, v in payload.items():
        db.set_setting(k, str(v))
    return {"status": "success", "message": "Đã lưu cấu hình cài đặt an toàn."}


@app.post("/api/settings/email")
async def configure_email_settings(request: Request):
    payload = await request.json()
    provider_type = payload.get("provider", "mock")

    if provider_type == "mock":
        clear_email_credentials()
        return {
            "status": "success",
            "provider": "mock",
            "is_mock": True,
            "message": "Đã chuyển sang chế độ Thử nghiệm Cục bộ (Mock Offline). Thư ứng tuyển sẽ được mô phỏng gửi mà không kết nối internet."
        }

    username = payload.get("username", "").strip()
    raw_password = payload.get("password", "").strip()
    clean_password = raw_password.replace(" ", "")
    host = payload.get("host", "smtp.gmail.com").strip()
    port = int(payload.get("port", 587))
    use_tls = payload.get("use_tls", True)

    if not username or "@" not in username:
        raise HTTPException(status_code=400, detail="Vui lòng nhập địa chỉ Gmail hợp lệ.")
    if not clean_password:
        raise HTTPException(status_code=400, detail="Vui lòng nhập Mật khẩu ứng dụng Google (App Password 16 ký tự).")

    # Verify SMTP credentials immediately against smtp.gmail.com:587
    test_prov = SmtpEmailProvider(
        host=host,
        port=port,
        username=username,
        password=clean_password,
        use_tls=use_tls
    )
    ok, err_msg = await asyncio.to_thread(test_prov.test_connection)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail=f"Xác thực Gmail thất bại: {err_msg}. Vui lòng kiểm tra lại địa chỉ Gmail và mã Mật khẩu ứng dụng (App Password 16 ký tự)."
        )

    # Save encrypted credentials
    save_email_credentials({
        "provider": "smtp",
        "host": host,
        "port": port,
        "username": username,
        "password": clean_password,
        "use_tls": use_tls
    })

    return {
        "status": "success",
        "provider": "smtp",
        "is_mock": False,
        "message": f"Kết nối và xác thực tài khoản Gmail ({username}) thành công! Mọi email ứng tuyển từ nay sẽ được gửi THẬT 100% từ hộp thư của bạn."
    }


@app.post("/api/email/test-connection")
async def test_email():
    provider = get_configured_email_provider()
    ok, msg = await asyncio.to_thread(provider.test_connection)
    is_mock = isinstance(provider, LocalMockEmailProvider)
    return {
        "success": ok,
        "is_mock": is_mock,
        "provider": "mock" if is_mock else "smtp",
        "message": msg
    }


@app.post("/api/browser/test-connection")
async def test_browser():
    def _run_browser_test():
        automator = FormAutomationManager(headless=False)
        try:
            ctx = automator.get_context()
            page = ctx.new_page()
            page.set_content("<html><body><h1>Kiểm tra trình duyệt Playwright thành công</h1></body></html>")
            time.sleep(1.0)
            page.close()
            return True, "Trình duyệt Playwright đã mở và phản hồi thành công."
        except Exception as e:
            return False, f"Lỗi khởi động trình duyệt: {str(e)}"
        finally:
            automator.close()

    ok, msg = await asyncio.to_thread(_run_browser_test)
    return {"success": ok, "message": msg}


@app.get("/api/tracker/export-csv")
async def export_csv():
    db = DatabaseManager()
    csv_file = TRACKER_DIR / "jobs_tracker.csv"
    sync_db_to_tracker_json(db.db_path)
    from src.tracker import JobTracker
    tracker = JobTracker()
    out = tracker.export_csv(csv_file)
    return FileResponse(path=str(out), filename="jobs_tracker.csv", media_type="text/csv")


# --- Safe File Serving Endpoint ---
@app.get("/files/{file_path:path}")
async def serve_project_file(file_path: str):
    full_path = PROJECT_ROOT / file_path
    try:
        safe_path = ensure_within_project(full_path)
    except Exception:
        raise HTTPException(status_code=403, detail="Từ chối truy cập ngoài thư mục dự án.")

    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp.")

    # Determine media type
    media_type = "application/octet-stream"
    if safe_path.suffix == ".pdf":
        media_type = "application/pdf"
    elif safe_path.suffix == ".html":
        media_type = "text/html"
    elif safe_path.suffix == ".png":
        media_type = "image/png"
    elif safe_path.suffix in [".txt", ".md"]:
        media_type = "text/plain; charset=utf-8"

    return FileResponse(path=str(safe_path), media_type=media_type)


def find_available_port(start_port: int = 8000, max_tries: int = 10) -> int:
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


def run_server(port: Optional[int] = None):
    chosen_port = port or find_available_port(8000)

    # Save active server info
    SERVER_INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
    info = {
        "host": "127.0.0.1",
        "port": chosen_port,
        "pid": os.getpid(),
        "csrf_token": CSRF_TOKEN,
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    SERVER_INFO_FILE.write_text(json.dumps(info, indent=2), encoding="utf-8")

    # Start worker
    get_worker()

    print(f"[*] Backend server started at: http://127.0.0.1:{chosen_port}")
    uvicorn.run(app, host="127.0.0.1", port=chosen_port, log_level="warning")


if __name__ == "__main__":
    port_arg = None
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--port", "-p"] and len(sys.argv) > 2:
            try:
                port_arg = int(sys.argv[2])
            except ValueError:
                pass
        elif sys.argv[1].isdigit():
            port_arg = int(sys.argv[1])
    run_server(port_arg)
