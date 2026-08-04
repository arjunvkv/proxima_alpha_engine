import subprocess

VPS_KEY  = r"C:\Users\Arjun Sasi\Downloads\ssh-key-2026-07-28.key"
VPS_HOST = "ubuntu@140.245.234.92"
REPO_DIR = "/home/ubuntu/proxima_alpha_engine"

def main():
    cmd = f"cat {REPO_DIR}/engine.log"
    res = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-i", VPS_KEY, VPS_HOST, f"bash -c \"{cmd}\""], capture_output=True, text=True)
    print("=" * 100)
    print("PROXIMA ALPHA ENGINE LOGS ON VPS:")
    print("=" * 100)
    print(res.stdout)
    print(res.stderr)
    print("=" * 100)

if __name__ == "__main__":
    main()
