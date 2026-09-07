#!/usr/bin/env bash
# Partial mitigation for Oracle's Always Free idle-reclaim policy (CPU,
# network, and memory all <20% 95th percentile over 7 days triggers reclaim).
# A bare health-check ping barely moves CPU/memory, so this also burns some
# CPU directly. Still not a guarantee — see README.md for the reliable fix
# (convert the account to Pay-As-You-Go).
set -euo pipefail

curl -fsS -o /dev/null "https://api.nexadesk.site/health" || true

# Light CPU nudge so the utilization sample isn't a flat zero.
python3 -c "sum(i*i for i in range(2_000_000))" || true
