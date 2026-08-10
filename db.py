"""
Persistent SQLite Database Engine for 'The Harvester'
Stores historical harvest runs and extracted contact leads permanently.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.resolve() / "harvest_history.db"

logger = logging.getLogger("HarvesterDB")


def _init_db_tables():
    """Initialize SQLite tables for persistent storage."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS harvest_runs (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                country TEXT NOT NULL,
                occupation TEXT NOT NULL,
                gender TEXT NOT NULL,
                requested_limit INTEGER NOT NULL,
                extracted_count INTEGER NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contact_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                name TEXT,
                occupation TEXT,
                gender TEXT,
                phone TEXT NOT NULL,
                country TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES harvest_runs(id)
            )
        """)
        conn.commit()


def save_harvest_run(run_id: str, country: str, occupation: str, gender: str, limit: int, records: list[dict]):
    """Save a harvest run and its extracted contact records into SQLite."""
    now_str = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO harvest_runs (id, timestamp, country, occupation, gender, requested_limit, extracted_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (run_id, now_str, country, occupation, gender, limit, len(records)))

        for rec in records:
            cursor.execute("""
                INSERT INTO contact_leads (run_id, name, occupation, gender, phone, country, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                rec.get("Name", "N/A"),
                rec.get("Occupation", occupation),
                rec.get("Gender (Inferred)", gender),
                rec.get("Phone Number", ""),
                rec.get("Country", country),
                now_str
            ))
        conn.commit()
        logger.info(f"Persisted harvest run {run_id} ({len(records)} records) to SQLite DB.")


def get_harvest_history(limit: int = 50) -> list[dict]:
    """Retrieve recent harvest runs from SQLite DB."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, country, occupation, gender, requested_limit, extracted_count
            FROM harvest_runs
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

# Initialize DB tables once on application startup.
_init_db_tables()
