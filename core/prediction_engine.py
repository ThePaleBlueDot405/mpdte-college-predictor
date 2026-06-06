"""
Prediction Engine for MPDTE College Predictor
Handles all admission probability calculations and recommendations
"""
import sqlite3
import logging
from core.database import get_connection

logger = logging.getLogger(__name__)

# ── Category mapping ─────────────────────────────────────────────────────────
CATEGORY_MAP = {
    "General (UR)": ["UR/X/OP", "UR/X/F", "UR/D/OP", "UR/D/F", "UR/S/OP", "UR/S/F", "UR/FF/OP", "UR/NCC/OP"],
    "OBC": ["OBC/X/OP", "OBC/X/F", "OBC/D/OP", "OBC/S/OP", "OBC/S/F"],
    "SC": ["SC/X/OP", "SC/X/F", "SC/D/OP", "SC/S/OP", "SC/S/F"],
    "ST": ["ST/X/OP", "ST/X/F", "ST/D/OP", "ST/S/OP"],
    "EWS": ["EWS", "EWS/X/OP", "EWS/X/F"],
}

DOMICILE_FILTER = {
    "Yes": ["Y", "Yes", "MP"],
    "No": ["N", "No", "AI", ""],
}

# ── Branch groups ─────────────────────────────────────────────────────────────
BRANCH_GROUPS = {
    "Computer Science Related": [
        "Computer Science and Engineering",
        "Computer Science and Engineering (Artificial Intelligence)",
        "Computer Science and Engineering (Artificial Intelligence and Machine Learning)",
        "Computer Science and Engineering (Data Science)",
        "Computer Science and Engineering (Cyber Security)",
        "Computer Science and Engineering (Internet of Things)",
        "Information Technology",
        "Computer Science and Engineering (Artificial Intelligence and Data Science)",
        "Computer Science and Engineering (Internet of Things and Cyber Security)",
        "Computer Science and Engineering (Blockchain Technology)",
        "Computer Science and Business Systems",
        "Computer Science and Design",
        "Computer Science and Technology",
        "Computer Science and Information Technology",
        "Artificial Intelligence and Machine Learning",
        "Artificial Intelligence and Data Science",
        "Artificial Intelligence",
        "Data Science",
        "Cyber Security",
        "Computer Science",
    ],
    "Computer Science + Electronics": [
        "Computer Science and Engineering",
        "Computer Science and Engineering (Artificial Intelligence)",
        "Computer Science and Engineering (Artificial Intelligence and Machine Learning)",
        "Computer Science and Engineering (Data Science)",
        "Computer Science and Engineering (Cyber Security)",
        "Computer Science and Engineering (Internet of Things)",
        "Information Technology",
        "Computer Science and Engineering (Artificial Intelligence and Data Science)",
        "Computer Science and Business Systems",
        "Electronics and Communication Engineering",
        "Electronics and Communication Engineering (Advanced Communication Technology)",
        "Electronics and Instrumentation Engineering",
        "Electronics and Electrical Engineering",
        "Electronics Engineering",
        "Electronics and Telecommunication Engineering",
        "Electronics and Telecommunications Engineering",
    ],
    "Core Engineering": [
        "Mechanical Engineering",
        "Civil Engineering",
        "Electrical Engineering",
        "Electronics and Communication Engineering",
        "Electronics and Instrumentation Engineering",
        "Industrial Engineering and Operations Technology",
        "Industrial and Production Engineering",
        "Automobile Engineering",
        "Chemical Engineering",
        "Materials and Metallurgical Engineering",
    ],
    "All Branches": [],  # Will be filled dynamically
}


def get_category_filters(category: str, domicile: str, fee_waiver: bool) -> list[str]:
    """Build list of matching category strings from DB"""
    base_cats = CATEGORY_MAP.get(category, CATEGORY_MAP["General (UR)"])

    if domicile == "Yes":
        # MP domicile gets both domicile and open seats
        cats = base_cats[:]
    else:
        # Non-domicile (All India) - only open/AI seats
        cats = [c for c in base_cats if "/F" not in c]
        cats += ["UR/X/OP AI", "AI"]

    if fee_waiver:
        cats.append("FW/OP")

    return cats


def calculate_probability(user_rank: int, opening_rank: int, closing_rank: int) -> float:
    """
    Calculate admission probability based on rank comparison.
    Returns probability as 0-100 float.
    """
    if closing_rank is None or closing_rank <= 0:
        return 0.0
    if opening_rank is None:
        opening_rank = closing_rank

    if user_rank <= opening_rank:
        return 99.0
    if user_rank > closing_rank * 1.5:
        return 2.0

    # Within closing rank
    if user_rank <= closing_rank:
        # Scale: the closer to opening rank, higher probability
        range_size = max(closing_rank - opening_rank, 1)
        position = user_rank - opening_rank
        prob = 95.0 - (position / range_size) * 35.0
        return max(60.0, min(99.0, prob))

    # Beyond closing rank
    overshoot_pct = (user_rank - closing_rank) / closing_rank
    if overshoot_pct <= 0.05:
        return 50.0
    elif overshoot_pct <= 0.10:
        return 40.0
    elif overshoot_pct <= 0.20:
        return 30.0
    elif overshoot_pct <= 0.35:
        return 20.0
    elif overshoot_pct <= 0.50:
        return 10.0
    else:
        return 5.0


def get_risk_level(prob: float) -> tuple[str, str]:
    """Returns (risk_label, color_tag)"""
    if prob >= 95:
        return "Almost Guaranteed", "green"
    elif prob >= 80:
        return "Very Safe", "lightgreen"
    elif prob >= 60:
        return "Safe", "yellow"
    elif prob >= 40:
        return "Possible", "orange"
    elif prob >= 20:
        return "Difficult", "red"
    else:
        return "Very Unlikely", "darkred"


def predict_colleges(
    user_rank: int,
    category: str,
    domicile: str,
    fee_waiver: bool,
    selected_branches: list[str],
    dream_pct: float = 10.0,
    safe_pct: float = 25.0,
    very_safe_pct: float = 50.0,
) -> dict:
    """
    Main prediction function.
    Returns dict with dream/safe/very_safe/all results.
    """
    conn = get_connection()
    c = conn.cursor()

    cat_filters = get_category_filters(category, domicile, fee_waiver)

    # Build category placeholders
    placeholders = ",".join(["?" for _ in cat_filters])

    # Build branch filter
    branch_sql = ""
    branch_params = []
    if selected_branches and "All Branches" not in selected_branches:
        bp = ",".join(["?" for _ in selected_branches])
        branch_sql = f"AND branch_full_name IN ({bp})"
        branch_params = selected_branches

    # Base rank window - search within reasonable range
    max_rank = int(user_rank * 1.6)

    sql = f"""
        SELECT institute_name, institute_type, fw, branch_code, branch_full_name,
               opening_rank, closing_rank, allotted_category, domicile,
               total_allotted, round_info, year, city, fee_waiver_available
        FROM counselling_data
        WHERE allotted_category IN ({placeholders})
          AND closing_rank <= ?
          AND closing_rank > 0
          {branch_sql}
        ORDER BY closing_rank ASC
        LIMIT 5000
    """
    params = cat_filters + [max_rank] + branch_params
    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]

    # Also get fee waiver rows if requested
    if fee_waiver:
        fw_sql = f"""
            SELECT institute_name, institute_type, fw, branch_code, branch_full_name,
                   opening_rank, closing_rank, allotted_category, domicile,
                   total_allotted, round_info, year, city, fee_waiver_available
            FROM counselling_data
            WHERE fw = 'Y'
              AND closing_rank <= ?
              AND closing_rank > 0
              {branch_sql}
            LIMIT 2000
        """
        c.execute(fw_sql, [max_rank] + branch_params)
        fw_rows = [dict(r) for r in c.fetchall()]
        # Merge unique rows
        existing_keys = {(r["institute_name"], r["branch_code"], r["allotted_category"]) for r in rows}
        for r in fw_rows:
            k = (r["institute_name"], r["branch_code"], r["allotted_category"])
            if k not in existing_keys:
                rows.append(r)
                existing_keys.add(k)

    conn.close()

    # Calculate probabilities
    results = []
    for row in rows:
        prob = calculate_probability(user_rank, row["opening_rank"], row["closing_rank"])
        risk, color = get_risk_level(prob)

        closing = row["closing_rank"] or 0
        pct_diff = ((closing - user_rank) / max(closing, 1)) * 100 if closing else 0

        explanation = _generate_explanation(user_rank, row, prob)

        results.append({
            **row,
            "probability": round(prob, 1),
            "risk_level": risk,
            "risk_color": color,
            "rank_difference": closing - user_rank,
            "pct_difference": round(pct_diff, 1),
            "explanation": explanation,
        })

    # Sort by probability desc
    results.sort(key=lambda x: (-x["probability"], x["closing_rank"] or 999999))

    # Categorize
    dream_limit = user_rank * (1 - dream_pct / 100)
    safe_limit = user_rank * (1 + safe_pct / 100)
    very_safe_limit = user_rank * (1 + very_safe_pct / 100)

    dream = [r for r in results if r["probability"] >= 80]
    safe = [r for r in results if 60 <= r["probability"] < 80]
    very_safe = [r for r in results if r["probability"] >= 40]

    return {
        "all": results,
        "dream": dream[:50],
        "safe": safe[:100],
        "very_safe": very_safe[:200],
        "total_eligible": len(results),
        "user_rank": user_rank,
        "category": category,
        "domicile": domicile,
        "fee_waiver": fee_waiver,
    }


def _generate_explanation(user_rank: int, row: dict, prob: float) -> str:
    """Generate human-readable explanation for each prediction"""
    closing = row.get("closing_rank", 0) or 0
    opening = row.get("opening_rank", 0) or 0
    diff = closing - user_rank

    if user_rank <= opening:
        return (
            f"✅ Your rank ({user_rank:,}) is better than the opening rank ({opening:,}). "
            f"You are very likely to get this option."
        )
    elif user_rank <= closing:
        return (
            f"✅ Your rank ({user_rank:,}) is within the closing rank ({closing:,}) for "
            f"{row.get('allotted_category', '')}. Historical data shows this as a safe option."
        )
    elif diff >= -50000:
        return (
            f"⚠️ Your rank ({user_rank:,}) is close to the closing rank ({closing:,}). "
            f"Difference of {abs(diff):,} ranks — possible with rank fluctuation."
        )
    else:
        return (
            f"❌ Your rank ({user_rank:,}) exceeds the closing rank ({closing:,}) by {abs(diff):,}. "
            f"This is a stretch option — lower probability."
        )


def get_missed_opportunities(user_rank: int, category: str, domicile: str, margin: int = 50000) -> list[dict]:
    """Find colleges missed by a small margin"""
    conn = get_connection()
    c = conn.cursor()
    cat_filters = get_category_filters(category, domicile, False)
    placeholders = ",".join(["?" for _ in cat_filters])

    lower = user_rank
    upper = user_rank + margin

    c.execute(f"""
        SELECT institute_name, branch_full_name, branch_code, closing_rank, allotted_category,
               (closing_rank - ?) as rank_diff
        FROM counselling_data
        WHERE allotted_category IN ({placeholders})
          AND closing_rank BETWEEN ? AND ?
          AND closing_rank > 0
        ORDER BY closing_rank ASC
        LIMIT 50
    """, [user_rank] + cat_filters + [lower, upper])

    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def generate_counselling_strategy(user_rank: int, category: str, domicile: str,
                                   fee_waiver: bool, selected_branches: list[str]) -> list[dict]:
    """Generate optimal preference order for counselling"""
    result = predict_colleges(user_rank, category, domicile, fee_waiver, selected_branches)
    all_results = result["all"]

    # Score colleges: probability * quality_bonus
    college_quality = {
        "GOVT": 1.3, "AIDED": 1.2, "S.F.I.": 1.15, "private": 1.0, "Private": 1.0,
    }

    scored = []
    for r in all_results:
        if r["probability"] < 30:
            continue
        q_score = college_quality.get(r.get("institute_type", "private"), 1.0)
        final_score = r["probability"] * q_score
        scored.append({**r, "strategy_score": round(final_score, 1)})

    scored.sort(key=lambda x: -x["strategy_score"])

    # Deduplicate (one entry per college+branch combo)
    seen = set()
    strategy = []
    for r in scored:
        key = (r["institute_name"], r["branch_code"])
        if key not in seen:
            seen.add(key)
            strategy.append(r)

    return strategy[:50]


def simulate_rank(base_rank: int, sim_ranks: list[int], category: str,
                   domicile: str, fee_waiver: bool) -> dict:
    """Simulate how different ranks change options"""
    results = {}
    for rank in [base_rank] + sim_ranks:
        conn = get_connection()
        c = conn.cursor()
        cat_filters = get_category_filters(category, domicile, fee_waiver)
        placeholders = ",".join(["?" for _ in cat_filters])
        max_rank = int(rank * 1.5)
        c.execute(f"""
            SELECT COUNT(*) as cnt FROM counselling_data
            WHERE allotted_category IN ({placeholders})
              AND closing_rank <= ? AND closing_rank > 0
        """, cat_filters + [max_rank])
        cnt = c.fetchone()[0]
        conn.close()
        results[rank] = cnt
    return results


def get_best_options(user_rank: int, category: str, domicile: str,
                      fee_waiver: bool, filter_type: str) -> list[dict]:
    """Get best options filtered by type"""
    cs_branches = [
        "Computer Science and Engineering",
        "Computer Science and Engineering (Artificial Intelligence and Machine Learning)",
        "Computer Science and Engineering (Data Science)",
        "Computer Science and Engineering (Cyber Security)",
        "Computer Science and Engineering (Internet of Things)",
        "Information Technology",
        "Artificial Intelligence and Machine Learning",
        "Artificial Intelligence and Data Science",
        "Computer Science and Business Systems",
    ]
    core_branches = [
        "Mechanical Engineering", "Civil Engineering", "Electrical Engineering",
        "Electronics and Communication Engineering", "Chemical Engineering",
        "Industrial and Production Engineering", "Automobile Engineering",
    ]

    branch_filter = []
    if filter_type == "cs":
        branch_filter = cs_branches
    elif filter_type == "core":
        branch_filter = core_branches

    result = predict_colleges(user_rank, category, domicile, fee_waiver, branch_filter)
    rows = result["all"]

    if filter_type == "govt":
        rows = [r for r in rows if "GOVT" in str(r.get("institute_type", "")).upper()]
    elif filter_type == "private":
        rows = [r for r in rows if "PRIVATE" in str(r.get("institute_type", "")).upper()]
    elif filter_type == "fw":
        rows = [r for r in rows if r.get("fee_waiver_available") == 1]

    return sorted(rows, key=lambda x: -x["probability"])[:100]


def generate_summary(user_rank: int, category: str, domicile: str, fee_waiver: bool,
                      selected_branches: list[str]) -> dict:
    """Generate complete admission summary"""
    result = predict_colleges(user_rank, category, domicile, fee_waiver, selected_branches)

    all_r = result["all"]
    eligible_colleges = set(r["institute_name"] for r in all_r if r["probability"] >= 40)
    eligible_branches = set(r["branch_full_name"] for r in all_r if r["probability"] >= 40)

    best_cs = next((r for r in all_r if "Computer Science" in r.get("branch_full_name", "")), None)
    best_core = next((r for r in all_r if "Mechanical" in r.get("branch_full_name", "") or
                      "Civil" in r.get("branch_full_name", "")), None)
    best_govt = next((r for r in all_r if "GOVT" in str(r.get("institute_type", "")).upper()), None)
    best_private = next((r for r in all_r if "PRIVATE" in str(r.get("institute_type", "")).upper()), None)
    best_fw = next((r for r in all_r if r.get("fee_waiver_available") == 1), None)

    top_20 = all_r[:20]

    prob_summary = {
        "guaranteed": len([r for r in all_r if r["probability"] >= 95]),
        "very_safe": len([r for r in all_r if 80 <= r["probability"] < 95]),
        "safe": len([r for r in all_r if 60 <= r["probability"] < 80]),
        "possible": len([r for r in all_r if 40 <= r["probability"] < 60]),
        "difficult": len([r for r in all_r if 20 <= r["probability"] < 40]),
        "unlikely": len([r for r in all_r if r["probability"] < 20]),
    }

    return {
        "user_rank": user_rank,
        "category": category,
        "domicile": domicile,
        "fee_waiver": fee_waiver,
        "total_eligible_colleges": len(eligible_colleges),
        "total_eligible_branches": len(eligible_branches),
        "best_cs_option": best_cs,
        "best_core_option": best_core,
        "best_govt_option": best_govt,
        "best_private_option": best_private,
        "best_fw_option": best_fw,
        "top_20": top_20,
        "probability_summary": prob_summary,
        "all_results": all_r,
    }
