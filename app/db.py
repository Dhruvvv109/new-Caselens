"""
app/db.py — Database management for CaseLens using SQLite.
Stores judgments (corpus) and pending cases with feature metrics and predictions.
"""

import math
import os
import sqlite3
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "caselens.db")


def _get_connection() -> sqlite3.Connection:
    """Return a sqlite3 connection configured with Row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not exist. Upgrade if old schema detected."""
    conn = _get_connection()
    try:
        cur = conn.cursor()

        # Check existing schema of judgments
        cur.execute("PRAGMA table_info(judgments)")
        cols_judgments = [r[1] for r in cur.fetchall()]
        if cols_judgments and "citation" not in cols_judgments:
            cur.execute("DROP TABLE judgments")

        # Check existing schema of pending_cases
        cur.execute("PRAGMA table_info(pending_cases)")
        cols_pending = [r[1] for r in cur.fetchall()]
        if cols_pending and "top1_similarity" not in cols_pending:
            cur.execute("DROP TABLE pending_cases")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS judgments (
                id           TEXT PRIMARY KEY,
                citation     TEXT,
                title        TEXT,
                court        TEXT,
                year         INTEGER,
                case_type    TEXT,
                subtheme     TEXT,
                text_content TEXT,
                outcome      TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_cases (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                case_no                TEXT UNIQUE,
                title                  TEXT,
                description            TEXT,
                case_type              TEXT,
                court                  TEXT,
                filing_date            TEXT,
                hearings_so_far        INTEGER DEFAULT 0,
                num_parties            INTEGER DEFAULT 2,
                is_appeal              INTEGER DEFAULT 0,
                status                 TEXT DEFAULT 'Pending',
                next_hearing_date      TEXT,
                top1_similarity        REAL DEFAULT 0,
                mean_top5_similarity   REAL DEFAULT 0,
                count_above_threshold  INTEGER DEFAULT 0,
                similarity_spread      REAL DEFAULT 0,
                predicted_days         INTEGER DEFAULT 0,
                lower_band             INTEGER DEFAULT 0,
                upper_band             INTEGER DEFAULT 0,
                priority_score         REAL DEFAULT 0,
                bucket                 TEXT DEFAULT 'Standard',
                why_text               TEXT DEFAULT ''
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def is_db_empty() -> bool:
    """Return True if judgments table count == 0."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM judgments")
        count = cur.fetchone()[0]
        return count == 0
    finally:
        conn.close()


def bulk_insert_judgments(records: List[Dict[str, Any]]) -> None:
    """INSERT OR IGNORE judgment records into judgments table."""
    if not records:
        return
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT OR IGNORE INTO judgments (
                id, citation, title, court, year, case_type, subtheme, text_content, outcome
            ) VALUES (
                :id, :citation, :title, :court, :year, :case_type, :subtheme, :text_content, :outcome
            )
            """,
            [
                {
                    "id": str(r.get("id", "")),
                    "citation": r.get("citation", ""),
                    "title": r.get("title", ""),
                    "court": r.get("court", ""),
                    "year": int(r.get("year", 0)),
                    "case_type": r.get("case_type", ""),
                    "subtheme": r.get("subtheme", ""),
                    "text_content": r.get("text_content", ""),
                    "outcome": r.get("outcome", ""),
                }
                for r in records
            ],
        )
        conn.commit()
    finally:
        conn.close()


def bulk_insert_pending_cases(records: List[Dict[str, Any]]) -> None:
    """INSERT OR IGNORE pending case records into pending_cases table."""
    if not records:
        return
    conn = _get_connection()
    try:
        cur = conn.cursor()
        for r in records:
            # Check if record has explicit 'id'
            has_id = r.get("id") is not None
            if has_id:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO pending_cases (
                        id, case_no, title, description, case_type, court,
                        filing_date, hearings_so_far, num_parties, is_appeal,
                        status, next_hearing_date, top1_similarity,
                        mean_top5_similarity, count_above_threshold, similarity_spread,
                        predicted_days, lower_band, upper_band, priority_score,
                        bucket, why_text
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        r.get("id"),
                        r.get("case_no", ""),
                        r.get("title", ""),
                        r.get("description", ""),
                        r.get("case_type", ""),
                        r.get("court", ""),
                        r.get("filing_date", ""),
                        int(r.get("hearings_so_far", 0)),
                        int(r.get("num_parties", 2)),
                        int(r.get("is_appeal", 0)),
                        r.get("status", "Pending"),
                        r.get("next_hearing_date", ""),
                        float(r.get("top1_similarity", 0.0)),
                        float(r.get("mean_top5_similarity", 0.0)),
                        int(r.get("count_above_threshold", 0)),
                        float(r.get("similarity_spread", 0.0)),
                        int(r.get("predicted_days", 0)),
                        int(r.get("lower_band", 0)),
                        int(r.get("upper_band", 0)),
                        float(r.get("priority_score", 0.0)),
                        r.get("bucket", "Standard"),
                        r.get("why_text", ""),
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO pending_cases (
                        case_no, title, description, case_type, court,
                        filing_date, hearings_so_far, num_parties, is_appeal,
                        status, next_hearing_date, top1_similarity,
                        mean_top5_similarity, count_above_threshold, similarity_spread,
                        predicted_days, lower_band, upper_band, priority_score,
                        bucket, why_text
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        r.get("case_no", ""),
                        r.get("title", ""),
                        r.get("description", ""),
                        r.get("case_type", ""),
                        r.get("court", ""),
                        r.get("filing_date", ""),
                        int(r.get("hearings_so_far", 0)),
                        int(r.get("num_parties", 2)),
                        int(r.get("is_appeal", 0)),
                        r.get("status", "Pending"),
                        r.get("next_hearing_date", ""),
                        float(r.get("top1_similarity", 0.0)),
                        float(r.get("mean_top5_similarity", 0.0)),
                        int(r.get("count_above_threshold", 0)),
                        float(r.get("similarity_spread", 0.0)),
                        int(r.get("predicted_days", 0)),
                        int(r.get("lower_band", 0)),
                        int(r.get("upper_band", 0)),
                        float(r.get("priority_score", 0.0)),
                        r.get("bucket", "Standard"),
                        r.get("why_text", ""),
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def get_all_judgments() -> List[Dict[str, Any]]:
    """Return all judgments as a list of dicts."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM judgments ORDER BY id")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_judgment(jid: str) -> Optional[Dict[str, Any]]:
    """Fetch single judgment by ID or citation."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM judgments WHERE id = ? OR citation = ?", (jid, jid))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_pending_cases(
    bucket: Optional[str] = None,
    case_type: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    sort: str = "priority",
    page: int = 1,
    page_size: int = 25,
) -> Dict[str, Any]:
    """
    Query pending cases with filters, text search, sorting, and pagination.
    Returns: {cases: list, total: int, page: int, pages: int}
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        where_clauses = []
        params: List[Any] = []

        if bucket:
            where_clauses.append("bucket = ?")
            params.append(bucket)
        if case_type:
            where_clauses.append("case_type = ?")
            params.append(case_type)
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        if q:
            clean_q = f"%{q.strip()}%"
            where_clauses.append("(title LIKE ? OR description LIKE ? OR case_no LIKE ?)")
            params.extend([clean_q, clean_q, clean_q])

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Total count
        cur.execute(f"SELECT COUNT(*) FROM pending_cases {where_sql}", params)
        total = cur.fetchone()[0]

        # Sorting
        sort_clean = (sort or "").lower()
        if sort_clean == "days":
            order_by = "predicted_days ASC"
        elif sort_clean == "filing":
            order_by = "filing_date ASC"
        else:
            order_by = "priority_score DESC"

        page = max(1, int(page))
        page_size = max(1, int(page_size))
        pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        offset = (page - 1) * page_size

        select_sql = f"SELECT * FROM pending_cases {where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?"
        cur.execute(select_sql, params + [page_size, offset])
        cases = [dict(row) for row in cur.fetchall()]

        return {
            "cases": cases,
            "total": total,
            "page": page,
            "pages": pages,
        }
    finally:
        conn.close()


def get_pending_case(case_id: int) -> Optional[Dict[str, Any]]:
    """Fetch single pending case by integer id (or case_no fallback)."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        if isinstance(case_id, int) or (isinstance(case_id, str) and case_id.isdigit()):
            cur.execute("SELECT * FROM pending_cases WHERE id = ?", (int(case_id),))
        else:
            cur.execute("SELECT * FROM pending_cases WHERE case_no = ?", (str(case_id),))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_case_features(case_id: int, features: Dict[str, Any]) -> None:
    """Update precedent metrics, prediction, bucket, and why_text for a pending case."""
    allowed_cols = {
        "top1_similarity",
        "mean_top5_similarity",
        "count_above_threshold",
        "similarity_spread",
        "predicted_days",
        "lower_band",
        "upper_band",
        "priority_score",
        "bucket",
        "why_text",
        "status",
        "next_hearing_date",
        "hearings_so_far",
    }
    updates = []
    params = []
    for k, v in features.items():
        if k in allowed_cols:
            updates.append(f"{k} = ?")
            params.append(v)

    if not updates:
        return

    params.append(int(case_id))
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE pending_cases SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    finally:
        conn.close()


def insert_pending_case(record: Dict[str, Any]) -> int:
    """Insert one pending case and return its integer id."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        case_no = record.get("case_no")
        if not case_no:
            # Auto-generate case number
            import random
            case_no = f"ARB/{random.randint(1000, 9999)}/2026"

        cur.execute(
            """
            INSERT INTO pending_cases (
                case_no, title, description, case_type, court,
                filing_date, hearings_so_far, num_parties, is_appeal,
                status, next_hearing_date, top1_similarity,
                mean_top5_similarity, count_above_threshold, similarity_spread,
                predicted_days, lower_band, upper_band, priority_score,
                bucket, why_text
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                case_no,
                record.get("title", ""),
                record.get("description", ""),
                record.get("case_type", ""),
                record.get("court", ""),
                record.get("filing_date", ""),
                int(record.get("hearings_so_far", 0)),
                int(record.get("num_parties", 2)),
                int(record.get("is_appeal", 0)),
                record.get("status", "Pending"),
                record.get("next_hearing_date", ""),
                float(record.get("top1_similarity", 0.0)),
                float(record.get("mean_top5_similarity", 0.0)),
                int(record.get("count_above_threshold", 0)),
                float(record.get("similarity_spread", 0.0)),
                int(record.get("predicted_days", 0)),
                int(record.get("lower_band", 0)),
                int(record.get("upper_band", 0)),
                float(record.get("priority_score", 0.0)),
                record.get("bucket", "Standard"),
                record.get("why_text", ""),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_overview_stats() -> Dict[str, Any]:
    """
    Return overview statistics:
    {total_active, by_status:{Pending,Under Hearing,Judgment Reserved},
     by_bucket:{Fast-track,Standard,Needs attention}, avg_hearings, judgment_count}
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()

        # Judgments count
        cur.execute("SELECT COUNT(*) FROM judgments")
        judgment_count = cur.fetchone()[0]

        # Total active cases
        cur.execute("SELECT COUNT(*), AVG(hearings_so_far) FROM pending_cases")
        row = cur.fetchone()
        total_active = row[0] if row else 0
        avg_hearings = round(row[1] if row and row[1] is not None else 0.0, 1)

        # Status counts
        by_status = {"Pending": 0, "Under Hearing": 0, "Judgment Reserved": 0}
        cur.execute("SELECT status, COUNT(*) FROM pending_cases GROUP BY status")
        for s_row in cur.fetchall():
            s_name = s_row[0]
            if s_name in by_status:
                by_status[s_name] = s_row[1]
            elif s_name:
                by_status[s_name] = s_row[1]

        # Bucket counts
        by_bucket = {"Fast-track": 0, "Standard": 0, "Needs attention": 0}
        cur.execute("SELECT bucket, COUNT(*) FROM pending_cases GROUP BY bucket")
        for b_row in cur.fetchall():
            b_name = b_row[0]
            if b_name in by_bucket:
                by_bucket[b_name] = b_row[1]
            elif b_name:
                by_bucket[b_name] = b_row[1]

        return {
            "total_active": total_active,
            "by_status": by_status,
            "by_bucket": by_bucket,
            "avg_hearings": avg_hearings,
            "judgment_count": judgment_count,
        }
    finally:
        conn.close()


def get_top_queue(limit: int = 10) -> List[Dict[str, Any]]:
    """Return top N cases by priority_score DESC."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM pending_cases ORDER BY priority_score DESC LIMIT ?",
            (max(1, int(limit)),),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
