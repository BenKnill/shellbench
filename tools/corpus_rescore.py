"""Re-classify a private replay corpus with shellbench's verdict rules and print aggregates only.

usage: python3 -I tools/corpus_rescore.py OUT.json CASES.jsonl TRUTH.jsonl UTILS_VERDICTS.jsonl \
          LABEL=SUBJECT.jsonl [LABEL=SUBJECT.jsonl ...]

CASES lines {k, n, script}; TRUTH and SUBJECT lines {k, stdoutB64, stderr, exitCode, delta, ...}
(later TRUTH lines for the same k win); UTILS_VERDICTS lines {k, utils}. The output holds instance
counts per subject, family and class: no command text, paths or outputs.
"""
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from families import families_of  # noqa: E402
from score import CLASSES, classify  # noqa: E402

out_p, cases_p, truth_p, utils_p = sys.argv[1:5]


def load(p):
    d = {}
    for line in open(p):
        if line.strip():
            r = json.loads(line)
            d[r["k"]] = r
    return d


cases, truth = load(cases_p), load(truth_p)
utils = {k: v.get("utils") for k, v in load(utils_p).items()}
res = {}
for arg in sys.argv[5:]:
    label, path = arg.split("=", 1)
    sub = load(path)
    tot, fam = {c: 0 for c in CLASSES}, {}
    skipped = 0
    for k, c in cases.items():
        rr, sr, n = truth.get(k), sub.get(k), c["n"]
        if rr is None or sr is None or rr.get("timeout") or rr["exitCode"] in (-1, -2) \
                or str(rr.get("stderr", "")).startswith("HARNESS"):
            skipped += n
            continue
        if sr.get("timeout") or sr.get("crashed"):
            cls = "loud-wrong"
        else:
            cls = classify(rr, sr, c.get("script") or "")[0]
        tot[cls] += n
        for f in families_of(utils.get(k)) or ["other"]:
            fam.setdefault(f, {x: 0 for x in CLASSES})[cls] += n
    res[label] = {"overall": tot, "skipped": skipped, "families": fam}
with open(out_p, "w") as f:
    json.dump(res, f, indent=1, sort_keys=True)
for label, d in res.items():
    n = sum(d["overall"].values())
    print(f"{label:28s} n={n} skipped={d['skipped']} " +
          " ".join(f"{k}={100 * v / n:.2f}%" for k, v in d["overall"].items()))
