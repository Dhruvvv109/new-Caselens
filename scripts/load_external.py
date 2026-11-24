"""
scripts/load_external.py
Load external CSV or JSON files of real Indian court judgments into CaseLens.

──────────────────────────────────────────────────────────────────────────────
WHERE TO GET INDIAN LEGAL DATASETS
──────────────────────────────────────────────────────────────────────────────

1. IndianKanoon (https://indiankanoon.org)
   - IndianKanoon does not provide bulk CSV exports officially.
   - You can use the IndianKanoon API (api.indiankanoon.org) with a registered
     API key to fetch judgments in JSON format.
   - Alternatively, community-scraped dumps are occasionally shared on Kaggle:
     search for "Indian court judgments dataset" on https://www.kaggle.com/datasets
   - Expected columns after download: id, title, court, year, case_type, text

2. ILDC Dataset (Indian Legal Documents Corpus) on HuggingFace
   - URL: https://huggingface.co/datasets/ashwani-tanwar/ILDC_multi
     or    https://huggingface.co/datasets/pav1ithra/ILDC_multi
   - Download via: `pip install datasets` then:
       from datasets import load_dataset
       ds = load_dataset("ashwani-tanwar/ILDC_multi")
   - Columns: text (judgment text), label (0/1 accepted/rejected)
   - You will need to add id, title, court, year, case_type manually or infer
     from the text. Export to CSV:
       ds["train"].to_csv("ildc_train.csv", index=False)

3. SCC Online / Manupatra / Lexisnexis
   - Commercial providers. Subscribe and use their export feature to download
     judgments as PDF or Word; then extract text with pdfminer / docx2txt.

4. e-Courts Open Data Portal
   - https://ecourts.gov.in/ecourts_home/static/open-data.php
   - Provides case-level statistics (not full text), useful for training features.

──────────────────────────────────────────────────────────────────────────────
USAGE
──────────────────────────────────────────────────────────────────────────────
  python scripts/load_external.py --file judgments.csv --format csv
  python scripts/load_external.py --file judgments.json --format json

Expected CSV columns (order doesn't matter):
  id, title, court, year, case_type, text   (or text_content instead of text)

Expected JSON format: list of objects with the same keys.
──────────────────────────────────────────────────────────────────────────────
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "caselens.db"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
JUDGMENT_IDS_PATH = DATA_DIR / "judgment_ids.json"


# ─────────────────────────────────────────────
# DB helpers (standalone, mirrors app/db.py)
# ─────────────────────────────────────────────

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS judgments (
            id          TEXT PRIMARY KEY,
            title       TEXT,
            court       TEXT,
            year        INTEGER,
            case_type   TEXT,
            text_content TEXT
        );
        CREATE TABLE IF NOT EXISTS pending_cases (
            case_no         TEXT PRIMARY KEY,
            title           TEXT,
            description     TEXT,
            case_type       TEXT,
            filing_date     TEXT,
            hearings_so_far INTEGER,
            num_parties     INTEGER,
            is_appeal       INTEGER,
            court           TEXT
        );
    """)
    conn.commit()


def upsert_judgment(conn: sqlite3.Connection, record: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO judgments
           (id, title, court, year, case_type, text_content)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            str(record["id"]),
            str(record.get("title", "")),
            str(record.get("court", "")),
            int(record.get("year", 0)),
            str(record.get("case_type", "")),
            str(record.get("text_content", "")),
        ),
    )


def normalise_record(raw: dict) -> dict:
    """Normalise column names from various source formats."""
    record = {}
    # id
    record["id"] = raw.get("id") or raw.get("doc_id") or raw.get("case_id") or ""
    # title
    record["title"] = raw.get("title") or raw.get("case_name") or raw.get("name") or ""
    # court
    record["court"] = raw.get("court") or raw.get("court_name") or ""
    # year
    year_raw = raw.get("year") or raw.get("decision_year") or raw.get("date", "0")
    try:
        record["year"] = int(str(year_raw)[:4])
    except (ValueError, TypeError):
        record["year"] = 0
    # case_type
    record["case_type"] = raw.get("case_type") or raw.get("category") or raw.get("type") or "Unknown"
    # text_content
    record["text_content"] = (
        raw.get("text_content")
        or raw.get("text")
        or raw.get("judgment_text")
        or raw.get("content")
        or ""
    )
    return record


# ─────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────

def load_csv(filepath: Path) -> list:
    records = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(dict(row))
    return records


def load_json(filepath: Path) -> list:
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        # Could be {judgments: [...]} or similar wrapper
        for key in ("judgments", "data", "results", "records"):
            if key in data and isinstance(data[key], list):
                return data[key]
        # Treat the dict itself as a single record
        return [data]
    else:
        raise ValueError(f"Unexpected JSON structure: {type(data)}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load external judgment CSV/JSON into CaseLens database."
    )
    parser.add_argument(
        "--file", required=True, help="Path to the input file (CSV or JSON)."
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        required=True,
        help="Format of the input file.",
    )
    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}")
        sys.exit(1)

    print(f"Loading {args.format.upper()} file: {filepath}")

    if args.format == "csv":
        raw_records = load_csv(filepath)
    else:
        raw_records = load_json(filepath)

    print(f"Found {len(raw_records)} records in input file.")

    # Normalise
    records = [normalise_record(r) for r in raw_records]

    # Filter out records with no id or no text
    valid = [r for r in records if r["id"] and r["text_content"]]
    skipped = len(records) - len(valid)
    if skipped:
        print(f"WARNING: Skipping {skipped} records missing id or text.")

    # Connect to DB and upsert
    print(f"Connecting to database: {DB_PATH}")
    if not DB_PATH.exists():
        print("Database not found. Initialising a new one ...")
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)

    inserted = 0
    errors = 0
    for rec in valid:
        try:
            upsert_judgment(conn, rec)
            inserted += 1
            if inserted % 100 == 0:
                print(f"  Inserted {inserted}/{len(valid)} records ...")
        except Exception as exc:
            print(f"  ERROR inserting record id={rec.get('id')}: {exc}")
            errors += 1

    conn.commit()
    conn.close()

    print(f"\nInserted {inserted} records ({errors} errors).")

    # Invalidate cached embedding index so it gets rebuilt on next app start
    if EMBEDDINGS_PATH.exists():
        EMBEDDINGS_PATH.unlink()
        print(f"Deleted stale embedding cache: {EMBEDDINGS_PATH}")
    if JUDGMENT_IDS_PATH.exists():
        JUDGMENT_IDS_PATH.unlink()
        print(f"Deleted stale embedding ID cache: {JUDGMENT_IDS_PATH}")

    print(
        "\nEmbedding index will be rebuilt automatically the next time "
        "the CaseLens application starts or a search is performed."
    )
    print("Done.")


if __name__ == "__main__":
    main()
