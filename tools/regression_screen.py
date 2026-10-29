"""Regression screen: compare each subject in a scored run directory with a base subject.

usage: python3 -I tools/regression_screen.py RUN_DIR BASE_SUBJECT [--cases suite/cases.jsonl] > screen.md

For each other subject: cases that match GNU on the base but not on the subject (regressions, with
the GNU, base and subject outputs), cases the subject newly matches, and silent-wrong counts.
Run score.py on RUN_DIR first.
"""
import json, os, sys

run, base = sys.argv[1], sys.argv[2]
cases_p = sys.argv[sys.argv.index("--cases") + 1] if "--cases" in sys.argv else "suite/cases.jsonl"
cases = {json.loads(l)["id"]: json.loads(l) for l in open(cases_p) if l.strip()}
load = lambda p: {json.loads(l)["id"]: json.loads(l) for l in open(p) if l.strip()}  # noqa: E731
gnu = load(os.path.join(run, "gnu.jsonl"))
verd = lambda s: load(os.path.join(run, f"verdicts-{s}.jsonl"))  # noqa: E731
subjects = sorted(f[9:-6] for f in os.listdir(run) if f.startswith("verdicts-") and f[9:-6] != base)
bv, braw = verd(base), load(os.path.join(run, base + ".jsonl"))


def show(r):
    out = {"exit": r["exitCode"], "stdout": r.get("stdout", "")[:600]}
    if r.get("stderr"):
        out["stderr"] = r["stderr"][:300]
    d = r.get("delta") or {}
    if d.get("added") or d.get("changed") or d.get("deleted"):
        out["files"] = d
    return json.dumps(out, ensure_ascii=False)


summary = ["| Subject | Regressions vs base | Newly matching | Silent-wrong (base -> subject) | Match (base -> subject) |",
           "|---|---|---|---|---|"]
detail = []
for s in subjects:
    v, raw = verd(s), load(os.path.join(run, s + ".jsonl"))
    reg = [k for k in bv if bv[k]["cls"] == "match" and v[k]["cls"] != "match"]
    new = [k for k in bv if bv[k]["cls"] != "match" and v[k]["cls"] == "match"]
    sb = sum(1 for k in bv if bv[k]["cls"] == "silent-wrong")
    ss = sum(1 for k in v if v[k]["cls"] == "silent-wrong")
    mb = sum(1 for k in bv if bv[k]["cls"] == "match")
    ms = sum(1 for k in v if v[k]["cls"] == "match")
    summary.append(f"| {s} | {len(reg)}{': ' + ', '.join(reg) if reg else ''} | {len(new)}{': ' + ', '.join(new) if new else ''} | {sb} -> {ss} | {mb} -> {ms} |")
    for k in reg:
        detail += [f"### {s}: {k} ({v[k]['cls']}, {v[k]['why']}, differs in {', '.join(v[k]['what'])})",
                   f"script: `{cases[k]['script']}`", "", f"- GNU:    `{show(gnu[k])}`", f"- base:   `{show(braw[k])}`",
                   f"- branch: `{show(raw[k])}`", ""]
print("\n".join(summary + ["", "## Regression details", ""] + (detail or ["None."])))
