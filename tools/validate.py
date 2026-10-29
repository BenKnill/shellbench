"""Compare suite scores with corpus scores for the same builds (aggregates only).

usage: python3 -I tools/validate.py RUN_DIR/scores.json validation/corpus-rescored.json OUT_PREFIX \
          [SUITE_SUBJECT=CORPUS_BUILD ...]

A suite subject is compared with the corpus build of the same name, or with the corpus build named
in a SUITE_SUBJECT=CORPUS_BUILD pair (for example when the suite measured a build through a
different host than the corpus did). The pairs used are recorded in OUT_PREFIX.json.

Writes OUT_PREFIX.json and OUT_PREFIX.md: overall ranking agreement, corpus-weighted suite scores,
per-family correlation across builds, and the direction of change between pairs of builds.
"""
import json, math, sys

suite = json.load(open(sys.argv[1]))["subjects"]
corpus_by_build = json.load(open(sys.argv[2]))
out = sys.argv[3]
paired = dict(a.split("=", 1) for a in sys.argv[4:])
corpus_build = {s: paired.get(s, s) for s in suite if paired.get(s, s) in corpus_by_build}
corpus = {s: corpus_by_build[c] for s, c in corpus_build.items()}
builds = sorted(corpus)


def rate(d, cls):
    n = sum(d[c] for c in d if c not in ("n", "match_pct", "silent_pct"))
    return d[cls] / n if n else None


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy) if sx and sy else None


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for t in range(i, j + 1):
            r[order[t]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


res = {"builds": builds, "corpus_build": corpus_build, "overall": {}, "weighted": {}, "families": {}, "pairs": {}}
for b in builds:
    s, c = suite[b], corpus[b]["overall"]
    n = sum(c.values())
    res["overall"][b] = {"suite_match": rate(s["classes"], "match"), "suite_silent": rate(s["classes"], "silent-wrong"),
                         "corpus_match": c["match"] / n, "corpus_silent": c["silent-wrong"] / n}
fams = sorted({f for b in builds for f in corpus[b]["families"]} & set(next(iter(suite.values()))["families"]))
share = {f: sum(corpus[builds[0]]["families"][f].values()) for f in fams}
tot_share = sum(share.values())
for b in builds:
    w_match = sum(share[f] / tot_share * rate(suite[b]["families"][f], "match") for f in fams)
    w_silent = sum(share[f] / tot_share * rate(suite[b]["families"][f], "silent-wrong") for f in fams)
    res["weighted"][b] = {"suite_match_corpus_weighted": w_match, "suite_silent_corpus_weighted": w_silent}
xs_m, ys_m, xs_s, ys_s = [], [], [], []
for f in fams:
    row = {}
    for b in builds:
        cf = corpus[b]["families"][f]
        row[b] = {"suite_n": suite[b]["families"][f]["n"], "corpus_n": sum(cf.values()),
                  "suite_nonmatch": 1 - rate(suite[b]["families"][f], "match"),
                  "corpus_nonmatch": 1 - rate(cf, "match"),
                  "suite_silent": rate(suite[b]["families"][f], "silent-wrong"), "corpus_silent": rate(cf, "silent-wrong")}
        xs_m.append(row[b]["suite_nonmatch"]); ys_m.append(row[b]["corpus_nonmatch"])
        xs_s.append(row[b]["suite_silent"]); ys_s.append(row[b]["corpus_silent"])
    res["families"][f] = row
o = res["overall"]
res["rank"] = {
    "spearman_match": spearman([o[b]["suite_match"] for b in builds], [o[b]["corpus_match"] for b in builds]),
    "spearman_silent": spearman([o[b]["suite_silent"] for b in builds], [o[b]["corpus_silent"] for b in builds]),
    "pearson_match": pearson([o[b]["suite_match"] for b in builds], [o[b]["corpus_match"] for b in builds]),
    "pearson_silent": pearson([o[b]["suite_silent"] for b in builds], [o[b]["corpus_silent"] for b in builds]),
    "family_build_points": len(xs_m),
    "family_pearson_nonmatch": pearson(xs_m, ys_m), "family_spearman_nonmatch": spearman(xs_m, ys_m),
    "family_pearson_silent": pearson(xs_s, ys_s), "family_spearman_silent": spearman(xs_s, ys_s),
}
for a, b in [(x, y) for i, x in enumerate(builds) for y in builds[i + 1:]]:
    agree = disagree = tie = 0
    for f in fams:
        ds = res["families"][f][b]["suite_nonmatch"] - res["families"][f][a]["suite_nonmatch"]
        dc = res["families"][f][b]["corpus_nonmatch"] - res["families"][f][a]["corpus_nonmatch"]
        if abs(ds) < 1e-9 or abs(dc) < 1e-4:
            tie += 1
        elif (ds > 0) == (dc > 0):
            agree += 1
        else:
            disagree += 1
    res["pairs"][f"{a} vs {b}"] = {
        "suite_match_delta_pp": 100 * (o[b]["suite_match"] - o[a]["suite_match"]),
        "corpus_match_delta_pp": 100 * (o[b]["corpus_match"] - o[a]["corpus_match"]),
        "suite_silent_delta_pp": 100 * (o[b]["suite_silent"] - o[a]["suite_silent"]),
        "corpus_silent_delta_pp": 100 * (o[b]["corpus_silent"] - o[a]["corpus_silent"]),
        "families_same_direction": agree, "families_opposite": disagree, "families_no_change": tie}
with open(out + ".json", "w") as fh:
    json.dump(res, fh, indent=1)

P = lambda v: f"{100 * v:.1f}%"  # noqa: E731
md = ["| Build | Suite match | Corpus match | Suite silent-wrong | Corpus silent-wrong | Suite, corpus-weighted match | Suite, corpus-weighted silent |",
      "|---|---|---|---|---|---|---|"]
for b in builds:
    md.append(f"| {b} | {P(o[b]['suite_match'])} | {P(o[b]['corpus_match'])} | {P(o[b]['suite_silent'])} | "
              f"{P(o[b]['corpus_silent'])} | {P(res['weighted'][b]['suite_match_corpus_weighted'])} | "
              f"{P(res['weighted'][b]['suite_silent_corpus_weighted'])} |")
r = res["rank"]
md += ["", "Corpus build for each suite subject: " + ", ".join(f"{b} = {corpus_build[b]}" for b in builds) + ".",
       "", f"Rank agreement across the {len(builds)} builds: Spearman {r['spearman_match']:.2f} (match), "
       f"{r['spearman_silent']:.2f} (silent-wrong). Pearson {r['pearson_match']:.2f} (match), {r['pearson_silent']:.2f} (silent-wrong).",
       f"Per family and build ({r['family_build_points']} points): Pearson {r['family_pearson_nonmatch']:.2f} / Spearman "
       f"{r['family_spearman_nonmatch']:.2f} for the non-match rate; Pearson {r['family_pearson_silent']:.2f} / Spearman "
       f"{r['family_spearman_silent']:.2f} for the silent-wrong rate.", "",
       "| Pair | Match change, suite | Match change, corpus | Silent change, suite | Silent change, corpus | Families: same direction / opposite / no change |",
       "|---|---|---|---|---|---|"]
for k, v in res["pairs"].items():
    md.append(f"| {k} | {v['suite_match_delta_pp']:+.1f} pp | {v['corpus_match_delta_pp']:+.2f} pp | "
              f"{v['suite_silent_delta_pp']:+.1f} pp | {v['corpus_silent_delta_pp']:+.2f} pp | "
              f"{v['families_same_direction']} / {v['families_opposite']} / {v['families_no_change']} |")
md += ["", "| Family | Corpus instances | Suite cases | " + " | ".join(f"{b} non-match suite / corpus" for b in builds) + " |",
       "|---|---|---|" + "---|" * len(builds)]
for f in fams:
    row = res["families"][f]
    md.append(f"| {f} | {row[builds[0]]['corpus_n']} | {row[builds[0]]['suite_n']} | " + " | ".join(
        f"{P(row[b]['suite_nonmatch'])} / {P(row[b]['corpus_nonmatch'])}" for b in builds) + " |")
with open(out + ".md", "w") as fh:
    fh.write("\n".join(md) + "\n")
print("\n".join(md))
