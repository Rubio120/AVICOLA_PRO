from __future__ import annotations

import subprocess
import sys

from .backup import RESTIC, _restic_environment


def main() -> int:
    try:
        environment = _restic_environment()
        result = subprocess.run(
            [RESTIC, "init"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=300,
        )  # noqa: S603 - executable and arguments are fixed by this image.
        if result.returncode != 0:
            raise RuntimeError
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print("Repository initialization failed; details withheld", file=sys.stderr)
        return 1
    print("repository_status=initialized; repository locator and key withheld")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
