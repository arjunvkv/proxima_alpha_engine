import subprocess

VPS_KEY  = r"C:\Users\Arjun Sasi\Downloads\ssh-key-2026-07-28.key"
VPS_HOST = "ubuntu@140.245.234.92"

def main():
    print("=" * 100)
    print("PROXIMA ALPHA ENGINE — INSTALLING WINDOWS PYTHON & METATRADER5 IN WINE ON VPS...")
    print("=" * 100)

    cmd = (
        "cd /tmp && "
        "wget -q https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe && "
        "DISPLAY=:0 WINEDEBUG=-all wine python-3.10.11-amd64.exe /quiet InstallAllUsers=1 PrependPath=1 && "
        "sleep 5 && "
        "find /home/ubuntu/.wine/ -name 'python.exe' 2>/dev/null"
    )

    res = subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-i", VPS_KEY, VPS_HOST, f"bash -c \"{cmd}\""], capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)
    print("=" * 100)

if __name__ == "__main__":
    main()
