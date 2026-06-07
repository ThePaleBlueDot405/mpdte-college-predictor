"""
Database layer for MPDTE College Predictor
Handles all SQLite operations with permanent storage
"""
import sqlite3
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Store DB in user's home directory for persistence
DB_PATH = os.path.join(Path.home(), "mpdte_predictor.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database schema"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS imported_pdfs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            import_date TEXT NOT NULL,
            records_imported INTEGER DEFAULT 0,
            duplicates_skipped INTEGER DEFAULT 0,
            round_info TEXT,
            year TEXT,
            UNIQUE(filepath)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS counselling_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_no INTEGER,
            institute_name TEXT NOT NULL,
            institute_type TEXT,
            fw TEXT,
            branch_code TEXT,
            branch_full_name TEXT,
            national_player TEXT,
            opening_rank INTEGER,
            closing_rank INTEGER,
            allotted_category TEXT,
            domicile TEXT,
            total_allotted INTEGER,
            round_info TEXT,
            year TEXT,
            pdf_source TEXT,
            city TEXT,
            state TEXT,
            fee_waiver_available INTEGER DEFAULT 0,
            hash_key TEXT,
            UNIQUE(hash_key)
        )
    """)

    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_closing_rank ON counselling_data(closing_rank)
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_category ON counselling_data(allotted_category)
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_branch ON counselling_data(branch_code)
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_institute ON counselling_data(institute_name)
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_type ON counselling_data(institute_type)
    """)

    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")


def get_db_stats():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM counselling_data")
    total_records = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM imported_pdfs")
    total_pdfs = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT institute_name) FROM counselling_data")
    total_colleges = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT branch_code) FROM counselling_data")
    total_branches = c.fetchone()[0]
    conn.close()
    return {
        "total_records": total_records,
        "total_pdfs": total_pdfs,
        "total_colleges": total_colleges,
        "total_branches": total_branches,
    }


def insert_records(records, pdf_filename, pdf_filepath, round_info="Round 1", year="2025"):
    """Insert records with duplicate detection via hash_key"""
    conn = get_connection()
    c = conn.cursor()
    imported = 0
    duplicates = 0

    for rec in records:
        try:
            c.execute(
                """INSERT OR IGNORE INTO counselling_data
                   (serial_no, institute_name, institute_type, fw, branch_code,
                    branch_full_name, national_player, opening_rank, closing_rank,
                    allotted_category, domicile, total_allotted, round_info, year,
                    pdf_source, city, state, fee_waiver_available, hash_key)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    rec.get("serial_no"),
                    rec.get("institute_name", ""),
                    rec.get("institute_type", ""),
                    rec.get("fw", "N"),
                    rec.get("branch_code", ""),
                    rec.get("branch_full_name", ""),
                    rec.get("national_player", ""),
                    rec.get("opening_rank"),
                    rec.get("closing_rank"),
                    rec.get("allotted_category", ""),
                    rec.get("domicile", ""),
                    rec.get("total_allotted"),
                    round_info,
                    year,
                    pdf_filename,
                    rec.get("city", ""),
                    rec.get("state", "MP"),
                    1 if rec.get("fw", "N").upper() == "Y" else 0,
                    rec.get("hash_key", ""),
                ),
            )
            if c.rowcount > 0:
                imported += 1
            else:
                duplicates += 1
        except Exception as e:
            logger.warning(f"Row insert error: {e}")

    # Log PDF import
    try:
        c.execute(
            """INSERT OR REPLACE INTO imported_pdfs
               (filename, filepath, import_date, records_imported, duplicates_skipped, round_info, year)
               VALUES (?, ?, datetime('now'), ?, ?, ?, ?)""",
            (pdf_filename, pdf_filepath, imported, duplicates, round_info, year),
        )
    except Exception as e:
        logger.warning(f"PDF log error: {e}")

    conn.commit()
    conn.close()
    return imported, duplicates


def search_records(query="", filters=None):
    """Global search across all fields"""
    conn = get_connection()
    c = conn.cursor()
    sql = "SELECT * FROM counselling_data WHERE 1=1"
    params = []

    if query:
        sql += """ AND (institute_name LIKE ? OR branch_full_name LIKE ?
                   OR branch_code LIKE ? OR allotted_category LIKE ?
                   OR city LIKE ? OR institute_type LIKE ?)"""
        q = f"%{query}%"
        params.extend([q, q, q, q, q, q])

    if filters:
        if filters.get("institute_type"):
            sql += " AND LOWER(institute_type) LIKE ?"
            params.append(f"%{filters['institute_type'].lower()}%")
        if filters.get("fee_waiver"):
            sql += " AND fee_waiver_available = 1"
        if filters.get("city"):
            sql += " AND city LIKE ?"
            params.append(f"%{filters['city']}%")
        if filters.get("min_rank"):
            sql += " AND closing_rank >= ?"
            params.append(filters["min_rank"])
        if filters.get("max_rank"):
            sql += " AND closing_rank <= ?"
            params.append(filters["max_rank"])

    sql += " ORDER BY institute_name, branch_code LIMIT 2000"
    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_all_institutes():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT institute_name, institute_type, city FROM counselling_data ORDER BY institute_name")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_all_branches():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT branch_code, branch_full_name FROM counselling_data ORDER BY branch_full_name")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_analytics():
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT MAX(closing_rank) FROM counselling_data")
    max_cr = c.fetchone()[0]
    c.execute("SELECT MIN(closing_rank) FROM counselling_data WHERE closing_rank > 0")
    min_cr = c.fetchone()[0]

    c.execute("""
        SELECT allotted_category, COUNT(*) as cnt
        FROM counselling_data GROUP BY allotted_category ORDER BY cnt DESC LIMIT 15
    """)
    cat_dist = [(r[0], r[1]) for r in c.fetchall()]

    c.execute("""
        SELECT branch_full_name, COUNT(*) as cnt
        FROM counselling_data GROUP BY branch_full_name ORDER BY cnt DESC LIMIT 15
    """)
    branch_dist = [(r[0], r[1]) for r in c.fetchall()]

    c.execute("""
        SELECT institute_type, COUNT(*) as cnt
        FROM counselling_data GROUP BY institute_type ORDER BY cnt DESC
    """)
    college_dist = [(r[0], r[1]) for r in c.fetchall()]

    c.execute("""
        SELECT institute_name, COUNT(DISTINCT branch_code) as branches
        FROM counselling_data GROUP BY institute_name ORDER BY branches DESC LIMIT 10
    """)
    top_colleges = [(r[0], r[1]) for r in c.fetchall()]

    conn.close()
    return {
        "max_closing_rank": max_cr,
        "min_closing_rank": min_cr,
        "category_distribution": cat_dist,
        "branch_distribution": branch_dist,
        "college_type_distribution": college_dist,
        "top_colleges_by_branches": top_colleges,
    }


def get_imported_pdfs():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM imported_pdfs ORDER BY import_date DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_college_detail(institute_name):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM counselling_data WHERE institute_name = ? ORDER BY branch_code, allotted_category",
        (institute_name,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def delete_pdf_records(pdf_source):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM counselling_data WHERE pdf_source = ?", (pdf_source,))
    c.execute("DELETE FROM imported_pdfs WHERE filename = ?", (pdf_source,))
    conn.commit()
    conn.close()
