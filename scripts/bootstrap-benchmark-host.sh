#!/usr/bin/env bash
# Provision a dedicated Linux host for long-running external benchmark runs.
#
# Written for a spare always-on machine: the full three-arm campaign takes
# days of wall-clock time, which is not something to run on a laptop you also
# use. Everything here is free and local — no paid API, no account, no key
# except an optional Gemini one used solely for judging.
#
#     bash scripts/bootstrap-benchmark-host.sh            # full setup
#     bash scripts/bootstrap-benchmark-host.sh --verify   # re-check only
#
# Idempotent: re-running skips whatever is already in place.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_ROOT="${ZEREF_BENCHMARK_DATA:-$HOME/zeref-benchmark-data}"
OLLAMA_MODEL="${ZEREF_OLLAMA_MODEL:-llama3.1:8b}"
VERIFY_ONLY=0
[ "${1:-}" = "--verify" ] && VERIFY_ONLY=1

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33m !  %s\033[0m\n' "$*"; }
die()  { printf '\033[31m x  %s\033[0m\n' "$*" >&2; exit 1; }

# --- preflight ---------------------------------------------------------------

say "Host"
printf '  os      : %s\n' "$(uname -srm)"
printf '  cores   : %s\n' "$(nproc 2>/dev/null || echo '?')"
printf '  ram     : %s\n' "$(free -h 2>/dev/null | awk '/^Mem:/{print $2}' || echo '?')"
printf '  disk    : %s free at %s\n' "$(df -h "$HOME" | awk 'NR==2{print $4}')" "$HOME"

# ConvoMem alone is ~26 GB. Failing here beats failing 20 GB into a download.
avail_gb=$(df -BG "$HOME" | awk 'NR==2{gsub(/G/,"",$4); print $4}')
[ "${avail_gb:-0}" -lt 60 ] && warn "only ${avail_gb}G free; the full dataset set needs ~30 GB plus model weights"

say "Python"
command -v python3 >/dev/null || die "python3 not found: sudo apt install -y python3 python3-pip"
python3 - <<'PY' || die "Python 3.11+ required (pyproject requires-python)"
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
printf '  %s\n' "$(python3 --version)"

# --- ollama ------------------------------------------------------------------

say "Ollama"
if ! command -v ollama >/dev/null; then
    [ "$VERIFY_ONLY" -eq 1 ] && die "ollama not installed"
    warn "installing Ollama from the official script (https://ollama.com/install.sh)"
    curl -fsSL https://ollama.com/install.sh | sh
fi
printf '  %s\n' "$(ollama --version 2>&1 | head -1)"

if ! curl -sf -m 5 http://localhost:11434/api/version >/dev/null; then
    if command -v systemctl >/dev/null && systemctl list-unit-files 2>/dev/null | grep -q '^ollama'; then
        sudo systemctl enable --now ollama
    else
        warn "starting 'ollama serve' in the background; use a systemd unit for an always-on host"
        nohup ollama serve >"$HOME/ollama-serve.log" 2>&1 &
    fi
    for _ in $(seq 1 30); do
        curl -sf -m 2 http://localhost:11434/api/version >/dev/null && break
        sleep 1
    done
fi
curl -sf -m 5 http://localhost:11434/api/version >/dev/null || die "Ollama daemon is not answering on :11434"

if ! ollama list 2>/dev/null | awk 'NR>1{print $1}' | grep -qx "$OLLAMA_MODEL"; then
    [ "$VERIFY_ONLY" -eq 1 ] && die "model $OLLAMA_MODEL not pulled"
    say "Pulling $OLLAMA_MODEL"
    ollama pull "$OLLAMA_MODEL"
fi

# Context window is the binding constraint on the full_context arm. Ollama
# derives num_ctx from available VRAM and silently truncates longer prompts,
# so the ceiling has to be measured, not assumed. Record it and pass the
# figure to --num-ctx.
say "Context budget"
printf '  The VRAM-derived default Ollama picks is in its log; override with --num-ctx.\n'
printf '  Measured on a 16 GB M4 for reference: 8k=27s, 16k=71s, 32k=274s per call.\n'
printf '  Prompt-processing time grows ~4x per doubling — measure before planning a run.\n'

# --- datasets ----------------------------------------------------------------

say "Datasets -> $DATA_ROOT"
export ZEREF_BENCHMARK_DATA="$DATA_ROOT"
if [ "$VERIFY_ONLY" -eq 0 ]; then
    # Resumable: files already present are skipped, and transient drops retry.
    python3 "$REPO_ROOT/scripts/fetch-benchmark-data.py" --all
fi

say "Dataset verification (offline, free)"
python3 - <<'PY'
import os, sys
from pathlib import Path
sys.path.insert(0, os.environ.get("REPO_ROOT", "."))
from benchmarks.external.loaders import locomo, longmemeval, personamem, convomem
root = Path(os.environ["ZEREF_BENCHMARK_DATA"])
bad = 0
for mod, name in ((locomo, "locomo"), (longmemeval, "longmemeval"),
                  (personamem, "personamem"), (convomem, "convomem")):
    try:
        c = mod.check(root / name)
        pin = "n/a" if c.sha256_pinned is None else ("MATCH" if c.sha256_actual == c.sha256_pinned else "MISMATCH")
        print(f"  {name:13} ok={str(c.ok):5} tasks={c.task_count:>7}  pin={pin}")
        if not c.ok or pin == "MISMATCH":
            bad += 1
            for err in c.errors:
                print(f"      {err}")
    except Exception as exc:
        bad += 1
        print(f"  {name:13} ERROR {type(exc).__name__}: {exc}")
if bad:
    print("\n  A checksum mismatch means the local copy is not the pinned release.")
    print("  Investigate — do not re-pin to silence it.")
    raise SystemExit(1)
PY

# --- repo verification -------------------------------------------------------

say "Repository verification"
cd "$REPO_ROOT"
python3 -m pytest -q
python3 scripts/zeref-validate.py >/dev/null && echo "  zeref-validate: pass"
python3 -m zeref audit-privacy --strict --fail-classes credentials >/dev/null && echo "  privacy (credentials class): pass"

say "Ready"
cat <<EOF
  Data       : $DATA_ROOT
  Model      : $OLLAMA_MODEL (generation, \$0, no quota)
  Judge      : Gemini, used ONLY where deterministic scoring cannot decide.
               Put GEMINI_API_KEY in a gitignored .env.local at the repo root.

  Proxy run — retrieval quality, zero network, minutes:
    python3 -m zeref.cli benchmark external --benchmark locomo \\
      --data \$ZEREF_BENCHMARK_DATA/locomo --arms all

  Scored run — checkpointed, resumable, resume by re-running the same command:
    python3 -m zeref.cli benchmark external --benchmark locomo \\
      --data \$ZEREF_BENCHMARK_DATA/locomo --arms all \\
      --provider ollama --provider-model $OLLAMA_MODEL --num-ctx 32768 \\
      --judge gemini --live --confirm --max-cost 1 \\
      --checkpoint-dir benchmarks/runs/locomo-01

  See docs/BENCHMARK_RUNBOOK.md before spending anything.
EOF
