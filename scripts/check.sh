#!/bin/sh
#
# Run what CI runs, before CI runs it.
#
# The steps and their order mirror .github/workflows/ci.yml exactly. When that
# file changes, change this one with it — the whole value here is that a green
# run locally means a green run on push, and the moment the two drift that
# stops being true.
#
#   sh scripts/check.sh          everything, stopping at the first failure
#   sh scripts/check.sh --fast   skip the tests, for a quick lint pass
#
# Installed as a pre-push hook by:  git config core.hooksPath .githooks
set -eu

FAST=0
[ "${1:-}" = "--fast" ] && FAST=1

# Prefer the project virtualenv, so this behaves the same however it is invoked
# — including from a git hook, which does not inherit an activated shell.
if   [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ];        then PY=.venv/bin/python
elif command -v python3 >/dev/null;  then PY=python3
else                                      PY=python
fi

# CI has no .env — a fresh checkout never does. Setting these explicitly gets
# most of the way there, since real environment variables take precedence over
# the file. It is not perfect parity: a local .env still supplies keys CI does
# not have, so CI remains the authority. It is close enough to catch the
# failures that actually happen, which are lint and import errors.
export APP_ENV=development
export SUPABASE_URL=https://placeholder.supabase.co
export SUPABASE_SERVICE_KEY=placeholder
export SUPABASE_ANON_KEY=placeholder
export LLM_API_KEY=placeholder
export APP_SECRET_KEY=test-secret-not-a-real-key

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
fail() { printf '\n\033[31m✗ %s failed — not pushing\033[0m\n' "$1"; exit 1; }

step "ruff"
"$PY" -m ruff check app/ tests/ scripts/ || fail "lint"

step "compileall"
"$PY" -m compileall -q app/ || fail "compile"

step "import app.main"
"$PY" -c "import app.main" >/dev/null || fail "import"

if [ "$FAST" -eq 1 ]; then
    printf '\n\033[33m! tests skipped (--fast)\033[0m\n'
    exit 0
fi

step "pytest"
"$PY" -m pytest -q || fail "tests"

printf '\n\033[32m✓ all green — matches CI\033[0m\n'
