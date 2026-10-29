"""Build suite/cases.jsonl and suite/world.json from cases_def.py and world.py.

usage: python3 -I suite/build.py
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from cases_def import CASES  # noqa: E402
from world import WORLD  # noqa: E402
from families import UTIL2FAM, families_of  # noqa: E402

KEYWORDS = {"if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done", "case", "esac",
            "in", "function", "!", "{", "}", "time", "select", "shopt"}
WRAPPERS = {"xargs", "timeout", "nice", "env", "command"}


def strip_heredocs(script):
    out, lines, i = [], script.split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        out.append(ln)
        m = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", ln.replace("<<<", "   "))
        i += 1
        if m:
            term = m.group(1)
            while i < len(lines) and lines[i].lstrip("\t") != term:
                i += 1
            i += 1
    return "\n".join(out)


def utilities(script):
    """Command words at command position (approximate; good enough for these hand-written scripts)."""
    s = strip_heredocs(script)
    s = re.sub(r"'[^']*'", "''", s)  # drop single-quoted text
    segs = re.split(r"\|\||&&|[|;\n(){}`]|\$\(|\bthen\b|\bdo\b|\belse\b|-exec\b", s)
    found = []
    for seg in segs:
        toks = seg.split()
        while toks and (re.match(r"^\w+=", toks[0]) or toks[0] in KEYWORDS or re.match(r"^\d*[<>]", toks[0])):
            toks = toks[1:]
        while toks:
            w = toks[0].strip("\"'")
            if w in UTIL2FAM:
                found.append(w)
            if w in WRAPPERS:
                toks = [t for t in toks[1:] if not t.startswith("-") and not re.match(r"^[\d{}]+$", t)
                        and t not in ("-n", "-I{}")]
                continue
            break
    return sorted(set(found))


def tags(script, files):
    t = set()
    body = script
    unq = re.sub(r"'[^']*'", "''", script)
    if re.search(r"<<-?\s*['\"]?\w", body.replace("<<<", "")):
        t.add("heredoc")
    if "<<<" in body:
        t.add("herestring")
    if re.search(r"(^|[^0-9&])>>?\s*(?!/dev/null|&)", unq):
        t.add("write")
    if re.search(r"[^\x00-\x7f]", body) or re.search(r"unicode\.txt|latin1\.txt|bin\.dat|crlf\.txt|\\3\d\d", body):
        t.add("non-ascii")
    if re.search(r"(?<!\|)\|(?!\|)", unq):
        t.add("pipeline")
    if re.search(r"rc=\$\?|PIPESTATUS|pipefail|set -e", body):
        t.add("exit-status")
    if re.search(r"link-to-src|latest\.md|old\.md|ln -s|\.lnk|readlink|realpath", body):
        t.add("symlink")
    if "set -u" in body:
        t.add("set-u")
    if re.search(r"\b(grep|rg)\b[^|;]*\s-[A-Za-z]*[ABC]\d*", body):
        t.add("context")
    if re.search(r"\bmissing|nodir|reports/", body):
        t.add("missing-path")
    if re.search(r"(^|\s)-[a-z]*i\b|sed -i", body) and "sed" in body:
        t.add("in-place")
    return sorted(t)


# Cases whose GNU result depends on the oracle host's file system: directory read order (the order
# rule scores a different order as formatting) or block allocation (du).
HOST_DEPENDENT = {"grep-017", "grep-018", "grep-020", "grep-021", "rg-011", "rg-022", "ls-stat-021"}


def main():
    rows = []
    for fam, entries in CASES.items():
        for i, e in enumerate(entries, 1):
            script, extra = (e, {}) if isinstance(e, str) else e
            utils = utilities(script)
            fams = sorted(set(families_of(utils)) | {fam})
            rows.append({"id": f"{fam}-{i:03d}", "family": fam, "families": fams, "utils": utils,
                         "tags": sorted(set(tags(script, extra)) | ({"host-fs"} if f"{fam}-{i:03d}" in HOST_DEPENDENT else set())),
                         "world": "project", "files": extra, "script": script})
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    with open(os.path.join(HERE, "cases.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(HERE, "world.json"), "w") as f:
        json.dump({"project": WORLD}, f, ensure_ascii=False, indent=1, sort_keys=True)
    by = {}
    for r in rows:
        by[r["family"]] = by.get(r["family"], 0) + 1
    print(len(rows), "cases", by)


if __name__ == "__main__":
    main()
