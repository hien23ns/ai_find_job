"""
Configuration and constants for ai-job-search.
Strictly confined to PROJECT_ROOT.
"""

from pathlib import Path
import os

# Normalize PROJECT_ROOT
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Local cache, logs, and temp paths - all inside PROJECT_ROOT/.local
LOCAL_DIR = PROJECT_ROOT / ".local"
CACHE_DIR = LOCAL_DIR / "cache"
TEMP_DIR = LOCAL_DIR / "temp"
LOG_DIR = LOCAL_DIR / "logs"

# Project data and output directories
DATA_DIR = PROJECT_ROOT / "data"
CANDIDATES_DIR = DATA_DIR / "candidates"
TRACKER_DIR = DATA_DIR / "tracker"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Ensure runtime directories exist inside PROJECT_ROOT
for directory in [LOCAL_DIR, CACHE_DIR, TEMP_DIR, LOG_DIR, DATA_DIR, CANDIDATES_DIR, TRACKER_DIR, OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Market Definitions & Skill Taxonomies
MARKETS = {
    "vietnam": {
        "name": "Việt Nam",
        "currency": "VND",
        "languages": ["vi", "en"],
        "target_roles": [
            "Security Intern",
            "SOC Intern",
            "SOC Analyst L1",
            "Network Security Intern",
            "Network Engineer Junior",
            "Information Security Trainee"
        ],
        "core_skills": [
            "TCP/IP", "Network Fundamentals", "Wireshark", "Linux", "Bash",
            "Python", "SIEM", "Splunk", "ELK", "Snort", "Suricata", "Nmap",
            "Log Analysis", "Firewall", "Incident Response Basics", "OSINT"
        ],
        "scoring_weights": {
            "hard_requirements": 0.40,
            "core_skills": 0.35,
            "relevant_projects_labs": 0.15,
            "education_certifications": 0.10
        }
    },
    "korea": {
        "name": "Hàn Quốc (Korea)",
        "currency": "KRW",
        "languages": ["ko", "en"],
        "target_roles": [
            "정보보안", "정보보호", "보안관제", "네트워크 보안",
            "취약점 진단", "모의해킹", "신입", "인턴"
        ],
        "core_skills": [
            "정보보안기사", "보안관제", "네트워크 보안", "Linux", "Wireshark",
            "취약점 진단", "웹 보안", "Python", "SIEM", "방화벽", "모의해킹"
        ],
        "scoring_weights": {
            "hard_requirements": 0.30,
            "core_skills": 0.30,
            "visa_and_residency": 0.20,
            "language_proficiency": 0.20
        }
    },
    "freelance": {
        "name": "Freelance & Remote Projects",
        "currency": "USD",
        "languages": ["en", "vi"],
        "target_roles": [
            "Python Log Processing",
            "Network Documentation",
            "Linux Server Hardening",
            "Log Monitoring Automation",
            "Authorized Security Assessment"
        ],
        "core_skills": [
            "Python", "Regex", "Pandas", "Log Parsing", "Bash Scripting",
            "Linux Administration", "SSH Hardening", "Network Topology Documentation",
            "Snort/Suricata Rules", "Auditd", "ELK Stack Config"
        ],
        "scoring_weights": {
            "scope_clarity": 0.25,
            "deliverable_feasibility": 0.30,
            "technical_match": 0.25,
            "budget_and_timeline": 0.20
        }
    }
}
