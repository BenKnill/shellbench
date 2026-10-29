#!/bin/bash
# Run the suite against Cloudflare Computer's worker-shell in local workerd and add the results to a run.
#
# usage: runners/workerd/run.sh COMPUTER_CHECKOUT RUN_DIR
#   COMPUTER_CHECKOUT  a cloudflare/computer checkout, set up as in the README ("Reproducing the
#                      published run"): dependencies installed and `npm run build:shell-bundle` done
#                      in packages/computer. Its tracked files must be unmodified. This script copies
#                      the shellbench host files into packages/computer (untracked files only).
#   RUN_DIR            an existing results directory (for example results/myrun after tools/run.sh)
#
# Writes RUN_DIR/cf-computer-workerd-REV.jsonl (REV = the checkout's 7-digit commit) and its
# .meta.json, then re-scores RUN_DIR. The vitest log goes to a temporary file whose path is printed.
set -euo pipefail
cd "$(dirname "$0")/../.."
CO=$(cd "$1" && pwd); RUN=$2; PKG=$CO/packages/computer
[ -d "$RUN" ] || { echo "no such run directory: $RUN" >&2; exit 1; }
git -C "$CO" diff --quiet HEAD || { echo "$CO has modified tracked files" >&2; exit 1; }
REV=$(git -C "$CO" rev-parse --short=7 HEAD)
VER=$(node -p 'require(process.argv[1]).version' "$PKG/package.json")
JB=$(node -p 'require(process.argv[1]).version' "$CO/node_modules/just-bash/package.json")
node runners/workerd/prepare.mjs suite/cases.jsonl suite/world.json "$PKG/tests/shellbench-cases.json"
cp runners/workerd/shellbench-worker.ts runners/workerd/shellbench.test.ts runners/workerd/wrangler.shellbench.jsonc "$PKG/tests/"
cp runners/workerd/vitest.config.shellbench.ts "$PKG/"
LOG=$(mktemp "${TMPDIR:-/tmp}/shellbench-workerd-XXXXXX")
# The test ends with a deliberate, labelled failure (SHELLBENCH-DONE): in this setup vitest prints a
# test's console output only when the test fails. So vitest's exit status is ignored here, and the
# result count is checked below instead.
( cd "$PKG" && npx vitest run --config vitest.config.shellbench.ts ) > "$LOG" 2>&1 || true
echo "vitest log: $LOG" >&2
OUT=$RUN/cf-computer-workerd-$REV.jsonl
node runners/workerd/collect.mjs "$LOG" "$OUT" \
  "computer@$REV (packages/computer $VER) worker-shell in local workerd via @cloudflare/vitest-pool-workers + just-bash@$JB [groups: core+jq+curl]"
want=$(grep -c . suite/cases.jsonl); got=$(grep -c . "$OUT")
[ "$got" = "$want" ] || { echo "expected $want results, got $got (see $LOG)" >&2; exit 1; }
python3 -I score.py "$RUN" > /dev/null
echo "$OUT: $got results; scores in $RUN/scores.md" >&2
