"""
MPDTE College Predictor — Prediction Engine v2
Redesigned with:
  • Correct rank logic (smaller = better)
  • Honest confidence bands instead of fake percentages
  • Rank-range uncertainty analysis
  • Detailed plain-language explanations
  • Full diagnostics support
"""
import sqlite3
import logging
from core.database import get_connection

logger = logging.getLogger(__name__)

# ── Category mapping ──────────────────────────────────────────────────────────
CATEGORY_MAP = {
    "General (UR)": ["UR/X/OP", "UR/X/F", "UR/D/OP", "UR/D/F",
                     "UR/S/OP", "UR/S/F", "UR/FF/OP", "UR/NCC/OP"],
    "OBC":          ["OBC/X/OP", "OBC/X/F", "OBC/D/OP", "OBC/S/OP", "OBC/S/F"],
    "SC":           ["SC/X/OP",  "SC/X/F",  "SC/D/OP",  "SC/S/OP",  "SC/S/F"],
    "ST":           ["ST/X/OP",  "ST/X/F",  "ST/D/OP",  "ST/S/OP"],
    "EWS":          ["EWS", "EWS/X/OP", "EWS/X/F"],
}

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
        "Mechanical Engineering", "Civil Engineering", "Electrical Engineering",
        "Electronics and Communication Engineering",
        "Electronics and Instrumentation Engineering",
        "Industrial Engineering and Operations Technology",
        "Industrial and Production Engineering",
        "Automobile Engineering", "Chemical Engineering",
        "Materials and Metallurgical Engineering",
    ],
    "All Branches": [],
}


# ── Confidence band definitions ───────────────────────────────────────────────
# Instead of fake percentages, we use 6 honest bands based on
# how the student rank relates to historical opening/closing ranks.
#
#  BAND                  CONDITION
#  ─────────────────────────────────────────────────────────────────────────
#  Extremely Likely      rank < opening_rank  (better than the best ever seen)
#  Likely                opening ≤ rank ≤ (opening + 25% of range)
#  Reasonable            rank within closing rank (middle zone)
#  Borderline            rank within 10% beyond closing rank
#  Stretch               rank 10-30% beyond closing rank
#  Historically Unavailable  rank > 30% beyond closing rank
#
# Each band also carries a numeric score (0-100) for SORTING purposes only.
# These scores are never shown to the user as "probability".

BANDS = [
    # (label,              sort_score, color_tag,   short_label)
    ("Extremely Likely",   98,         "green",      "✅ Extremely Likely"),
    ("Likely",             80,         "lightgreen", "🟢 Likely"),
    ("Reasonable",         60,         "yellow",     "🟡 Reasonable"),
    ("Borderline",         38,         "orange",     "🟠 Borderline"),
    ("Stretch",            18,         "red",        "🔴 Stretch"),
    ("Historically Unavailable", 3,   "darkred",    "❌ Historically Unavailable"),
]
BAND_LABELS   = [b[0] for b in BANDS]
BAND_SCORES   = {b[0]: b[1] for b in BANDS}
BAND_COLORS   = {b[0]: b[2] for b in BANDS}
BAND_SHORT    = {b[0]: b[3] for b in BANDS}


def classify_band(user_rank: int, opening_rank: int | None, closing_rank: int | None) -> str:
    """
    Core classification function.
    Smaller rank = better rank (JEE logic: rank 1 is the best).

    Returns one of the six BAND labels.
    """
    if closing_rank is None or closing_rank <= 0:
        return "Historically Unavailable"
    if opening_rank is None or opening_rank <= 0:
        opening_rank = closing_rank  # fallback: treat opening = closing

    # Safety: ensure opening <= closing (data sanity)
    if opening_rank > closing_rank:
        opening_rank, closing_rank = closing_rank, opening_rank

    # ── Zone 1: Better than opening rank (student rank < opening rank)
    if user_rank < opening_rank:
        return "Extremely Likely"

    # ── Zone 2: Between opening and closing (student rank ≤ closing rank)
    if user_rank <= closing_rank:
        rank_range = closing_rank - opening_rank
        if rank_range <= 0:
            return "Extremely Likely"
        position_frac = (user_rank - opening_rank) / rank_range
        # First 25% of the range → Likely; rest → Reasonable
        if position_frac <= 0.25:
            return "Likely"
        else:
            return "Reasonable"

    # ── Zone 3: Beyond closing rank (student rank > closing rank)
    overshoot_pct = (user_rank - closing_rank) / closing_rank
    if overshoot_pct <= 0.10:
        return "Borderline"
    elif overshoot_pct <= 0.30:
        return "Stretch"
    else:
        return "Historically Unavailable"


def get_band_score(band: str) -> int:
    return BAND_SCORES.get(band, 0)


def get_band_color(band: str) -> str:
    return BAND_COLORS.get(band, "darkred")


def get_category_filters(category: str, domicile: str, fee_waiver: bool) -> list[str]:
    base_cats = CATEGORY_MAP.get(category, CATEGORY_MAP["General (UR)"])
    if domicile == "Yes":
        cats = base_cats[:]
    else:
        cats = [c for c in base_cats if "/F" not in c]
        cats += ["AI"]
    if fee_waiver:
        cats.append("FW/OP")
    return cats


def _build_explanation(user_rank: int, opening_rank: int | None,
                        closing_rank: int | None, band: str) -> str:
    """
    Plain-language explanation of why this band was assigned.
    Uses concrete numbers, no vague phrases.
    """
    cr = closing_rank or 0
    op = opening_rank or cr

    if band == "Extremely Likely":
        return (
            f"Your rank ({user_rank:,}) is better than the historical opening rank "
            f"({op:,}). In past years, students with this rank were comfortably admitted."
        )
    elif band == "Likely":
        margin = cr - user_rank
        return (
            f"Your rank ({user_rank:,}) is within the historical range "
            f"({op:,} – {cr:,}), close to the opening. "
            f"You have {margin:,} ranks of buffer before the closing cutoff."
        )
    elif band == "Reasonable":
        margin = cr - user_rank
        return (
            f"Your rank ({user_rank:,}) falls within the historical closing rank "
            f"({cr:,}) with {margin:,} ranks to spare. This option was available "
            f"to students in this rank range in previous years."
        )
    elif band == "Borderline":
        excess = user_rank - cr
        pct = round((excess / cr) * 100, 1)
        return (
            f"Your rank ({user_rank:,}) exceeds the historical closing rank "
            f"({cr:,}) by {excess:,} ranks ({pct}%). "
            f"This option may open if cutoffs relax slightly, but it is not reliable."
        )
    elif band == "Stretch":
        excess = user_rank - cr
        pct = round((excess / cr) * 100, 1)
        return (
            f"Your rank ({user_rank:,}) is significantly beyond the historical "
            f"closing rank ({cr:,}) — {excess:,} ranks ({pct}%) over the cutoff. "
            f"Consider this only as a backup and do not rely on it."
        )
    else:  # Historically Unavailable
        excess = user_rank - cr if cr else 0
        return (
            f"Your rank ({user_rank:,}) is far beyond the historical closing rank "
            f"({cr:,}). This option was not historically available at this rank range."
        )


def _fetch_all_rows(category: str, domicile: str, fee_waiver: bool,
                    selected_branches: list[str]) -> list[dict]:
    """
    Fetch ALL relevant rows from the DB with NO rank cap.
    The rank cap was the primary bug — removed entirely.
    Filtering is done post-fetch by classify_band.
    """
    conn = get_connection()
    c = conn.cursor()
    cat_filters = get_category_filters(category, domicile, fee_waiver)
    placeholders = ",".join(["?" for _ in cat_filters])

    branch_sql = ""
    branch_params = []
    if selected_branches and "All Branches" not in selected_branches:
        bp = ",".join(["?" for _ in selected_branches])
        branch_sql = f"AND branch_full_name IN ({bp})"
        branch_params = list(selected_branches)

    # NO closing_rank cap — fetch everything for this category
    sql = f"""
        SELECT institute_name, institute_type, fw, branch_code, branch_full_name,
               opening_rank, closing_rank, allotted_category, domicile,
               total_allotted, round_info, year, city, fee_waiver_available
        FROM counselling_data
        WHERE allotted_category IN ({placeholders})
          AND closing_rank > 0
          {branch_sql}
        ORDER BY closing_rank ASC
        LIMIT 10000
    """
    c.execute(sql, cat_filters + branch_params)
    rows = [dict(r) for r in c.fetchall()]

    # Extra: fee waiver rows
    if fee_waiver:
        fw_sql = f"""
            SELECT institute_name, institute_type, fw, branch_code, branch_full_name,
                   opening_rank, closing_rank, allotted_category, domicile,
                   total_allotted, round_info, year, city, fee_waiver_available
            FROM counselling_data
            WHERE fw = 'Y' AND closing_rank > 0
              {branch_sql}
            LIMIT 5000
        """
        c.execute(fw_sql, branch_params)
        existing_keys = {(r["institute_name"], r["branch_code"], r["allotted_category"]) for r in rows}
        for r in [dict(x) for x in c.fetchall()]:
            k = (r["institute_name"], r["branch_code"], r["allotted_category"])
            if k not in existing_keys:
                rows.append(r)
                existing_keys.add(k)

    conn.close()
    return rows


def predict_colleges(user_rank: int, category: str, domicile: str,
                     fee_waiver: bool, selected_branches: list[str],
                     show_unavailable: bool = False) -> dict:
    """
    Main prediction function.
    Returns all rows annotated with band, score, explanation, diagnostics.
    """
    raw_rows = _fetch_all_rows(category, domicile, fee_waiver, selected_branches)

    results = []
    for row in raw_rows:
        op = row.get("opening_rank")
        cr = row.get("closing_rank")
        band = classify_band(user_rank, op, cr)

        # Optionally skip historically unavailable
        if not show_unavailable and band == "Historically Unavailable":
            continue

        score = get_band_score(band)
        explanation = _build_explanation(user_rank, op, cr, band)

        # Diagnostics payload
        dist_from_opening = (user_rank - op) if op else None
        dist_from_closing = user_rank - cr if cr else None

        results.append({
            **row,
            # ── Band fields (replace fake probability)
            "band":             band,
            "band_score":       score,
            "band_color":       get_band_color(band),
            "band_short":       BAND_SHORT.get(band, band),
            # ── Legacy alias so GUI code doesn't break
            "probability":      score,
            "risk_level":       band,
            "risk_color":       get_band_color(band),
            # ── Explanation
            "explanation":      explanation,
            # ── Diagnostics
            "diag_user_rank":         user_rank,
            "diag_opening_rank":      op,
            "diag_closing_rank":      cr,
            "diag_dist_from_opening": dist_from_opening,
            "diag_dist_from_closing": dist_from_closing,
            "diag_band":              band,
            "diag_band_score":        score,
        })

    # Sort: best band first, then by closing rank ascending within band
    results.sort(key=lambda x: (-x["band_score"], x["closing_rank"] or 999999))

    band_counts = {b[0]: 0 for b in BANDS}
    for r in results:
        band_counts[r["band"]] = band_counts.get(r["band"], 0) + 1

    eligible_colleges = set(r["institute_name"] for r in results
                            if r["band"] not in ("Stretch", "Historically Unavailable"))
    eligible_branches = set(r["branch_full_name"] for r in results
                            if r["band"] not in ("Stretch", "Historically Unavailable"))

    return {
        "all": results,
        "band_counts": band_counts,
        "total_eligible": len(results),
        "eligible_colleges": len(eligible_colleges),
        "eligible_branches": len(eligible_branches),
        "user_rank": user_rank,
        "category": category,
        "domicile": domicile,
        "fee_waiver": fee_waiver,
    }


def simulate_rank(base_rank: int, sim_ranks: list[int], category: str,
                  domicile: str, fee_waiver: bool) -> dict:
    """
    Simulate options at different ranks.
    Returns dict: rank → {total, extremely_likely, likely, reasonable, borderline, stretch}
    Correct logic: fetch ALL rows, classify each, count per band.
    """
    all_ranks = sorted(set([base_rank] + sim_ranks))
    raw_rows = _fetch_all_rows(category, domicile, fee_waiver, [])

    results = {}
    for rank in all_ranks:
        band_counts = {b[0]: 0 for b in BANDS}
        total_useful = 0
        for row in raw_rows:
            band = classify_band(rank, row.get("opening_rank"), row.get("closing_rank"))
            band_counts[band] = band_counts.get(band, 0) + 1
            if band != "Historically Unavailable":
                total_useful += 1
        results[rank] = {
            "total_useful": total_useful,
            **band_counts,
        }
    return results


def analyze_rank_range(user_rank: int, margin: int, category: str,
                       domicile: str, fee_waiver: bool) -> dict:
    """
    Rank range uncertainty analysis.
    Given rank ± margin, show best/expected/worst case option counts.
    """
    best_rank  = max(1, user_rank - margin)   # better rank = smaller number
    worst_rank = user_rank + margin            # worse rank  = larger number

    raw_rows = _fetch_all_rows(category, domicile, fee_waiver, [])

    def count_bands(rank):
        counts = {b[0]: 0 for b in BANDS}
        for row in raw_rows:
            b = classify_band(rank, row.get("opening_rank"), row.get("closing_rank"))
            counts[b] += 1
        return counts

    best_counts     = count_bands(best_rank)
    expected_counts = count_bands(user_rank)
    worst_counts    = count_bands(worst_rank)

    def useful(counts):
        return sum(v for k, v in counts.items() if k != "Historically Unavailable")

    return {
        "base_rank":          user_rank,
        "margin":             margin,
        "best_rank":          best_rank,
        "worst_rank":         worst_rank,
        "best_case":          best_counts,
        "expected_case":      expected_counts,
        "worst_case":         worst_counts,
        "best_useful":        useful(best_counts),
        "expected_useful":    useful(expected_counts),
        "worst_useful":       useful(worst_counts),
    }


def get_missed_opportunities(user_rank: int, category: str, domicile: str,
                              margin: int = 50000) -> list[dict]:
    """
    Find options just beyond the closing rank (Borderline band).
    These are options the student narrowly missed.
    """
    raw_rows = _fetch_all_rows(category, domicile, False, [])
    missed = []
    for row in raw_rows:
        cr = row.get("closing_rank") or 0
        if cr <= 0:
            continue
        # Borderline: rank > closing but within 10% of closing
        if user_rank > cr:
            excess = user_rank - cr
            if excess <= margin:
                band = classify_band(user_rank, row.get("opening_rank"), cr)
                if band in ("Borderline", "Stretch"):
                    missed.append({
                        **row,
                        "rank_diff": excess,
                        "band": band,
                        "band_color": get_band_color(band),
                    })

    missed.sort(key=lambda x: x["rank_diff"])
    return missed[:50]


def generate_counselling_strategy(user_rank: int, category: str, domicile: str,
                                   fee_waiver: bool, selected_branches: list[str]) -> list[dict]:
    """
    Optimal preference ordering for counselling.
    Score = band_score * college_quality_multiplier.
    Only includes options up to and including Borderline.
    """
    result = predict_colleges(user_rank, category, domicile, fee_waiver, selected_branches)
    rows = [r for r in result["all"]
            if r["band"] not in ("Stretch", "Historically Unavailable")]

    quality = {"GOVT": 1.30, "AIDED": 1.20, "S.F.I.": 1.15,
               "private": 1.00, "Private": 1.00}

    scored = []
    for r in rows:
        q = quality.get(r.get("institute_type", "private"), 1.0)
        strat_score = round(r["band_score"] * q, 1)
        scored.append({**r, "strategy_score": strat_score})

    scored.sort(key=lambda x: -x["strategy_score"])

    seen = set()
    strategy = []
    for r in scored:
        key = (r["institute_name"], r["branch_code"])
        if key not in seen:
            seen.add(key)
            strategy.append(r)

    return strategy[:50]


def get_best_options(user_rank: int, category: str, domicile: str,
                      fee_waiver: bool, filter_type: str) -> list[dict]:
    """Best options filtered by type (cs/core/govt/private/fw)"""
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

    return rows[:100]


def generate_summary(user_rank: int, category: str, domicile: str,
                      fee_waiver: bool, selected_branches: list[str]) -> dict:
    """Complete admission summary for the GUI results view"""
    result = predict_colleges(user_rank, category, domicile, fee_waiver, selected_branches)
    all_r = result["all"]

    best_cs     = next((r for r in all_r if "Computer Science" in r.get("branch_full_name", "")), None)
    best_core   = next((r for r in all_r if "Mechanical" in r.get("branch_full_name", "")
                        or "Civil" in r.get("branch_full_name", "")), None)
    best_govt   = next((r for r in all_r if "GOVT" in str(r.get("institute_type", "")).upper()), None)
    best_private = next((r for r in all_r if "PRIVATE" in str(r.get("institute_type", "")).upper()), None)
    best_fw     = next((r for r in all_r if r.get("fee_waiver_available") == 1), None)

    bc = result["band_counts"]
    prob_summary = {
        "guaranteed": bc.get("Extremely Likely", 0),
        "very_safe":  bc.get("Likely", 0),
        "safe":       bc.get("Reasonable", 0),
        "possible":   bc.get("Borderline", 0),
        "difficult":  bc.get("Stretch", 0),
        "unlikely":   bc.get("Historically Unavailable", 0),
    }

    return {
        "user_rank":               user_rank,
        "category":                category,
        "domicile":                domicile,
        "fee_waiver":              fee_waiver,
        "total_eligible_colleges": result["eligible_colleges"],
        "total_eligible_branches": result["eligible_branches"],
        "best_cs_option":          best_cs,
        "best_core_option":        best_core,
        "best_govt_option":        best_govt,
        "best_private_option":     best_private,
        "best_fw_option":          best_fw,
        "top_20":                  all_r[:20],
        "probability_summary":     prob_summary,
        "band_counts":             bc,
        "all_results":             all_r,
    }
