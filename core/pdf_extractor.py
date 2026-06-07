"""
PDF Extraction Layer for MPDTE Counselling PDFs
Handles automatic table extraction and data normalization
"""
import pdfplumber
import re
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

BRANCH_MAP = {
    "CSE": "Computer Science and Engineering",
    "CSEIML": "Computer Science and Engineering (Artificial Intelligence and Machine Learning)",
    "CSEAI": "Computer Science and Engineering (Artificial Intelligence)",
    "CSEDS": "Computer Science and Engineering (Data Science)",
    "CSECS": "Computer Science and Engineering (Cyber Security)",
    "CSEIOT": "Computer Science and Engineering (Internet of Things)",
    "CSERC": "Computer Science and Engineering (Robotics and Cloud Computing)",
    "CSEITCS": "Computer Science and Engineering (Internet of Things and Cyber Security)",
    "CSEIL": "Computer Science and Engineering (Emerging Internet and Language)",
    "CSEAIADS": "Computer Science and Engineering (Artificial Intelligence and Data Science)",
    "CSEAIML": "Computer Science and Engineering (Artificial Intelligence and Machine Learning)",
    "CSEBC": "Computer Science and Engineering (Blockchain Technology)",
    "CSBS": "Computer Science and Business Systems",
    "CSD": "Computer Science and Design",
    "CST": "Computer Science and Technology",
    "CMPS": "Computer Science",
    "IT": "Information Technology",
    "CSIT": "Computer Science and Information Technology",
    "ITAIAR": "Information Technology (AI and AR)",
    "AIAIDS": "Artificial Intelligence and Data Science",
    "AIADS": "Artificial Intelligence and Data Science",
    "AIML": "Artificial Intelligence and Machine Learning",
    "AI": "Artificial Intelligence",
    "EC": "Electronics and Communication Engineering",
    "ECACT": "Electronics and Communication Engineering (Advanced Communication Technology)",
    "ECS": "Electronics and Communication Systems",
    "EL": "Electronics Engineering",
    "EE": "Electrical Engineering",
    "ELECT ELEX": "Electronics and Electrical Engineering",
    "EI": "Electronics and Instrumentation Engineering",
    "Electronics and Telecommunications": "Electronics and Telecommunications Engineering",
    "ET": "Electronics and Telecommunication Engineering",
    "EACE": "Electronics and Computer Engineering",
    "EEVDT": "Electrical Engineering (Electric Vehicle and Drone Technology)",
    "EAPE": "Electrical and Power Engineering",
    "CE": "Civil Engineering",
    "CEng": "Civil Engineering",
    "CEWCA": "Civil Engineering (Water and Climate Adaptation)",
    "MECH": "Mechanical Engineering",
    "MAC": "Mechanical and Automation Engineering",
    "MTENG": "Materials and Metallurgical Engineering",
    "INOT": "Industrial Engineering and Operations Technology",
    "IP": "Industrial and Production Engineering",
    "AUTO": "Automobile Engineering",
    "CHEM": "Chemical Engineering",
    "MINING": "Mining Engineering",
    "AGRITECH": "Agricultural Technology Engineering",
    "AGE": "Agricultural Engineering",
    "AG": "Agricultural Engineering",
    "AIR": "Aeronautical and Industrial Engineering",
    "BT": "Bio Technology",
    "BEIL": "Biomedical Engineering and Instrumentation Laboratory",
    "BM": "Biomedical Engineering",
    "FTS": "Fire Technology and Safety Engineering",
    "DS": "Data Science",
    "CYSEC": "Cyber Security",
    "PCT": "Polymer and Chemical Technology",
    "EV": "Electric Vehicle Technology",
    "LG": "Landscape and Garden Engineering",
    "ARE": "Architecture and Real Estate Engineering",
    "AME": "Aeronautical and Mechanical Engineering",
    "NTPC": "National Thermal Power Corporation Sponsored",
}

CITIES = [
    "Indore","Bhopal","Gwalior","Jabalpur","Ujjain","Sagar","Rewa",
    "Satna","Chhindwara","Khargone","Khandwa","Raisen","Vidisha",
    "Betul","Burhanpur","Ratlam","Balaghat","Seoni","Jhabua",
    "Shahdol","Shivpuri","Tekanpur","Obedullaganj","Borawan","Banmore",
    "Nowgong",
]

# MPDTE PDF standard column indices (0-based):
# 0=S.No, 1=InstituteName, 2=InstType, 3=FW, 4=Branch,
# 5=NationalPlayer, 6=OpenRank, 7=CloseRank, 8=Category, 9=Domicile, 10=TotalAllotted

# Known header cell patterns (reversed text too) to skip
SKIP_PATTERNS = [
    r"^directorate",
    r"^bachelor",
    r"^opening closing",
    r"^based on",
    r"^s\.?\s*no",
    r"^\.on",       # reversed S.No
    r"^eman",       # reversed NAME
    r"^epyt",       # reversed TYPE
    r"^hcnarb",     # reversed BRANCH
    r"^reyalp",     # reversed PLAYER
    r"^nommoc",     # reversed COMMON
    r"^yrogetac",   # reversed CATEGORY
    r"^elicimod",   # reversed DOMICILE
    r"^dettolla",   # reversed ALLOTTED
    r"^institute",
    r"^page \d+",
]


def _should_skip_row(row: list) -> bool:
    if not row:
        return True
    first = str(row[0] or "").strip().lower()
    if not first and row[1]:
        first = str(row[1] or "").strip().lower()
    for pat in SKIP_PATTERNS:
        if re.match(pat, first):
            return True
    # Skip if all cells are None/empty
    if all(not str(c or "").strip() for c in row):
        return True
    return False


def _is_data_row(row: list) -> bool:
    """Row must have institute name and at least one rank"""
    if len(row) < 8:
        return False
    institute = str(row[1] or "").strip()
    closing = str(row[7] if len(row) > 7 else "").strip()
    if len(institute) < 6:
        return False
    if not re.search(r"\d{4,}", closing):
        return False
    return True


def get_branch_full_name(code: str) -> str:
    code = str(code).strip()
    if code in BRANCH_MAP:
        return BRANCH_MAP[code]
    for k, v in BRANCH_MAP.items():
        if k.upper() == code.upper():
            return v
    return code


def extract_city(name: str) -> str:
    for city in CITIES:
        if city.lower() in name.lower():
            return city
    m = re.search(r",\s*([A-Za-z]+)\s*\(", name)
    if m:
        return m.group(1).strip()
    return ""


def clean_rank(val) -> int | None:
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace(" ", "")
    if not s:
        return None
    m = re.search(r"\d{4,7}", s)
    if m:
        v = int(m.group())
        if 100 <= v <= 9_999_999:
            return v
    return None


def safe_int(val):
    try:
        s = str(val or "").strip().split(".")[0]
        return int(s) if s.isdigit() else None
    except Exception:
        return None


def make_hash(rec: dict) -> str:
    key = "|".join([
        str(rec.get("institute_name", "")),
        str(rec.get("branch_code", "")),
        str(rec.get("allotted_category", "")),
        str(rec.get("opening_rank", "")),
        str(rec.get("closing_rank", "")),
        str(rec.get("fw", "")),
        str(rec.get("domicile", "")),
    ])
    return hashlib.md5(key.encode()).hexdigest()


def _parse_row(row: list) -> dict | None:
    def cell(idx, default=""):
        try:
            return str(row[idx] or "").strip() if idx < len(row) else default
        except Exception:
            return default

    try:
        institute = cell(1)
        branch_code = cell(4)
        opening_str = cell(6)
        closing_str = cell(7)
        category = cell(8)

        if not institute or len(institute) < 5:
            return None
        for bad in ["DIRECTORATE", "BACHELOR", "BASED ON", "OPENING", "INSTITUTE NAME"]:
            if bad in institute.upper():
                return None
        if not branch_code or branch_code.upper() in ["BRANCH", "HCNARB", "COURSE", ""]:
            return None

        closing_rank = clean_rank(closing_str)
        opening_rank = clean_rank(opening_str)
        if closing_rank is None and opening_rank is None:
            return None

        fw_val = cell(3, "N").strip().upper()
        fw_val = "Y" if fw_val == "Y" else "N"

        # Handle MERIT AFTER 10% WEIGHTAGE in national player column
        national = cell(5)

        return {
            "serial_no": safe_int(cell(0)),
            "institute_name": institute,
            "institute_type": cell(2),
            "fw": fw_val,
            "branch_code": branch_code,
            "branch_full_name": get_branch_full_name(branch_code),
            "national_player": national,
            "opening_rank": opening_rank,
            "closing_rank": closing_rank,
            "allotted_category": category,
            "domicile": cell(9),
            "total_allotted": safe_int(cell(10)),
            "city": extract_city(institute),
        }
    except Exception as e:
        logger.debug(f"Row parse error: {e} | row={row}")
        return None


def _detect_round_year(text: str, filepath: str) -> tuple[str, str]:
    round_info = "Round 1"
    year = "2025"
    t = text.upper()
    if "FIRST ROUND" in t:
        round_info = "First Round"
    elif "SECOND ROUND" in t:
        round_info = "Second Round"
    elif "THIRD ROUND" in t:
        round_info = "Third Round"
    elif "FOURTH ROUND" in t:
        round_info = "Fourth Round"
    elif "UPGRADE" in t:
        round_info = "Upgrade Round"
    m = re.search(r"20(\d{2})", text)
    if m:
        year = m.group(0)
    else:
        m2 = re.search(r"20(\d{2})", Path(filepath).stem)
        if m2:
            year = m2.group(0)
    return round_info, year


def extract_pdf(filepath: str) -> tuple[list[dict], str, str]:
    """Main extraction — returns (records, round_info, year)"""
    records = []
    round_info = "Round 1"
    year = "2025"

    try:
        with pdfplumber.open(filepath) as pdf:
            # Metadata from first page text
            first_text = pdf.pages[0].extract_text() or ""
            round_info, year = _detect_round_year(first_text, filepath)

            seen = set()
            total_raw = 0

            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        total_raw += 1
                        if _should_skip_row(row):
                            continue
                        if not _is_data_row(row):
                            continue
                        rec = _parse_row(row)
                        if rec:
                            h = make_hash(rec)
                            if h not in seen:
                                seen.add(h)
                                rec["hash_key"] = h
                                records.append(rec)

            logger.info(f"Scanned {total_raw} raw rows → {len(records)} unique records")

    except Exception as e:
        logger.error(f"PDF extraction error: {e}", exc_info=True)
        raise

    return records, round_info, year


def extract_round_year(filepath: str) -> tuple[str, str]:
    try:
        with pdfplumber.open(filepath) as pdf:
            text = pdf.pages[0].extract_text() or ""
        return _detect_round_year(text, filepath)
    except Exception:
        return "Round 1", "2025"
