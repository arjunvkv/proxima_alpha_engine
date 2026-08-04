import subprocess

VPS_KEY  = r"C:\Users\Arjun Sasi\Downloads\ssh-key-2026-07-28.key"
VPS_HOST = "ubuntu@140.245.234.92"

def main():
    print("=" * 100)
    print("PROXIMA ALPHA ENGINE — CHECKING WINE PYTHON ENVIRONMENT ON VPS...")
    print("=" * 100)

    cmd = (
        "find /home/ubuntu/.wine/ -name 'python.exe' 2>/dev/null"
    )

    res = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-i", VPS_KEY, VPS_HOST, f"bash -c \"{cmd}\""], capture_output=True, text=True)
    print("Found python.exe instances under Wine:")
    print(res.stdout)
    print("=" * 100)

if __name__ == "__main__":
    main()
