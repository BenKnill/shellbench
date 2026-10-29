"""Score subject results against the GNU oracle and classify every case.

usage: python3 -I score.py RUN_DIR [--cases suite/cases.jsonl]
  RUN_DIR holds gnu.jsonl, optionally gnu-repeat.jsonl (a second oracle run), and one SUBJECT.jsonl
  per subject. A case that times out, fails in the harness (negative exit status) or is missing in
  gnu.jsonl, or in gnu-repeat.jsonl when that file exists (even empty), is oracle-unusable. A usable
  case whose two oracle runs differ in stdout, stderr, exit status or files is nondeterministic.
  Neither kind is scored. Writes RUN_DIR/verdicts-SUBJECT.jsonl, RUN_DIR/scores.json and
  RUN_DIR/scores.md.

Verdict classes (checked in this order; the first that applies wins):
  match            stdout bytes, exit status, file changes and stderr all identical
  error-text       only stderr differs
  loud-unsupported the answer differs and the subject prints a not-found / unknown-option /
                   unsupported message that GNU does not print (whatever the final exit status:
                   scripts often end in `echo` or a pipeline that hides a failing command's status)
  formatting       exit status and file changes identical; stdout differs only in whitespace, in
                   line order, or in `ls -l` fields an in-memory file system cannot know (owner,
                   group, link count, times, directory sizes, totals). Exception: when the script
                   runs `sort` and stdout differs only in line order, the class is silent-wrong.
  loud-wrong       the answer differs and the subject's stderr is non-empty and differs from GNU's
  silent-wrong     everything else: the answer differs in substance and the subject printed no
                   error that would tell an agent so. `silent_exit0` counts the subset where the
                   subject also exited 0.
"""
import base64, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from families import FAMILIES  # noqa: E402

UNSUP = re.compile(r"command not found|not supported|unsupported|unknown option|unrecognized option|"
                   r"invalid option|illegal option|not implemented|No such module|unknown command|"
                   r"Unknown flag|unknown flag|invalid flag|is not a valid option|not yet supported|"
                   r"unrecognized|unknown argument|Usage:|usage:", re.I)
LSL = re.compile(r"^([-dlcbps])([rwxsStT-]{9})[.+@]?\s+\d+\s+\S+\s+\S+\s+(\d+(?:[.,]\d+)?[KMGTP]?)\s+"
                 r"(\w{3}\s+\d{1,2}\s+(?:\d{1,2}:\d{2}|\d{4}))\s+(.*)$")
CLASSES = ["match", "error-text", "formatting", "loud-unsupported", "loud-wrong", "silent-wrong"]


def outbytes(r):
    return base64.b64decode(r.get("stdoutB64") or "")


def ws_norm(b):
    t = b.decode("utf-8", "replace")
    return "\n".join(re.sub(r"[ \t]+", " ", ln).strip() for ln in t.split("\n")).strip()


def ls_norm(b):
    out = []
    for ln in b.decode("utf-8", "replace").split("\n"):
        if re.match(r"^total \d+(\.\d+)?[KMG]?$", ln.strip()):
            continue
        m = LSL.match(ln.strip())
        if m:
            t, perm, size, _, name = m.groups()
            out.append(f"{t}{perm} {size if t == '-' else ''} {name}")
        else:
            out.append(re.sub(r"[ \t]+", " ", ln).strip())
    return "\n".join(out).strip()


def delta_norm(d):
    d = d or {}
    return (tuple(sorted((d.get("added") or {}).items())), tuple(sorted((d.get("changed") or {}).items())),
            tuple(sorted(d.get("deleted") or [])))


def classify(rr, sr, script):
    ro, so = outbytes(rr), outbytes(sr)
    same_out, same_code = ro == so, rr["exitCode"] == sr["exitCode"]
    same_delta = delta_norm(rr.get("delta")) == delta_norm(sr.get("delta"))
    rerr, serr = rr.get("stderr") or "", sr.get("stderr") or ""
    what = [k for k, ok in (("stdout", same_out), ("exit", same_code), ("files", same_delta),
                            ("stderr", rerr == serr)) if not ok]
    if same_out and same_code and same_delta:
        return ("match" if rerr == serr else "error-text"), what, None
    # Loud classes look at what the subject printed on stderr, not only at its final exit status:
    # scripts often end in `echo` or a pipeline, which hides a failing command's status.
    if UNSUP.search(serr) and not UNSUP.search(rerr):
        return "loud-unsupported", what, None
    if same_code and same_delta:
        if ws_norm(ro) == ws_norm(so):
            return "formatting", what, "whitespace"
        if sorted(ro.split(b"\n")) == sorted(so.split(b"\n")):
            if re.search(r"(^|[|;&(\s])sort\b(?![^|;&]*\s-R)", script):
                return "silent-wrong", what, "sort-order"
            return "formatting", what, "order"
        if ls_norm(ro) == ls_norm(so):
            return "formatting", what, "ls-metadata"
    if serr.strip() and serr != rerr:
        return "loud-wrong", what, ("both-fail" if rerr.strip() else None)
    return "silent-wrong", what, ("exit-code" if same_out and same_delta else None)


def load(p):
    return {r["id"]: r for r in map(json.loads, filter(str.strip, open(p)))}


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def main():
    run = sys.argv[1]
    cases_p = sys.argv[sys.argv.index("--cases") + 1] if "--cases" in sys.argv else "suite/cases.jsonl"
    cases = [json.loads(l) for l in open(cases_p) if l.strip()]
    gnu = load(os.path.join(run, "gnu.jsonl"))
    rep_p = os.path.join(run, "gnu-repeat.jsonl")
    rep_present = os.path.exists(rep_p)  # a present repeat file counts even when empty
    rep = load(rep_p) if rep_present else {}
    ids = [c["id"] for c in cases]
    unusable = lambda r: r is None or r.get("timeout") or r["exitCode"] < 0  # noqa: E731
    bad = sorted(k for k in ids if unusable(gnu.get(k)) or (rep_present and unusable(rep.get(k))))
    nondet = sorted(k for k in ids if k not in bad and rep_present and (
        outbytes(rep[k]) != outbytes(gnu[k]) or (rep[k].get("stderr") or "") != (gnu[k].get("stderr") or "")
        or rep[k]["exitCode"] != gnu[k]["exitCode"]
        or delta_norm(rep[k].get("delta")) != delta_norm(gnu[k].get("delta"))))
    scored = [c for c in cases if c["id"] not in nondet and c["id"] not in bad]
    subjects = sorted(f[:-6] for f in os.listdir(run) if f.endswith(".jsonl") and not f.startswith(("gnu", "verdicts-")))
    report = {"cases": len(cases), "scored": len(scored), "nondeterministic": nondet, "oracle_unusable": bad,
              "subjects": {}}
    for s in subjects:
        sub = load(os.path.join(run, s + ".jsonl"))
        meta_p = os.path.join(run, s + ".jsonl.meta.json")
        meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
        tot = {k: 0 for k in CLASSES}
        fam = {f: {k: 0 for k in CLASSES} for f in FAMILIES}
        tag = {}
        silent0 = 0
        with open(os.path.join(run, f"verdicts-{s}.jsonl"), "w") as vf:
            for c in scored:
                rr, sr = gnu[c["id"]], sub.get(c["id"])
                if sr is None or sr.get("timeout") or sr.get("crashed") or sr.get("missing"):
                    cls, what, why = "loud-wrong", ["harness"], "subject-timeout-or-crash"
                else:
                    cls, what, why = classify(rr, sr, c["script"])
                if cls == "silent-wrong" and sr and sr.get("exitCode") == 0:
                    silent0 += 1
                tot[cls] += 1
                for f in c["families"]:
                    fam[f][cls] += 1
                for t in c["tags"]:
                    tag.setdefault(t, {k: 0 for k in CLASSES})[cls] += 1
                vf.write(json.dumps({"id": c["id"], "cls": cls, "why": why, "what": what}) + "\n")
        n = len(scored)
        report["subjects"][s] = {
            "version": meta.get("version"), "classes": tot, "match_pct": pct(tot["match"], n),
            "match_or_errtext_pct": pct(tot["match"] + tot["error-text"], n),
            "match_errtext_formatting_pct": pct(tot["match"] + tot["error-text"] + tot["formatting"], n),
            "silent_wrong": tot["silent-wrong"], "silent_wrong_pct": pct(tot["silent-wrong"], n),
            "silent_exit0": silent0,
            "families": {f: {"n": sum(v.values()), **v, "match_pct": pct(v["match"], sum(v.values())),
                             "silent_pct": pct(v["silent-wrong"], sum(v.values()))} for f, v in fam.items()},
            "tags": {t: {"n": sum(v.values()), **v} for t, v in sorted(tag.items())},
        }
    with open(os.path.join(run, "scores.json"), "w") as f:
        json.dump(report, f, indent=1)
    md = [f"Scored {len(scored)} of {len(cases)} cases (nondeterministic on the oracle: {', '.join(nondet) or 'none'}; "
          f"oracle unusable: {', '.join(bad) or 'none'}).", "",
          "| Subject | Match | + error text | + formatting | Silent-wrong (exit 0) | Loud-wrong | Loud-unsupported |",
          "|---|---|---|---|---|---|---|"]
    for s, d in report["subjects"].items():
        c = d["classes"]
        md.append(f"| {s} | {d['match_pct']}% | {d['match_or_errtext_pct']}% | {d['match_errtext_formatting_pct']}% | "
                  f"**{c['silent-wrong']}** ({d['silent_exit0']}) | {c['loud-wrong']} | {c['loud-unsupported']} |")
    md += ["", "Per family (a case counts in every family whose utilities it uses): match % / silent-wrong count", "",
           "| Family | Cases | " + " | ".join(report["subjects"]) + " |", "|---|---|" + "---|" * len(report["subjects"])]
    for f in FAMILIES:
        n = next(iter(report["subjects"].values()))["families"][f]["n"] if report["subjects"] else 0
        cells = [f"{d['families'][f]['match_pct']}% / {d['families'][f]['silent-wrong']}" for d in report["subjects"].values()]
        md.append(f"| {f} | {n} | " + " | ".join(cells) + " |")
    with open(os.path.join(run, "scores.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
