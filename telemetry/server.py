"""
Proxima Alpha Engine — Gaming UI Telemetry Server (Obsidian Terminal)
Serves the Obsidian Gaming UI at http://0.0.0.0:8888 and broadcasts all 6-strategy
live telemetry via SocketIO. Field names exactly match what hud_app.js expects.
Zero performance impact — decoupled daemon thread, no MT5 imports here.
"""

import time
import threading
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import deque
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO

import engine.db as db
HERE = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(HERE / "templates"),
    static_folder=str(HERE / "static")
)
app.config['SECRET_KEY'] = 'proxima_alpha_2026'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # No browser caching — always fresh CSS/JS
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ─── Shared Live State (written by run.py, read by broadcaster) ──────────────
_telemetry_state = {
    "active_positions": [],     # list of dicts from tracker.active_positions
    "closed_trades":    [],     # list of closed trade audit records
    "signals_today":    [],     # list of {strategy, pair, side, lot, time}
    "daily_pnl":        0.0,
    "daily_dd_pct":     0.0,
    "shield_ok":        True,
    "engine_status":    "OFFLINE",
    "connected":        False,
    "mt5_latency_ms":   None,
    "account_equity":   0.0,
    "account_balance":  0.0,
    "engine_logs":      deque(maxlen=200),  # raw log lines from engine
}

STRATEGY_META = {
    "tokyo_h0":     {"name": "Tokyo H0",       "type": "Asian Midnight Reversion",   "lot": 1.00, "h": 0,  "m": 0,  "hold_mins": 60,  "symbols": ["EURJPY", "USDJPY", "GBPJPY"]},
    "ultra_monster":{"name": "Ultra Monster",  "type": "Volatility Dislocation",     "lot": 1.20, "h": -1, "m": -1, "hold_mins": 15,  "symbols": ["EURAUD", "GBPAUD"]},
    "cppf_z":       {"name": "CPPF Z",          "type": "Cross-Pair Z≥6 Reversion",   "lot": 1.40, "h": -1, "m": -1, "hold_mins": 90,  "symbols": ["EURAUD", "GBPAUD"]},
    "msv_asian":    {"name": "MSV Asian",       "type": "FX Exhaustion Gate",         "lot": 1.00, "h": 0,  "m": 30, "hold_mins": 60,  "symbols": ["EURJPY", "GBPJPY"]},
    "ny_h21":       {"name": "NY H21",           "type": "NY Close JPY Reversion",    "lot": 1.50, "h": 21, "m": 0,  "hold_mins": 60,  "symbols": ["EURJPY", "GBPJPY"]},
    "cpmc_z":       {"name": "CPMC Z",           "type": "Cross-Momentum Dislocation","lot": 1.40, "h": -1, "m": -1, "hold_mins": 45,  "symbols": ["EURAUD", "GBPAUD", "EURNZD"]},
}

# ─── SQLite read cache (broadcaster fires 1x/sec; don't hammer SQLite 4x/sec) ─
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 5.0
_CACHE = {}

def _cached(name, builder):
    with _CACHE_LOCK:
        now = time.time()
        hit = _CACHE.get(name)
        if hit and now - hit[0] < _CACHE_TTL:
            return hit[1]
        val = builder()
        _CACHE[name] = (now, val)
        return val

def _cached_stats():
    return _cached("stats", _real_stats)

def _cached_trades(limit=20):
    def _build():
        return db.trades_by_range(limit=limit)
    return _cached(f"trades_{limit}", _build)

def _normalize_closed_trade(t):
    """Convert a SQLite trades row into a plain closed-trade record."""
    hold_min = 0
    try:
        fmt = "%Y-%m-%d %H:%M:%S"
        et = datetime.strptime(t.get("entry_time", ""), fmt)
        xt = datetime.strptime(t.get("exit_time", ""), fmt)
        hold_min = max(0, int(round((xt - et).total_seconds() / 60)))
    except Exception:
        pass
    net = float(t.get("net_pnl", 0.0))
    return {
        "ticket":       t.get("ticket"),
        "strategy":     t.get("strategy", "—"),
        "pair":         t.get("pair", "—"),
        "symbol":       t.get("pair", "—"),
        "side":         t.get("side", "BUY"),
        "type":         t.get("side", "BUY"),
        "lot":          float(t.get("lot", 0)),
        "entry_price":  float(t.get("entry_price", 0.0)),
        "exit_price":   float(t.get("exit_price", 0.0)),
        "pips":         float(t.get("pips", 0.0)),
        "net_pnl":      net,
        "is_win":       net >= 0,
        "entry_time":   t.get("entry_time", ""),
        "exit_time":    t.get("exit_time", ""),
        "hold_min":     hold_min,
    }

def update_telemetry(key, value):
    """Called by run.py to push live engine state into the telemetry bus."""
    _telemetry_state[key] = value

def push_engine_log(line: str):
    """Push a raw engine log line to the live console stream."""
    _telemetry_state["engine_logs"].append({
        "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
        "severity": _classify_log(line),
        "raw": line.strip()
    })

def _classify_log(line: str) -> str:
    upper = line.upper()
    if any(k in upper for k in ["❌", "ERROR", "FAIL", "EXCEPTION", "BLOCK"]):
        return "ERROR"
    if any(k in upper for k in ["🛑", "RISK", "SHIELD", "DD BREACH"]):
        return "WARN"
    if any(k in upper for k in ["🔥", "SIGNAL", "EXECUTE", "TICKET", "FILLED"]):
        return "INFO"
    return "DEBUG"

# ─── Payload Builders ─────────────────────────────────────────────────────────

def _countdown(h, m, now_utc):
    if h < 0:
        return None
    target = now_utc.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now_utc:
        target = target + timedelta(days=1)
    secs = (target - now_utc).total_seconds()
    return int(secs // 60), int(secs % 60), secs

def _build_imminent(now_utc):
    """Hero banner: next scheduled strategy to fire."""
    best_key, best_cfg, best_secs = None, None, float('inf')
    for key, cfg in STRATEGY_META.items():
        if cfg["h"] < 0:
            continue
        r = _countdown(cfg["h"], cfg["m"], now_utc)
        if r and r[2] < best_secs:
            best_secs = r[2]
            best_key, best_cfg = key, cfg

    if not best_cfg:
        best_cfg = list(STRATEGY_META.values())[0]
        best_secs = 3600
    mins = int(best_secs // 60)
    secs = int(best_secs % 60)

    h = now_utc.hour
    if 0 <= h < 7:
        regime = "Asian Session Active 🟡"
    elif 8 <= h < 12:
        regime = "London Open 🟢"
    elif 13 <= h < 17:
        regime = "New York Session 🔵"
    else:
        regime = "Compression Zone 🟠"

    st = _cached_stats().get(best_cfg["name"], {})
    target_win = st.get("avg_win") if st.get("n") else None

    return {
        "name":            best_cfg["name"],
        "regime":          regime,
        "countdown_formatted": f"{mins:02d}m {secs:02d}s",
        "next_symbol":     best_cfg["symbols"][0],
        "direction":       None,
        "confidence":      st.get("win_rate") if st.get("n") else None,
        "target_win_usd":  round(target_win, 2) if target_win else None,
    }

_last_valid_radar = None

def _build_radar():
    """Market radar metrics panel — REAL metrics from live MT5 snapshot with fallback caching.
    Ensures telemetry metrics never drop or reset to empty."""
    global _last_valid_radar
    real = _telemetry_state.get("real_radar")
    if real and isinstance(real, dict):
        _last_valid_radar = dict(real)
        return _last_valid_radar
    if _last_valid_radar:
        return _last_valid_radar
    return {
        "tick_velocity_per_sec":     0.0,
        "network_dispersion_pct":    50.0,
        "directional_agreement_pct": 50.0,
        "volatility_regime":         "COMPRESSION 🟠",
        "regime_description":        "Monitoring Live MT5 Stream",
        "blips":                     [],
        "real":                      True,
    }

def _real_stats():
    """Real per-strategy stats from the SQLite trade store (WR/PF/net/avg win/loss)."""
    try:
        return db.strategy_stats()
    except Exception:
        return {}

def _build_predictions(now_utc):
    """6-strategy card deck with live countdowns + REAL performance stats."""
    stats = _cached_stats()
    cards = []
    for key, cfg in STRATEGY_META.items():
        r = _countdown(cfg["h"], cfg["m"], now_utc)
        if r:
            mins, secs, total_secs = r
            countdown = f"{mins:02d}m {secs:02d}s"
            status = "IMMINENT" if total_secs < 300 else "SCHEDULED"
        else:
            countdown = "REAL-TIME"
            status = "MONITORING"

        st = stats.get(cfg["name"], {})
        n     = st.get("n", 0)
        wr    = st.get("win_rate") if n else None
        pf    = st.get("profit_factor") if n else None
        a_w   = st.get("avg_win", 0.0)
        a_l   = st.get("avg_loss", 0.0)

        avg_win_usd  = round(a_w, 2) if n else None
        avg_loss_usd = round(a_l, 2) if n else None

        cards.append({
            "name":            cfg["name"],
            "type":            cfg["type"],
            "status":          status,
            "countdown_formatted": countdown,
            "effective_lot":   cfg["lot"],
            "target_win_usd":  avg_win_usd,
            "target_loss_usd": avg_loss_usd,
            "next_symbol":     cfg["symbols"][0],
            "direction":       None,
            "win_rate":        wr,
            "profit_factor":   pf,
            "confidence":      wr,
            "real_trades":     n,
        })
    return cards

def _build_exposure():
    """Currency exposure table derived from active positions."""
    pos = _telemetry_state["active_positions"]
    eq  = _telemetry_state["account_equity"]

    exposure_map = {}
    for p in pos:
        pair = p.get("pair", "")
        lot  = float(p.get("lot", 0))
        side = p.get("side", "BUY").upper()
        if len(pair) >= 6:
            base, quote = pair[:3], pair[3:6]
            for ccy, sign in [(base, 1), (quote, -1)]:
                if ccy not in exposure_map:
                    exposure_map[ccy] = 0.0
                exposure_map[ccy] += sign * lot * (1 if side == "BUY" else -1)

    rows = []
    for ccy, net_lots in exposure_map.items():
        direction = "LONG" if net_lots > 0 else "SHORT"
        notional   = abs(net_lots) * 100_000
        exp_usd    = round(notional * 0.0001 * (eq / 100_000 if eq else 1.0), 2)
        rows.append({
            "currency":           ccy,
            "direction":          direction,
            "net_exposure_lots":  round(abs(net_lots), 2),
            "exposure_usd":       round(exp_usd, 2),
            "risk_pct":           round(notional / max(eq, 1) * 100, 2),
        })

    return rows

def _build_risk():
    """Real daily risk payload: equity, daily PnL, DD%, shield status."""
    ts = _telemetry_state
    eq = ts["account_equity"]
    dd = ts["daily_dd_pct"]
    limit = 4.5
    return {
        "equity":          round(eq, 2),
        "balance":         round(ts["account_balance"], 2),
        "daily_pnl":       round(ts["daily_pnl"], 2),
        "daily_dd_pct":    round(dd, 3),
        "daily_limit_pct": limit,
        "daily_limit_usd": round(eq * (limit / 100), 2),
        "shield_active":   dd < limit,
    }

def _build_mt5_telemetry():
    """Active trades + closed audit records for the UI tables."""
    ts = _telemetry_state
    active_trades = []
    for p in ts["active_positions"]:
        active_trades.append({
            "ticket":      p.get("ticket", "—"),
            "entry_time":  p.get("entry_time", "—"),
            "strategy":    p.get("strategy", "—"),
            "symbol":      p.get("pair", "—"),
            "type":        p.get("side", "BUY"),
            "lot":         float(p.get("lot", 0)),
            "entry_price": p.get("entry_price", 0.0),
            "exit_price":  p.get("exit_price", 0.0),
            "pips":        p.get("pips", 0),
            "net_pnl":     float(p.get("net_pnl", 0)),
            "hold_min":    int(p.get("bars_held", 0)) * 5,
        })

    # Real closed trades from the SQLite store (fallback when auditor buffer empty)
    closed = list(ts["closed_trades"][-20:]) or _cached_trades(limit=20)
    closed_norm = [_normalize_closed_trade(t) for t in closed]

    return {
        "connected":      ts["connected"],
        "engine_status":  ts["engine_status"],
        "latency_ms":     ts["mt5_latency_ms"],
        "trades":         (closed_norm + active_trades)[-20:],
        "active_count":   len(ts["active_positions"]),
    }

def _build_health():
    """Deployment health payload: git SHA, uptime, RPyC latency, last engine errors."""
    ts = _telemetry_state
    sha = db.get_meta("git_sha", "unknown")
    started = db.get_meta("started_at")
    uptime_s = 0
    if started:
        try:
            uptime_s = int(time.time() - datetime.strptime(started, "%Y-%m-%d %H:%M:%S").timestamp())
        except Exception:
            uptime_s = 0
    last_errors = [e for e in reversed(list(ts["engine_logs"])) if e.get("severity") == "ERROR"][:5]
    return {
        "git_sha":          sha,
        "uptime_s":         uptime_s,
        "uptime_formatted": f"{uptime_s // 3600}h {uptime_s % 3600 // 60}m" if uptime_s else "—",
        "rpyc_latency_ms":  ts["mt5_latency_ms"],
        "engine_status":    ts["engine_status"],
        "connected":        ts["connected"],
        "last_errors":      last_errors,
    }

BADGE_META = {
    "trades_10":          {"name": "First Dozen",      "icon": "fa-fire",       "desc": "10 trades closed"},
    "trades_100":         {"name": "Century Club",     "icon": "fa-medal",      "desc": "100 trades closed"},
    "streak10_overall":   {"name": "Unstoppable",      "icon": "fa-bolt",       "desc": "10-win streak"},
    "daily_5wins":        {"name": "Five Alive",       "icon": "fa-dice-five",  "desc": "5 wins in a day"},
    "single_500_day_trade":{"name": "Big Game Hunter", "icon": "fa-fish-fins",  "desc": "+$500 single trade"},
}
BADGE_PREFIX = "streak5_"

def _level_for_xp(xp):
    """Level curve: level = floor(sqrt(xp/50)) + 1. L1 @0, L2 @50, L3 @200, L4 @450..."""
    lvl = int((xp / 50.0) ** 0.5) + 1 if xp > 0 else 1
    lo = 50 * (lvl - 1) ** 2
    hi = 50 * lvl ** 2
    pct = round((xp - lo) / max(hi - lo, 1) * 100, 1)
    return lvl, pct, hi

def _build_game_state():
    """Game layer payload: XP, level, streaks, badges (persisted in SQLite)."""
    xp = db.get_streak("xp")
    overall = db.get_streak("streak_overall")
    lvl, pct, next_xp = _level_for_xp(xp)

    per_strategy = {}
    for key, cfg in STRATEGY_META.items():
        per_strategy[cfg["name"]] = db.get_streak(f"streak_{cfg['name']}")

    badges = []
    unlocked = {a["key"] for a in db.achievements()}
    for key, meta in BADGE_META.items():
        badges.append({
            "key": key, "name": meta["name"], "icon": meta["icon"],
            "desc": meta["desc"], "unlocked": key in unlocked,
        })
    # Dynamic per-strategy 5-streak badges
    for key, cfg in STRATEGY_META.items():
        bkey = BADGE_PREFIX + cfg["name"]
        badges.append({
            "key": bkey, "name": f"{cfg['name']} Prodigy", "icon": "fa-crown",
            "desc": f"5-win streak on {cfg['name']}", "unlocked": bkey in unlocked,
        })

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sessions = db.daily_sessions(limit=7)
    return {
        "xp":               xp,
        "level":            lvl,
        "level_progress_pct": pct,
        "xp_to_next":       next_xp,
        "streak_overall":   overall,
        "streaks":          per_strategy,
        "badges":           badges,
        "badges_unlocked":  sum(1 for b in badges if b["unlocked"]),
        "badges_total":     len(badges),
        "today":            today,
        "week_sessions":    sessions,
    }

def _build_ticker():
    """Live market ticker marquee — latest closed trades + signals from the store."""
    items = []
    for t in db.trades_by_range(limit=12):
        items.append({
            "kind": "TRADE",
            "symbol": t.get("pair", ""),
            "side": t.get("side", "BUY"),
            "pnl": round(t.get("net_pnl", 0.0), 2),
        })
    for s in db.signals_since_midnight(datetime.now(timezone.utc).strftime("%Y-%m-%d")):
        items.append({
            "kind": "SIGNAL",
            "symbol": s.get("pair", ""),
            "side": s.get("side", "BUY"),
            "strategy": s.get("strategy", ""),
        })
    if not items:
        items = [{"kind": "BOOT", "symbol": "PROXIMA", "side": "ONLINE", "strategy": "Awaiting first live events"}]
    return items[:40]

def _build_vps_logs():
    """Return last 50 engine log lines."""
    return list(_telemetry_state["engine_logs"])[-50:]

def _build_performance():
    """Honest live performance payload from the SQLite store: real TODAY and
    ALL-TIME aggregates + the equity series. No fake rolling/backtest framing."""
    stats = _cached_stats()

    # Real today (closed trades with entry_time today)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    t_rows = db.trades_for_day(today)
    t_n    = len(t_rows)
    t_wins = sum(1 for t in t_rows if t["net_pnl"] > 0)
    t_pnl  = round(sum(t["net_pnl"] for t in t_rows), 2)
    t_wr   = round(t_wins / t_n * 100, 1) if t_n else 0.0

    # Real all-time aggregates across all strategies with closed trades
    n_total = sum(s["n"] for s in stats.values())
    wins    = sum(s["wins"] for s in stats.values())
    net     = sum(s["net_pnl"] for s in stats.values())
    gw = sum(s["avg_win"] * s["wins"] for s in stats.values())
    gl = sum(s["avg_loss"] * (s["n"] - s["wins"]) for s in stats.values())

    wr = round(wins / n_total * 100, 1) if n_total else 0.0
    pf = round(gw / gl, 2) if gl > 0 else (99.99 if gw > 0 else 0.0)

    # Real last-30d equity series for the chart
    eq_series = []
    try:
        for snap in db.equity_series(limit=1500):
            eq_series.append({"ts": snap["ts"], "equity": snap["equity"], "balance": snap["balance"]})
    except Exception:
        pass

    trades = list(_telemetry_state["closed_trades"][-20:]) or _cached_trades(limit=20)
    trades_norm = [_normalize_closed_trade(t) for t in trades]

    return {
        "today":    {"win_rate_percent": t_wr, "net_pnl_usd": t_pnl, "total_trades": t_n, "wins": t_wins},
        "all_time": {"win_rate_percent": wr, "net_pnl_usd": round(net, 2), "total_trades": n_total, "profit_factor": pf},
        "trades":   trades_norm,
        "equity_series": eq_series[-500:],
    }

# ─── Flask Routes ─────────────────────────────────────────────────────────────

@app.route('/')
def page_overview():
    return render_template('index.html', active_page='overview')

@app.route('/logs')
@app.route('/vps-logs')
def page_logs():
    return render_template('logs.html', active_page='logs')

@app.route('/risk')
@app.route('/analytics')
@app.route('/rolling-backtest')
@app.route('/yesterday-summary')
def page_risk():
    return render_template('risk.html', active_page='risk')

@app.route('/trades')
@app.route('/positions')
@app.route('/signals')
def page_trades():
    return render_template('trades.html', active_page='trades')

@app.route('/api/predictive_radar')
def api_predictive_radar():
    now_utc = datetime.now(timezone.utc)
    eq = _telemetry_state["account_equity"]
    return jsonify({
        "predictions":    _build_predictions(now_utc),
        "radar":          _build_radar(),
        "imminent":       _build_imminent(now_utc),
        "exposure":       _build_exposure(),
        "mt5_telemetry":  _build_mt5_telemetry(),
        "risk":           _build_risk(),
        "vps_logs":       _build_vps_logs(),
        "performance":    _build_performance(),
        "signals_today":  _telemetry_state["signals_today"],
        "health":         _build_health(),
        "game":           _build_game_state(),
        "ticker":         _build_ticker(),
        "timestamp":      datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "config": {
            "account_size":    int(eq),
            "daily_limit_usd": round(eq * 0.045, 0),
        }
    })

# ─── Background SocketIO Broadcaster ─────────────────────────────────────────

def _background_broadcaster():
    print("🟢 [Telemetry] Obsidian Gaming UI SocketIO broadcaster active (1s pulse)...")
    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            eq = _telemetry_state["account_equity"]
            socketio.emit('radar_update', {
                "predictions":    _build_predictions(now_utc),
                "radar":          _build_radar(),
                "imminent":       _build_imminent(now_utc),
                "exposure":       _build_exposure(),
                "mt5_telemetry":  _build_mt5_telemetry(),
                "risk":           _build_risk(),
                "vps_logs":       _build_vps_logs(),
                "performance":    _build_performance(),
                "signals_today":  _telemetry_state["signals_today"],
                "health":         _build_health(),
                "game":           _build_game_state(),
                "ticker":         _build_ticker(),
                "timestamp":      now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "config": {
                    "account_size":    int(eq),
                    "daily_limit_usd": round(eq * 0.045, 0),
                }
            })
        except Exception:
            pass
        time.sleep(1.0)

# ─── Public Entry Point (called by run.py) ────────────────────────────────────

from werkzeug.serving import make_server

def start_telemetry_server(port=8888):
    """Start the Gaming UI server on a non-blocking daemon thread. No MT5 imports."""
    threading.Thread(target=_background_broadcaster, daemon=True).start()

    def _serve():
        for p in range(port, port + 10):
            try:
                server = make_server('0.0.0.0', p, app, threaded=True)
                print(f"🟢 [Telemetry] Obsidian Gaming UI → http://0.0.0.0:{p}")
                server.serve_forever()
                break
            except Exception as e:
                print(f"⚠️ [Telemetry] Port {p} unavailable ({e}), trying {p+1}...")
                continue

    threading.Thread(target=_serve, daemon=True).start()
