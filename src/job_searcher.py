"""
Job Searcher Module for ai-job-search.
Reuses upstream ai-job-search portal search CLIs (.agents/skills/linkedin-search, .agents/skills/freehire-search),
integrates upstream/tools/job_key.py for canonical deduplication,
and applies upstream/tools/posting_guard.py for text integrity and prompt injection defense.

Enforces strict privacy:
- Never transmits candidate contact details (email, phone, address, name) to search providers.
- Evaluates real postings against candidate profile and preserves unverified conditions.
- Stages jobs into tracker with non-submitted statuses ('Đã tìm thấy', 'Đã đánh giá', 'Sẵn sàng rà soát').
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from src.config import (
    CANDIDATES_DIR,
    LOCAL_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
    TRACKER_DIR,
)
from src.evaluator import JobEvaluator
from src.generator import DocumentGenerator
from src.security import ensure_within_project, sanitize_untrusted_text
from src.tracker import JobTracker
from src.upstream_bridge import get_canonical_job_key

TRACKER_FILE = TRACKER_DIR / "jobs_tracker.json"
UPSTREAM_DIR = PROJECT_ROOT / "upstream"
LINKEDIN_CLI = UPSTREAM_DIR / ".agents" / "skills" / "linkedin-search" / "cli" / "src" / "cli.ts"
FREEHIRE_CLI = UPSTREAM_DIR / ".agents" / "skills" / "freehire-search" / "cli" / "src" / "cli.ts"
SEARCH_SESSIONS_DIR = LOCAL_DIR / "search_sessions"
SEARCH_CACHE_FILE = LOCAL_DIR / "temp" / "latest_search_results.json"


# Default target search configuration aligned with user preferences
DEFAULT_SEARCH_CONFIG = {
    "target_roles": [
        "SOC Intern",
        "Security Intern",
        "Network Intern",
        "Network Engineer Fresher"
    ],
    "locations": {
        "primary": "Da Nang, Vietnam",
        "remote": "Remote",
        "secondary": ["Hanoi, Vietnam", "Ho Chi Minh City, Vietnam"]
    },
    "priorities": [
        {
            "id": "danang",
            "tier": 1,
            "label": "Đà Nẵng (Ưu tiên tại chỗ)",
            "portal": "linkedin",
            "location": "Da Nang, Vietnam",
            "queries": ["Network Intern", "Security Intern", "IT Network", "Network Engineer"],
            "remote": None
        },
        {
            "id": "remote_vietnam",
            "tier": 2,
            "label": "Remote — cần xác minh quốc gia làm việc",
            "portal": "linkedin",
            "location": "Vietnam",
            "queries": ["Security Intern", "Network Intern", "Cyber Security"],
            "remote": "remote"
        },
        {
            "id": "secondary_cities",
            "tier": 3,
            "label": "Hà Nội / TP.HCM (Nhóm phụ - Cần xác nhận di chuyển)",
            "portal": "linkedin",
            "location": "Vietnam",
            "queries": ["SOC Intern", "Security Intern", "Network Intern"],
            "remote": None
        },
        {
            "id": "freelance",
            "tier": 4,
            "label": "Freelance (Theo dự án / Hợp đồng)",
            "portal": "freehire",
            "region": "apac",
            "queries": ["python log", "linux support", "network"],
            "remote": "remote"
        }
    ],
    "privacy_policy": {
        "strip_candidate_contact": True,
        "allow_remote_from_vietnam": True,
        "do_not_assert_fulltime": True,
        "do_not_assert_relocation": True
    }
}


def load_search_profile(profile_path: Path) -> Dict[str, Any]:
    """
    Load candidate profile and extract ONLY search-relevant parameters.
    Strictly strips private contact information (email, phone, address, website, bio).
    """
    ensure_within_project(profile_path)
    if not profile_path.exists():
        raise FileNotFoundError(f"Hồ sơ ứng viên không tồn tại: {profile_path}")

    raw = json.loads(profile_path.read_text(encoding="utf-8"))

    # Safely extract skills
    extracted_skills: List[str] = []
    skills_obj = raw.get("skills", {})
    if isinstance(skills_obj, dict):
        for category, items in skills_obj.items():
            if isinstance(items, list):
                extracted_skills.extend([str(item) for item in items])
    elif isinstance(skills_obj, list):
        extracted_skills = [str(item) for item in skills_obj]

    # Education and experience summary without PII
    education = raw.get("education", [])
    edu_summary = "Sinh viên đang theo học"
    grad_year = 2028
    if education and isinstance(education, list):
        first_edu = education[0]
        edu_summary = f"{first_edu.get('degree', 'Đang theo học')} - {first_edu.get('major', 'Mạng và ATTT')}"
        year_str = str(first_edu.get("year", ""))
        grad_matches = re.findall(r"20\d\d", year_str)
        if grad_matches:
            grad_year = int(grad_matches[-1])


    return {
        "candidate_summary_non_pii": edu_summary,
        "expected_graduation": grad_year,
        "years_of_experience": raw.get("years_of_experience", 0),
        "target_skills": extracted_skills,
        "preferred_location": "Đà Nẵng, Việt Nam",
        "has_fulltime_verified": False,
        "has_relocation_verified": False,
        # Verification that PII is NOT present
        "_privacy_guarantee": "No email, phone, personal addresses or full bio transmitted."
    }


class JobSearcher:
    """
    Search manager orchestrating upstream CLIs and applying deduplication and security guards.
    """

    def __init__(self, root_dir: Path = PROJECT_ROOT):
        self.root = root_dir
        self.upstream_dir = self.root / "upstream"
        self.linkedin_cli = self.upstream_dir / ".agents" / "skills" / "linkedin-search" / "cli" / "src" / "cli.ts"
        self.freehire_cli = self.upstream_dir / ".agents" / "skills" / "freehire-search" / "cli" / "src" / "cli.ts"
        self._bun_cmd = self._detect_bun_executable()

    def _detect_bun_executable(self) -> Optional[List[str]]:
        """
        Detect a functional bun invocation command on Windows or POSIX.
        """
        # 1. Try cmd.exe /c bun on Windows
        if sys.platform == "win32":
            try:
                res = subprocess.run(
                    ["cmd.exe", "/c", "bun", "--version"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5
                )
                if res.returncode == 0 and res.stdout.strip():
                    return ["cmd.exe", "/c", "bun"]
            except Exception:
                pass

        # 2. Try direct bun on PATH
        bun_path = shutil.which("bun")
        if bun_path:
            try:
                res = subprocess.run(
                    [bun_path, "--version"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5
                )
                if res.returncode == 0:
                    return [bun_path]
            except Exception:
                pass

        return None

    def is_bun_available(self) -> bool:
        """Return True if bun runtime is executable."""
        return self._bun_cmd is not None

    def run_posting_guard_clean(self, text: str) -> str:
        """
        Clean raw posting text using upstream/tools/posting_guard.py if available,
        falling back to internal security sanitization.
        """
        cleaned = text
        tools_path = self.upstream_dir / "tools"
        if tools_path.exists():
            if str(tools_path) not in sys.path:
                sys.path.insert(0, str(tools_path))
            try:
                from posting_guard import clean_text
                cleaned_text, _ = clean_text(text)
                cleaned = cleaned_text
            except Exception:
                pass

        # Apply internal anti-injection sanitization
        return sanitize_untrusted_text(cleaned)

    def search_linkedin(
        self,
        query: str,
        location: str,
        limit: int = 5,
        remote: Optional[str] = None,
        jobage: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search LinkedIn public job postings via upstream linkedin-search CLI.
        """
        if not self.is_bun_available() or not self.linkedin_cli.exists():
            return []

        cmd = list(self._bun_cmd) + [
            "run",
            str(self.linkedin_cli),
            "search",
            "-l",
            location,
            "-q",
            query,
            "--limit",
            str(limit),
            "--format",
            "json"
        ]
        if remote:
            cmd.extend(["--remote", remote])
        if jobage:
            cmd.extend(["--jobage", str(jobage)])

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                cwd=self.root
            )
            if res.returncode != 0 or not res.stdout.strip():
                return []
            data = json.loads(res.stdout)
            results = data.get("results", [])
            for r in results:
                r["search_source"] = "LinkedIn (Public Guest API)"
                r["search_portal"] = "linkedin"
            return results
        except Exception:
            return []

    def get_linkedin_detail(self, job_id_or_url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full details for a LinkedIn job posting via upstream CLI.
        """
        if not self.is_bun_available() or not self.linkedin_cli.exists():
            return None

        cmd = list(self._bun_cmd) + [
            "run",
            str(self.linkedin_cli),
            "detail",
            str(job_id_or_url),
            "--format",
            "json"
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=25,
                cwd=self.root
            )
            if res.returncode != 0 or not res.stdout.strip():
                return None
            data = json.loads(res.stdout)
            if isinstance(data, dict):
                # Clean description text via posting guard
                if "description" in data and isinstance(data["description"], str):
                    data["description"] = self.run_posting_guard_clean(data["description"])
                return data
            return None
        except Exception:
            return None

    def search_freehire(
        self,
        query: str,
        region: str = "apac",
        limit: int = 5,
        remote: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search tech jobs via upstream freehire-search CLI.
        """
        if not self.is_bun_available() or not self.freehire_cli.exists():
            return []

        cmd = list(self._bun_cmd) + [
            "run",
            str(self.freehire_cli),
            "search",
            "-q",
            query,
            "--limit",
            str(limit),
            "--format",
            "json"
        ]
        if region:
            cmd.extend(["--region", region])
        if remote:
            cmd.extend(["--remote", remote])

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                cwd=self.root
            )
            if res.returncode != 0 or not res.stdout.strip():
                return []
            data = json.loads(res.stdout)
            results = data.get("results", [])
            for r in results:
                r["search_source"] = "freehire.me (Public Aggregator API)"
                r["search_portal"] = "freehire"
                if "description" in r and isinstance(r["description"], str):
                    r["description"] = self.run_posting_guard_clean(r["description"])
            return results
        except Exception:
            return []

    @staticmethod
    def is_marketing_or_ads_job(title: str, desc: str) -> bool:
        """
        Check if job is advertising, marketing, or Facebook Ads.
        These are strictly excluded from network, security, and cloud priority groups.
        """
        t = title.lower()
        d = desc.lower()
        ads_title_patterns = [
            r"\bmarketing\b", r"\bfacebook ads\b", r"\bfb ads\b", r"\bgoogle ads\b",
            r"\bmedia buyer\b", r"\bseo\b", r"\bcontent creator\b", r"\bchạy ads\b",
            r"\bquảng cáo\b", r"\btelesales\b", r"\btelemarketing\b", r"\bsales executive\b",
            r"\bnhân viên kinh doanh\b", r"\bdigital marketing\b", r"\btiktok ads\b",
            r"\bcopywriter\b", r"\bcreative strategist\b"
        ]
        for p in ads_title_patterns:
            if re.search(p, t):
                return True
        if re.search(r"\b(chạy ads|quảng cáo facebook|tối ưu hóa chiến dịch quảng cáo|ngân sách quảng cáo)\b", d):
            # Only if not an explicit network/security role
            if not re.search(r"\b(soc|security|network|an toàn thông tin|an ninh mạng|quản trị mạng)\b", t):
                return True
        return False

    @staticmethod
    def is_senior_or_lead_job(title: str, desc: str) -> bool:
        """
        Check if job is Senior/Lead/Manager level.
        Must be placed in Out of Target group; never auto-selected for a 0 YOE candidate.
        """
        t = title.lower()
        # If title clearly indicates student, intern or fresher, do not classify as senior
        if re.search(r"\b(intern|internship|thực tập|thực tập sinh|fresher)\b", t):
            return False
        # Direct seniority indicators in title
        if re.search(r"\b(senior|lead|leader|manager|director|head of|principal|architect|trưởng nhóm|trưởng phòng|giám đốc|chuyên viên cao cấp)\b", t):
            return True
        # Severe experience requirements (>= 3 years) when not marked as entry level
        if re.search(r"\b([3-9]|\d{2})\+?\s*(?:năm|year|\+)\s*(?:kinh nghiệm|experience)\b", desc.lower()):
            if not re.search(r"\b(intern|fresher|junior|0 năm|chấp nhận sinh viên)\b", desc.lower()):
                return True
        return False

    @staticmethod
    def is_freelance_or_contract(job: Dict[str, Any], title: str, desc: str, location: str) -> bool:
        """
        Check if job has factual evidence of freelance, contract, or project-based scope.
        Freehire does NOT automatically default to freelance; requires explicit contract/project evidence.
        """
        emp_type = str(job.get("employmentType", "")).lower()
        combined = f"{title} {desc} {emp_type}".lower()
        freelance_patterns = [
            r"\bfreelance\b", r"\bfreelancer\b", r"\bcontract\b", r"\bcontractor\b",
            r"\bproject-based\b", r"\bgig\b", r"\bdự án\b", r"\btheo dự án\b",
            r"\bbán thời gian theo dự án\b", r"\bcộng tác viên\b", r"\bhợp đồng dịch vụ\b",
            r"\bhợp đồng vụ việc\b", r"\bshort-term\b"
        ]
        return any(re.search(p, combined) for p in freelance_patterns)

    def categorize_and_audit_job(
        self,
        job: Dict[str, Any],
        candidate_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Categorize job into priority tiers and identify unverified conditions.
        Enforces strict rules:
        - Exclude Ads/Marketing from tech priorities (Tier 99).
        - Exclude Senior/Lead/Manager from auto-selection for 0 YOE candidate (Tier 98).
        - Tier 2 Remote: "Remote — cần xác minh quốc gia làm việc" (checks explicit Vietnam evidence; APAC/toàn quốc/trong nước does NOT suffice).
        - Freelance: requires contract/project evidence (Tier 4). Unrecognized goes to "Chưa phân loại" (Tier 5).
        """
        title = (job.get("title") or "").strip()
        company = (job.get("company") or "").strip()
        location = (job.get("location") or "").strip()
        desc = (job.get("description") or "").lower()

        # Generate canonical deduplication key from upstream
        url = job.get("url", "")
        canonical_key = get_canonical_job_key(company, title, url)
        job["canonical_key"] = canonical_key

        unverified: List[str] = []

        # 1. Rule: Loại quảng cáo/marketing/Facebook Ads khỏi nhóm ưu tiên
        if self.is_marketing_or_ads_job(title, desc):
            tier = 99
            tier_label = "Ngoài mục tiêu: Quảng cáo / Marketing"
            unverified.append("Tin tuyển dụng thuộc lĩnh vực Quảng cáo / Marketing; bị loại khỏi các nhóm ưu tiên mạng, ATTT và cloud.")

        # 2. Rule: Đưa Senior/Lead/Manager vào nhóm ngoài mục tiêu
        elif self.is_senior_or_lead_job(title, desc):
            tier = 98
            tier_label = "Ngoài mục tiêu: Vị trí Senior / Lead / Manager (Không phù hợp hồ sơ 0 năm kinh nghiệm)"
            unverified.append("Vị trí cấp cao (Senior/Lead/Manager): Vượt quá hồ sơ ứng viên 0 năm kinh nghiệm.")

        else:
            loc_lower = location.lower()
            is_remote = (
                job.get("work_mode") == "remote"
                or "remote" in loc_lower
                or "từ xa" in loc_lower
                or "wfh" in desc
                or "remote" in desc
            )
            is_danang = "da nang" in loc_lower or "đà nẵng" in loc_lower or "danang" in loc_lower

            # Vietnam evidence check for remote work: must explicitly mention Vietnam / Vietnamese jurisdiction.
            # APAC, toàn quốc, trong nước do NOT establish Vietnam eligibility by themselves.
            has_vietnam_evidence = bool(re.search(
                r"\b(vietnam|việt nam|viet nam|da nang|đà nẵng|hanoi|ha noi|hà nội|ho chi minh|hồ chí minh|saigon|vn)\b",
                f"{desc} {location}".lower()
            ))

            if is_danang:
                tier = 1
                tier_label = "Đà Nẵng (Ưu tiên tại chỗ)"
            elif is_remote:
                tier = 2
                tier_label = "Remote — cần xác minh quốc gia làm việc"
                if has_vietnam_evidence:
                    job["vietnam_supported"] = True
                    job["vietnam_evidence"] = "Có bằng chứng cho phép làm việc tại Việt Nam / khu vực APAC trong thông tin tuyển dụng."
                else:
                    job["vietnam_supported"] = False
                    unverified.append("Chưa có bằng chứng JD hỗ trợ làm việc từ xa từ Việt Nam; cần xác minh quốc gia/khu vực được phép làm việc.")
            elif any(city in loc_lower for city in ["hanoi", "ha noi", "hà nội", "ho chi minh", "hồ chí minh", "hcm", "saigon"]):
                tier = 3
                tier_label = "Hà Nội / TP.HCM (Nhóm phụ - Cần xác nhận di chuyển)"
                unverified.append(f"Địa điểm tại {location}: Cần xác nhận khả năng di chuyển hoặc hỗ trợ on-site từ công ty.")
            elif self.is_freelance_or_contract(job, title, desc, location):
                tier = 4
                tier_label = "Freelance (Theo dự án / Hợp đồng)"
                unverified.append(f"Vị trí làm việc theo dự án / freelance tại {location}: Cần làm rõ quy định múi giờ, khối lượng công việc và hợp đồng dịch vụ.")
            else:
                tier = 5
                tier_label = "Chưa phân loại (Địa điểm / hình thức làm việc chưa rõ)"
                unverified.append(f"Chưa xác định được địa điểm và hình thức làm việc cụ thể từ thông tin tuyển dụng ({location}).")

        # Feasibility condition checks
        if "full-time" in desc or "toàn thời gian" in desc or "full time" in desc:
            unverified.append("JD yêu cầu toàn thời gian: Cần xác nhận tiến độ học tập có đáp ứng được lịch làm việc không.")

        if re.search(r"\b(1|2)\s*(?:năm|year|\+)\s*(?:kinh nghiệm|experience)", desc):
            unverified.append("JD đề cập 1-2 năm kinh nghiệm: Cần làm rõ xem có chấp nhận hồ sơ thực tập/fresher 0 năm kinh nghiệm không.")

        # Active status check (with evidence distinction)
        is_active = job.get("isActive", True)
        if is_active is False or re.search(r"\b(closed|no longer accepting applications|đã hết hạn|ngừng nhận hồ sơ)\b", desc):
            is_active = False
            job["status_evidence"] = "Phát hiện thông báo hoặc cờ ngừng nhận hồ sơ (Closed / No longer accepting applications)."
            unverified.append("CẢNH BÁO: Tin tuyển dụng đã đóng hoặc hết hạn nhận hồ sơ.")
        else:
            is_active = True
            job["status_evidence"] = "Không phát hiện banner đóng tuyển dụng; cần xác nhận thêm với nhà tuyển dụng về tình trạng thực tế."

        job["priority_tier"] = tier
        job["priority_label"] = tier_label
        job["is_remote"] = (tier == 2 or "remote" in location.lower())
        job["unverified_conditions"] = unverified
        job["is_active"] = is_active
        return job

    def save_search_session(
        self,
        unique_jobs: List[Dict[str, Any]],
        candidate_summary: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Persist search results into a session file with a stable session ID.
        """
        import datetime
        SEARCH_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        (LOCAL_DIR / "temp").mkdir(parents=True, exist_ok=True)

        if not session_id:
            now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"search_session_{now_str}"

        session_file = SEARCH_SESSIONS_DIR / f"{session_id}.json"
        latest_file = SEARCH_SESSIONS_DIR / "latest_session.json"

        session_payload = {
            "session_id": session_id,
            "created_at": datetime.datetime.now().isoformat(),
            "candidate_criteria": candidate_summary,
            "total_jobs": len(unique_jobs),
            "jobs": unique_jobs
        }

        # Write stable session file
        session_file.write_text(json.dumps(session_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        # Write pointer to latest session
        latest_file.write_text(json.dumps(session_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        # Backwards compatibility cache file
        SEARCH_CACHE_FILE.write_text(
            json.dumps({"session_id": session_id, "results": unique_jobs, "count": len(unique_jobs)}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return {
            "session_id": session_id,
            "session_path": session_file,
            "total_jobs": len(unique_jobs)
        }

    def search_all_sources(
        self,
        config: Optional[Dict[str, Any]] = None,
        candidate_profile_path: Optional[Path] = None,
        max_per_tier: int = 3,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run configured searches across upstream portals, deduplicate, categorize into tiers,
        and save into a persistent search session with a stable session ID.

        Note on limit: max_per_tier specifies the maximum results per individual upstream query,
        not the total cumulative results after deduplication.
        """
        cfg = config or DEFAULT_SEARCH_CONFIG
        cand_summary = None
        if candidate_profile_path and candidate_profile_path.exists():
            cand_summary = load_search_profile(candidate_profile_path)

        all_jobs: List[Dict[str, Any]] = []
        source_status = {
            "bun_available": self.is_bun_available(),
            "linkedin_status": "OK" if self.is_bun_available() else "DISABLED (Bun missing)",
            "freehire_status": "OK" if self.is_bun_available() else "DISABLED (Bun missing)"
        }

        # 1. Execute Priority 1: Da Nang
        for q in ["Network Intern", "Security Intern", "Network Engineer"]:
            jobs = self.search_linkedin(query=q, location="Da Nang, Vietnam", limit=max_per_tier)
            for j in jobs:
                j["target_query"] = q
                all_jobs.append(j)

        # 2. Execute Priority 2: Remote Vietnam
        for q in ["Security Intern", "Cyber Security"]:
            jobs = self.search_linkedin(query=q, location="Vietnam", limit=max_per_tier, remote="remote")
            for j in jobs:
                j["target_query"] = q
                all_jobs.append(j)

        # 3. Execute Priority 3: Secondary Cities (Hanoi / HCMC)
        for q in ["SOC Intern", "Security Intern"]:
            jobs = self.search_linkedin(query=q, location="Vietnam", limit=max_per_tier)
            for j in jobs:
                j["target_query"] = q
                all_jobs.append(j)

        # 4. Execute Priority 4: Freelance via Freehire
        for q in ["python log", "linux"]:
            jobs = self.search_freehire(query=q, region="apac", limit=max_per_tier, remote="remote")
            for j in jobs:
                j["target_query"] = q
                all_jobs.append(j)

        # Deduplicate using canonical keys
        seen_keys = set()
        unique_jobs: List[Dict[str, Any]] = []
        for j in all_jobs:
            self.categorize_and_audit_job(j, cand_summary)
            k = j["canonical_key"]
            if k not in seen_keys:
                seen_keys.add(k)
                unique_jobs.append(j)

        # Sort by tier: Tier 1 -> 2 -> 3 -> 4 -> 5 -> 98 (Senior) -> 99 (Ads)
        unique_jobs.sort(key=lambda x: x.get("priority_tier", 99))

        # Hydrate descriptions for top priority jobs that lack it (e.g. from LinkedIn search)
        for j in unique_jobs[:6]:
            if not j.get("description") and j.get("search_portal") == "linkedin" and j.get("id"):
                detail = self.get_linkedin_detail(j["id"])
                if detail:
                    j["description"] = detail.get("description", "")
                    j["employmentType"] = detail.get("employmentType")
                    j["isActive"] = detail.get("isActive", True)
                    # Re-audit with full description
                    self.categorize_and_audit_job(j, cand_summary)

        # Save to persistent search session
        session_info = self.save_search_session(
            unique_jobs=unique_jobs,
            candidate_summary=cand_summary,
            session_id=session_id
        )

        return {
            "session_id": session_info["session_id"],
            "session_path": str(session_info["session_path"]),
            "source_status": source_status,
            "total_found": len(unique_jobs),
            "jobs": unique_jobs,
            "candidate_criteria": cand_summary
        }

    def evaluate_and_stage_job(
        self,
        job: Dict[str, Any],
        candidate_path: Path,
        tracker_file: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        tracker_status: str = "Đã đánh giá",
        market: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate selected real job and generate application documents.
        Strictly sets tracker status to non-applied state ('Đã tìm thấy', 'Đã đánh giá', 'Sẵn sàng rà soát', 'Cần xác minh GPA và lịch thực tập').
        """
        allowed_statuses = [
            "Đã tìm thấy",
            "Đã đánh giá",
            "Sẵn sàng rà soát",
            "Cần xác minh GPA và lịch thực tập"
        ]
        if tracker_status not in allowed_statuses:
            tracker_status = "Đã đánh giá"

        # Ensure description is present
        desc = job.get("description", "")
        if not desc and job.get("search_portal") == "linkedin" and job.get("id"):
            detail = self.get_linkedin_detail(job["id"])
            if detail:
                desc = detail.get("description", "")
                job["description"] = desc

        if not desc:
            desc = f"Vị trí: {job.get('title', '')}\nCông ty: {job.get('company', '')}\nĐịa điểm: {job.get('location', '')}\n(Mô tả chi tiết đang được cập nhật từ nguồn tuyển dụng)"

        # Determine market
        if not market:
            if job.get("priority_tier") == 4 or "freelance" in str(job.get("search_source", "")).lower():
                market = "freelance"
            else:
                market = "vietnam"

        # Load candidate
        cand_data = json.loads(candidate_path.read_text(encoding="utf-8"))

        jd_data = {
            "title": job.get("title", "Chưa rõ"),
            "company": job.get("company", "Chưa rõ"),
            "raw_content": desc,
            "content": desc,
            "url": job.get("url", ""),
            "location": job.get("location", ""),
            "employment_type": job.get("employmentType", "")
        }

        # Run evaluation
        evaluator = JobEvaluator(candidate=cand_data)
        eval_result = evaluator.evaluate(jd_data=jd_data, market=market)

        # Include unverified conditions identified during search
        existing_unverified = eval_result.setdefault("unverified_conditions", [])
        for uc in job.get("unverified_conditions", []):
            if uc not in existing_unverified:
                existing_unverified.append(uc)

        # Target output directory
        target_out = output_dir or OUTPUT_DIR
        target_out.mkdir(parents=True, exist_ok=True)

        # Generate tailored documents
        gen = DocumentGenerator(candidate=cand_data)
        company_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', jd_data.get('company', 'company').lower()).strip('_')[:20]
        role_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', eval_result['title'].lower()).strip('_')[:30]
        clean_prefix = f"{company_clean}_{role_clean}".strip('_')
        if not clean_prefix or clean_prefix == "_":
            clean_prefix = f"job_{market}_eval"

        doc_paths: Dict[str, Path] = {}

        cv_md = gen.generate_cv_markdown(target_role=eval_result['title'], market=market)
        cv_path = ensure_within_project(target_out / f"{clean_prefix}_cv.md")
        cv_path.write_text(cv_md, encoding="utf-8")
        doc_paths["cv_md"] = cv_path

        if market == "freelance":
            prop_md = gen.generate_freelance_proposal(eval_result)
            prop_path = ensure_within_project(target_out / f"{clean_prefix}_proposal.md")
            prop_path.write_text(prop_md, encoding="utf-8")
            doc_paths["proposal_md"] = prop_path
        else:
            cl_md = gen.generate_cover_letter(eval_result, language="vi")
            cl_path = ensure_within_project(target_out / f"{clean_prefix}_cover_letter.md")
            cl_path.write_text(cl_md, encoding="utf-8")
            doc_paths["cover_letter_md"] = cl_path

        prep_md = gen.generate_interview_prep(eval_result)
        prep_path = ensure_within_project(target_out / f"{clean_prefix}_interview_prep.md")
        prep_path.write_text(prep_md, encoding="utf-8")
        doc_paths["interview_prep_md"] = prep_path

        raw_html_path = ensure_within_project(target_out / f"{clean_prefix}_cv.html")
        html_path = gen.export_to_html(cv_md, raw_html_path)
        doc_paths["cv_html"] = html_path

        # Save to Tracker
        tracker = JobTracker(file_path=tracker_file or TRACKER_FILE)
        canonical_key = job.get("canonical_key") or get_canonical_job_key(
            jd_data["company"], eval_result["title"], eval_result["source"]
        )
        import hashlib
        raw_hash = hashlib.sha1(f"{market}_{canonical_key}".encode("utf-8")).hexdigest()[:6]
        calc_id = f"job_{raw_hash}"

        rec = tracker.add_or_update(
            title=eval_result["title"],
            company=jd_data["company"],
            market=market,
            source=eval_result["source"],
            match_score=eval_result.get("match_score"),
            status=tracker_status,
            notes=f"Tự động tìm kiếm qua {job.get('search_source', 'Portal')} | Nhóm: {job.get('priority_label', '')}",
            next_step="Xác minh điều kiện & Chuẩn bị phỏng vấn",
            job_id=calc_id
        )

        return {
            "job_id": rec["id"],
            "tracker_status": tracker_status,
            "eval_result": eval_result,
            "document_paths": doc_paths
        }

    def fetch_and_compare_jobs(
        self,
        job_ids_or_urls: List[str],
        candidate_profile_path: Path
    ) -> Dict[str, Any]:
        """
        Fetch full JD for target job URLs/IDs, verify recruitment status with evidence,
        and perform a 6-dimension comparative analysis against candidate profile.
        Strictly factual: does not fabricate skills or use unverified SecMon as evidence.
        """
        safe_profile_path = ensure_within_project(candidate_profile_path)
        if not safe_profile_path.exists():
            mock_path = PROJECT_ROOT / "data" / "candidates" / "candidate_mock.json"
            if mock_path.exists():
                safe_profile_path = mock_path
        cand_data = json.loads(safe_profile_path.read_text(encoding="utf-8"))
        cand_summary = load_search_profile(safe_profile_path)

        evaluator = JobEvaluator(candidate=cand_data)
        detailed_jobs: List[Dict[str, Any]] = []

        for item in job_ids_or_urls:
            # Extract ID if URL or slug
            m = re.search(r"(\d{6,})", str(item))
            job_id = m.group(1) if m else str(item)

            detail = self.get_linkedin_detail(job_id)
            if not detail:
                detailed_jobs.append({
                    "id": job_id,
                    "url": str(item),
                    "error": "Không thể tải chi tiết từ LinkedIn API",
                    "fetch_success": False
                })
                continue

            detail["fetch_success"] = True
            detail["search_portal"] = "linkedin"
            detail["search_source"] = "LinkedIn (Public Guest API)"

            # Audit and categorize
            self.categorize_and_audit_job(detail, cand_summary)

            # Evaluate against candidate
            jd_payload = {
                "title": detail.get("title", ""),
                "company": detail.get("company", ""),
                "raw_content": detail.get("description", ""),
                "content": detail.get("description", ""),
                "url": detail.get("url", f"https://www.linkedin.com/jobs/view/{job_id}"),
                "location": detail.get("location", ""),
                "employment_type": detail.get("employmentType", "")
            }
            eval_res = evaluator.evaluate(jd_payload, market="vietnam")
            detail["eval_result"] = eval_res

            # Extract 6 comparison dimensions
            desc_text = detail.get("description", "")
            title_text = detail.get("title", "")

            # Dimension 1: Nhận sinh viên đang học hay yêu cầu tốt nghiệp
            if re.search(r"\b(pursuing a bachelor|đang theo học|sinh viên đang học|sinh viên năm|undergraduate)\b", desc_text, re.IGNORECASE):
                edu_policy = "CHẤP NHẬN SINH VIÊN ĐANG HỌC (Pursuing Bachelor's degree)"
                edu_match = True
            elif re.search(r"\b(graduated|đã tốt nghiệp|bachelor's degree required|yêu cầu bằng tốt nghiệp)\b", desc_text, re.IGNORECASE):
                edu_policy = "YÊU CẦU ĐÃ TỐT NGHIỆP (College/University graduated)"
                edu_match = False
            else:
                edu_policy = "Chưa nêu rõ yêu cầu tốt nghiệp; cần xác minh"
                edu_match = None

            # Dimension 2: Kinh nghiệm và kỹ năng bắt buộc
            req_exp_match = re.search(r"\b(\d+)\+?\s*(?:year|năm)\s*(?:of\s+)?(?:hands-on\s+)?experience\b", desc_text, re.IGNORECASE)
            req_exp = req_exp_match.group(0) if req_exp_match else "0 năm (Thực tập / Không yêu cầu kinh nghiệm trước)"

            # Dimension 3: Tiếng Anh
            eng_match = re.search(r"(?:english[^\n.]*|tiếng anh[^\n.]*)", desc_text, re.IGNORECASE)
            eng_req = eng_match.group(0).strip() if eng_match else "Không ghi rõ yêu cầu tiếng Anh trong JD"

            # Dimension 4: Lịch làm việc và địa điểm
            work_loc = f"{detail.get('location', 'Chưa rõ')} | {detail.get('employmentType', 'Chưa rõ')}"

            # Dimension 5: Bằng chứng phù hợp trong my_profile.json (Không dùng SecMon)
            matched_evidence = [
                f"{item['skill']} ({item['evidence_type']})"
                for item in eval_res.get("matched_skills", [])
            ]

            # Dimension 6: Điều kiện chưa rõ cần hỏi nhà tuyển dụng
            unverified_list = list(detail.get("unverified_conditions", []))
            for q in eval_res.get("clarification_questions", []):
                if q not in unverified_list:
                    unverified_list.append(q)

            detail["comparison_dimensions"] = {
                "education_policy": edu_policy,
                "education_match": edu_match,
                "required_experience": req_exp,
                "english_requirement": eng_req,
                "work_schedule_and_location": work_loc,
                "profile_evidence": matched_evidence,
                "unverified_questions": unverified_list
            }

            detailed_jobs.append(detail)

        return {
            "total_evaluated": len(detailed_jobs),
            "jobs": detailed_jobs
        }

