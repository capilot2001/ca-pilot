"""SQLite adapter for the ``ClientRepository`` port (ADR-0007).

Migrated unchanged from v1 ``store.py`` (P5): the schema, SQL, seeding and the
in-place mutation of ``domain.config.COMPANY`` are byte-for-byte the v1 logic.
The only structural change is the shape — v1's module of functions becomes a
class behind the port, and the DB path is injected (by ``deps.py``) rather than
read from the environment here, so the composition root owns that one piece of
infra config (``settings.ledgerflow_db``).

sqlite3 is stdlib and the data is tiny (one row per client, written a handful
of times a day), so a connection is opened per call rather than pooled — that
sidesteps SQLite's thread affinity entirely, which matters because FastAPI runs
sync endpoints on a threadpool.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.domain.clients import fill_state_code as _fill_state_code
from app.domain.config import COMPANY, CompanyConfig, STATE_CODES
from app.domain.validate import validate_gstin
from app.ports.client_repository import DuplicateGSTIN

# Columns that mirror CompanyConfig, in the order the UI shows them.
FIELDS = ("name", "gstin", "state_code", "pan", "registration_type",
          "address", "pincode", "stock_enabled")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT    NOT NULL,
    gstin             TEXT    NOT NULL DEFAULT '',
    state_code        TEXT    NOT NULL DEFAULT '',
    pan               TEXT    NOT NULL DEFAULT '',
    registration_type TEXT    NOT NULL DEFAULT 'Regular',
    address           TEXT    NOT NULL DEFAULT '',
    pincode           TEXT    NOT NULL DEFAULT '',
    stock_enabled     INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL
);

-- One row per GSTIN: re-adding a client the office already has is a mistake,
-- not a second client. Partial so half-entered rows (no GSTIN yet) don't
-- collide with each other.
CREATE UNIQUE INDEX IF NOT EXISTS clients_gstin ON clients(gstin) WHERE gstin <> '';

CREATE TABLE IF NOT EXISTS app_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# helpers (pure — no DB / self state)
# ---------------------------------------------------------------------------
def _values(d: dict) -> tuple:
    d = _fill_state_code(d)
    return tuple(
        int(bool(d.get(f))) if f == "stock_enabled" else str(d.get(f) or "").strip()
        for f in FIELDS)


def _set_state(con: sqlite3.Connection, key: str, value: str) -> None:
    con.execute("INSERT INTO app_state(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def _row_to_dict(row: sqlite3.Row) -> Dict:
    d = _fill_state_code({f: row[f] for f in FIELDS})
    d["stock_enabled"] = bool(row["stock_enabled"])
    d["id"] = row["id"]
    d["state"] = STATE_CODES.get(d["state_code"], "")
    d["country"] = "India"
    ok, reason = validate_gstin(d["gstin"])
    d["gstin_valid"] = ok
    d["gstin_reason"] = reason
    d["updated_at"] = row["updated_at"]
    return d


def _apply_to_company(d: Dict) -> None:
    """Copy a stored row onto the process-wide COMPANY, in place.

    In place because config.COMPANY was imported by name into masters/exporters
    at module load; rebinding it here would leave them on the old object.
    """
    for f in FIELDS:
        setattr(COMPANY, f, d[f])


class SqliteClientRepo:
    """``ClientRepository`` backed by a single SQLite file at ``db_path``.

    The file lives wherever ``deps.py`` passes (``settings.ledgerflow_db``). On
    a host with an ephemeral filesystem — Cloud Run's writable layer is tmpfs —
    that points at a mounted volume, or the list dies with the instance
    (ADR-0007).
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self._db_path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def init(self) -> None:
        """Create the schema, seed the built-in client, and load the active one.

        Seeding uses whatever config.py's defaults / COMPANY_* env vars resolved to,
        so an existing single-client deployment keeps working with no data entry —
        its client is simply now row 1.
        """
        with self._connect() as con:
            con.executescript(_SCHEMA)
            empty = con.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 0
            if empty:
                seed = CompanyConfig()
                cur = con.execute(
                    f"INSERT INTO clients ({','.join(FIELDS)}, created_at, updated_at) "
                    f"VALUES ({','.join('?' * len(FIELDS))}, ?, ?)",
                    (*_values(seed.to_dict()), _now(), _now()))
                _set_state(con, "active_client_id", str(cur.lastrowid))
        self._load_active()

    def _load_active(self) -> None:
        d = self.get_active()
        if d:
            _apply_to_company(d)

    # -----------------------------------------------------------------------
    # queries
    # -----------------------------------------------------------------------
    def active_id(self) -> Optional[int]:
        with self._connect() as con:
            row = con.execute(
                "SELECT value FROM app_state WHERE key='active_client_id'").fetchone()
        return int(row["value"]) if row else None

    def get_active(self) -> Optional[Dict]:
        """The active client, falling back to the oldest row if the pointer is stale
        (the active client was deleted, or the DB was restored without app_state)."""
        with self._connect() as con:
            row = None
            state = con.execute(
                "SELECT value FROM app_state WHERE key='active_client_id'").fetchone()
            if state:
                row = con.execute("SELECT * FROM clients WHERE id=?",
                                  (int(state["value"]),)).fetchone()
            if row is None:
                row = con.execute("SELECT * FROM clients ORDER BY id LIMIT 1").fetchone()
                if row is not None:
                    _set_state(con, "active_client_id", str(row["id"]))
        return _row_to_dict(row) if row else None

    def get(self, client_id: int) -> Optional[Dict]:
        with self._connect() as con:
            row = con.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        return _row_to_dict(row) if row else None

    def search(self, q: str = "", limit: int = 200) -> List[Dict]:
        """Clients matching a free-text query on name, GSTIN or PAN.

        LIKE with an escaped pattern rather than FTS: the list is a few hundred rows
        at most, and the CA types a fragment of a name ("narsingh") or a GSTIN.
        """
        sql = "SELECT * FROM clients"
        args: tuple = ()
        q = (q or "").strip()
        if q:
            like = f"%{q.replace('!', '!!').replace('%', '!%').replace('_', '!_')}%"
            sql += (" WHERE name LIKE ? ESCAPE '!' OR gstin LIKE ? ESCAPE '!' "
                    "OR pan LIKE ? ESCAPE '!'")
            args = (like, like, like)
        sql += " ORDER BY name COLLATE NOCASE LIMIT ?"
        with self._connect() as con:
            rows = con.execute(sql, (*args, limit)).fetchall()
        return [_row_to_dict(r) for r in rows]

    # -----------------------------------------------------------------------
    # mutations
    # -----------------------------------------------------------------------
    def create(self, data: Dict, activate_it: bool = True) -> Dict:
        with self._connect() as con:
            try:
                cur = con.execute(
                    f"INSERT INTO clients ({','.join(FIELDS)}, created_at, updated_at) "
                    f"VALUES ({','.join('?' * len(FIELDS))}, ?, ?)",
                    (*_values(data), _now(), _now()))
            except sqlite3.IntegrityError as exc:
                raise DuplicateGSTIN(
                    f"A client with GSTIN {data.get('gstin')} already exists.") from exc
            new_id = int(cur.lastrowid)
            if activate_it:
                _set_state(con, "active_client_id", str(new_id))
        d = self.get(new_id)
        if activate_it and d:
            _apply_to_company(d)
        return d

    def update(self, client_id: int, data: Dict) -> Optional[Dict]:
        with self._connect() as con:
            try:
                cur = con.execute(
                    f"UPDATE clients SET {','.join(f + '=?' for f in FIELDS)}, updated_at=? "
                    f"WHERE id=?", (*_values(data), _now(), client_id))
            except sqlite3.IntegrityError as exc:
                raise DuplicateGSTIN(
                    f"Another client already has GSTIN {data.get('gstin')}.") from exc
            if not cur.rowcount:
                return None
        d = self.get(client_id)
        # Keep COMPANY in step when the row being edited is the one in use.
        if d and client_id == self.active_id():
            _apply_to_company(d)
        return d

    def activate(self, client_id: int) -> Optional[Dict]:
        d = self.get(client_id)
        if d is None:
            return None
        with self._connect() as con:
            _set_state(con, "active_client_id", str(client_id))
        _apply_to_company(d)
        return d

    def delete(self, client_id: int) -> bool:
        """Remove a client. The last remaining one is kept: COMPANY has to point
        somewhere, and an empty list would leave the app with no GSTIN to classify
        purchase-vs-sale against."""
        with self._connect() as con:
            if con.execute("SELECT COUNT(*) FROM clients").fetchone()[0] <= 1:
                return False
            cur = con.execute("DELETE FROM clients WHERE id=?", (client_id,))
            if not cur.rowcount:
                return False
        self._load_active()   # falls back to the oldest row if we just deleted the active one
        return True
