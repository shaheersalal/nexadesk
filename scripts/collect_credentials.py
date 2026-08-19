"""
Collect credentials from every project's .env under AI_Dev into one master file.

Deliberate trade-off: a single file is convenient but is also a single point of
compromise. It is therefore written **outside every git repository** (so no
`git add -A` can ever capture it) and its NTFS permissions are reduced to the
owning user only.

Values are never printed to stdout — only key names and counts — so running
this does not leak anything into a terminal transcript or CI log.

    python scripts/collect_credentials.py [--out PATH] [--apply]
"""
import argparse
import datetime
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"C:\Users\DELL\AI_Dev")
DEFAULT_OUT = pathlib.Path(r"C:\Users\DELL\.credentials\AI_Dev_master_credentials.md")

SKIP_DIRS = {
    "node_modules", ".venv", "venv", "site-packages", ".next", "dist",
    "ClaudeData", ".git", "__pycache__", "build", ".pytest_cache",
}

ENV_NAMES = {".env", ".env.local", ".env.production", ".env.development", "config.env"}

SECRETISH = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASS", "SID", "DSN", "CREDENTIAL")

# Credentials that passed through an AI chat transcript on 2026-08-17/18 and
# should be treated as disclosed regardless of where they are stored now.
EXPOSED = {
    "RAILWAY_TOKEN": "Railway project token — can read every other Railway var",
    "CLOUDFLARE_API_TOKEN": "Cloudflare zone DNS token",
    "QDRANT_API_KEY": "Qdrant Cloud",
    "REDIS_URL": "contains the Upstash password",
    "UPSTASH_REDIS_REST_TOKEN": "Upstash REST token",
    "STT_API_KEY": "Deepgram",
    "SUPABASE_JWT_SECRET": "Supabase legacy HS256 secret",
    "VERCEL_TOKEN": "Vercel project token",
}


def find_env_files(root: pathlib.Path) -> list[pathlib.Path]:
    found = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in ENV_NAMES or path.name.endswith(".env"):
            found.append(path)
    return sorted(found)


def parse_env(path: pathlib.Path) -> list[tuple[str, str]]:
    pairs = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return pairs
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        pairs.append((key.strip(), value.strip().strip('"').strip("'")))
    return pairs


def build(files: list[pathlib.Path]) -> tuple[str, int, int]:
    now = datetime.datetime.now(datetime.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    out = [
        "# AI_Dev — master credentials",
        "",
        f"Generated {now} by `nexa_desk/scripts/collect_credentials.py`.",
        "",
        "Collected from every `.env` under `C:\\Users\\DELL\\AI_Dev`. This file is",
        "**not** the source of truth — each project still reads its own `.env`.",
        "Regenerate rather than hand-editing, or the two will drift.",
        "",
        "Stored outside every git repository so no `git add -A` can capture it,",
        "with NTFS permissions reduced to this user account.",
        "",
        "---",
        "",
        "## Rotate these",
        "",
        "Passed through an AI chat transcript and should be considered disclosed.",
        "Ordered by blast radius:",
        "",
    ]
    for key, why in EXPOSED.items():
        out.append(f"- **`{key}`** — {why}")
    out += [
        "",
        "The Railway token is the one that matters most: it can read every other",
        "secret in the Railway environment, so rotating it first shrinks the",
        "value of anything else that leaked.",
        "",
        "---",
        "",
    ]

    total_keys = 0
    for path in files:
        pairs = parse_env(path)
        if not pairs:
            continue
        rel = str(path).replace(str(ROOT) + "\\", "")
        project = rel.split("\\")[0]
        modified = datetime.datetime.fromtimestamp(
            path.stat().st_mtime, tz=datetime.timezone.utc
        ).astimezone().strftime("%Y-%m-%d")

        out.append(f"## {project}")
        out.append("")
        out.append(f"`{rel}` — last modified {modified}")
        out.append("")
        out.append("| Key | Value |")
        out.append("|---|---|")
        for key, value in pairs:
            total_keys += 1
            if not value:
                shown = "*(empty)*"
            else:
                # Escape pipes so the table does not break on connection strings.
                shown = "`" + value.replace("|", "\\|") + "`"
            flag = " ⚠️" if key in EXPOSED else ""
            out.append(f"| `{key}`{flag} | {shown} |")
        out.append("")

    return "\n".join(out) + "\n", len(files), total_keys


def lock_down(path: pathlib.Path) -> None:
    """Remove inherited ACLs and grant only the current user."""
    user = subprocess.run(["whoami"], capture_output=True, text=True, shell=True).stdout.strip()
    for args in (
        ["icacls", str(path), "/inheritance:r"],
        ["icacls", str(path), "/grant:r", f"{user}:(F)"],
    ):
        r = subprocess.run(args, capture_output=True, text=True, shell=True)
        if r.returncode != 0:
            print(f"  ACL step failed: {' '.join(args)}\n    {r.stdout.strip()[:200]}")
            return
    print(f"  permissions: {user} only (inheritance removed)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--apply", action="store_true", help="write the file")
    args = ap.parse_args()

    files = find_env_files(ROOT)
    content, file_count, key_count = build(files)

    print(f"scanned {file_count} env file(s), {key_count} key(s)")
    for path in files:
        n = len(parse_env(path))
        if n:
            print(f"  {str(path).replace(str(ROOT) + chr(92), ''):58} {n:3} keys")

    if not args.apply:
        print(f"\n--apply not passed. Would write {len(content)} bytes to:\n  {args.out}")
        return 0

    # Refuse to write anywhere a git repo could pick it up.
    for parent in [args.out, *args.out.parents]:
        if (parent / ".git").exists():
            print(f"\nREFUSING: {args.out} sits inside a git repo ({parent})")
            return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(content, encoding="utf-8", newline="")
    print(f"\nwrote {len(content)} bytes to {args.out}")
    lock_down(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
