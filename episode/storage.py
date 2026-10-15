"""Project-owned storage and transactional catalog."""

import os, json, sqlite3, hashlib
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(os.environ.get("EPISODE_STORAGE", "/Volumes/External Storage/Episode"))
REVISION = "f641879e22172be7e8161d5e6c1503c2d2feb657"
REPO = "lerobot/svla_so101_pickplace"


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def root():
    if not (ROOT / ".episode-storage").is_file():
        raise RuntimeError(
            "Episode storage is unavailable. Mount the configured drive; no replacement directory was created."
        )
    return ROOT


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, repository TEXT, revision TEXT, info TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS assets(path TEXT PRIMARY KEY, sha256 TEXT, bytes INTEGER, source TEXT);
CREATE TABLE IF NOT EXISTS episodes(id INTEGER PRIMARY KEY, source TEXT, metadata TEXT, task TEXT, duration REAL, samples INTEGER, family TEXT);
CREATE TABLE IF NOT EXISTS findings(id INTEGER PRIMARY KEY, episode INTEGER, rule TEXT, severity TEXT, start REAL, end REAL, observed TEXT, threshold TEXT, explanation TEXT, fixture INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, kind TEXT, args TEXT, state TEXT, stage TEXT, completed INTEGER DEFAULT 0, total INTEGER DEFAULT 0, error TEXT, created TEXT, updated TEXT, cancel INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, episode INTEGER, status TEXT, outcome TEXT, reason TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS annotations(id INTEGER PRIMARY KEY, episode INTEGER, start REAL, end REAL, label TEXT, note TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS selections(id INTEGER PRIMARY KEY, name TEXT, criteria TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY, name TEXT, manifest TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS validation_runs(id TEXT PRIMARY KEY, job TEXT, config TEXT, result TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS verifications(id INTEGER PRIMARY KEY, version TEXT, result TEXT, created TEXT);
"""

SCHEMA += "\nCREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY, episode INTEGER NOT NULL, mode TEXT NOT NULL, result TEXT NOT NULL, created TEXT NOT NULL);\nCREATE TABLE IF NOT EXISTS suggestions(id TEXT PRIMARY KEY, analysis TEXT NOT NULL REFERENCES analyses(id), episode INTEGER NOT NULL, body TEXT NOT NULL);\nCREATE TABLE IF NOT EXISTS suggestion_decisions(id INTEGER PRIMARY KEY, suggestion TEXT UNIQUE NOT NULL REFERENCES suggestions(id), decision TEXT NOT NULL, reason TEXT NOT NULL, annotation INTEGER REFERENCES annotations(id), created TEXT NOT NULL);\n"


def connect():
    db = sqlite3.connect(root() / "runtime/catalog.sqlite", timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    return db


def rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]


def source_root():
    return root() / "sources" / REVISION
