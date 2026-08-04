"""
Auto-Updater Service — Polls Git every 15s and:
  - Hot-reloads strategy modules instantly (no restart needed)
  - Full process self-restart via os.execv() when critical files change
    (run.py, telemetry/server.py, config/settings.py, engine/*.py)
nohup keeps the process alive through the self-restart transparently.
"""

import os
import sys
import time
import subprocess
import threading
import importlib
from pathlib import Path

# Files that require a full process restart (can't be hot-reloaded)
CRITICAL_FILES = {
    "run.py",
    "telemetry/server.py",
    "telemetry/templates/index.html",
    "telemetry/static/js/hud_app.js",
    "telemetry/static/css/obsidian_terminal.css",
    "config/settings.py",
    "engine/auto_updater.py",
    "engine/lock.py",
    "engine/risk_manager.py",
    "engine/execution_guard.py",
    "engine/mt5_bridge.py",
    "engine/tracker.py",
    "engine/evaluator.py",
}

# Modules that can be hot-reloaded without restart
HOT_RELOAD_MODULES = [
    "strategies.tokyo_h0",
    "strategies.ultra_monster",
    "strategies.cppf_z",
    "strategies.msv_asian",
    "strategies.ny_h21",
    "strategies.cpmc_z",
]


class AutoUpdater:
    def __init__(self, repo_dir, check_interval_sec=15):
        self.repo_dir = Path(repo_dir)
        self.check_interval_sec = check_interval_sec
        self.running = False
        self._thread = None

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        print("🟢 [AutoUpdater] Git Push Auto-Puller started (15s interval). Critical-file changes → full self-restart.")

    def stop(self):
        self.running = False

    def _changed_files(self):
        """Returns set of file paths changed by the last pull."""
        try:
            res = subprocess.run(
                ["git", "diff", "--name-only", "HEAD@{1}", "HEAD"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return set(res.stdout.strip().splitlines())
        except Exception:
            return set()

    def _poll_loop(self):
        while self.running:
            time.sleep(self.check_interval_sec)
            try:
                subprocess.run(["git", "fetch"], cwd=self.repo_dir, capture_output=True, text=True, timeout=10)
                res_status = subprocess.run(["git", "status", "-uno"], cwd=self.repo_dir, capture_output=True, text=True)

                if "Your branch is behind" not in res_status.stdout:
                    continue

                print("🚀 [AutoUpdater] New push detected on GitHub! Pulling...")
                subprocess.run(["git", "pull", "origin", "main"], cwd=self.repo_dir, capture_output=True, text=True)

                changed = self._changed_files()
                print(f"   Changed files: {', '.join(changed) or 'unknown'}")

                needs_restart = bool(changed & CRITICAL_FILES) or not changed
                if needs_restart:
                    print("🔄 [AutoUpdater] Critical file changed — performing full process self-restart in 2s...")
                    time.sleep(2)
                    self._self_restart()
                else:
                    self.hot_reload_strategies()

            except Exception as e:
                print(f"⚠️ [AutoUpdater] Poll error: {e}")

    def hot_reload_strategies(self):
        """Hot-reload strategy modules only (no downtime, no restart)."""
        print("🔄 [AutoUpdater] Hot-reloading strategy modules...")
        for mod_name in HOT_RELOAD_MODULES:
            if mod_name in sys.modules:
                try:
                    importlib.reload(sys.modules[mod_name])
                    print(f"  🟢 Hot-reloaded: {mod_name}")
                except Exception as e:
                    print(f"  ❌ Error hot-reloading {mod_name}: {e}")

    def _self_restart(self):
        """
        Replace this process with a fresh copy of itself.
        os.execv() swaps the process in-place — same PID group,
        nohup/logs stay alive, port is re-bound on the new startup.
        """
        print("♻️  [AutoUpdater] Self-restarting process now...")
        try:
            # Flush output before exec
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        os.execv(sys.executable, [sys.executable] + sys.argv)
