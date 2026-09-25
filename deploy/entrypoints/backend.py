from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SECRET_FILES = {
    "AVICOLA_DATABASE_URL": "AVICOLA_DATABASE_URL_FILE",
    "AVICOLA_SESSION_HMAC_KEY": "AVICOLA_SESSION_HMAC_KEY_FILE",
}


def load_mounted_secrets() -> None:
    for environment_name, file_environment_name in SECRET_FILES.items():
        secret_path = os.environ.pop(file_environment_name, None)
        if not secret_path:
            raise SystemExit(f"Required secret file setting is missing: {file_environment_name}")
        try:
            secret_value = Path(secret_path).read_text(encoding="utf-8").rstrip("\r\n")
        except OSError:
            raise SystemExit(f"Required secret file is unavailable: {file_environment_name}") from None
        if not secret_value:
            raise SystemExit(f"Required secret file is empty: {file_environment_name}")
        os.environ[environment_name] = secret_value


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("A container process command is required")
    load_mounted_secrets()
    if os.name == "nt":
        # The command is the image's fixed CMD or its explicit Compose override.
        raise SystemExit(subprocess.call(sys.argv[1:], env=os.environ))  # noqa: S603
    os.execvpe(sys.argv[1], sys.argv[1:], os.environ)  # noqa: S606


if __name__ == "__main__":
    main()
