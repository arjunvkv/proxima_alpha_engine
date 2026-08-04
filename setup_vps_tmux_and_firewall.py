import subprocess

VPS_KEY  = r"C:\Users\Arjun Sasi\Downloads\ssh-key-2026-07-28.key"
VPS_HOST = "ubuntu@140.245.234.92"
REPO_DIR = "/home/ubuntu/proxima_alpha_engine"

def main():
    print("=" * 100)
    print("PROXIMA ALPHA ENGINE — CONFIGURING FIREWALL & TMUX LIVE TERMINAL ON VPS...")
    print("=" * 100)

    cmd = (
        f"sudo ufw allow 8888/tcp || true && "
        f"sudo iptables -A INPUT -p tcp --dport 8888 -j ACCEPT || true && "
        f"sudo apt-get update -qq && sudo apt-get install -y -qq tmux && "
        f"cd '{REPO_DIR}' && git pull origin main && "
        f"pkill -f 'python3 run.py' || true && "
        f"tmux kill-session -t proxima_engine 2>/dev/null || true && "
        f"tmux new-session -d -s proxima_engine 'python3 run.py' && "
        f"sleep 2 && "
        f"tmux capture-pane -pt proxima_engine"
    )

    res = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-i", VPS_KEY, VPS_HOST, f"bash -c \"{cmd}\""], capture_output=True, text=True)
    print("=" * 100)
    print("VPS LIVE TERMINAL OUTPUT (TMUX PROXIMA_ENGINE):")
    print("=" * 100)
    print(res.stdout)
    print(res.stderr)
    print("=" * 100)

if __name__ == "__main__":
    main()
