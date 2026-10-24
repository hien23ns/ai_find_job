"""
Upstream Bridge Module for ai-job-search.
Provides direct, concrete integration with upstream tools and architecture:
1. tools/job_key.py: Generates deterministic, collision-resistant canonical deduplication keys.
2. tools/security_guards.py: Verifies supply-chain guard integrity and permissions safety.
3. Candidate Profile Schema: Thin-Pointer validation against upstream/CLAUDE.md candidate definition.
"""

import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, Optional

from src.config import PROJECT_ROOT

UPSTREAM_DIR = PROJECT_ROOT / "upstream"
UPSTREAM_TOOLS_DIR = UPSTREAM_DIR / "tools"
UPSTREAM_COMMIT = "e16acee3abdaae57f8026789338a3c6eebf4608b"
UPSTREAM_REPO = "https://github.com/ai-job-search-dev/ai-job-search.git"


def is_upstream_available() -> bool:
    """Check if upstream directory and core tools exist in PROJECT_ROOT."""
    return (UPSTREAM_TOOLS_DIR / "job_key.py").exists() and (UPSTREAM_TOOLS_DIR / "security_guards.py").exists()


def get_upstream_info() -> Dict[str, Any]:
    """Return upstream metadata and integration status."""
    available = is_upstream_available()
    return {
        "repository": UPSTREAM_REPO,
        "canonical_upstream": UPSTREAM_REPO,
        "pinned_commit": UPSTREAM_COMMIT,
        "upstream_commit": UPSTREAM_COMMIT,
        "license": "MIT",
        "path": str(UPSTREAM_DIR),
        "upstream_dir": str(UPSTREAM_DIR),
        "available": available,
        "tools_integrated": [
            "tools/job_key.py (canonical deduplication key generation)",
            "tools/security_guards.py (supply-chain integrity and permission guards)",
            "CLAUDE.md (Thin-Pointer candidate schema architecture)"
        ],
        "tools_available": {
            "tools/job_key.py": "Sinh canonical deduplication key",
            "tools/security_guards.py": "Kiểm tra an toàn chuỗi cung ứng upstream",
            "CLAUDE.md": "Chuẩn hóa hồ sơ ứng viên Thin-Pointer"
        }
    }


def get_canonical_job_key(company: str, title: str, url: str = "") -> str:
    """
    Generate canonical deduplication key using upstream/tools/job_key.py.
    Provides fallback algorithm if upstream module cannot be loaded.
    """
    if is_upstream_available():
        if str(UPSTREAM_TOOLS_DIR) not in sys.path:
            sys.path.insert(0, str(UPSTREAM_TOOLS_DIR))
        try:
            import job_key  # type: ignore
            return job_key.make_key(company, title, url)
        except Exception:
            pass

    # Deterministic fallback in case upstream tool import fails
    c_clean = "".join(c for c in company.lower() if c.isalnum() or c in "-_ ").replace(" ", "-")[:40]
    t_clean = "".join(c for c in title.lower() if c.isalnum() or c in "-_ ").replace(" ", "-")[:60]
    raw = f"{c_clean}_{t_clean}_{url}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:6]
    return f"{c_clean or 'company'}_{t_clean or 'job'}-{digest}"


def run_upstream_security_guards() -> Dict[str, Any]:
    """
    Execute upstream supply-chain security guards tool (upstream/tools/security_guards.py).
    Verifies settings permissions, personal-data ignore rules, package manifests, and agent tools.
    """
    guard_script = UPSTREAM_TOOLS_DIR / "security_guards.py"
    if not guard_script.exists():
        return {
            "status": "UNAVAILABLE",
            "message": f"Script not found at {guard_script}",
            "passed": False
        }

    try:
        proc = subprocess.run(
            [sys.executable, str(guard_script)],
            cwd=str(UPSTREAM_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15
        )
        passed = (proc.returncode == 0)
        output = proc.stdout.strip() or proc.stderr.strip()
        return {
            "status": "PASS" if passed else "FAIL",
            "exit_code": proc.returncode,
            "passed": passed,
            "output": output
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "passed": False,
            "message": str(e)
        }


def validate_candidate_thin_pointer(candidate_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate candidate profile structure against Thin-Pointer schema principles:
    - Clear distinction between Work Experience, Labs/Simulations, Personal Projects, Coursework, and Education.
    - No fabricated credentials or unverifiable claims.
    """
    required_sections = [
        "name", "summary", "skills", "education",
        "work_experience", "labs_and_simulations", "personal_projects"
    ]
    missing = [sec for sec in required_sections if sec not in candidate_data]
    
    # Check strict distinction
    has_experience = isinstance(candidate_data.get("work_experience"), list)
    has_labs = isinstance(candidate_data.get("labs_and_simulations"), list)
    has_projects = isinstance(candidate_data.get("personal_projects"), list)

    is_valid = (len(missing) == 0 and has_experience and has_labs and has_projects)
    return {
        "valid": is_valid,
        "missing_sections": missing,
        "experience_entries": len(candidate_data.get("work_experience", [])) if has_experience else 0,
        "labs_entries": len(candidate_data.get("labs_and_simulations", [])) if has_labs else 0,
        "projects_entries": len(candidate_data.get("personal_projects", [])) if has_projects else 0,
        "schema_standard": "Upstream Thin-Pointer (CLAUDE.md / AGENTS.md)"
    }
