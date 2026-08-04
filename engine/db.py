"""
Proxima Alpha Engine — SQLite Persistence Store (Real Data Backbone)
Persists trades, equity snapshots, daily sessions, signals, achievements & streaks
so the dashboard reflects reality across restarts. Zero MT5 imports — safe everywhere.
"""

import os
import json
import sqlite3
import threading
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "proxima.db"

_LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id    INTEGER UNIQUE,
    ticket         INTEGER,
    strategy       TEXT,
    pair           TEXT,
    side           TEXT,
    lot            REAL,
    magic          INTEGER,
    entry_time     TEXT,
    exit_time      TEXT,
    entry_price    REAL,
    exit_price     REAL,
    pips           REAL,
    net_pnl        REAL,
    r_multiple     REAL,
    exit_reason    TEXT,
    is_live        INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS equity_snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT,
    equity     REAL,
    balance    REAL,
    floating   REAL
);
CREATE TABLE IF NOT EXISTS daily_sessions (
    day            TEXT PRIMARY KEY,
    start_equity   REAL,
    end_equity     REAL,
    pnl            REAL,
    dd_pct         REAL,
    trades         INTEGER,
    wins           INTEGER
);
CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy    TEXT,
    pair        TEXT,
    side        TEXT,
    lot         REAL,
    time_utc    TEXT,
    executed    INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS achievements (
    key         TEXT PRIMARY KEY,
    unlocked_at TEXT,
    value       REAL
);
CREATE TABLE IF NOT EXISTS streaks (
    key         TEXT PRIMARY KEY,
    value       INTEGER,
    updated_at  TEXT
);
CREATE TABLE IF NOT EXISTS engine_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT
);
"""

def _migrate_legacy_trades(conn):
    """Migrate the pre-Aug-2026 schema (ticket INTEGER PRIMARY KEY, no position_id).

    Partial closes create multiple MT5 deals under the same position_id; the old
    schema keyed rows by position ticket, so a partial close overwrote the row and
    lost the individual deal prices. New schema: autoincrement id + UNIQUE
    position_id so each position keeps exactly one reconciled row.
    """
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()]
    except Exception:
        return
    if cols and "position_id" in cols:
        return  # already migrated
    try:
        conn.execute("ALTER TABLE trades RENAME TO trades_legacy")
        conn.executescript("""
            CREATE TABLE trades (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id    INTEGER UNIQUE,
                ticket         INTEGER,
                strategy       TEXT,
                pair           TEXT,
                side           TEXT,
                lot            REAL,
                magic          INTEGER,
                entry_time     TEXT,
                exit_time      TEXT,
                entry_price    REAL,
                exit_price     REAL,
                pips           REAL,
                net_pnl        REAL,
                r_multiple     REAL,
                exit_reason    TEXT,
                is_live        INTEGER DEFAULT 1
            );
            INSERT INTO trades (position_id, ticket, strategy, pair, side, lot, magic,
                                entry_time, exit_time, entry_price, exit_price, pips,
                                net_pnl, r_multiple, exit_reason, is_live)
            SELECT ticket, ticket, strategy, pair, side, lot, magic,
                   entry_time, exit_time, entry_price, exit_price, pips,
                   net_pnl, r_multiple, exit_reason, is_live
            FROM trades_legacy;
            DROP TABLE trades_legacy;
        """)
        conn.commit()
        print("🔄 [DB] Migrated trades table to position_id schema.")
    except Exception as e:
        print(f"⚠️ [DB] trades migration skipped: {e}")

def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Idempotent schema creation + legacy migration. Called once at engine startup."""
    with _LOCK:
        conn = _connect()
        try:
            conn.executescript(SCHEMA)
            _migrate_legacy_trades(conn)
            conn.commit()
        finally:
            conn.close()

def now_utc_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

# ─── Trades ──────────────────────────────────────────────────────────────────

def upsert_trade(trade: dict):
    """Insert or replace a trade record keyed by position_id (autoincrement id)."""
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """INSERT INTO trades
                   (position_id, ticket, strategy, pair, side, lot, magic, entry_time, exit_time,
                    entry_price, exit_price, pips, net_pnl, r_multiple, exit_reason, is_live)
                   VALUES (:position_id, :ticket, :strategy, :pair, :side, :lot, :magic, :entry_time, :exit_time,
                    :entry_price, :exit_price, :pips, :net_pnl, :r_multiple, :exit_reason, :is_live)
                   ON CONFLICT(position_id) DO UPDATE SET
                    ticket=excluded.ticket, strategy=excluded.strategy, pair=excluded.pair,
                    side=excluded.side, lot=excluded.lot, magic=excluded.magic,
                    entry_time=excluded.entry_time, exit_time=excluded.exit_time,
                    entry_price=excluded.entry_price, exit_price=excluded.exit_price,
                    pips=excluded.pips, net_pnl=excluded.net_pnl, r_multiple=excluded.r_multiple,
                    exit_reason=excluded.exit_reason, is_live=excluded.is_live""",
                trade,
            )
            conn.commit()
        finally:
            conn.close()

def trades_by_range(limit=200, offset=0):
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM trades WHERE is_live=1 ORDER BY entry_time DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

def trades_since_day(day_str="1970-01-01"):
    """All trades whose entry_time falls on/after a given YYYY-MM-DD."""
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM trades WHERE is_live=1 AND entry_time >= ? ORDER BY entry_time ASC",
                (day_str,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

def trades_for_day(day_str):
    """Trades whose entry_time starts with a YYYY-MM-DD prefix."""
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM trades WHERE is_live=1 AND entry_time LIKE ? ORDER BY entry_time ASC",
                (day_str + "%",),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

def closed_trade_count():
    with _LOCK:
        conn = _connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM trades WHERE is_live=1 AND exit_time IS NOT NULL").fetchone()[0]
        finally:
            conn.close()

def strategy_stats():
    """Real per-strategy win-rate / PF / net PnL from closed live trades."""
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                """SELECT strategy,
                          COUNT(*) AS n,
                          SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) AS wins,
                          SUM(net_pnl) AS net_pnl,
                          SUM(CASE WHEN net_pnl > 0 THEN net_pnl ELSE 0 END) AS gross_win,
                          SUM(CASE WHEN net_pnl <= 0 THEN -net_pnl ELSE 0 END) AS gross_loss
                   FROM trades
                   WHERE is_live=1 AND exit_time IS NOT NULL
                   GROUP BY strategy ORDER BY net_pnl DESC"""
            ).fetchall()
            out = {}
            for r in rows:
                n = r["n"] or 0
                wins = r["wins"] or 0
                gw = r["gross_win"] or 0.0
                gl = r["gross_loss"] or 0.0
                out[r["strategy"]] = {
                    "n": n,
                    "wins": wins,
                    "win_rate": round(wins / n * 100, 1) if n else 0.0,
                    "net_pnl": round(r["net_pnl"] or 0.0, 2),
                    "profit_factor": round(gw / gl, 2) if gl > 0 else (99.99 if gw > 0 else 0.0),
                    "avg_win": round(gw / wins, 2) if wins else 0.0,
                    "avg_loss": round(gl / (n - wins), 2) if (n - wins) else 0.0,
                }
            return out
        finally:
            conn.close()

# ─── Equity snapshots ────────────────────────────────────────────────────────

def append_equity(equity, balance, floating=0.0):
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO equity_snapshots (ts, equity, balance, floating) VALUES (?,?,?,?)",
                (now_utc_str(), float(equity), float(balance), float(floating)),
            )
            conn.commit()
        finally:
            conn.close()

def equity_series(limit=2000):
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT ts, equity, balance, floating FROM equity_snapshots ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()

# ─── Daily sessions ──────────────────────────────────────────────────────────

def upsert_daily_session(day, start_equity, end_equity, pnl, dd_pct, trades, wins):
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO daily_sessions
                   (day, start_equity, end_equity, pnl, dd_pct, trades, wins)
                   VALUES (?,?,?,?,?,?,?)""",
                (day, start_equity, end_equity, pnl, dd_pct, trades, wins),
            )
            conn.commit()
        finally:
            conn.close()

def daily_sessions(limit=90):
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM daily_sessions ORDER BY day DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

# ─── Signals ─────────────────────────────────────────────────────────────────

def insert_signal(strategy, pair, side, lot, time_utc, executed=1):
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO signals (strategy, pair, side, lot, time_utc, executed) VALUES (?,?,?,?,?,?)",
                (strategy, pair, side, lot, time_utc, executed),
            )
            conn.commit()
        finally:
            conn.close()

def signals_since_midnight(midnight_str):
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM signals WHERE time_utc >= ? ORDER BY id DESC LIMIT 50",
                (midnight_str,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

# ─── Achievements & streaks (game state) ────────────────────────────────────

def unlock_achievement(key):
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO achievements (key, unlocked_at, value) VALUES (?,?,1)",
                (key, now_utc_str()),
            )
            conn.commit()
        finally:
            conn.close()

def achievements():
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute("SELECT key, unlocked_at FROM achievements ORDER BY unlocked_at").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

def get_streak(key):
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute("SELECT value FROM streaks WHERE key=?", (key,)).fetchone()
            return int(row["value"]) if row else 0
        finally:
            conn.close()

def set_streak(key, value):
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO streaks (key, value, updated_at) VALUES (?,?,?)",
                (key, int(value), now_utc_str()),
            )
            conn.commit()
        finally:
            conn.close()

# ─── Meta ────────────────────────────────────────────────────────────────────

def set_meta(key, value):
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO engine_meta (key, value) VALUES (?,?)",
                (key, str(value)),
            )
            conn.commit()
        finally:
            conn.close()

def get_meta(key, default=None):
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute("SELECT value FROM engine_meta WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default
        finally:
            conn.close()
