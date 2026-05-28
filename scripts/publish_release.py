from __future__ import annotations

import argparse
import getpass
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload TAFSQ release files to a VPS over SSH/SFTP.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--remote-dir", default="/var/www/html/tafsq")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()

    try:
        import paramiko
    except ImportError as exc:
        raise SystemExit("Please install paramiko first: python -m pip install paramiko") from exc

    password = getpass.getpass(f"Password for {args.user}@{args.host}: ")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(args.host, username=args.user, password=password, timeout=20)
    try:
        ssh.exec_command(f"mkdir -p {args.remote_dir!r}")
        sftp = ssh.open_sftp()
        try:
            for path in args.files:
                local = path.resolve()
                if not local.is_file():
                    raise SystemExit(f"file not found: {local}")
                remote = f"{args.remote_dir.rstrip('/')}/{local.name}"
                print(f"{local} -> {args.user}@{args.host}:{remote}")
                sftp.put(str(local), remote)
        finally:
            sftp.close()
    finally:
        ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
