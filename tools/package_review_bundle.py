"""
Packaging Script for review_bundle_v4.zip.
Builds an allowlist-only distribution archive inside PROJECT_ROOT.
Includes full upstream dependencies required for standalone testing and verification.
Scans file contents for secrets and private data prior to inclusion.
Ensures zero leaks of real trackers, credentials, output docs, my_profile.json, my_jd.txt, or git history.
"""

import os
from pathlib import Path
import re
import sys
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Allowed root files (relative to PROJECT_ROOT)
ALLOWED_FILES = [
    "README.md",
    "AGENTS.md",
    "UPSTREAM_INTEGRATION.md",
    "run.ps1",
    "START_APP.bat",
    ".gitignore",
    ".gitmodules"
]

# Allowed directories (relative to PROJECT_ROOT)
ALLOWED_DIRS = [
    "src",
    "tests",
    "docs",
    "data/candidates",
    "data/live_jds",
    "data/tracker",
    "output",
    ".agents",
    "tools",
    "upstream"
]

# Patterns strictly forbidden in archive
DENIED_PATTERNS = [
    r"__pycache__",
    r"\.py[cod]$",
    r"(^|[/\\])\.local([/\\]|$)",
    r"(^|[/\\])\.git([/\\]|$)",
    r"\.pytest_cache",
    r"node_modules",
    r"output[/\\].*\.(md|html|pdf|png)$",
    r"output[/\\]applications",
    r"data[/\\]private",
    r"avatar\.png",
    r"review_bundle.*\.zip$",
    r"my_profile\.json$",
    r"my_jd\.txt$",
    r"\.tmp$",
    r"\.env$",
    r"secrets\.json$"
]

# Content inspection regex for potential secrets
SECRET_PATTERNS = [
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"AIzaSy[a-zA-Z0-9_-]{33}"),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"sk-[a-zA-Z0-9]{48}")
]

def is_denied(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/")
    # Strict candidate profile whitelist
    if norm.startswith("data/candidates/"):
        allowed_cand = [
            "data/candidates/candidate_mock.json",
            "data/candidates/candidate_incomplete.json",
            "data/candidates/.gitkeep"
        ]
        if norm not in allowed_cand:
            return True

    # Strict tracker whitelist
    if norm.startswith("data/tracker/"):
        allowed_tracker = [
            "data/tracker/.gitkeep"
        ]
        if norm not in allowed_tracker:
            return True

    for pat in DENIED_PATTERNS:
        if re.search(pat, norm, re.IGNORECASE):
            return True
    return False

def scan_content_for_secrets(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return True # Non-text or binary files skipped from regex scan
    for pat in SECRET_PATTERNS:
        if pat.search(content):
            return False # Failed secret check
    return True

def package_bundle(bundle_name: str = "review_bundle_v4.zip") -> Path:
    bundle_path = PROJECT_ROOT / bundle_name
    if bundle_path.exists():
        bundle_path.unlink()

    files_to_pack = []

    # 1. Collect allowed root files
    for f in ALLOWED_FILES:
        fp = PROJECT_ROOT / f
        if fp.exists() and not is_denied(f):
            files_to_pack.append(fp)

    # 2. Collect files from allowed directories
    for d in ALLOWED_DIRS:
        dp = PROJECT_ROOT / d
        if not dp.exists():
            continue
        for root, dirs, files in os.walk(dp):
            for file in files:
                fp = Path(root) / file
                rel = fp.relative_to(PROJECT_ROOT).as_posix()
                if not is_denied(rel):
                    files_to_pack.append(fp)

    print(f"[*] Tổng số file dự kiến đóng gói: {len(files_to_pack)}")

    # 3. Scan file contents
    scanned_count = 0
    for fp in files_to_pack:
        if not scan_content_for_secrets(fp):
            rel = fp.relative_to(PROJECT_ROOT).as_posix()
            print(f"[!] PHÁT HIỆN DẤU HIỆU SECRET TRONG FILE: {rel}. HỦY ĐÓNG GÓI!", file=sys.stderr)
            sys.exit(1)
        scanned_count += 1

    print(f"[+] Đã quét nội dung {scanned_count} file: 0 secret rò rỉ.")

    # 4. Create ZIP archive
    with zipfile.ZipFile(bundle_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in files_to_pack:
            rel = fp.relative_to(PROJECT_ROOT).as_posix()
            zf.write(fp, arcname=rel)

    size_kb = bundle_path.stat().st_size / 1024
    print(f"[+] Đã tạo thành công {bundle_path.name} ({size_kb:.1f} KB, {len(files_to_pack)} files).")
    
    # 5. Verify contents of archive
    with zipfile.ZipFile(bundle_path, mode="r") as zf:
        names = zf.namelist()
        forbidden_substrings = [
            "data/tracker/jobs_tracker.json",
            "data/tracker/jobs_tracker.csv",
            "data/candidates/my_profile.json",
            "my_profile.json",
            "data/my_jd.txt",
            "my_jd.txt",
            "data/private",
            "avatar.png",
            ".local",
        ]
        for forbidden in forbidden_substrings:
            for n in names:
                assert forbidden not in n, f"Lỗi: Tìm thấy file nhạy cảm '{forbidden}' trong archive ({n})!"

        # Ensure no generated documents in output/
        for n in names:
            if n.startswith("output/") and n != "output/.gitkeep":
                assert False, f"Lỗi: Thư mục output chứa tài liệu ứng tuyển cá nhân '{n}'!"

        assert not any(n == ".git" or n.startswith(".git/") or "/.git/" in n for n in names), "Lỗi: Thư mục .git lọt vào archive!"

    print("[+] Kiểm tra toàn vẹn gói: 100% tuân thủ danh sách cho phép (Allowlist), không chứa my_profile.json, my_jd.txt, tracker thật hoặc tài liệu cá nhân.")
    return bundle_path

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "review_bundle_latest.zip"
    package_bundle(target)
