"""
Set or update keys in .env, preserving everything else.

Values are read from the process environment (prefix `SETENV_`), never
hardcoded — this file is committed, so a literal secret here would be a leak.

Usage:
    SETENV_QDRANT_URL=... python scripts/set_env.py
"""
import os
import pathlib
import sys

PREFIX = "SETENV_"
ENV_PATH = pathlib.Path(".env")


def main() -> int:
    updates = {
        k[len(PREFIX):]: v
        for k, v in os.environ.items()
        if k.startswith(PREFIX) and v
    }
    if not updates:
        print("nothing to set — pass values as SETENV_<KEY> env vars")
        return 1

    lines = (
        ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        if ENV_PATH.is_file() else []
    )

    seen = set()
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)

    added = [k for k in updates if k not in seen]
    if added:
        out.append("")
        out.append("# ── Added by scripts/set_env.py ──")
        for k in added:
            out.append(f"{k}={updates[k]}")

    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")

    for k in sorted(seen):
        print(f"  updated  {k}")
    for k in sorted(added):
        print(f"  added    {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
