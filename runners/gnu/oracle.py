"""shellbench truth oracle: run every case with GNU bash and GNU tools in a bubblewrap sandbox.
Linux only.

usage: python3 -I runners/gnu/oracle.py --cases suite/cases.jsonl --world suite/world.json \
          --gnubin DIR --workdir NEW_DIR --out results/gnu.jsonl [--workers 4] [--timeout 10]

--gnubin  a directory of GNU coreutils under their plain names, put first on PATH (on distributions
          whose default coreutils are not GNU, e.g. symlinks `ls -> /usr/bin/gnuls`). Other tools
          (grep, sed, gawk, findutils, diffutils, jq, rg, perl's shasum) come from /usr/bin.
--workdir a new directory for the materialized case trees; the script never deletes anything.

Each case runs in its own sandbox: read-only /usr and /etc, an /etc/passwd naming the runner's uid
`user`, private /tmp, no network, new pid/ipc/uts/user namespaces, rlimits, a timeout, and a
copy-on-write overlay over the case's tree at /home, so writes vanish with the sandbox.
"""
import argparse, base64, concurrent.futures as cf, json, os, subprocess, sys

FIXED = 1790856000  # 2026-10-01T12:00:00Z, every seeded file, link and directory
HERE = os.path.dirname(os.path.abspath(__file__))
HOME, CWD = "/home/user", "/home/user/work"
ENV = {"HOME": HOME, "USER": "user", "LOGNAME": "user", "PATH": "/opt/gnubin:/usr/local/bin:/usr/bin:/bin",
       "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC", "SHELL": "/bin/bash", "TERM": "dumb"}

ap = argparse.ArgumentParser()
ap.add_argument("--cases", required=True)
ap.add_argument("--world", required=True)
ap.add_argument("--gnubin", required=True)
ap.add_argument("--workdir", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--timeout", type=int, default=10)
a = ap.parse_args()

os.makedirs(a.workdir)  # must be new
wd = os.path.abspath(a.workdir)
worlds = json.load(open(a.world))
cases = [json.loads(l) for l in open(a.cases) if l.strip()]
uid, gid = os.getuid(), os.getgid()
with open(os.path.join(wd, "passwd"), "w") as f:
    f.write(f"root:x:0:0:root:/root:/bin/bash\nuser:x:{uid}:{gid}:user:{HOME}:/bin/bash\n")
with open(os.path.join(wd, "group"), "w") as f:
    f.write(f"root:x:0:\nuser:x:{gid}:\n")


def materialize(case):
    top = os.path.join(wd, "cases", case["id"])
    root = top + CWD
    os.makedirs(root)
    entries = dict(worlds[case["world"]])
    entries.update(case.get("files") or {})
    for rel, v in sorted(entries.items()):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if isinstance(v, str):
            v = {"text": v}
        if v.get("dir"):
            os.makedirs(p, exist_ok=True)
        elif "symlink" in v:
            os.symlink(v["symlink"], p)
        else:
            data = base64.b64decode(v["b64"]) if "b64" in v else v["text"].encode()
            with open(p, "wb") as f:
                f.write(data)
            os.chmod(p, v.get("mode", 0o644))
    for dp, dns, fns in os.walk(top, topdown=False):
        for n in fns + dns:
            os.utime(os.path.join(dp, n), (FIXED, FIXED), follow_symlinks=False)
        os.utime(dp, (FIXED, FIXED))
    return top


def argv(top):
    return ["bwrap", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/sbin", "/sbin", "--ro-bind", "/etc", "/etc",
            "--ro-bind", os.path.join(wd, "passwd"), "/etc/passwd", "--ro-bind", os.path.join(wd, "group"), "/etc/group",
            "--tmpfs", "/tmp", "--tmpfs", "/var/tmp", "--dev", "/dev", "--proc", "/proc",
            "--ro-bind", os.path.abspath(a.gnubin), "/opt/gnubin", "--ro-bind", HERE, "/opt/sb",
            "--dir", "/home", "--overlay-src", os.path.join(top, "home"), "--tmp-overlay", "/home",
            "--unshare-all", "--hostname", "shellbench", "--die-with-parent", "--new-session", "--clearenv",
            "--setenv", "PATH", "/usr/bin:/bin", "/usr/bin/python3", "-I", "/opt/sb/inner.py"]


def run_one(case, top):
    payload = {"script": case["script"], "cwd": CWD, "env": ENV, "timeout": a.timeout, "roots": [HOME, "/tmp"],
               "nproc": 4096}
    try:
        cp = subprocess.run(argv(top), input=json.dumps(payload).encode(), capture_output=True, timeout=a.timeout + 60)
        r = json.loads(cp.stdout.decode())
    except (subprocess.TimeoutExpired, ValueError, OSError) as e:
        r = {"stdout": "", "stdoutB64": "", "stderr": f"HARNESS-ORACLE-FAIL: {e}", "exitCode": -1,
             "delta": {"added": {}, "changed": {}, "deleted": []}}
    r["id"] = case["id"]
    return r


tops = {c["id"]: materialize(c) for c in cases}
with cf.ThreadPoolExecutor(a.workers) as ex:
    results = list(ex.map(lambda c: run_one(c, tops[c["id"]]), cases))
with open(a.out, "w") as f:
    for r in results:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# record the tool versions seen inside the sandbox
probe = {"id": "_versions", "world": cases[0]["world"], "files": {}, "script": (
    "for t in bash ls sort cut wc head sed grep awk find xargs diff od jq rg; do "
    "printf '%s\\t' \"$t\"; $t --version 2>&1 | head -n 1; done; "
    "printf 'xxd\\t'; xxd -v 2>&1 | head -n 1; "
    "printf 'shasum\\t'; shasum --version; printf 'command -v ls\\t'; command -v ls")}
v = run_one(probe, materialize(probe))
meta = {"oracle": "GNU", "sandbox": "bubblewrap " + subprocess.run(["bwrap", "--version"], capture_output=True,
                                                                     text=True).stdout.strip(),
        "env": ENV, "cwd": CWD, "cases": len(results), "versions": dict(
            ln.split("\t", 1) for ln in v["stdout"].splitlines() if "\t" in ln)}
with open(a.out + ".meta.json", "w") as f:
    json.dump(meta, f, indent=1)
print(json.dumps({"done": len(results), "versions": meta["versions"]}, indent=1), file=sys.stderr)
