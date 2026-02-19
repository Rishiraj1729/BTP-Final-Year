"""
database.py
-----------
SQLite-backed storage for:
  - prd_versions  : versioned PRD state
  - users         : simple name+role registry
  - discussions   : threaded chat per PRD
  - prd_shares    : admin → user share + approval workflow
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from state_schema import AgentState

DB_PATH = Path(__file__).resolve().parent / "prd_store.db"


class PRDDatabase:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS prd_versions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                version     INTEGER NOT NULL,
                project     TEXT,
                user_name   TEXT DEFAULT '',
                timestamp   TEXT,
                state_json  TEXT,
                prd_md      TEXT
            );

            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE NOT NULL,
                role        TEXT NOT NULL DEFAULT 'user',
                email       TEXT DEFAULT '',
                picture     TEXT DEFAULT '',
                created_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS discussions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                prd_id       INTEGER NOT NULL,
                sender_name  TEXT NOT NULL,
                sender_role  TEXT NOT NULL DEFAULT 'user',
                message      TEXT NOT NULL,
                timestamp    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prd_shares (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                prd_id      INTEGER NOT NULL,
                user_name   TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                note        TEXT DEFAULT '',
                shared_at   TEXT NOT NULL,
                responded_at TEXT
            );
        """)
        # Add user_name column to prd_versions if it doesn't exist (migration)
        try:
            self._conn.execute("ALTER TABLE prd_versions ADD COLUMN user_name TEXT DEFAULT ''")
        except Exception:
            pass
        self._conn.commit()

    # ── PRD versions ──────────────────────────────────────────────────────────

    def save(self, state: AgentState, user_name: str = "") -> int:
        if self._version_exists(state.version):
            state.version += 1
        ts = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO prd_versions (version, project, user_name, timestamp, state_json, prd_md) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (state.version, state.project_name, user_name,
             ts, json.dumps(state.to_dict()), state.prd_markdown),
        )
        self._conn.commit()
        return state.version

    def load(self, prd_id: int) -> AgentState:
        row = self._conn.execute(
            "SELECT state_json FROM prd_versions WHERE id = ?", (prd_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"PRD id={prd_id} not found.")
        return AgentState.from_dict(json.loads(row["state_json"]))

    def load_by_version(self, version: int) -> AgentState:
        row = self._conn.execute(
            "SELECT state_json FROM prd_versions WHERE version = ?", (version,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Version {version} not found.")
        return AgentState.from_dict(json.loads(row["state_json"]))

    def load_latest(self) -> Optional[AgentState]:
        row = self._conn.execute(
            "SELECT state_json FROM prd_versions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return AgentState.from_dict(json.loads(row["state_json"]))

    def list_all(self, user_name: Optional[str] = None) -> List[Dict[str, Any]]:
        if user_name:
            rows = self._conn.execute(
                "SELECT id, version, project, user_name, timestamp, state_json, prd_md "
                "FROM prd_versions WHERE user_name = ? ORDER BY id DESC",
                (user_name,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, version, project, user_name, timestamp, state_json, prd_md "
                "FROM prd_versions ORDER BY id DESC"
            ).fetchall()

        result = []
        for r in rows:
            entry: Dict[str, Any] = {
                "id": r["id"],
                "version": r["version"],
                "project_name": r["project"],
                "user_name": r["user_name"],
                "timestamp": r["timestamp"],
                "prd_md": (r["prd_md"] or "")[:200],  # preview only
            }
            try:
                d = json.loads(r["state_json"])
                entry["functional_count"] = len(d.get("functional", []))
                entry["nfr_count"] = len(d.get("non_functional", []))
                entry["completion"] = d.get("completion_status", {}).get("overall_score", 0)
            except Exception:
                entry["functional_count"] = 0
                entry["nfr_count"] = 0
                entry["completion"] = 0
            result.append(entry)
        return result

    def get_prd_full(self, prd_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT id, version, project, user_name, timestamp, prd_md, state_json "
            "FROM prd_versions WHERE id = ?", (prd_id,)
        ).fetchone()
        if not row:
            return None
        try:
            d = json.loads(row["state_json"])
        except Exception:
            d = {}
        return {
            "id": row["id"],
            "version": row["version"],
            "project_name": row["project"],
            "user_name": row["user_name"],
            "timestamp": row["timestamp"],
            "prd_md": row["prd_md"] or "",
            "functional": d.get("functional", []),
            "non_functional": d.get("non_functional", []),
        }

    def _version_exists(self, version: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM prd_versions WHERE version = ?", (version,)
        ).fetchone()
        return row is not None

    # ── Users ─────────────────────────────────────────────────────────────────

    def upsert_user(self, name: str, role: str,
                    email: str = "", picture: str = "") -> Dict[str, Any]:
        existing = self._conn.execute(
            "SELECT id, name, role, email, picture FROM users WHERE name = ?", (name,)
        ).fetchone()
        if existing:
            # Update email/picture if provided (Google re-login)
            if email or picture:
                self._conn.execute(
                    "UPDATE users SET email=COALESCE(NULLIF(?,''),email), "
                    "picture=COALESCE(NULLIF(?,''),picture) WHERE id=?",
                    (email, picture, existing["id"]),
                )
                self._conn.commit()
            return {
                "id":      existing["id"],
                "name":    existing["name"],
                "role":    existing["role"],
                "email":   email or existing["email"] or "",
                "picture": picture or existing["picture"] or "",
            }
        ts = datetime.now(timezone.utc).isoformat()
        # Migrate: add columns if they don't exist yet
        for col, default in [("email", "''"), ("picture", "''")]:
            try:
                self._conn.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT {default}")
            except Exception:
                pass
        cur = self._conn.execute(
            "INSERT INTO users (name, role, email, picture, created_at) VALUES (?,?,?,?,?)",
            (name, role, email, picture, ts),
        )
        self._conn.commit()
        return {"id": cur.lastrowid, "name": name, "role": role, "email": email, "picture": picture}

    def list_users(self, role: Optional[str] = None) -> List[Dict[str, Any]]:
        if role:
            rows = self._conn.execute(
                "SELECT id, name, role, created_at FROM users WHERE role = ? ORDER BY id",
                (role,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, name, role, created_at FROM users ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Discussions ───────────────────────────────────────────────────────────

    def add_message(self, prd_id: int, sender_name: str, sender_role: str, message: str) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO discussions (prd_id, sender_name, sender_role, message, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (prd_id, sender_name, sender_role, message, ts),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_discussion(self, prd_id: int) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, sender_name, sender_role, message, timestamp "
            "FROM discussions WHERE prd_id = ? ORDER BY id",
            (prd_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── PRD Shares ────────────────────────────────────────────────────────────

    def share_prd(self, prd_id: int, user_name: str, note: str = "") -> int:
        # Check if already shared
        existing = self._conn.execute(
            "SELECT id FROM prd_shares WHERE prd_id = ? AND user_name = ?",
            (prd_id, user_name),
        ).fetchone()
        if existing:
            self._conn.execute(
                "UPDATE prd_shares SET status='pending', note=?, shared_at=? WHERE id=?",
                (note, datetime.now(timezone.utc).isoformat(), existing["id"]),
            )
            self._conn.commit()
            return existing["id"]

        ts = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO prd_shares (prd_id, user_name, status, note, shared_at) "
            "VALUES (?, ?, 'pending', ?, ?)",
            (prd_id, user_name, note, ts),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_shares_for_user(self, user_name: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT s.id, s.prd_id, s.status, s.note, s.shared_at, s.responded_at,
                      p.project, p.user_name as owner, p.version, p.prd_md
               FROM prd_shares s
               JOIN prd_versions p ON p.id = s.prd_id
               WHERE s.user_name = ? ORDER BY s.id DESC""",
            (user_name,),
        ).fetchall()
        result = []
        for r in rows:
            result.append({
                "share_id": r["id"],
                "prd_id": r["prd_id"],
                "status": r["status"],
                "note": r["note"],
                "shared_at": r["shared_at"],
                "responded_at": r["responded_at"],
                "project_name": r["project"],
                "owner": r["owner"],
                "version": r["version"],
                "prd_preview": (r["prd_md"] or "")[:300],
            })
        return result

    def get_shares_for_prd(self, prd_id: int) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, user_name, status, note, shared_at, responded_at "
            "FROM prd_shares WHERE prd_id = ? ORDER BY id",
            (prd_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def respond_to_share(self, share_id: int, status: str, comment: str = "") -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE prd_shares SET status=?, note=?, responded_at=? WHERE id=?",
            (status, comment, ts, share_id),
        )
        self._conn.commit()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def __del__(self) -> None:
        self.close()
