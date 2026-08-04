import subprocess

VPS_KEY  = r"C:\Users\Arjun Sasi\Downloads\ssh-key-2026-07-28.key"
VPS_HOST = "ubuntu@140.245.234.92"
REPO_URL = "https://github.com/arjunvkv/proxima_alpha_engine.git"
TARGET_DIR = "/home/ubuntu/proxima_alpha_engine"

def main():
    print("=" * 100)
    print("PROXIMA ALPHA ENGINE — CLONING REPOSITORY ON VPS FOR AUTO-PUSH DEPLOYMENT...")
    print("=" * 100)

    cmd = (
        f"if [ -d '{TARGET_DIR}' ]; then rm -rf '{TARGET_DIR}'; fi && "
        f"git clone '{REPO_URL}' '{TARGET_DIR}' && "
        f"cd '{TARGET_DIR}' && git status"
    )

    res = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-i", VPS_KEY, VPS_HOST, f"bash -c \"{cmd}\""], capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)

    print("=" * 100)
    print("🟢 SUCCESS: PROXIMA ALPHA ENGINE REPOSITORY INITIALIZED ON VPS!")
    print("===================================================================================================")

if __name__ == "__main__":
    main()
