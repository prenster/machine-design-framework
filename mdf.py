#!/usr/bin/env python3
"""Cross-platform entry point (Windows PowerShell, macOS, Linux). Same as the Makefile targets.

    python mdf.py install                     # pip install -r requirements.txt
    python mdf.py test                        # unit tests
    python mdf.py verify [PROJECT] [--variant V] [--gate G3]
    python mdf.py verify-broken               # broken example must FAIL
    python mdf.py all                         # test + verify + verify-broken (what CI runs)
    python mdf.py plc PROJECT                 # regenerate PLC GVLs
    python mdf.py checks PROJECT              # print check definitions for review
    python mdf.py lock PROJECT --by "Name"    # chief engineer approves the check definitions
    python mdf.py baseline PROJECT            # unreviewed baseline lock (Claude may write this)
    python mdf.py animate [PROJECT] [--variant V]   # MP4 of the machine cycle (needs ffmpeg)
    python mdf.py new DEST                    # scaffold a station project
    python mdf.py claimcheck PROJECT...       # used by the git hook
    python mdf.py hooks                       # install the claim-contract git hook

PROJECT defaults to examples/pick-glue-place.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT = "examples/pick-glue-place"


def _utf8_relaunch() -> None:
    # Windows defaults to a legacy code page for files and the console; reports contain degree signs etc.
    if not sys.flags.utf8_mode:
        env = dict(os.environ, PYTHONUTF8="1")
        sys.exit(subprocess.call([sys.executable, "-X", "utf8", *sys.argv], env=env))


def _mdf(*args: str) -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    from mdf.__main__ import main
    return main(list(args))


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    os.chdir(ROOT)
    if cmd == "install":
        return subprocess.call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    if cmd == "test":
        return subprocess.call([sys.executable, "-X", "utf8", "-m", "pytest", "-q", "tests/"])
    if cmd == "verify":
        if not rest or rest[0].startswith("-"):
            rest = [DEFAULT, *rest]
        return _mdf("verify", *rest)
    if cmd == "verify-broken":
        out = str(Path(tempfile.gettempdir()) / "mdf-broken")
        rc = _mdf("verify", "examples/pick-glue-place-broken", "--out", out)
        if rc == 1:
            print("OK: broken example failed as expected")
            return 0
        print(f"ERROR: broken example did not fail (rc={rc})")
        return 1
    if cmd == "all":
        for step in (["test"], ["verify"], ["verify-broken"]):
            rc = subprocess.call([sys.executable, "-X", "utf8", str(ROOT / "mdf.py"), *step])
            if rc != 0:
                return rc
        return 0
    if cmd == "animate":
        if not rest or rest[0].startswith("-"):
            rest = [DEFAULT, *rest]
        return _mdf("animate", *rest)
    if cmd in ("plc", "checks", "new", "claimcheck"):
        return _mdf(cmd, *rest)
    if cmd == "lock":
        if "--by" not in rest:
            print('usage: python mdf.py lock PROJECT --by "<your name>"   (chief engineer, after reading PROJECT/CHECKS.md)')
            return 2
        return _mdf("lock", *rest)
    if cmd == "baseline":
        return _mdf("lock", *(rest or [DEFAULT]))
    if cmd == "hooks":
        return subprocess.call(["git", "config", "core.hooksPath", ".githooks"])
    print(f"unknown command {cmd!r}\n{__doc__}")
    return 2


if __name__ == "__main__":
    _utf8_relaunch()
    sys.exit(main(sys.argv[1:]))
