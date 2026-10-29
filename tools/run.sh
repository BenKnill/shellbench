#!/bin/bash
# Run the whole benchmark: build the suite, run the GNU oracle twice, run every subject, score.
#
# usage: tools/run.sh RUN_ID SUBJECTS.tsv
#   RUN_ID        a new name; results go to results/RUN_ID (must not exist)
#   SUBJECTS.tsv  one subject per line: NAME<TAB>ADAPTER_MODULE<TAB>ADAPTER_OPTS_JSON ('#' comments)
# env:
#   SB_GNUBIN       directory of GNU coreutils under plain names (on the oracle host)   [required]
#   SB_ORACLE_SSH   ssh destination of a Linux host with bubblewrap; empty = run the oracle here
#   SB_ORACLE_ROOT  working directory on that host (default: ~/shellbench-oracle)
set -euo pipefail
cd "$(dirname "$0")/.."
RUN=$1; SUBJ=$2; OUT=results/$RUN
: "${SB_GNUBIN:?set SB_GNUBIN}"
ROOT=${SB_ORACLE_ROOT:-shellbench-oracle}
mkdir -p results && mkdir "$OUT"
python3 -I suite/build.py
# The commit, the git object id of each code path (compare with `git rev-parse HEAD:PATH` in any
# checkout), and any uncommitted changes to them.
{ echo "commit $(git rev-parse HEAD 2>/dev/null || echo unknown)"
  for p in suite runners tools score.py families.py; do echo "$p $(git rev-parse "HEAD:$p" 2>/dev/null || echo unknown)"; done
  git status --porcelain suite runners tools score.py families.py 2>/dev/null | head -n 20 || true; } > "$OUT/source-rev.txt"
ORACLE="set -e; mkdir -p $ROOT; cd $ROOT; mkdir $RUN; tar -xf - -C $RUN; cd $RUN; \
for r in gnu gnu-repeat; do nice -n 15 python3 -I runners/gnu/oracle.py --cases suite/cases.jsonl \
--world suite/world.json --gnubin $SB_GNUBIN --workdir wd-\$r --out \$r.jsonl --workers 4 2>/dev/null; done"
if [ -n "${SB_ORACLE_SSH:-}" ]; then
  # macOS bsdtar would otherwise add extended attributes and AppleDouble files; GNU tar does not
  # accept --no-mac-metadata, so the flags are used only with bsdtar.
  TARFLAGS=""; if tar --version 2>/dev/null | grep -q bsdtar; then TARFLAGS="--no-xattrs --no-mac-metadata"; fi
  # shellcheck disable=SC2086
  COPYFILE_DISABLE=1 tar $TARFLAGS -cf - suite/cases.jsonl suite/world.json runners/gnu \
    | ssh "$SB_ORACLE_SSH" "$ORACLE"
  scp -q "$SB_ORACLE_SSH:$ROOT/$RUN/gnu*.jsonl*" "$OUT/"
else
  tar -cf - suite/cases.jsonl suite/world.json runners/gnu | bash -c "$ORACLE"
  cp "$ROOT/$RUN"/gnu*.jsonl* "$OUT/"
fi
while IFS=$'\t' read -r name adapter opts; do
  if [ -z "$name" ] || [ "${name:0:1}" = "#" ]; then continue; fi
  nice -n 10 node runners/node/run.mjs --adapter "$adapter" --adapter-opts "$opts" --cases suite/cases.jsonl \
    --world suite/world.json --out "$OUT/$name.jsonl" --workers 4
done < "$SUBJ"
python3 -I score.py "$OUT"
