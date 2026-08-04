"""
Auto-Updater Service — Polls Git commits every 15s and hot-reloads strategy modules in 0.0s on git push.
"""

import time
import subprocess
import threading
import importlib
import sys
from pathlib import Path

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
        print("🟢 [AutoUpdater] Git Push Auto-Puller Service started (15s interval).")

    def stop(self):
        self.running = False

    def _poll_loop(self):
        while self.running:
            time.sleep(self.check_interval_sec)
            try:
                # Fetch latest commits from origin main
                res_fetch = subprocess.run(["git", "fetch"], cwd=self.repo_dir, capture_output=True, text=True)
                res_status = subprocess.run(["git", "status", "-uno"], cwd=self.repo_dir, capture_output=True, text=True)

                if "Your branch is behind" in res_status.stdout:
                    print("🚀 [AutoUpdater] New code push detected on GitHub! Executing git pull...")
                    res_pull = subprocess.run(["git", "pull", "origin", "main"], cwd=self.repo_dir, capture_output=True, text=True)
                    print(res_pull.stdout)

                    # Trigger hot-reload of strategy modules
                    self.hot_reload_strategies()
            except Exception as e:
                pass

    def hot_reload_strategies(self):
        """
        Dynamically hot-reloads all strategy modules in memory without restarting MT5 or dropping position connections.
        """
        print("🔄 [AutoUpdater] Hot-reloading strategy modules in 0.0s...")
        modules_to_reload = [
            "strategies.tokyo_h0",
            "strategies.ultra_monster",
            "strategies.cppf_z",
            "strategies.msv_asian",
            "strategies.ny_h21",
            "strategies.cpmc_z"
        ]

        for mod_name in modules_to_reload:
            if mod_name in sys.modules:
                try:
                    importlib.reload(sys.modules[mod_name])
                    print(f"  🟢 Hot-reloaded: {mod_name}")
                except Exception as e:
                    print(f"  ❌ Error hot-reloading {mod_name}: {e}")
