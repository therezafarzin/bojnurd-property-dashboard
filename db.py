import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from config import Config

SCHEMA = '''
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    title TEXT,
    district TEXT,
    district_raw TEXT,
    size_m2 REAL,
    total_price INTEGER,
    price_per_m2 REAL,
    year_built INTEGER,
    building_age INTEGER,
    rooms INTEGER,
    floor TEXT,
    has_elevator INTEGER,
    has_parking INTEGER,
    has_storage INTEGER,
    image_url TEXT,
    description TEXT,
    url TEXT,
    source TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_modified TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    duplicate_of TEXT,
    is_outlier INTEGER NOT NULL DEFAULT 0,
    detail_fetched_at TEXT,
    raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_listing_district ON listings(district);
CREATE INDEX IF NOT EXISTS idx_listing_active ON listings(active);
CREATE INDEX IF NOT EXISTS idx_listing_ppm ON listings(price_per_m2);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    total_price INTEGER,
    price_per_m2 REAL,
    UNIQUE(token, observed_at)
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    district TEXT NOT NULL,
    valid_count INTEGER NOT NULL,
    median_ppm REAL,
    q1_ppm REAL,
    q3_ppm REAL,
    new_build_median_ppm REAL,
    new_build_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS update_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    source TEXT,
    fetched_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    outlier_count INTEGER NOT NULL DEFAULT 0,
    detail_total INTEGER NOT NULL DEFAULT 0,
    detail_done INTEGER NOT NULL DEFAULT 0,
    detail_errors INTEGER NOT NULL DEFAULT 0,
    pages_done INTEGER NOT NULL DEFAULT 0,
    complete_coverage INTEGER NOT NULL DEFAULT 0,
    progress INTEGER NOT NULL DEFAULT 0,
    stage TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    message TEXT
);
'''

@contextmanager
def connect():
    Config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(Config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_columns(conn, table, columns):
    existing = {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Migration path from the earlier prototype, if its DB is copied over.
        _ensure_columns(conn, 'listings', {
            'district_raw': 'TEXT', 'floor': 'TEXT', 'has_storage': 'INTEGER',
            'image_url': 'TEXT', 'description': 'TEXT', 'detail_fetched_at': 'TEXT'
        })
        _ensure_columns(conn, 'update_runs', {
            'outlier_count': 'INTEGER NOT NULL DEFAULT 0',
            'detail_total': 'INTEGER NOT NULL DEFAULT 0',
            'detail_done': 'INTEGER NOT NULL DEFAULT 0',
            'detail_errors': 'INTEGER NOT NULL DEFAULT 0',
            'pages_done': 'INTEGER NOT NULL DEFAULT 0',
            'complete_coverage': 'INTEGER NOT NULL DEFAULT 0',
            'progress': 'INTEGER NOT NULL DEFAULT 0',
            'stage': 'TEXT'
        })


def now_iso():
    return datetime.now(timezone.utc).isoformat()
