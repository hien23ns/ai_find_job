"""
Database and Transactional Persistence Layer (SQLite).
Provides ACID transactions, versioned migrations, JSON tracker sync,
anti-duplicate locking, and application audit history.
All files strictly reside inside PROJECT_ROOT.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple

from src.config import PROJECT_ROOT, TRACKER_DIR
from src.security import ensure_within_project

DB_FILE = TRACKER_DIR / "app_database.db"
BACKUP_DIR = TRACKER_DIR / "backups"
TRACKER_JSON_FILE = TRACKER_DIR / "jobs_tracker.json"

_DB_LOCK = threading.RLock()


def get_db_path() -> Path:
    ensure_within_project(DB_FILE)
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    return DB_FILE


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Returns an SQLite connection configured with WAL mode and row factory.
    """
    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_database(db_path: Optional[Path] = None) -> None:
    """
    Initializes database schema and runs versioned migrations.
    """
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version TEXT PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    );
                """)

                # Check if v1.0 migration needed
                cur = conn.execute("SELECT version FROM schema_version WHERE version = '1.0'")
                if not cur.fetchone():
                    _apply_migration_v1(conn)
                    conn.execute(
                        "INSERT INTO schema_version (version, applied_at) VALUES ('1.0', ?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
                    )

                # Check if v2.0 migration needed (category, location, work_mode, employment_type)
                cur2 = conn.execute("SELECT version FROM schema_version WHERE version = '2.0'")
                if not cur2.fetchone():
                    _apply_migration_v2(conn)
                    conn.execute(
                        "INSERT INTO schema_version (version, applied_at) VALUES ('2.0', ?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
                    )
        finally:
            conn.close()


def _apply_migration_v1(conn: sqlite3.Connection) -> None:
    """
    Applies Schema Version 1.0.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            market TEXT NOT NULL,
            source TEXT NOT NULL,
            match_score INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Chưa nộp',
            application_date TEXT,
            notes TEXT,
            next_step TEXT,
            canonical_key TEXT,
            raw_jd TEXT,
            evidence TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS applications (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            package_dir TEXT,
            status TEXT NOT NULL DEFAULT 'DISCOVERED',
            channel TEXT NOT NULL DEFAULT 'missing_channel',
            recipient TEXT,
            eml_draft_file TEXT,
            preview_file TEXT,
            form_answers_json TEXT,
            unverified_conditions_json TEXT,
            attachments_json TEXT,
            current_step TEXT,
            error_message TEXT,
            correlation_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS application_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            proof_data_json TEXT,
            FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS worker_tasks (
            id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            priority INTEGER NOT NULL DEFAULT 10,
            worker_id TEXT,
            heartbeat TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
        CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
        CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
    """)

    # Populate default settings if not exists
    default_settings = {
        "automation_mode": "review",  # "prepare" | "review" | "auto"
        "daily_limit": "5",
        "timezone": "Asia/Ho_Chi_Minh",
        "allowed_markets": json.dumps(["vietnam", "korea", "freelance"]),
        "kill_switch_activated": "0",
        "email_provider": "local_mock",
        "browser_headless": "0"  # Visible browser for human intervention
    }
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for k, v in default_settings.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (k, v, now)
        )


def infer_job_attributes(
    title: str = "",
    location: str = "",
    raw_jd: str = "",
    explicit_attrs: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Infers domain category, detailed location, work mode, and employment type.
    """
    explicit = explicit_attrs or {}
    t_lower = (title or "").lower()
    l_lower = (location or "").lower()
    d_lower = (raw_jd or "").lower()
    combined = f"{t_lower} {l_lower} {d_lower}"

    # 1. Category (design, marketing, data_ai, security, it, sales, hr_admin, finance, translation, logistics, content_media)
    category = explicit.get("category")
    if not category or category in ["all", "general", ""]:
        if any(k in t_lower or k in d_lower for k in [
            "data analyst", "phân tích dữ liệu", "business analyst", "ba intern", "data engineer",
            "machine learning", "trí tuệ nhân tạo", "ai engineer", "deep learning", "power bi", "tableau", "bi intern"
        ]):
            category = "data_ai"
        elif any(k in t_lower or k in d_lower for k in [
            "ui/ux", "ui-ux", "ux/ui", "graphic design", "thiết kế đồ họa", "thiết kế",
            "figma", "photoshop", "illustrator", "creative", "product design", "2d", "3d", "motion", "designer"
        ]):
            category = "design"
        elif any(k in t_lower or k in d_lower for k in [
            "video editor", "quay dựng", "dựng phim", "media", "tiktok", "tiktoker", "quay phim", "premiere", "after effects"
        ]):
            category = "content_media"
        elif any(k in t_lower or k in d_lower for k in [
            "marketing", "truyền thông", "seo", "content", "copywriter", "facebook ads",
            "google ads", "social media", "performance marketing", "growth", "quảng cáo"
        ]):
            category = "marketing"
        elif any(k in t_lower or k in d_lower for k in [
            "nhân sự", "tuyển dụng", "talent acquisition", "hr intern", "human resources", "hành chính", "admin", "trợ lý", "headhunter"
        ]):
            category = "hr_admin"
        elif any(k in t_lower or k in d_lower for k in [
            "kế toán", "tài chính", "accounting", "finance", "kiểm toán", "thu ngân", "auditor", "công nợ"
        ]):
            category = "finance"
        elif any(k in t_lower or k in d_lower for k in [
            "biên dịch", "phiên dịch", "dịch thuật", "translator", "interpreter", "tiếng hàn", "tiếng nhật", "tiếng trung", "localization"
        ]):
            category = "translation"
        elif any(k in t_lower or k in d_lower for k in [
            "xuất nhập khẩu", "logistics", "supply chain", "chuỗi cung ứng", "kho vận", "mua hàng", "procurement", "vận chuyển"
        ]):
            category = "logistics"
        elif any(k in t_lower or k in d_lower for k in [
            "security", "an ninh mạng", "an toàn thông tin", "soc", "network", "mạng",
            "cloud", "devops", "pentest", "siem", "firewall", "hạ tầng"
        ]):
            category = "security"
        elif any(k in t_lower or k in d_lower for k in [
            "developer", "lập trình", "software", "backend", "frontend", "fullstack",
            "python", "java", "react", "flutter", "engineer", "kỹ sư phần mềm", "coder", "programmer", "it helpdesk"
        ]):
            category = "it"
        elif any(k in t_lower or k in d_lower for k in [
            "sales", "kinh doanh", "bán hàng", "business development", "account executive", "cskh", "telesales", "tư vấn", "chăm sóc khách hàng"
        ]):
            category = "sales"
        else:
            category = "it"

    # 2. Detailed Location
    loc_val = explicit.get("location")
    if not loc_val or loc_val in ["all", "Toàn quốc", ""]:
        if any(k in l_lower or k in d_lower or k in t_lower for k in ["đà nẵng", "da nang", "danang"]):
            loc_val = "Đà Nẵng"
        elif any(k in l_lower or k in d_lower or k in t_lower for k in ["hà nội", "ha noi", "hanoi"]):
            loc_val = "Hà Nội"
        elif any(k in l_lower or k in d_lower or k in t_lower for k in ["hồ chí minh", "ho chi minh", "hcm", "sài gòn", "saigon"]):
            loc_val = "TP. Hồ Chí Minh"
        elif any(k in l_lower or k in d_lower for k in ["cần thơ", "can tho"]):
            loc_val = "Cần Thơ"
        elif any(k in l_lower or k in d_lower for k in ["hải phòng", "hai phong"]):
            loc_val = "Hải Phòng"
        elif any(k in l_lower or k in d_lower for k in ["korea", "hàn quốc", "seoul"]):
            loc_val = "Hàn Quốc"
        elif any(k in l_lower or k in d_lower for k in ["remote", "từ xa", "wfh", "làm việc tại nhà"]):
            loc_val = "Remote / Toàn quốc"
        else:
            loc_val = location if location else "Toàn quốc"

    # 3. Work Mode (remote, hybrid, onsite)
    work_mode = explicit.get("work_mode")
    if not work_mode or work_mode in ["all", ""]:
        if any(k in combined for k in ["remote", "từ xa", "wfh", "work from home", "làm việc tại nhà", "online"]):
            work_mode = "remote"
        elif any(k in combined for k in ["hybrid", "linh hoạt", "kết hợp"]):
            work_mode = "hybrid"
        else:
            work_mode = "onsite"

    # 4. Employment Type (internship, full_time, part_time, freelance)
    emp_type = explicit.get("employment_type")
    if not emp_type or emp_type in ["all", ""]:
        if any(k in t_lower or k in d_lower for k in ["intern", "thực tập", "internship", "học việc", "fresher", "sinh viên"]):
            emp_type = "internship"
        elif any(k in combined for k in ["part-time", "part time", "bán thời gian", "bán tg", "theo ca", "ca gãy"]):
            emp_type = "part_time"
        elif any(k in combined for k in ["freelance", "dự án", "project-based", "cộng tác viên", "ctv", "contract"]):
            emp_type = "freelance"
        else:
            emp_type = "full_time"

    return {
        "category": category,
        "location": loc_val,
        "work_mode": work_mode,
        "employment_type": emp_type
    }


def _apply_migration_v2(conn: sqlite3.Connection) -> None:
    """
    Applies Schema Version 2.0: Adds multi-domain category, location, work_mode, and employment_type.
    """
    cols = [
        ("category", "TEXT DEFAULT 'tech'"),
        ("location", "TEXT DEFAULT 'Toàn quốc'"),
        ("work_mode", "TEXT DEFAULT 'onsite'"),
        ("employment_type", "TEXT DEFAULT 'full_time'")
    ]
    for col_name, col_def in cols:
        try:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_def};")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Backfill inferred attributes for existing jobs
    try:
        cur = conn.execute("SELECT id, title, notes, raw_jd, location, category, work_mode, employment_type FROM jobs")
        rows = cur.fetchall()
        for r in rows:
            inferred = infer_job_attributes(
                title=r["title"],
                location=r["location"] if (r["location"] and r["location"] != "Toàn quốc") else (r["notes"] or ""),
                raw_jd=r["raw_jd"] or "",
                explicit_attrs={
                    "category": r["category"],
                    "location": r["location"],
                    "work_mode": r["work_mode"],
                    "employment_type": r["employment_type"]
                }
            )
            conn.execute("""
                UPDATE jobs SET
                    category = ?,
                    location = ?,
                    work_mode = ?,
                    employment_type = ?
                WHERE id = ?
            """, (
                inferred["category"],
                inferred["location"],
                inferred["work_mode"],
                inferred["employment_type"],
                r["id"]
            ))
    except Exception as e:
        print(f"Warning: Backfill migration v2.0: {e}")


def migrate_tracker_json_to_db(
    json_path: Optional[Path] = None,
    db_path: Optional[Path] = None
) -> Tuple[int, Optional[Path]]:
    """
    Safely migrates tracking data from JSON to SQLite database.
    - Creates timestamped backup before touching anything.
    - Preserves all IDs, statuses, dates, notes, and canonical keys.
    - Updates Hitachi application status to protect from re-submission.
    - Returns (migrated_count, backup_path).
    """
    json_file = json_path or TRACKER_JSON_FILE
    ensure_within_project(json_file)
    if not json_file.exists():
        return 0, None

    init_database(db_path)

    # 1. Create safe backup
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"jobs_tracker_pre_migration_{ts}.json"
    shutil.copy2(json_file, backup_file)

    # 2. Parse JSON
    try:
        content = json_file.read_text(encoding="utf-8")
        if not content.strip():
            return 0, backup_file
        data = json.loads(content)
        raw_jobs = data.get("jobs", {})
    except Exception as e:
        raise ValueError(f"Không thể đọc file tracker JSON để migration: {e}") from e

    # 3. Insert / Update into SQLite
    count = 0
    with _DB_LOCK:
        conn = get_connection(db_path)
        try:
            with conn:
                for j_id, j in raw_jobs.items():
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    status = j.get("status", "Chưa nộp")
                    notes = j.get("notes", "")

                    # Hitachi safeguarding: if Hitachi 4481162663, enforce submitted status
                    company = j.get("company", "")
                    title = j.get("title", "")
                    if "hitachi" in company.lower() or "4481162663" in str(j.get("source", "")):
                        status = "Đã nộp qua form"
                        notes = (notes + " [Đã nộp qua form chính thức - Chống nộp trùng]").strip()

                    conn.execute("""
                        INSERT INTO jobs (
                            id, title, company, market, source, match_score,
                            status, application_date, notes, next_step,
                            canonical_key, raw_jd, evidence, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            title=excluded.title,
                            company=excluded.company,
                            market=excluded.market,
                            source=excluded.source,
                            match_score=excluded.match_score,
                            status=excluded.status,
                            application_date=excluded.application_date,
                            notes=excluded.notes,
                            next_step=excluded.next_step,
                            canonical_key=excluded.canonical_key,
                            updated_at=excluded.updated_at;
                    """, (
                        j_id,
                        title,
                        company,
                        j.get("market", "vietnam"),
                        j.get("source", ""),
                        int(j.get("match_score", 0)),
                        status,
                        j.get("application_date"),
                        notes,
                        j.get("next_step", ""),
                        j.get("canonical_key", ""),
                        j.get("raw_jd", ""),
                        j.get("evidence", ""),
                        j.get("created_at", now),
                        j.get("updated_at", now)
                    ))
                    count += 1
        finally:
            conn.close()

    # Sync back to JSON so legacy scripts maintain exact parity
    sync_db_to_tracker_json(db_path, json_file)
    return count, backup_file


def sync_db_to_tracker_json(
    db_path: Optional[Path] = None,
    json_path: Optional[Path] = None
) -> None:
    """
    Syncs the SQLite jobs table back to jobs_tracker.json atomically.
    Ensures that existing CLI commands and older modules don't suffer drift.
    """
    json_file = json_path or TRACKER_JSON_FILE
    ensure_within_project(json_file)

    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT * FROM jobs ORDER BY updated_at DESC")
        rows = cur.fetchall()
        jobs_dict = {}
        for r in rows:
            jobs_dict[r["id"]] = {
                "id": r["id"],
                "title": r["title"],
                "company": r["company"],
                "market": r["market"],
                "source": r["source"],
                "match_score": r["match_score"],
                "status": r["status"],
                "application_date": r["application_date"],
                "notes": r["notes"] or "",
                "next_step": r["next_step"] or "",
                "canonical_key": r["canonical_key"] or "",
                "category": r["category"] if "category" in r.keys() else "tech",
                "location": r["location"] if "location" in r.keys() else "Toàn quốc",
                "work_mode": r["work_mode"] if "work_mode" in r.keys() else "onsite",
                "employment_type": r["employment_type"] if "employment_type" in r.keys() else "full_time",
                "created_at": r["created_at"],
                "updated_at": r["updated_at"]
            }

        payload = {
            "version": "1.0",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_jobs": len(jobs_dict),
            "jobs": jobs_dict
        }

        json_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = json_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, json_file)
    finally:
        conn.close()


class DatabaseManager:
    """
    High-level API for Application state, queue, settings, and jobs.
    """
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        init_database(self.db_path)

    def get_setting(self, key: str, default: str = "") -> str:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cur.fetchone()
            return row["value"] if row else default
        finally:
            conn.close()

    def set_setting(self, key: str, value: str) -> None:
        with _DB_LOCK:
            conn = get_connection(self.db_path)
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with conn:
                    conn.execute("""
                        INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                    """, (key, value, now))
            finally:
                conn.close()

    def get_all_settings(self) -> Dict[str, str]:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT key, value FROM settings")
            return {r["key"]: r["value"] for r in cur.fetchall()}
        finally:
            conn.close()

    # --- Jobs Operations ---
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_jobs(
        self,
        market: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
        category: Optional[str] = None,
        location: Optional[str] = None,
        work_mode: Optional[str] = None,
        employment_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            query = "SELECT * FROM jobs WHERE 1=1"
            params: List[Any] = []
            if market and market != "all":
                query += " AND market = ?"
                params.append(market)
            if status and status != "all":
                query += " AND status = ?"
                params.append(status)
            if category and category != "all":
                if category == "it":
                    query += " AND (category = 'it' OR category = 'tech')"
                else:
                    query += " AND category = ?"
                    params.append(category)
            if location and location != "all":
                loc_map = {
                    "danang": ["%đà nẵng%", "%danang%", "%da nang%"],
                    "hanoi": ["%hà nội%", "%hanoi%", "%ha noi%"],
                    "hcm": ["%hồ chí minh%", "%hcm%", "%saigon%", "%ho chi minh%"],
                    "cantho": ["%cần thơ%", "%can tho%"],
                    "haiphong": ["%hải phòng%", "%hai phong%"],
                    "remote": ["%remote%", "%từ xa%", "%wfh%"],
                    "korea": ["%hàn quốc%", "%korea%", "%seoul%"],
                    "international": ["%quốc tế%", "%korea%", "%seoul%", "%global%"]
                }
                patterns = loc_map.get(location.lower(), [f"%{location}%"])
                loc_clause = " OR ".join(["location LIKE ?" for _ in patterns])
                query += f" AND ({loc_clause})"
                params.extend(patterns)
            if work_mode and work_mode != "all":
                query += " AND work_mode = ?"
                params.append(work_mode)
            if employment_type and employment_type != "all":
                emp_clean = employment_type.replace("-", "").replace("_", "").lower()
                query += " AND (REPLACE(REPLACE(employment_type, '-', ''), '_', '') = ?)"
                params.append(emp_clean)
            if search_query:
                query += " AND (title LIKE ? OR company LIKE ? OR notes LIKE ? OR raw_jd LIKE ?)"
                kw = f"%{search_query}%"
                params.extend([kw, kw, kw, kw])
            query += " ORDER BY updated_at DESC"
            cur = conn.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def save_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        with _DB_LOCK:
            conn = get_connection(self.db_path)
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                from src.upstream_bridge import get_canonical_job_key
                company = (job_data.get("company") or "").strip()
                title = (job_data.get("title") or "").strip()
                source = (job_data.get("source") or "").strip()
                can_key = job_data.get("canonical_key") or get_canonical_job_key(company, title, source)
                job_data["canonical_key"] = can_key

                # Infer or respect domain attributes (category, location, work_mode, employment_type)
                inferred = infer_job_attributes(
                    title=title,
                    location=job_data.get("location") or job_data.get("notes") or "",
                    raw_jd=job_data.get("raw_jd", ""),
                    explicit_attrs=job_data
                )
                category = inferred["category"]
                location = inferred["location"]
                work_mode = inferred["work_mode"]
                employment_type = inferred["employment_type"]
                job_data["category"] = category
                job_data["location"] = location
                job_data["work_mode"] = work_mode
                job_data["employment_type"] = employment_type

                # Collision-resistant deduplication across searches:
                # Check by ID, canonical_key, or normalized (company, title)
                cur = conn.execute("""
                    SELECT id, status, application_date, canonical_key, created_at FROM jobs
                    WHERE id = ?
                       OR (canonical_key IS NOT NULL AND canonical_key != '' AND canonical_key = ?)
                       OR (LOWER(TRIM(company)) = LOWER(TRIM(?)) AND LOWER(TRIM(title)) = LOWER(TRIM(?)))
                    LIMIT 1
                """, (job_data["id"], can_key, company, title))
                existing = cur.fetchone()

                if existing:
                    target_id = existing["id"]
                    job_data["id"] = target_id
                    # Preserve applied/submitted status if incoming status is default 'Chưa nộp' so repeated searches never reset user progress
                    incoming_status = job_data.get("status", "Chưa nộp")
                    if incoming_status == "Chưa nộp" and existing["status"] in ["Đã gửi email", "Đã nộp", "Đã nộp qua form", "SUBMITTED"]:
                        job_data["status"] = existing["status"]
                        job_data["application_date"] = existing["application_date"]
                    created_at = existing["created_at"] or now
                else:
                    target_id = job_data["id"]
                    created_at = job_data.get("created_at", now)

                with conn:
                    conn.execute("""
                        INSERT INTO jobs (
                            id, title, company, market, source, match_score,
                            status, application_date, notes, next_step,
                            canonical_key, raw_jd, evidence,
                            category, location, work_mode, employment_type,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            title=excluded.title,
                            company=excluded.company,
                            market=excluded.market,
                            source=excluded.source,
                            match_score=excluded.match_score,
                            status=excluded.status,
                            application_date=excluded.application_date,
                            notes=excluded.notes,
                            next_step=excluded.next_step,
                            canonical_key=excluded.canonical_key,
                            raw_jd=excluded.raw_jd,
                            evidence=excluded.evidence,
                            category=excluded.category,
                            location=excluded.location,
                            work_mode=excluded.work_mode,
                            employment_type=excluded.employment_type,
                            updated_at=excluded.updated_at
                    """, (
                        target_id,
                        title,
                        company,
                        job_data.get("market", "vietnam"),
                        source,
                        int(job_data.get("match_score", 0)),
                        job_data.get("status", "Chưa nộp"),
                        job_data.get("application_date"),
                        job_data.get("notes", ""),
                        job_data.get("next_step", ""),
                        can_key,
                        job_data.get("raw_jd", ""),
                        job_data.get("evidence", ""),
                        category,
                        location,
                        work_mode,
                        employment_type,
                        created_at,
                        now
                    ))
            finally:
                conn.close()
            sync_db_to_tracker_json(self.db_path)
            return job_data

    # --- Applications Operations ---
    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
            row = cur.fetchone()
            if not row:
                return None
            data = dict(row)
            data["form_answers"] = json.loads(data["form_answers_json"] or "{}")
            data["unverified_conditions"] = json.loads(data["unverified_conditions_json"] or "[]")
            data["attachments"] = json.loads(data["attachments_json"] or "[]")
            return data
        finally:
            conn.close()

    def get_application_by_job_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT * FROM applications WHERE job_id = ? ORDER BY updated_at DESC LIMIT 1", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            data = dict(row)
            data["form_answers"] = json.loads(data["form_answers_json"] or "{}")
            data["unverified_conditions"] = json.loads(data["unverified_conditions_json"] or "[]")
            data["attachments"] = json.loads(data["attachments_json"] or "[]")
            return data
        finally:
            conn.close()

    def list_applications(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            query = "SELECT * FROM applications"
            params = []
            if status:
                query += " WHERE status = ?"
                params.append(status)
            query += " ORDER BY updated_at DESC"
            cur = conn.execute(query, params)
            results = []
            for row in cur.fetchall():
                data = dict(row)
                data["form_answers"] = json.loads(data["form_answers_json"] or "{}")
                data["unverified_conditions"] = json.loads(data["unverified_conditions_json"] or "[]")
                data["attachments"] = json.loads(data["attachments_json"] or "[]")
                results.append(data)
            return results
        finally:
            conn.close()

    def save_application(self, app_data: Dict[str, Any]) -> None:
        with _DB_LOCK:
            conn = get_connection(self.db_path)
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with conn:
                    conn.execute("""
                        INSERT INTO applications (
                            id, job_id, company, role, package_dir, status,
                            channel, recipient, eml_draft_file, preview_file,
                            form_answers_json, unverified_conditions_json, attachments_json,
                            current_step, error_message, correlation_id, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            package_dir=excluded.package_dir,
                            status=excluded.status,
                            channel=excluded.channel,
                            recipient=excluded.recipient,
                            eml_draft_file=excluded.eml_draft_file,
                            preview_file=excluded.preview_file,
                            form_answers_json=excluded.form_answers_json,
                            unverified_conditions_json=excluded.unverified_conditions_json,
                            attachments_json=excluded.attachments_json,
                            current_step=excluded.current_step,
                            error_message=excluded.error_message,
                            correlation_id=excluded.correlation_id,
                            updated_at=excluded.updated_at
                    """, (
                        app_data["id"],
                        app_data["job_id"],
                        app_data["company"],
                        app_data["role"],
                        app_data.get("package_dir"),
                        app_data.get("status", "DISCOVERED"),
                        app_data.get("channel", "missing_channel"),
                        app_data.get("recipient"),
                        app_data.get("eml_draft_file"),
                        app_data.get("preview_file"),
                        json.dumps(app_data.get("form_answers", {}), ensure_ascii=False),
                        json.dumps(app_data.get("unverified_conditions", []), ensure_ascii=False),
                        json.dumps(app_data.get("attachments", []), ensure_ascii=False),
                        app_data.get("current_step"),
                        app_data.get("error_message"),
                        app_data.get("correlation_id"),
                        app_data.get("created_at", now),
                        app_data.get("updated_at", now)
                    ))
            finally:
                conn.close()

    def add_history(
        self,
        application_id: str,
        action: str,
        status: str,
        details: str,
        proof_data: Optional[Dict[str, Any]] = None
    ) -> None:
        with _DB_LOCK:
            conn = get_connection(self.db_path)
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with conn:
                    conn.execute("""
                        INSERT INTO application_history (
                            application_id, timestamp, action, status, details, proof_data_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        application_id,
                        now,
                        action,
                        status,
                        details,
                        json.dumps(proof_data or {}, ensure_ascii=False)
                    ))
            finally:
                conn.close()

    def get_history(self, application_id: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                "SELECT * FROM application_history WHERE application_id = ? ORDER BY id ASC",
                (application_id,)
            )
            results = []
            for r in cur.fetchall():
                d = dict(r)
                d["proof_data"] = json.loads(d["proof_data_json"] or "{}")
                results.append(d)
            return results
        finally:
            conn.close()

    def get_dashboard_summary(self) -> Dict[str, Any]:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("""
                SELECT
                    COUNT(*) as total_jobs,
                    SUM(CASE WHEN status = 'Đã nộp' OR status = 'Đã nộp qua form' OR status = 'Đã gửi email' THEN 1 ELSE 0 END) as submitted_jobs,
                    SUM(CASE WHEN match_score >= 80 AND status = 'Chưa nộp' THEN 1 ELSE 0 END) as new_matching_jobs,
                    SUM(CASE WHEN status = 'Cần xác minh GPA và lịch thực tập' OR status = 'AWAITING_USER' THEN 1 ELSE 0 END) as needs_attention,
                    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_jobs
                FROM jobs
            """)
            stats = dict(cur.fetchone())

            cur_apps = conn.execute("""
                SELECT
                    SUM(CASE WHEN status = 'QUEUED' OR status = 'FILLING' OR status = 'SUBMITTING' THEN 1 ELSE 0 END) as queue_count,
                    SUM(CASE WHEN status = 'NEEDS_REVIEW' OR status = 'READY' THEN 1 ELSE 0 END) as review_count
                FROM applications
            """)
            app_stats = dict(cur_apps.fetchone())

            return {
                "total_jobs": stats["total_jobs"] or 0,
                "submitted_jobs": stats["submitted_jobs"] or 0,
                "new_matching_jobs": stats["new_matching_jobs"] or 0,
                "needs_attention": stats["needs_attention"] or 0,
                "failed_jobs": stats["failed_jobs"] or 0,
                "queue_count": app_stats["queue_count"] or 0,
                "review_count": app_stats["review_count"] or 0,
                "kill_switch": self.get_setting("kill_switch_activated", "0") == "1",
                "automation_mode": self.get_setting("automation_mode", "review"),
                "daily_limit": int(self.get_setting("daily_limit", "5")),
            }
        finally:
            conn.close()

    def get_setting(self, key: str, default: str = "") -> str:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cur.fetchone()
            return row["value"] if row else default
        finally:
            conn.close()

    def set_setting(self, key: str, value: str) -> None:
        with _DB_LOCK:
            conn = get_connection(self.db_path)
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with conn:
                    conn.execute("""
                        INSERT INTO settings (key, value, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                    """, (key, str(value), now))
            finally:
                conn.close()
