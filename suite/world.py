"""The invented project tree every case starts from (cwd = /home/user/work).

All names and contents here are made up for the benchmark. Entries map a path relative to the
working directory to one of:
  str                      UTF-8 text, mode 0644
  {"b64": ..., "mode": n}  raw bytes
  {"text": ..., "mode": n} text with a mode
  {"symlink": target}
  {"dir": True}            an empty directory
"""
import base64


def _lines(fmt, n, start=1):
    return "".join(fmt.format(i=i) + "\n" for i in range(start, start + n))


NOTES = (
    "Tidepool field notes\n"
    "====================\n"
    "\n"
    "Day 1: the north rocks had 14 anemones and 3 hermit crabs.\n"
    "TODO: recount the anemones at low tide.\n"
    "Day 2: fog until noon; counted 9 sea stars.\n"
    "\n"
    "\n"
    "Day 3: Error in the log sheet, the crab column was shifted.\n"
    "todo: fix the crab column\n"
    "Day 4: calm water, 21 anemones, 2 octopus sightings.\n"
    "Todo: buy a new waterproof notebook\n"
    "Day 5: ERROR copying photos; card was full.\n"
    "Day 6: storm. No survey.\n"
    "Day 7: sea stars 12, anemones 18, crabs 5.\n"
    "\n"
    "Summary\n"
    "-------\n"
    "anemones peaked on day 4\n"
    "sea stars were steady\n"
    "crabs: hard to count\n"
    "Day 8: error rate in counts is about 10 percent.\n"
    "Day 9: low tide at 06:40.\n"
    "Day 10: final survey; 16 anemones.\n"
    "end of notes\n"
)

APP = (
    '"""Tidepool survey service."""\n'
    "import json\n"
    "import os\n"
    "from util import clamp, mean\n"
    "\n"
    "VERSION = \"2.4.1\"\n"
    "MAX_ITEMS = 50\n"
    "\n"
    "\n"
    "class Survey:\n"
    "    def __init__(self, site, day):\n"
    "        self.site = site\n"
    "        self.day = day\n"
    "        self.counts = {}\n"
    "\n"
    "    def add(self, species, n):\n"
    "        # TODO: validate species names\n"
    "        self.counts[species] = self.counts.get(species, 0) + n\n"
    "\n"
    "    def total(self):\n"
    "        return sum(self.counts.values())\n"
    "\n"
    "    def to_json(self):\n"
    "        return json.dumps({\"site\": self.site, \"day\": self.day, \"counts\": self.counts})\n"
    "\n"
    "\n"
    "def load(path):\n"
    "    with open(path) as f:\n"
    "        return json.load(f)\n"
    "\n"
    "\n"
    "def handler(request):\n"
    "    if request.get(\"method\") != \"GET\":\n"
    "        return {\"status\": 405}\n"
    "    items = load(os.environ.get(\"ITEMS\", \"items.json\"))\n"
    "    # fixme: pagination\n"
    "    return {\"status\": 200, \"items\": items[:MAX_ITEMS]}\n"
    "\n"
    "\n"
    "def summarize(surveys):\n"
    "    totals = [s.total() for s in surveys]\n"
    "    return {\"mean\": mean(totals), \"max\": max(totals, default=0)}\n"
    "\n"
    "\n"
    "def main():\n"
    "    s = Survey(\"north\", 1)\n"
    "    s.add(\"anemone\", 14)\n"
    "    s.add(\"crab\", 3)\n"
    "    print(s.to_json())\n"
    "    print(clamp(s.total(), 0, MAX_ITEMS))\n"
    "\n"
    "\n"
    "if __name__ == \"__main__\":\n"
    "    main()\n"
)

UTIL = (
    "def clamp(x, lo, hi):\n"
    "    return max(lo, min(hi, x))\n"
    "\n"
    "\n"
    "def mean(xs):\n"
    "    xs = list(xs)\n"
    "    if not xs:\n"
    "        return 0\n"
    "    return sum(xs) / len(xs)\n"
    "\n"
    "\n"
    "def chunks(xs, n):\n"
    "    # TODO: handle n <= 0\n"
    "    for i in range(0, len(xs), n):\n"
    "        yield xs[i:i + n]\n"
)

ROUTES = (
    "import { Router } from './router.js';\n"
    "\n"
    "export const routes = new Router();\n"
    "\n"
    "routes.get('/api/items', async (req) => {\n"
    "  const items = await req.store.list('items');\n"
    "  return { status: 200, body: items };\n"
    "});\n"
    "\n"
    "routes.get('/api/items/:id', async (req) => {\n"
    "  const item = await req.store.get('items', req.params.id);\n"
    "  if (!item) return { status: 404 };\n"
    "  return { status: 200, body: item };\n"
    "});\n"
    "\n"
    "// TODO: add rate limiting\n"
    "routes.post('/api/items', async (req) => {\n"
    "  const id = await req.store.put('items', req.body);\n"
    "  return { status: 201, body: { id } };\n"
    "});\n"
)

LEVELS = ["INFO", "INFO", "WARN", "INFO", "ERROR", "INFO", "DEBUG"]
PATHS = ["/api/items", "/api/items/7", "/health", "/api/items", "/api/sites", "/api/items/12"]
LOG = "".join(
    "2026-03-14T09:{m:02d}:{s:02d}Z {lvl:<5} req={i} path={p} status={st} ms={ms}\n".format(
        m=i // 6, s=(i * 7) % 60, lvl=LEVELS[i % 7], i=100 + i, p=PATHS[i % 6],
        st=500 if LEVELS[i % 7] == "ERROR" else (404 if i % 11 == 0 else 200), ms=(i * 37) % 250 + 3)
    for i in range(48))

REGIONS = ["north", "south", "east", "west"]
ITEMS = ["kelp", "net", "bucket", "lamp", "rope", "float"]
ORDERS = "id,customer,item,qty,price,region\n" + "".join(
    f"{i},cust{(i * 7) % 13:02d},{ITEMS[i % 6]},{(i * 3) % 17 + 1},{(i * 113) % 900 / 10 + 1:.2f},{REGIONS[i % 4]}\n"
    for i in range(1, 21))

SCORES = "name\tround\tscore\n" + "".join(
    f"{n}\t{r}\t{(len(n) * 13 + r * 29) % 100}\n"
    for r in (1, 2) for n in ("ana", "bo", "cy", "dee", "eli", "fay"))

ITEMS_JSON = (
    '[\n'
    '  {"id": 1, "name": "kelp", "tags": ["green", "soft"], "price": 2.5, "stock": 10},\n'
    '  {"id": 2, "name": "net", "tags": [], "price": 12.0, "stock": 0},\n'
    '  {"id": 3, "name": "bucket", "tags": ["blue"], "price": 4.25, "stock": 7, "note": null},\n'
    '  {"id": 4, "name": "lamp", "tags": ["brass", "old"], "price": 30, "stock": 2},\n'
    '  {"id": 5, "name": "café sign", "tags": ["wood"], "price": 1e2, "stock": 1}\n'
    ']\n'
)

WORLD = {
    "README.md": (
        "# tidepool\n\nA small survey service.\n\n## Usage\n\n"
        "    python3 src/app.py\n\n## Layout\n\n- `src/` code\n- `docs/` guides\n- `tests/` tests\n\n"
        "## License\n\nMIT\n"),
    "CHANGELOG.md": (
        "# Changelog\n\n## 2.4.1\n- fix: crab counts\n\n## 2.4.0\n- feat: JSON export\n- feat: sites API\n\n"
        "## 2.3.9\n- fix: fog days\n\n## 2.10.0-rc1\n- preview\n"),
    "notes.txt": NOTES,
    "server.log": LOG,
    "orders.csv": ORDERS,
    "scores.tsv": SCORES,
    "items.json": ITEMS_JSON,
    "config.ini": (
        "[server]\nhost = 127.0.0.1\nport = 8080\ndebug = false\n\n[survey]\nsites = north,south,east\n"
        "max_items = 50\n# comment line\n; other comment\n"),
    "src/app.py": APP,
    "src/util.py": UTIL,
    "src/web/routes.js": ROUTES,
    "src/web/style.css": "body { margin: 0; }\n.card {\n  padding: 4px;\n  color: #333;\n}\n",
    "tests/test_app.py": (
        "from app import Survey\n\n\ndef test_total():\n    s = Survey('x', 1)\n    s.add('crab', 2)\n"
        "    assert s.total() == 2\n\n\ndef test_empty():\n    assert Survey('y', 2).total() == 0\n"),
    "scripts/build.sh": {"text": "#!/bin/sh\nset -e\necho building tidepool\n", "mode": 0o755},
    "scripts/check.sh": {"text": "#!/bin/sh\necho check ok\nexit 3\n", "mode": 0o755},
    "scripts/notes.md": "build.sh builds; check.sh exits 3 on purpose.\n",
    "docs/guide.md": "# Guide\n\nRun the survey at low tide.\nRecord counts per species.\n",
    "docs/faq.md": "# FAQ\n\nQ: Why tidepools?\nA: They are small.\n",
    "docs/latest.md": {"symlink": "guide.md"},
    "docs/old.md": {"symlink": "removed.md"},
    "link-to-src": {"symlink": "src"},
    ".env.example": "PORT=8080\nDEBUG=0\n",
    ".hidden/keep.txt": "hidden file\n",
    "empty": {"dir": True},
    "unicode.txt": "café au lait\nnaïve résumé\n日本語のテキスト\nÜber straße\nemoji 🌊 wave\nplain ascii\n",
    "latin1.txt": {"b64": base64.b64encode(b"caf\xe9 cr\xe8me\nplain\n").decode()},
    "bin.dat": {"b64": base64.b64encode(bytes(range(0, 48)) + b"\nmarker text\n\x00\xff\xfe").decode()},
    "versions.txt": "v1.10.0\nv1.2.0\nv1.9.3\nv2.0.0\nv1.2.10\nv1.2.9\nv10.0.0\n",
    "words.txt": "banana\nApple\napple\n_under\nZebra\nzebra\néclair\nbanana\n10\n9\n100\n-5\napple\n",
    "nums.txt": "42\n7\n-3\n7\n1e3\n0x10\n3.14\n 8\n100\n",
    "dup.txt": "a\na\nb\nb\nb\nc\na\n",
    "crlf.txt": {"b64": base64.b64encode(b"one\r\ntwo\r\nthree\r\n").decode()},
    "noeol.txt": {"b64": base64.b64encode(b"first\nsecond\nno newline at end").decode()},
    "blank.txt": "",
    "spaces in name.txt": "file with spaces\n",
    "long.txt": _lines("line {i}: the quick brown fox jumps over the lazy dog", 120),
}
