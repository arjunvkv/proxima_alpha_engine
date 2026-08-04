"""
Single Instance Process Lock — Prevents duplicate engine instances from running simultaneously.
"""

import sys
import os
from pathlib import Path

LOCK_FILE = Path(__file__).resolve().parent.parent / "data" / "engine.lock"

class SingleInstanceLock:
    def __init__(self):
        self.lock_file = LOCK_FILE
        self.fp = None

    def acquire(self):
        """
        Acquires a process lock. If another instance is already running, exits immediately.
        """
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if os.name == 'nt':
                import msvcrt
                self.fp = open(self.lock_file, 'w')
                msvcrt.locking(self.fp.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                self.fp = open(self.lock_file, 'w')
                fcntl.flock(self.fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Write current process PID to lock file
            self.fp.write(str(os.getpid()))
            self.fp.flush()
            print(f"🔒 [SingleInstanceLock] Acquired process lock (PID #{os.getpid()}). Zero duplicate instances guaranteed.")
            return True
        except (IOError, OSError):
            print("🛑 [SingleInstanceLock] ERROR: Another instance of Proxima Alpha Engine is ALREADY RUNNING! Aborting duplicate start.")
            sys.exit(0)

    def release(self):
        try:
            if self.fp:
                if os.name == 'nt':
                    import msvcrt
                    self.fp.seek(0)
                    msvcrt.locking(self.fp.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fp.fileno(), fcntl.LOCK_UN)
                self.fp.close()
            if self.lock_file.exists():
                self.lock_file.unlink()
        except Exception:
            pass
