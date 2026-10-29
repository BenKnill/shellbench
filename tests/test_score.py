"""Focused checks of score.py's documented rules (no dependencies).

usage: python3 -I tests/test_score.py      (prints "ok" and exits 0 when every check passes)

Covers the verdict order documented in README.md and score.py, and the oracle validity rules
(repeat check, timeouts, harness failures, cases missing from either oracle run).
"""
import base64, json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from score import classify  # noqa: E402

D0 = {"added": {}, "changed": {}, "deleted": []}


def res(out=b"", err="", code=0, delta=None, **kw):
    return {"stdoutB64": base64.b64encode(out).decode(), "stderr": err, "exitCode": code, "delta": delta or D0, **kw}


def cls(gnu, sub, script="true"):
    return classify(gnu, sub, script)[0]


checks = [
    ("identical", cls(res(b"a\n"), res(b"a\n")), "match"),
    ("stderr wording only", cls(res(b"", "x: No such file"), res(b"", "x: not found file")), "error-text"),
    ("whitespace only", cls(res(b"a  b\n"), res(b"a b\n")), "formatting"),
    ("line order, no sort", cls(res(b"a\nb\n"), res(b"b\na\n")), "formatting"),
    ("line order, script sorts", cls(res(b"a\nb\n"), res(b"b\na\n"), "sort f"), "silent-wrong"),
    ("unsupported message beats formatting",
     cls(res(b"a  b\n"), res(b"a b\n", "x: unknown option -- q")), "loud-unsupported"),
    ("other new stderr", cls(res(b"1\n"), res(b"2\n", "x: something broke")), "loud-wrong"),
    ("wrong answer, no error", cls(res(b"1\n"), res(b"2\n")), "silent-wrong"),
    ("wrong exit status only", cls(res(b"", "", 1), res(b"", "", 0)), "silent-wrong"),
    ("files differ", cls(res(), res(delta={"added": {"/tmp/x": "0" * 16}, "changed": {}, "deleted": []})),
     "silent-wrong"),
]

failed = [f"{name}: got {got}, want {want}" for name, got, want in checks if got != want]

# Oracle validity. A case whose two oracle runs differ (here only in stderr) is nondeterministic. A
# case that times out, fails in the harness (negative exit status) or is missing in either oracle run
# is oracle-unusable. Neither kind is scored. A gnu-repeat.jsonl that exists counts as a repeat run
# even when empty; only an absent file skips the repeat check.
IDS = ("t-001", "t-002", "t-003")


def score_run(gnu, repeat, subj=None):
    """Run score.py on a temporary run dir; repeat=None means no gnu-repeat.jsonl. Returns scores.json or an error."""
    with tempfile.TemporaryDirectory() as tmp:
        run = os.path.join(tmp, "run")
        os.mkdir(run)
        cases_p = os.path.join(tmp, "cases.jsonl")
        with open(cases_p, "w") as f:
            for i in IDS:
                f.write(json.dumps({"id": i, "families": [], "tags": [], "script": "true"}) + "\n")
        rows = {"gnu": gnu, "gnu-repeat": repeat, "subj": subj if subj is not None else gnu}
        for name, rs in rows.items():
            if rs is not None:
                with open(os.path.join(run, name + ".jsonl"), "w") as f:
                    f.writelines(json.dumps(r) + "\n" for r in rs)
        sp = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "score.py"), run, "--cases", cases_p],
                            capture_output=True, text=True)
        if sp.returncode:
            return f"score.py exited {sp.returncode}: {sp.stderr.strip().splitlines()[-1:]}"
        return json.load(open(os.path.join(run, "scores.json")))


def ok(i, out=b"x\n", err=""):
    return res(out, err, id=i)


oracle_checks = [
    # (name, gnu rows, repeat rows or None, want nondeterministic, want oracle_unusable, want scored)
    ("stderr differs between runs; t-003 missing from repeat",
     [ok("t-001", err="e1"), ok("t-002"), ok("t-003")], [ok("t-001", err="e2"), ok("t-002")],
     ["t-001"], ["t-003"], 1),
    ("timeout or harness failure in either run",
     [ok("t-001"), ok("t-002") | {"timeout": True}, ok("t-003")],
     [ok("t-001"), ok("t-002"), res(b"", "HARNESS-ORACLE-FAIL", -1, id="t-003")],
     [], ["t-002", "t-003"], 1),
    ("case missing from the first oracle run",
     [ok("t-001"), ok("t-003")], [ok("t-001"), ok("t-002"), ok("t-003")],
     [], ["t-002"], 2),
    ("empty repeat file: every case is missing from the repeat run",
     [ok("t-001"), ok("t-002"), ok("t-003")], [],
     [], ["t-001", "t-002", "t-003"], 0),
    ("absent repeat file: no repeat check, nothing excluded",
     [ok("t-001"), ok("t-002"), ok("t-003")], None,
     [], [], 3),
]
for name, gnu, repeat, want_nd, want_bad, want_n in oracle_checks:
    rep = score_run(gnu, repeat)
    if isinstance(rep, str):
        failed.append(f"oracle check '{name}': {rep}")
        continue
    got = (rep["nondeterministic"], rep["oracle_unusable"], rep["scored"])
    if got != (want_nd, want_bad, want_n):
        failed.append(f"oracle check '{name}': got nondeterministic/unusable/scored {got}, want {(want_nd, want_bad, want_n)}")

if failed:
    print("\n".join(failed))
    sys.exit(1)
print(f"ok ({len(checks)} verdict checks, {len(oracle_checks)} oracle validity checks)")
