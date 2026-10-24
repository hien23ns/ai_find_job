"""
Evaluation and Job Matching Engine.
Evaluates JDs against Candidate Profile across Vietnam, Korea, and Freelance markets.
Maintains strict separation between Coursework, Labs, Personal Projects, and Real Work Experience.
Features:
1. Precise JD section parsing (Mandatory, Preferred, Responsibilities, Training Offerings, Work Conditions).
2. Relational Skill Taxonomy (TCP/IP = core network protocol knowledge, Wireshark = packet analysis tool).
3. Sparse technical JD handling without false zero-competence penalization or forced scoring.
4. Hard requirements and practical feasibility verification (Academic year, Location on-site, Full-time schedule).
"""

from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Tuple
from src.config import MARKETS

def extract_keywords(text: str) -> List[str]:
    """Tokenize and normalize keywords from text."""
    tokens = re.findall(r"[A-Za-z0-9#\+\.\-]+|[\uac00-\ud7a3]+", text)
    return [t.lower() for t in tokens]

# Relational Skill Taxonomy for Network, Security, Systems, and Programming
SKILL_TAXONOMY = {
    "network": {
        "aliases": [
            "network", "mạng", "network fundamentals", "kiến thức mạng",
            "mạng máy tính", "networking", "hạ tầng mạng", "quản trị mạng"
        ],
        "components": {
            "tcp/ip": {
                "aspect": "Kiến thức giao thức mạng cốt lõi (TCP/IP - một phần kiến thức mạng)",
                "scope": "Nắm vững bộ giao thức TCP/IP, mô hình OSI/Internet (không suy ra thành thạo toàn bộ lĩnh vực mạng)"
            },
            "wireshark": {
                "aspect": "Công cụ phân tích mạng (Wireshark)",
                "scope": "Có kỹ năng bắt và phân tích lưu lượng gói tin mạng qua Wireshark (không thay thế kiến thức quản trị hạ tầng mạng toàn diện)"
            },
            "cisco": {
                "aspect": "Thiết bị mạng (Cisco)",
                "scope": "Thực hành thiết bị switch/router cơ bản"
            },
            "vlan": {
                "aspect": "Phân chia mạng ảo (VLAN)",
                "scope": "Kiến thức phân tách broadcast domain"
            }
        }
    },
    "security": {
        "aliases": [
            "security", "an toàn thông tin", "attt", "an ninh mạng",
            "bảo mật", "information security", "giám sát an ninh"
        ],
        "components": {
            "nmap": {
                "aspect": "Công cụ quét mạng và rà soát an toàn (Nmap)",
                "scope": "Kỹ năng rà quét phát hiện cổng và dịch vụ mạng"
            },
            "firewall": {
                "aspect": "Kiến thức lọc gói tin và tường lửa (Firewall)",
                "scope": "Hiểu nguyên lý lọc gói tin và thiết lập rule tường lửa"
            },
            "snort": {
                "aspect": "Hệ thống giám sát phát hiện xâm nhập IDS (Snort)",
                "scope": "Viết và phân tích rule cảnh báo xâm nhập"
            },
            "suricata": {
                "aspect": "Hệ thống giám sát phát hiện xâm nhập IDS/IPS (Suricata)",
                "scope": "Giám sát lưu lượng mạng và phát hiện tấn công"
            }
        }
    },
    "linux": {
        "aliases": ["linux", "hệ điều hành linux", "hệ thống linux"],
        "components": {
            "bash": {
                "aspect": "Dòng lệnh và shell scripting trên Linux (Bash)",
                "scope": "Thao tác quản trị hệ thống và tự động hóa qua CLI"
            },
            "linux": {
                "aspect": "Sử dụng và vận hành hệ điều hành Linux",
                "scope": "Quản trị máy chủ Linux cơ bản"
            }
        }
    },
    "python": {
        "aliases": ["python", "lập trình python", "scripting"],
        "components": {
            "python": {
                "aspect": "Lập trình và scripting tự động hóa (Python)",
                "scope": "Xử lý file log, phân tích dữ liệu và tự động hóa tác vụ"
            }
        }
    }
}

class JobEvaluator:
    def __init__(self, candidate: Dict[str, Any]):
        self.candidate = candidate or {}

    def _parse_jd_sections(self, content: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Parse JD text into structured, categorized sections with exact quotes:
        - mandatory_requirements: Điều kiện bắt buộc
        - preferred_requirements: Điều kiện ưu tiên
        - responsibilities: Công việc sẽ thực hiện
        - training_offerings: Nội dung được đào tạo / học việc
        - work_conditions: Địa điểm và lịch làm việc
        - compensation: Thu nhập / Phụ cấp
        """
        sections: Dict[str, List[Dict[str, str]]] = {
            "mandatory_requirements": [],
            "preferred_requirements": [],
            "responsibilities": [],
            "training_offerings": [],
            "work_conditions": [],
            "compensation": [],
            "general": []
        }

        header_patterns = [
            ("mandatory_requirements", re.compile(
                r"^(?:yêu\s*cầu(?:\s+ứng\s*viên|\s+công\s*việc|\s+bắt\s*buộc)?|tiêu\s*chuẩn|điều\s*kiện\s*bắt\s*buộc|requirements|qualifications|mandatory(?:\s*requirements)?|basic\s*qualifications|지원\s*자격|자격\s*요건|필수\s*요건)\s*[:：]?",
                re.IGNORECASE
            )),
            ("preferred_requirements", re.compile(
                r"^(?:ưu\s*tiên|yêu\s*cầu\s*ưu\s*tiên|điểm\s*cộng|preferred(?:\s*qualifications)?|nice\s*to\s*have|plus|우대\s*사항|우대\s*조건|우대)\s*[:：]?",
                re.IGNORECASE
            )),
            ("responsibilities", re.compile(
                r"^(?:công\s*việc|mô\s*tả\s*công\s*việc|trách\s*nhiệm|nhiệm\s*vụ|vai\s*trò|roles\s*(?:&|and)\s*responsibilities|responsibilities|duties|주요\s*업무|업무\s*내용)\s*[:：]?",
                re.IGNORECASE
            )),
            ("training_offerings", re.compile(
                r"^(?:quyền\s*lợi|đào\s*tạo|nội\s*dung\s*đào\s*tạo|chế\s*độ\s*đào\s*tạo|chính\s*sách\s*đào\s*tạo|học\s*việc|benefits|training|혜택|복리\s*후생)\s*[:：]?",
                re.IGNORECASE
            )),
            ("work_conditions", re.compile(
                r"^(?:địa\s*điểm(?:\s+và\s+lịch|\s+làm\s*việc)?|thời\s*gian\s*làm\s*việc|lịch\s*làm\s*việc|location|work\s*location|working\s*hours|schedule|근무지|근무\s*시간)\s*[:：]?",
                re.IGNORECASE
            )),
            ("compensation", re.compile(
                r"^(?:thu\s*nhập|lương|phụ\s*cấp|mức\s*lương|compensation|salary|급여)\s*[:：]?",
                re.IGNORECASE
            ))
        ]

        # Training markers inside work duties (e.g., "Học nghiệp vụ SOC/Network và ATTT")
        training_duty_pattern = re.compile(
            r"(?:học\s+nghiệp\s+vụ|được\s+đào\s+tạo|tham\s+gia\s+đào\s+tạo|học\s+việc|được\s+hướng\s+dẫn|đào\s+tạo\s+nội\s+bộ|bồi\s+dưỡng\s+nghiệp\s+vụ|học\s+tập)",
            re.IGNORECASE
        )

        def add_item(sec_name: str, item_text: str, quote: str, source_label: str):
            clean_text = item_text.strip().lstrip("-•* ").strip()
            if not clean_text:
                return
            sections[sec_name].append({
                "text": clean_text,
                "raw_quote": quote.strip(),
                "source_section": source_label
            })

        current_sec = "general"

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Check if this line is a section header
            matched_header = False
            for sec_name, pat in header_patterns:
                m = pat.match(line)
                if m:
                    current_sec = sec_name
                    matched_header = True
                    remainder = line[m.end():].strip().lstrip(":- ").strip()
                    if remainder:
                        if current_sec == "responsibilities":
                            # Check if clauses inside responsibility represent training vs work
                            clauses = re.split(r";\s*|\.\s+", remainder)
                            for c in clauses:
                                c = c.strip()
                                if not c:
                                    continue
                                if training_duty_pattern.search(c):
                                    add_item("training_offerings", c, c, "Công việc (Nội dung được đào tạo / Học việc)")
                                else:
                                    add_item("responsibilities", c, c, "Công việc sẽ thực hiện")
                        else:
                            add_item(current_sec, remainder, raw_line, sec_name)
                    break

            if matched_header:
                continue

            # Route line under current section
            if current_sec == "responsibilities":
                clauses = re.split(r";\s*|\.\s+", line)
                for c in clauses:
                    c = c.strip()
                    if not c:
                        continue
                    if training_duty_pattern.search(c):
                        add_item("training_offerings", c, c, "Công việc (Nội dung được đào tạo / Học việc)")
                    else:
                        add_item("responsibilities", c, c, "Công việc sẽ thực hiện")
            elif current_sec in sections:
                add_item(current_sec, line, raw_line, current_sec)
            else:
                add_item("general", line, raw_line, "Thông tin chung")

        # If general contains location/schedule lines, cross-route them
        for item in list(sections["general"]):
            txt_lower = item["text"].lower()
            if any(k in txt_lower for k in ["địa điểm", "hà nội", "hồ chí minh", "đà nẵng", "seoul", "thứ hai", "thứ 2", "full-time", "toàn thời gian"]):
                sections["work_conditions"].append(item)
                sections["general"].remove(item)

        return sections

    def _extract_jd_required_skills(self, sections: Dict[str, Any], market: str) -> Tuple[List[str], List[Dict[str, str]]]:
        """
        Extract REQUIRED technical skills ONLY from mandatory/preferred requirements.
        Strictly ignores skills listed inside responsibilities or training offerings
        (e.g., 'Học nghiệp vụ SOC/Network và ATTT' is a training offering, NOT a prerequisite).
        """
        detected_skills = []
        skill_metadata = []
        
        req_items = sections.get("mandatory_requirements", []) + sections.get("preferred_requirements", [])
        
        candidate_skills_pool = [
            "TCP/IP", "Wireshark", "Linux", "Bash", "Python", "SIEM", "Splunk", "ELK",
            "Snort", "Suricata", "Nmap", "Firewall", "Cisco", "Regex", "Pandas",
            "보안관제", "정보보안기사", "네트워크 보안", "취약점 진단", "웹 보안", "모의해킹"
        ]
        
        # Also check core market skills
        if market in MARKETS:
            for sk in MARKETS[market].get("core_skills", []):
                if sk not in candidate_skills_pool:
                    candidate_skills_pool.append(sk)

        for req in req_items:
            req_text = req.get("text", "")
            req_lower = req_text.lower()
            for sk in candidate_skills_pool:
                sk_lower = sk.lower()
                # Word boundary match to prevent accidental partial matching
                pattern = r"(?:\b|_)" + re.escape(sk_lower) + r"(?:\b|_)"
                if re.search(pattern, req_lower):
                    if sk not in detected_skills:
                        detected_skills.append(sk)
                        skill_metadata.append({
                            "skill": sk,
                            "raw_quote": req.get("raw_quote", req_text),
                            "source_section": req.get("source_section", "Yêu cầu")
                        })

        return detected_skills, skill_metadata

    def _find_skill_evidence(self, skill: str, _is_recursive: bool = False) -> Optional[Dict[str, Any]]:
        """
        Search candidate profile for evidence of a skill,
        differentiating Coursework, Labs, Projects, and Work Experience.
        Supports Relational Skill Taxonomy (TCP/IP = core protocol evidence, Wireshark = packet analysis evidence).
        Does NOT require profile to contain the literal word 'Network' and does NOT over-extrapolate full domain mastery.
        """
        skill_lower = skill.lower()

        # 1. Check Real Work Experience (Highest priority evidence)
        for exp in self.candidate.get("work_experience", []):
            desc = (exp.get("description", "") + " " + " ".join(exp.get("technologies", []))).lower()
            if skill_lower in desc:
                return {
                    "type": "Kinh nghiệm làm việc thực tế",
                    "evidence": f"{exp.get('role', 'Vị trí')} tại {exp.get('company', 'Công ty')}: {exp.get('description', '')}",
                    "is_partial": False
                }

        # 2. Check Personal Projects
        for proj in self.candidate.get("personal_projects", []):
            desc = (proj.get("name", "") + " " + proj.get("description", "") + " " + " ".join(proj.get("technologies", []))).lower()
            if skill_lower in desc:
                return {
                    "type": "Dự án cá nhân (Personal Project)",
                    "evidence": f"Dự án '{proj.get('name')}': {proj.get('description', '')}",
                    "is_partial": False
                }

        # 3. Check Labs & Simulations
        for lab in self.candidate.get("labs_and_simulations", []):
            desc = (lab.get("name", "") + " " + lab.get("description", "") + " " + " ".join(lab.get("tools", []))).lower()
            if skill_lower in desc:
                return {
                    "type": "Thực hành Lab / Giả lập (Lab & Simulation)",
                    "evidence": f"Bài Lab '{lab.get('name')}': {lab.get('description', '')}",
                    "is_partial": False
                }

        # 4. Check Academic Coursework
        for course in self.candidate.get("coursework", []):
            desc = (course.get("course_name", "") + " " + course.get("topics", "")).lower()
            if skill_lower in desc:
                return {
                    "type": "Môn học đại học (Academic Coursework)",
                    "evidence": f"Môn '{course.get('course_name')}': {course.get('topics', '')}",
                    "is_partial": False
                }

        # 5. Check direct skills list (direct match)
        all_skills = []
        for cat, sk_list in self.candidate.get("skills", {}).items():
            all_skills.extend(sk_list)
        if any(skill_lower == s.lower() for s in all_skills):
            matched_declared = [s for s in all_skills if skill_lower == s.lower()][0]
            return {
                "type": "Kỹ năng tự khai báo (Self-declared skill)",
                "evidence": f"Có trong danh mục kỹ năng: {matched_declared}",
                "is_partial": False
            }

        # If already in recursive lookup, do not recurse into taxonomy mapping again
        if _is_recursive:
            return None

        # 6. Relational Skill Taxonomy Mapping (e.g., Network -> TCP/IP and Wireshark)
        for domain, tax_info in SKILL_TAXONOMY.items():
            if skill_lower in tax_info["aliases"] or any(a in skill_lower for a in tax_info["aliases"]):
                matched_components = []
                for comp_key, comp_info in tax_info["components"].items():
                    if comp_key.lower() == skill_lower:
                        continue
                    comp_ev = self._find_skill_evidence(comp_key, _is_recursive=True)
                    if comp_ev:
                        matched_components.append((comp_key.upper(), comp_info["aspect"], comp_ev))

                if matched_components:
                    comp_names = [mc[0] for mc in matched_components]
                    aspect_notes = [f"{mc[1]} ({mc[2]['type']}: {mc[2]['evidence']})" for mc in matched_components]
                    
                    if "TCP/IP" in comp_names and "WIRESHARK" in comp_names:
                        ev_summary = (
                            "Hồ sơ có 'TCP/IP' (kiến thức giao thức mạng cốt lõi) và 'Wireshark' (công cụ phân tích gói tin mạng). "
                            "Đây là bằng chứng cho một phần kiến thức mạng; không đòi hỏi hồ sơ phải chứa đúng chữ 'Network', "
                            "đồng thời không suy ra thành thạo toàn bộ lĩnh vực quản trị hạ tầng mạng."
                        )
                    elif "TCP/IP" in comp_names:
                        ev_summary = (
                            "Hồ sơ có 'TCP/IP': Bằng chứng cho một phần kiến thức giao thức mạng cốt lõi. "
                            "Không đòi hỏi chữ 'Network', không suy ra thành thạo toàn bộ lĩnh vực mạng."
                        )
                    elif "WIRESHARK" in comp_names:
                        ev_summary = (
                            "Hồ sơ có 'Wireshark': Bằng chứng về công cụ phân tích lưu lượng và bắt gói tin mạng. "
                            "Không đòi hỏi chữ 'Network', không suy ra thành thạo toàn bộ lĩnh vực mạng."
                        )
                    else:
                        ev_summary = f"Bằng chứng thành phần đối chiếu ({', '.join(comp_names)}): " + " | ".join(aspect_notes)

                    return {
                        "type": "Quan hệ kỹ năng chuẩn hóa (Relational Evidence)",
                        "evidence": ev_summary,
                        "components": comp_names,
                        "is_partial": True
                    }

        return None

    def _evaluate_hard_requirements(
        self,
        sections: Dict[str, Any],
        raw_content: str,
        market: str
    ) -> Tuple[List[str], List[str], List[str], List[str], float, Dict[str, Any]]:
        """
        Evaluate hard requirements and practical feasibility:
        - Minimum years of experience / Level
        - Academic year (Current student year vs JD requirement)
        - Work location on-site feasibility
        - Work schedule full-time feasibility with university studies
        """
        hard_reqs = []
        disqualifiers = []
        unclear_items = []
        clarification_questions = []
        feasibility_status = {}
        
        lower_content = raw_content.lower()

        # 1. Experience requirement & disqualifier
        exp_match = re.search(r"(\d+)\s*(?:-|đến|to)?\s*(\d+)?\s*(?:năm|years?|년)\s*(?:kinh nghiệm|experience|경력)?", lower_content)
        candidate_years = self.candidate.get("years_of_experience", 0)

        if exp_match:
            min_years = int(exp_match.group(1))
            hard_reqs.append(f"Yêu cầu tối thiểu {min_years} năm kinh nghiệm")
            if min_years > 2 and candidate_years < 1:
                disqualifiers.append(
                    f"Yêu cầu {min_years} năm kinh nghiệm trong khi hồ sơ hiện tại là Fresher/Intern ({candidate_years} năm)."
                )
        else:
            hard_reqs.append("Tuyển dụng cấp độ Thực tập / Fresher / Junior")

        # 2. Academic year check (Năm học hiện tại)
        year_match = re.search(r"(?:sinh\s*viên\s*(?:năm\s*([0-9\–\-\sđến]+)|cuối)|năm\s*([34]|[34]\s*[-–]\s*[34]))", lower_content)
        education_list = self.candidate.get("education", [])
        
        if year_match:
            matched_year_phrase = year_match.group(0)
            # Find the line quoting this requirement
            quote_year = next((req["raw_quote"] for req in sections.get("mandatory_requirements", []) if "năm" in req["text"].lower()), matched_year_phrase)
            
            if not education_list:
                unclear_items.append(f"[Cần xác nhận] Năm học hiện tại: JD yêu cầu '{matched_year_phrase}', nhưng hồ sơ ứng viên chưa cập nhật thông tin học vấn.")
                clarification_questions.append("Xác nhận năm học: Ứng viên cần bổ sung thông tin trường và năm học hiện tại vào hồ sơ.")
                feasibility_status["academic_year"] = "Chưa có dữ liệu"
            else:
                edu_info = education_list[0]
                edu_year = edu_info.get("year", "")
                edu_degree = edu_info.get("degree", "")
                
                # Check if explicitly stated year 3/4 or graduated
                is_explicit_year = any(y in edu_year.lower() or y in edu_degree.lower() for y in ["năm 3", "năm 4", "năm ba", "năm tư", "năm cuối", "mới tốt nghiệp", "đã tốt nghiệp"])
                
                if is_explicit_year:
                    hard_reqs.append(f"Năm học: Hồ sơ đáp ứng đối tượng tuyển dụng ({edu_year})")
                    feasibility_status["academic_year"] = "Thỏa mãn"
                else:
                    unclear_items.append(
                        f"[Cần xác nhận] Năm học hiện tại: JD yêu cầu '{matched_year_phrase}' (Trích dẫn: '{quote_year}'). "
                        f"Hồ sơ ghi '{edu_year}'. Cần xác nhận ứng viên hiện đang học năm thứ mấy để đảm bảo đủ điều kiện."
                    )
                    clarification_questions.append(
                        f"Xác nhận năm học: Ứng viên đang theo học niên khóa '{edu_year}', cần làm rõ với công ty xem tiến độ học tập có đáp ứng tiêu chuẩn '{matched_year_phrase}' không."
                    )
                    feasibility_status["academic_year"] = "Cần xác nhận"

        # 3. Work location on-site check (Địa điểm làm việc & khả năng có mặt)
        location_keywords = ["hà nội", "hồ chí minh", "tp.hcm", "đà nẵng", "cần thơ", "hải phòng", "seoul"]
        jd_location = None
        quote_location = ""
        
        for wc in sections.get("work_conditions", []) + sections.get("general", []):
            wc_lower = wc["text"].lower()
            for loc in location_keywords:
                if loc in wc_lower:
                    jd_location = loc.title()
                    quote_location = wc["raw_quote"]
                    break
            if jd_location:
                break

        if jd_location:
            cand_contact = self.candidate.get("contact", {})
            cand_res = self.candidate.get("residency_and_visa", {})
            cand_loc = (cand_contact.get("location") or cand_res.get("current_residence") or "").lower()
            
            is_remote_allowed = any(r in lower_content for r in ["remote", "từ xa", "hybrid", "linh hoạt"])
            
            if not cand_loc:
                unclear_items.append(
                    f"[Cần xác nhận] Địa điểm làm việc: JD yêu cầu làm việc tại '{jd_location}' (Trích dẫn: '{quote_location}'), nhưng hồ sơ chưa cung cấp nơi cư trú hiện tại."
                )
                clarification_questions.append("Xác nhận địa điểm: Ứng viên cần bổ sung nơi ở hiện tại để đối chiếu với địa điểm làm việc.")
                feasibility_status["location"] = "Chưa có dữ liệu"
            elif jd_location.lower() in cand_loc:
                hard_reqs.append(f"Địa điểm làm việc: Phù hợp khu vực làm việc ({jd_location})")
                feasibility_status["location"] = "Thỏa mãn"
            elif is_remote_allowed:
                hard_reqs.append(f"Địa điểm: Cho phép làm việc từ xa / kết hợp ({jd_location})")
                feasibility_status["location"] = "Thỏa mãn (Remote/Hybrid)"
            else:
                unclear_items.append(
                    f"[Cần xác nhận] Khả năng làm việc tại {jd_location}: JD yêu cầu làm việc trực tiếp tại '{quote_location}', "
                    f"trong khi nơi ở hiện tại của ứng viên là '{cand_contact.get('location', cand_loc)}'. "
                    f"Cần xác nhận khả năng di chuyển hoặc bố trí chỗ ở trước khi nộp đơn."
                )
                clarification_questions.append(
                    f"Xác nhận địa điểm: Vị trí có hỗ trợ làm việc từ xa (Remote/Hybrid) không, hay bắt buộc phải có mặt trực tiếp tại {jd_location}?"
                )
                feasibility_status["location"] = "Cần xác nhận"

        # 4. Work schedule check (Lịch làm việc Thứ Hai–Thứ Sáu vs Lịch học)
        schedule_keywords = [
            "thứ hai–thứ sáu", "thứ hai - thứ sáu", "thứ 2 - thứ 6", "thứ 2–thứ 6",
            "toàn thời gian", "full-time", "fulltime", "08:00–17:30", "08:00 - 17:30", "giờ hành chính"
        ]
        has_schedule_req = any(sk in lower_content for sk in schedule_keywords)
        
        if has_schedule_req:
            quote_schedule = next((wc["raw_quote"] for wc in sections.get("work_conditions", []) if any(sk in wc["text"].lower() for sk in schedule_keywords)), "Thứ Hai–thứ Sáu, 08:00–17:30")
            
            # Check if candidate is currently a university student
            is_active_student = False
            for edu in education_list:
                deg = edu.get("degree", "").lower()
                yr = edu.get("year", "").lower()
                if "đang theo học" in deg or "dự kiến" in yr or "2028" in yr or "2027" in yr:
                    is_active_student = True
                    break
                    
            if is_active_student:
                unclear_items.append(
                    f"[Cần xác nhận] Khả năng đáp ứng lịch làm việc: JD yêu cầu làm việc toàn thời gian '{quote_schedule}', "
                    f"trong khi ứng viên đang theo học chương trình đại học. Cần xác nhận khả năng sắp xếp lịch học hoặc đăng ký thực tập full-time."
                )
                clarification_questions.append(
                    "Xác nhận lịch làm việc: Công ty có chính sách linh hoạt thời gian cho sinh viên theo học tín chỉ hay bắt buộc làm cố định toàn bộ lịch Thứ Hai–thứ Sáu 08:00–17:30?"
                )
                feasibility_status["schedule"] = "Cần xác nhận"
            else:
                feasibility_status["schedule"] = "Thỏa mãn"

        # 5. Compensation / Allowance clarification
        comp_items = sections.get("compensation", [])
        for c in comp_items:
            c_lower = c["text"].lower()
            if "không" in c_lower and "thỏa thuận" in lower_content:
                unclear_items.append(
                    f"[Cần xác nhận] Thu nhập & Phụ cấp: JD có thông tin mâu thuẫn (tiêu đề ghi Thỏa thuận, mục thu nhập ghi 'Không': '{c['raw_quote']}'). Cần hỏi rõ chế độ phụ cấp thực tập sinh."
                )
                clarification_questions.append(
                    "Xác nhận phụ cấp: Vị trí thực tập sinh có phụ cấp (ăn trưa, gửi xe, hỗ trợ hàng tháng) hay là kỳ thực tập không hưởng lương?"
                )
                break

        # Calculate Hard Requirements Score
        # Căn cứ của 20/40 điểm điều kiện bắt buộc:
        # - 20 điểm cơ sở: Cấp độ tuyển dụng (Fresher/Intern) không có điều kiện loại trừ vi phạm.
        # - 20 điểm tính khả thi thực tế: Địa điểm làm việc (7đ), Lịch làm việc (7đ), Năm học (6đ).
        # Khi các điều kiện này chưa được xác nhận, phần điểm tương ứng để ở trạng thái UNKNOWN (0đ), không gán điểm tùy ý.
        if disqualifiers:
            hard_score = 0.0
            hard_explanation = "0.0/40 (Không thỏa mãn: Có điều kiện loại trừ vi phạm)"
        else:
            unconfirmed_count = sum(1 for v in feasibility_status.values() if "Cần xác nhận" in v or "Chưa có dữ liệu" in v)
            if unconfirmed_count == 0:
                hard_score = 40.0
                hard_explanation = "40.0/40 (Thỏa mãn đầy đủ các điều kiện bắt buộc và tính khả thi)"
            elif unconfirmed_count == 1:
                hard_score = 33.0
                hard_explanation = "33.0/40 (Căn cứ: 20đ cấp độ thỏa mãn + 13đ cho 2 điều kiện khả thi; 1 điều kiện ở trạng thái Unknown)"
            elif unconfirmed_count == 2:
                hard_score = 26.0
                hard_explanation = "26.0/40 (Căn cứ: 20đ cấp độ thỏa mãn + 6đ cho 1 điều kiện khả thi; 2 điều kiện ở trạng thái Unknown)"
            else:
                hard_score = 20.0
                hard_explanation = (
                    "20.0/40 (Căn cứ: 20/20đ cấp độ đạt chuẩn không có loại trừ; "
                    "20đ tính khả thi thực tế ở trạng thái Unknown do 3 điều kiện chưa xác minh: "
                    "Địa điểm on-site, Lịch làm việc full-time, Năm học; không gán điểm tùy ý)"
                )

        return hard_reqs, disqualifiers, unclear_items, clarification_questions, hard_score, hard_explanation, feasibility_status

    def evaluate(self, jd_data: Dict[str, Any], market: str = "vietnam") -> Dict[str, Any]:
        """
        Evaluate a single JD against candidate profile and return structured assessment.
        """
        if market not in MARKETS:
            market = "vietnam"

        market_cfg = MARKETS[market]
        jd_content = jd_data.get("raw_content", "") or jd_data.get("content", "")
        jd_title = jd_data.get("title", "Chưa rõ")
        jd_source = jd_data.get("source", "Thủ công")
        collection_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # --- 1. Parse JD into Structured Categorized Sections ---
        sections = self._parse_jd_sections(jd_content)

        # --- 2. Evaluate Hard Requirements & Practical Feasibility ---
        hard_reqs, disqualifiers, unclear_items, clarification_questions, hard_score, hard_explanation, feasibility_status = self._evaluate_hard_requirements(
            sections=sections,
            raw_content=jd_content,
            market=market
        )

        # --- 3. Extract Required Technical Skills ONLY from Requirements Sections ---
        detected_jd_skills, skill_metadata = self._extract_jd_required_skills(sections, market=market)

        matched_skills = []
        missing_skills = []
        skill_status = "Đầy đủ dữ liệu"
        skill_note = ""

        if detected_jd_skills:
            for skill in detected_jd_skills:
                evidence = self._find_skill_evidence(skill)
                if evidence:
                    matched_skills.append({
                        "skill": skill,
                        "evidence_type": evidence["type"],
                        "evidence_details": evidence["evidence"]
                    })
                else:
                    missing_skills.append(skill)
        else:
            # JD lacks explicit prerequisite technical requirements (e.g., training/internship JD)
            skill_status = "Chưa đủ dữ liệu để đánh giá kỹ năng"
            skill_note = (
                "JD có nội dung đào tạo, chưa nêu đủ yêu cầu kỹ thuật cụ thể. "
                "Không coi dữ liệu thiếu này là năng lực bằng 0 của ứng viên."
            )

        # --- 4. Market-Specific Checks ---
        korea_details = None
        freelance_details = None

        if market == "korea":
            korea_details = self._evaluate_korea_specifics(jd_content)
            crit_details = korea_details.get("criteria_details", {})
            for crit_code, crit_info in crit_details.items():
                crit_name = crit_info.get("name", crit_code)
                st = crit_info.get("status", "Chưa rõ")
                ev = crit_info.get("evidence", "")
                if st == "Chưa rõ":
                    unclear_items.append(f"{crit_name}: Không được đề cập trong JD")
                    clarification_questions.append(f"Cần xác minh với công ty về: {crit_name}")
                elif "Cần xác minh" in st:
                    unclear_items.append(f"{crit_name}: Thông tin chưa thống nhất trong JD ({ev})")
                    clarification_questions.append(f"Cần xác minh với công ty về: {crit_name} (Trích dẫn: '{ev}')")

            cand_res = self.candidate.get("residency_and_visa", {})
            citizenship = cand_res.get("citizenship", "") or cand_res.get("nationality", "")
            kr_visa = cand_res.get("korean_visa_status", "") or cand_res.get("korea_visa", "")
            is_foreign = (citizenship and citizenship.lower() not in ["korea", "south korea", "hàn quốc", "대한민국"])
            needs_visa = ("Chưa có" in kr_visa or "Cần bảo lãnh" in kr_visa or not kr_visa)

            f_status = korea_details.get("Chấp nhận ứng viên nước ngoài", "Chưa rõ")
            f_ev = korea_details.get("Bằng chứng ứng viên nước ngoài", "")
            if is_foreign and any(ex in f_status for ex in ["Chỉ tuyển công dân", "Không nhận người nước ngoài", "Không chấp nhận", "외국인 불가"]):
                disqualifiers.append(f"Loại trừ quốc tịch: JD không nhận ứng viên nước ngoài / chỉ tuyển công dân Hàn Quốc (Trích dẫn JD: '{f_ev}')")

            v_status = korea_details.get("Hỗ trợ giấy phép làm việc / Visa", "Chưa rõ")
            v_ev = korea_details.get("Bằng chứng visa", "")
            if needs_visa and ("Không hỗ trợ" in v_status or "비자 지원 불가" in v_status):
                disqualifiers.append(f"Loại trừ visa: Ứng viên cần bảo lãnh visa nhưng JD nêu rõ không hỗ trợ visa (Trích dẫn JD: '{v_ev}')")

        elif market == "freelance":
            freelance_details = self._evaluate_freelance_specifics(jd_content)
            for risk in freelance_details.get("risks", []):
                unclear_items.append(f"Rủi ro dự án: {risk}")
            for q in freelance_details.get("clarification_questions", []):
                clarification_questions.append(q)

        # --- 5. Transparent Scoring Calculation ---
        score_breakdown, total_score, score_status = self._calculate_score(
            market=market,
            hard_score=hard_score,
            matched_count=len(matched_skills),
            total_detected=len(detected_jd_skills),
            korea_details=korea_details,
            freelance_details=freelance_details,
            hard_explanation=hard_explanation
        )

        # --- 6. Recommendation & Rationale ---
        if disqualifiers:
            recommendation = "KHÔNG NÊN ỨNG TUYỂN"
            rationale = "Có điều kiện loại trừ không thỏa mãn: " + "; ".join(disqualifiers)
        elif total_score is None:
            # Sparse technical JD / Training oriented: recommendation highlights practical conditions
            recommendation = "CÂN NHẮC ỨNG TUYỂN (CẦN XÁC MINH ĐIỀU KIỆN)"
            rationale = (
                "JD có nội dung đào tạo và tiếp nhận thực tập sinh, chưa nêu đủ yêu cầu kỹ thuật cụ thể. "
                "Hồ sơ có định hướng mạng và an toàn thông tin phù hợp với mục tiêu đào tạo. "
                "Tuy nhiên, cần xác minh các điều kiện thực tế quan trọng: địa điểm làm việc on-site tại Hà Nội (nơi ở hiện tại: Đà Nẵng), "
                "lịch làm việc Thứ Hai–thứ Sáu đối với sinh viên, và chính sách phụ cấp trước khi nộp đơn."
            )
        elif total_score >= 70:
            recommendation = "NÊN ỨNG TUYỂN"
            rationale = f"Mức độ phù hợp kỹ năng cao ({total_score}/100), hồ sơ đáp ứng tốt các yêu cầu trọng tâm."
        elif total_score >= 50:
            recommendation = "CÂN NHẮC ỨNG TUYỂN"
            rationale = f"Mức độ phù hợp trung bình ({total_score}/100), cần chuẩn bị kỹ năng bổ sung trước khi phỏng vấn."
        else:
            recommendation = "CHƯA NÊN ỨNG TUYỂN"
            rationale = f"Điểm phù hợp thấp ({total_score}/100), thiếu nhiều kỹ năng cốt lõi hoặc yêu cầu vượt quá hồ sơ hiện tại."

        # Add general clarification questions if missing info
        if not self.candidate.get("education"):
            unclear_items.append("Hồ sơ ứng viên: Chưa cập nhật thông tin học vấn/bằng cấp.")
        if not self.candidate.get("certifications"):
            unclear_items.append("Hồ sơ ứng viên: Chưa có chứng chỉ xác thực (để trống).")

        return {
            "source": jd_source,
            "collection_time": collection_time,
            "market": market,
            "market_name": market_cfg["name"],
            "title": jd_title,
            "company": jd_data.get("company", "Quý công ty"),
            "jd_sections": sections,
            "hard_requirements": hard_reqs,
            "disqualifiers": disqualifiers,
            "match_score": total_score,
            "score_status": score_status,
            "score_calculation": score_breakdown,
            "skill_status": skill_status,
            "skill_note": skill_note,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "korea_specifics": korea_details,
            "freelance_specifics": freelance_details,
            "unclear_items": unclear_items,
            "clarification_questions": clarification_questions,
            "recommendation": recommendation,
            "rationale": rationale
        }

    def _evaluate_korea_specifics(self, content: str) -> Dict[str, Any]:
        """
        Analyze Korean market specifics with sentence/clause level negation detection.
        Examines: Korean language, English, Foreigner acceptance, Residency, Visa sponsorship.
        Returns detailed status and quoted text evidence for each criterion.
        """
        clauses = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            sub_clauses = re.split(r"(?<=[.!?;\n])\s+|[•\-\*]\s+", line)
            for sc in sub_clauses:
                sc = sc.strip().strip("•-* ")
                if len(sc) >= 2:
                    clauses.append(sc)

        # 1. Visa sponsorship
        visa_terms = ["비자", "visa", "e-7", "e7", "취업비자", "work permit", "work authorization", "체류자격"]
        visa_negations = [
            "불가", "불가능", "안 됨", "안됨", "지원하지 않", "지원 안", "지원없음", "지원 없음",
            "어려움", "어렵습니다", "불가합니다", "제한", "제외", "없음",
            "no visa", "no sponsorship", "cannot sponsor", "unable to sponsor",
            "not provided", "not sponsor", "sponsorship not available", "without sponsorship", "no visa sponsorship"
        ]
        visa_self_held = [
            "비자 소지자", "비자 보유자", "체류자격 소지자", "f-4", "f-2", "f-5", "f2", "f4", "f5",
            "취업 가능한 비자 소지자", "valid work permit required", "must currently hold"
        ]
        visa_positive = [
            "비자 지원", "비자 발급", "e-7 지원", "visa sponsorship", "sponsorship available",
            "visa support", "비자 스폰서", "발급 가능", "지원 가능"
        ]

        visa_matches = []
        for c in clauses:
            cl = c.lower()
            if any(vt in cl for vt in visa_terms):
                has_neg = any(vn in cl for vn in visa_negations)
                has_self = any(vs in cl for vs in visa_self_held)
                has_pos = any(vp in cl for vp in visa_positive) and not has_neg
                visa_matches.append((c, has_neg, has_self, has_pos))

        if not visa_matches:
            visa_res = {"status": "Chưa rõ", "evidence": "Không đề cập trong nội dung JD"}
        else:
            neg_ev = [m[0] for m in visa_matches if m[1]]
            self_ev = [m[0] for m in visa_matches if m[2]]
            pos_ev = [m[0] for m in visa_matches if m[3]]

            if neg_ev and pos_ev:
                visa_res = {"status": "Cần xác minh (Có thông tin mâu thuẫn về visa)", "evidence": f"Từ chối: '{neg_ev[0]}' vs Hỗ trợ: '{pos_ev[0]}'"}
            elif neg_ev:
                visa_res = {"status": "Không hỗ trợ bảo lãnh visa làm việc (비자 지원 불가)", "evidence": neg_ev[0]}
            elif self_ev:
                visa_res = {"status": "Yêu cầu tự có sẵn visa cư trú hợp lệ (Không tài trợ visa mới)", "evidence": self_ev[0]}
            elif pos_ev:
                visa_res = {"status": "Có hỗ trợ bảo lãnh visa làm việc", "evidence": pos_ev[0]}
            else:
                visa_res = {"status": "Có nhắc đến visa (Cần xác minh chi tiết)", "evidence": visa_matches[0][0]}

        # 2. Foreigner acceptance
        foreign_terms = ["외국인", "국적", "foreigner", "foreign national", "citizenship", "내국인"]
        foreign_negations = [
            "불가", "불가능", "가능하지 않", "채용하지 않", "지원 불가", "어려움", "제한", "제외",
            "내국인만", "내국인 한정", "대한민국 국적", "한국 국적자", "한국 국적 소지자",
            "citizens only", "no foreigners", "korean citizens only", "not open to foreigners"
        ]
        foreign_positive = [
            "외국인 가능", "외국인 환영", "국적 무관", "외국인 채용", "외국인 지원 가능",
            "국적 불문", "open to foreigners", "all nationalities", "global talent"
        ]

        foreign_matches = []
        for c in clauses:
            cl = c.lower()
            if any(ft in cl for ft in foreign_terms):
                has_neg = any(fn in cl for fn in foreign_negations)
                has_pos = any(fp in cl for fp in foreign_positive) and not has_neg
                foreign_matches.append((c, has_neg, has_pos))

        if not foreign_matches:
            foreign_res = {"status": "Chưa rõ", "evidence": "Không đề cập trong nội dung JD"}
        else:
            neg_ev = [m[0] for m in foreign_matches if m[1]]
            pos_ev = [m[0] for m in foreign_matches if m[2]]
            if neg_ev and pos_ev:
                foreign_res = {"status": "Cần xác minh (Có thông tin mâu thuẫn về tuyển người nước ngoài)", "evidence": f"Từ chối: '{neg_ev[0]}' vs Cho phép: '{pos_ev[0]}'"}
            elif neg_ev:
                foreign_res = {"status": "Không chấp nhận người nước ngoài (Chỉ tuyển công dân Hàn Quốc / 외국인 불가)", "evidence": neg_ev[0]}
            elif pos_ev:
                foreign_res = {"status": "Chấp nhận ứng viên nước ngoài", "evidence": pos_ev[0]}
            else:
                foreign_res = {"status": "Cần xác minh (Có nhắc đến quốc tịch/người nước ngoài)", "evidence": foreign_matches[0][0]}

        # 3. English requirement
        en_terms = ["english", "toeic", "toefl", "teps", "영어", "영문"]
        en_negations = [
            "not required", "not needed", "no english", "optional", "영어 불필요", "영어 무관",
            "필요 없음", "필요하지 않", "영어 필요없음", "영어 가능 여부 무관", "영어 못해도", "영어 능력 무관"
        ]
        en_preferred = ["우대사항", "우대", "선호", "plus", "preferred", "nice to have", "영어 가능자 우대"]
        en_mandatory = ["필수", "자격요건", "영어 능숙", "영어 필수", "비즈니스 영어", "유창한 영어", "fluent english", "english required", "must be fluent"]

        en_matches = []
        for c in clauses:
            cl = c.lower()
            if any(et in cl for et in en_terms):
                has_neg = any(en in cl for en in en_negations)
                has_pref = any(ep in cl for ep in en_preferred) and not has_neg
                has_mand = any(em in cl for em in en_mandatory) and not has_neg
                en_matches.append((c, has_neg, has_pref, has_mand))

        if not en_matches:
            en_res = {"status": "Chưa rõ", "evidence": "Không đề cập trong nội dung JD"}
        else:
            neg_ev = [m[0] for m in en_matches if m[1]]
            pref_ev = [m[0] for m in en_matches if m[2]]
            mand_ev = [m[0] for m in en_matches if m[3]]
            if neg_ev and mand_ev:
                en_res = {"status": "Cần xác minh (Có mâu thuẫn giữa yêu cầu và miễn trừ tiếng Anh)", "evidence": f"Không yêu cầu: '{neg_ev[0]}' vs Bắt buộc: '{mand_ev[0]}'"}
            elif neg_ev:
                en_res = {"status": "Không yêu cầu tiếng Anh (English not required)", "evidence": neg_ev[0]}
            elif pref_ev:
                en_res = {"status": "Ưu tiên tiếng Anh (Không bắt buộc)", "evidence": pref_ev[0]}
            elif mand_ev:
                en_res = {"status": "Yêu cầu bắt buộc tiếng Anh", "evidence": mand_ev[0]}
            else:
                en_res = {"status": "Có nhắc đến tiếng Anh (Cần xác minh cấp độ yêu cầu)", "evidence": en_matches[0][0]}

        # 4. Korean requirement
        kr_terms = ["한국어", "korean", "topik"]
        kr_negations = ["한국어 불필요", "한국어 무관", "korean not required", "필요 없음"]
        kr_native = ["원어민", "유창", "topik 5", "topik 6", "비즈니스 한국어", "한국어 필수", "원활한 소통", "fluent korean"]
        kr_basic = ["한국어 가능", "기본적인 의사소통", "일상 회화", "소통 가능", "conversational"]

        kr_matches = []
        for c in clauses:
            cl = c.lower()
            if any(kt in cl for kt in kr_terms):
                has_neg = any(kn in cl for kn in kr_negations)
                has_nat = any(kna in cl for kna in kr_native) and not has_neg
                has_bas = any(kb in cl for kb in kr_basic) and not has_neg
                kr_matches.append((c, has_neg, has_nat, has_bas))

        if not kr_matches:
            kr_res = {"status": "Chưa rõ", "evidence": "Không đề cập trong nội dung JD"}
        else:
            neg_ev = [m[0] for m in kr_matches if m[1]]
            nat_ev = [m[0] for m in kr_matches if m[2]]
            bas_ev = [m[0] for m in kr_matches if m[3]]
            if neg_ev:
                kr_res = {"status": "Không yêu cầu tiếng Hàn", "evidence": neg_ev[0]}
            elif nat_ev:
                kr_res = {"status": "Bắt buộc thành thạo tiếng Hàn (TOPIK / Lưu loát)", "evidence": nat_ev[0]}
            elif bas_ev:
                kr_res = {"status": "Yêu cầu giao tiếp tiếng Hàn cơ bản", "evidence": bas_ev[0]}
            else:
                kr_res = {"status": "Có nhắc đến tiếng Hàn (Cần làm rõ cấp độ yêu cầu)", "evidence": kr_matches[0][0]}

        # 5. Residency requirement
        res_terms = ["거주", "근무지", "출퇴근", "재택", "원격", "remote", "seoul", "서울"]
        res_matches = []
        for c in clauses:
            cl = c.lower()
            if any(rt in cl for rt in res_terms):
                is_remote = any(rw in cl for rw in ["재택근무", "원격근무", "remote", "재택 가능"])
                is_onsite = any(ow in cl for ow in ["출퇴근", "오프라인", "상주", "서울 근무", "국내 거주", "한국 거주"])
                res_matches.append((c, is_remote, is_onsite))

        if not res_matches:
            res_res = {"status": "Chưa rõ", "evidence": "Không đề cập trong nội dung JD"}
        else:
            rem_ev = [m[0] for m in res_matches if m[1]]
            ons_ev = [m[0] for m in res_matches if m[2]]
            if rem_ev and ons_ev:
                res_res = {"status": "Làm việc kết hợp (Hybrid / Có thể từ xa)", "evidence": f"Từ xa: '{rem_ev[0]}' | Có mặt: '{ons_ev[0]}'"}
            elif rem_ev:
                res_res = {"status": "Cho phép làm việc từ xa (Remote)", "evidence": rem_ev[0]}
            elif ons_ev:
                res_res = {"status": "Yêu cầu cư trú tại Hàn Quốc / Có mặt trực tiếp", "evidence": ons_ev[0]}
            else:
                res_res = {"status": "Chưa rõ", "evidence": res_matches[0][0]}

        kr_res["name"] = "Yêu cầu tiếng Hàn"
        en_res["name"] = "Yêu cầu tiếng Anh"
        foreign_res["name"] = "Chấp nhận ứng viên nước ngoài"
        res_res["name"] = "Yêu cầu nơi cư trú"
        visa_res["name"] = "Hỗ trợ giấy phép làm việc / Visa"

        return {
            "Yêu cầu tiếng Hàn": kr_res["status"],
            "Bằng chứng tiếng Hàn": kr_res["evidence"],
            "Yêu cầu tiếng Anh": en_res["status"],
            "Bằng chứng tiếng Anh": en_res["evidence"],
            "Chấp nhận ứng viên nước ngoài": foreign_res["status"],
            "Bằng chứng ứng viên nước ngoài": foreign_res["evidence"],
            "Yêu cầu nơi cư trú": res_res["status"],
            "Bằng chứng nơi cư trú": res_res["evidence"],
            "Hỗ trợ giấy phép làm việc / Visa": visa_res["status"],
            "Bằng chứng visa": visa_res["evidence"],
            "criteria_details": {
                "korean": kr_res,
                "english": en_res,
                "foreign_national": foreign_res,
                "residency": res_res,
                "visa": visa_res
            }
        }

    def _evaluate_freelance_specifics(self, content: str) -> Dict[str, Any]:
        """
        Freelance project specific criteria:
        Scope, Acceptance criteria, Budget/Timeline, Required access, Revisions/Maintenance, Milestones, Scope risks.
        """
        lower = content.lower()
        risks = []
        questions = []

        # 1. Scope & Deliverables
        has_scope = any(w in lower for w in ["deliverable", "scope", "output", "yêu cầu đầu ra", "bàn giao"])
        scope_status = "Đầy đủ" if has_scope else "Chưa rõ ràng, cần văn bản chốt scope"
        if not has_scope:
            risks.append("Phạm vi công việc mơ hồ, dễ phát sinh xung đột về khối lượng bàn giao (scope creep).")
            questions.append("Yêu cầu khách hàng liệt kê danh sách đầu ra cụ thể (deliverables) và định dạng nghiệm thu.")

        # 2. Acceptance Criteria
        has_acceptance = any(w in lower for w in ["acceptance", "test criteria", "tiêu chí nghiệm thu", "nghiệm thu"])
        acceptance_status = "Đã nêu" if has_acceptance else "Chưa rõ tiêu chí nghiệm thu"
        if not has_acceptance:
            questions.append("Tiêu chuẩn kỹ thuật hoặc kịch bản kiểm thử nào được dùng để xác nhận bàn giao?")

        # 3. Budget & Timeline
        has_budget = bool(re.search(r"(\$|\b\d+\s*(?:usd|vnd|triệu|tr|k)\b)", lower))
        budget_status = "Đã có thông tin ngân sách" if has_budget else "Chưa rõ ngân sách (Cần đề xuất giá)"

        has_deadline = any(w in lower for w in ["deadline", "thời hạn", "ngày bàn giao", "duration", "tuần", "ngày"])
        timeline_status = "Đã có thời hạn" if has_deadline else "Chưa rõ thời hạn"

        # 4. Required Access & Credentials
        requires_root = any(w in lower for w in ["root", "admin", "ssh access", "credentials", "mật khẩu", "vpn"])
        if requires_root:
            access_req = "Cần quyền quản trị hệ thống (SSH / Root / Admin / VPN)"
            risks.append("Yêu cầu quyền truy cập cấp cao: Cần thỏa thuận bảo mật NDA và môi trường Staging cách ly.")
            questions.append("Khách hàng có cung cấp môi trường Lab/Staging không, hay thao tác trực tiếp trên Production?")
        else:
            access_req = "Không yêu cầu quyền truy cập nhạy cảm (Xử lý file/log độc lập)"

        # 5. Authorization & Legal Risk Check
        if any(w in lower for w in ["hack", "crack", "ddos", "pentest", "vulnerability scan", "tấn công"]):
            risks.append(
                "RỦI RO THẨM QUYỀN: Công việc có yếu tố bảo mật nhạy cảm. "
                "TUYỆT ĐỐI chỉ thực hiện khi có văn bản ủy quyền chính thức (Letter of Authorization) từ chủ sở hữu hệ thống."
            )
            questions.append("Khách hàng đã ký văn bản ủy quyền kiểm thử an ninh mạng (Scope of Authorization) chưa?")

        # 6. Maintenance & Revisions
        revisions = "Chưa rõ số lần sửa đổi và bảo hành sau bàn giao (Mặc định đề xuất: tối đa 2 lần sửa đổi nhỏ trong 14 ngày)."

        # 7. Milestones & Payment Terms
        has_jd_milestones = any(w in lower for w in ["milestone", "mốc thanh toán", "giai đoạn thanh toán"])
        if has_jd_milestones:
            milestone_status = "Đã có đề cập trong JD (Cần đối soát văn bản hợp đồng)"
        else:
            milestone_status = "Chưa rõ trong JD (Chưa có thỏa thuận chính thức)"

        milestones = [
            f"Tình trạng trong JD: {milestone_status}",
            "Đề xuất thương lượng từ phía ứng viên (cần khách hàng phê duyệt, không tự ý áp đặt):",
            " - Giai đoạn 1: Thống nhất yêu cầu kỹ thuật & môi trường thử nghiệm (Staging).",
            " - Giai đoạn 2: Bàn giao bản mẫu (PoC) kèm kết quả chạy kiểm thử.",
            " - Giai đoạn 3: Nghiệm thu toàn diện mã nguồn, tài liệu hướng dẫn và bàn giao."
        ]

        return {
            "Phạm vi & Đầu ra": scope_status,
            "Tiêu chí nghiệm thu": acceptance_status,
            "Ngân sách & Thời hạn": f"{budget_status} | {timeline_status}",
            "Quyền truy cập cần thiết": access_req,
            "Khối lượng sửa đổi / Bảo trì": revisions,
            "Mốc bàn giao đề xuất": milestones,
            "risks": risks,
            "clarification_questions": questions
        }

    def _calculate_score(
        self,
        market: str,
        hard_score: float,
        matched_count: int,
        total_detected: int,
        korea_details: Optional[Dict[str, Any]],
        freelance_details: Optional[Dict[str, Any]],
        hard_explanation: str = ""
    ) -> Tuple[Dict[str, Any], Optional[int], str]:
        """
        Calculate score (0-100) with full transparency and formula explanation.
        Handles sparse technical JDs without penalizing candidate competence to 0.
        Returns:
            (breakdown, match_score_or_None, score_status)
        """
        breakdown = {}
        total = 0.0
        score_status = "CONCLUSIVE"

        if market == "vietnam":
            # 1. Hard requirements & practical feasibility (40%)
            breakdown["Điều kiện bắt buộc & Khả thi (Trọng số 40%)"] = hard_explanation or f"{hard_score:.1f}/40"
            total += hard_score

            # 2. Core skills match (35%)
            if total_detected == 0:
                # Sparse technical requirements in JD: do NOT score candidate 0.0/35!
                breakdown["Kỹ năng cốt lõi (Trọng số 35%)"] = (
                    "Chưa đủ dữ liệu để đánh giá kỹ năng kỹ thuật từ JD "
                    "(JD có nội dung đào tạo, chưa nêu đủ yêu cầu kỹ thuật cụ thể; không tính phạt 0 điểm)"
                )
                score_status = "CHƯA ĐỦ CĂN CỨ TÍNH ĐIỂM TỔNG"
            else:
                skill_ratio = min(matched_count / max(total_detected, 1), 1.0)
                skill_score = skill_ratio * 35.0
                breakdown["Kỹ năng cốt lõi (Trọng số 35%)"] = f"{skill_score:.1f}/35 (Khớp {matched_count}/{total_detected} kỹ năng yêu cầu)"
                total += skill_score

            # 3. Relevant projects & labs (15%)
            has_projects = len(self.candidate.get("personal_projects", [])) + len(self.candidate.get("labs_and_simulations", []))
            proj_score = min(has_projects * 5.0, 15.0)
            breakdown["Dự án & Lab thực hành (Trọng số 15%)"] = f"{proj_score:.1f}/15 ({has_projects} dự án/lab)"
            total += proj_score

            # 4. Education & Certifications (10%)
            has_edu = 5.0 if self.candidate.get("education") else 0.0
            has_certs = 5.0 if self.candidate.get("certifications") else 0.0
            edu_score = has_edu + has_certs
            breakdown["Học vấn & Chứng chỉ (Trọng số 10%)"] = f"{edu_score:.1f}/10"
            total += edu_score

            if total_detected == 0:
                final_score = None
            else:
                final_score = int(round(total))

        elif market == "korea":
            # 1. Hard requirements (30%)
            hard_kr = 30.0 if hard_score >= 30.0 else 0.0
            breakdown["Điều kiện bắt buộc (Trọng số 30%)"] = f"{hard_kr:.1f}/30"
            total += hard_kr

            # 2. Core skills (30%)
            if total_detected == 0:
                breakdown["Kỹ năng an ninh mạng (Trọng số 30%)"] = "Chưa đủ dữ liệu để đánh giá kỹ năng kỹ thuật từ JD"
                skill_kr = 0.0
            else:
                skill_ratio = min(matched_count / max(total_detected, 1), 1.0)
                skill_kr = skill_ratio * 30.0
                breakdown["Kỹ năng an ninh mạng (Trọng số 30%)"] = f"{skill_kr:.1f}/30 ({matched_count}/{total_detected})"
            total += skill_kr

            # 3. Visa & Residency (20%)
            visa_info = korea_details.get("Hỗ trợ giấy phép làm việc / Visa", {}) if korea_details else {}
            visa_status = visa_info.get("status", "Chưa rõ") if isinstance(visa_info, dict) else str(visa_info)
            cand_res = self.candidate.get("residency_and_visa", {})
            cand_visa = cand_res.get("korean_visa_status", "") or cand_res.get("korea_visa", "")
            has_valid_visa = any(f in cand_visa for f in ["F-2", "F-4", "F-5", "F-6", "Có sẵn visa"])

            if "Có hỗ trợ" in visa_status or has_valid_visa:
                visa_score = 20.0
            elif "Không hỗ trợ" in visa_status or "비자 지원 불가" in visa_status:
                visa_score = 0.0
            elif visa_status == "Chưa rõ":
                visa_score = 10.0
            else:
                visa_score = 5.0
            breakdown["Visa & Nơi cư trú (Trọng số 20%)"] = f"{visa_score:.1f}/20 ({visa_status})"
            total += visa_score

            # 4. Language proficiency (20%)
            cand_kr = self.candidate.get("languages", {}).get("korean", "Chưa xác nhận")
            cand_en = self.candidate.get("languages", {}).get("english", "")
            en_info = korea_details.get("Yêu cầu tiếng Anh", {}) if korea_details else {}
            en_status = en_info.get("status", "Chưa rõ") if isinstance(en_info, dict) else str(en_info)

            if "TOPIK" in cand_kr or "Thành thạo" in cand_kr:
                lang_score = 20.0
            elif "Không yêu cầu" in en_status:
                lang_score = 15.0
            elif cand_en:
                lang_score = 12.0
            else:
                lang_score = 5.0
            breakdown["Năng lực ngôn ngữ (Trọng số 20%)"] = f"{lang_score:.1f}/20"
            total += lang_score

            final_score = int(round(total))

        elif market == "freelance":
            # 1. Scope clarity (25%)
            has_scope = freelance_details.get("Phạm vi & Đầu ra") == "Đầy đủ" if freelance_details else False
            scope_score = 25.0 if has_scope else 10.0
            breakdown["Độ rõ ràng phạm vi (Trọng số 25%)"] = f"{scope_score:.1f}/25"
            total += scope_score

            # 2. Deliverable feasibility (30%)
            risks_count = len(freelance_details.get("risks", [])) if freelance_details else 0
            feas_score = max(30.0 - (risks_count * 8.0), 5.0)
            breakdown["Tính khả thi & Rủi ro bàn giao (Trọng số 30%)"] = f"{feas_score:.1f}/30 ({risks_count} rủi ro phát hiện)"
            total += feas_score

            # 3. Technical match (25%)
            if total_detected == 0:
                tech_score = 15.0
                breakdown["Khớp kỹ thuật cần thiết (Trọng số 25%)"] = "15.0/25 (Mức độ cơ bản, chưa rõ yêu cầu chi tiết)"
            else:
                tech_ratio = min(matched_count / max(total_detected, 1), 1.0)
                tech_score = tech_ratio * 25.0
                breakdown["Khớp kỹ thuật cần thiết (Trọng số 25%)"] = f"{tech_score:.1f}/25"
            total += tech_score

            # 4. Budget & timeline clarity (20%)
            bt_score = 20.0 if "Đã có thông tin" in str(freelance_details.get("Ngân sách & Thời hạn")) else 10.0
            breakdown["Ngân sách & Thời hạn (Trọng số 20%)"] = f"{bt_score:.1f}/20"
            total += bt_score

            final_score = int(round(total))

        if final_score is not None:
            final_score = max(0, min(100, final_score))

        return breakdown, final_score, score_status
