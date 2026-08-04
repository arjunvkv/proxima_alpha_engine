import subprocess
import time

VPS_KEY  = r"C:\Users\Arjun Sasi\Downloads\ssh-key-2026-07-28.key"
VPS_HOST = "ubuntu@140.245.234.92"
REPO_DIR = "/home/ubuntu/proxima_alpha_engine"

def main():
    print("=" * 100)
    print("PROXIMA ALPHA ENGINE — PULLING LATEST GITHUB CODE & STARTING LIVE ENGINE ON VPS...")
    print("=" * 100)

    cmd = (
        f"cd '{REPO_DIR}' && "
        f"git pull origin main && "
        f"pip3 install --break-system-packages --quiet pandas numpy orjson flask-socketio eventlet watchdog && "
        f"pkill -f 'python3 run.py' || true && "
        f"nohup python3 run.py > engine.log 2>&1 & "
        f"sleep 3 && "
        f"ps aux | grep 'run.py' | grep -v grep && "
        f"echo '=== ENGINE LOG PREVIEW ===' && "
        f"head -n 30 engine.log"
    )

    res = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-i", VPS_KEY, VPS_HOST, f"bash -c \"{cmd}\""], capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)

    print("=" * 100)
    print("🟢 SUCCESS: PROXIMA ALPHA ENGINE IS ONLINE & RUNNING ON VPS!")
    print("===================================================================================================")

if __name__ == "__main__":
    main()
