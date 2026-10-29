"""Runs INSIDE the sandbox: snapshot the roots, run one script with real bash, snapshot again,
and print stdout, stderr, exit code and the file delta as JSON.

stdin: {"script", "cwd", "env", "timeout", "roots": [...], "nproc"}
"""
import base64, hashlib, json, os, resource, signal, stat, subprocess, sys

c = json.loads(sys.stdin.read())
CAP = 4 * 1024 * 1024


def snapshot(roots):
    snap = {}
    for root in roots:
        for dp, dns, fns in os.walk(root):
            for n in dns + fns:
                p = os.path.join(dp, n)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                if stat.S_ISLNK(st.st_mode):
                    snap[p] = "<symlink>"
                elif stat.S_ISDIR(st.st_mode):
                    snap[p] = "<dir>"
                elif stat.S_ISREG(st.st_mode):
                    try:
                        with open(p, "rb") as f:
                            snap[p] = hashlib.sha256(f.read()).hexdigest()[:16]
                    except OSError:
                        snap[p] = "<unreadable>"
                else:
                    snap[p] = "<other>"
    return snap


def limits():
    os.setsid()
    resource.setrlimit(resource.RLIMIT_CPU, (20, 25))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 << 20, 64 << 20))
    resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))
    if c.get("nproc"):
        resource.setrlimit(resource.RLIMIT_NPROC, (c["nproc"], c["nproc"]))


before = snapshot(c["roots"])
timed_out = False
p = subprocess.Popen(["bash", "-c", c["script"]], executable="/bin/bash", cwd=c["cwd"], env=c["env"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=limits)
try:
    out, err = p.communicate(timeout=c.get("timeout", 10))
except subprocess.TimeoutExpired:
    timed_out = True
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        pass
    out, err = p.communicate()
code = p.returncode
if code is not None and code < 0:
    code = 128 - code
try:
    os.killpg(p.pid, signal.SIGKILL)
except OSError:
    pass
after = snapshot(c["roots"])
delta = {"added": {}, "changed": {}, "deleted": sorted(k for k in before if k not in after)}
for k, v in after.items():
    if k not in before:
        delta["added"][k] = v
    elif before[k] != v:
        delta["changed"][k] = v
sys.stdout.write(json.dumps({
    "stdout": out[:CAP].decode("utf-8", "replace"),
    "stdoutB64": base64.b64encode(out[:CAP]).decode(),
    "stdoutLen": len(out),
    "stderr": err[:CAP].decode("utf-8", "replace"),
    "exitCode": code,
    "timeout": timed_out,
    "delta": delta,
}))
