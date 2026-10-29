# shellbench

shellbench measures how closely a simulated shell reproduces real bash and GNU tools. It is aimed at
the shell emulators that coding agents use inside V8 isolates and other sandboxes, where a
TypeScript interpreter over a virtual file system stands in for bash and coreutils.

An agent acts on what the shell tells it. When a shell fails loudly, the agent sees an error and can
retry or work around it. When a shell gives a different answer and reports no error, the agent has
no sign that anything went wrong. shellbench counts both kinds of difference and reports the silent
kind separately.

Every case is synthetic. The choice of families and weights was informed by a private study of
commands that coding agents ran (see [Relation to the private corpus](#relation-to-the-private-corpus)),
but no command, path, file name or output from that study appears here.

The results below are from run `2026-10-29c`. It was made from a fresh clone of this repository's
code; `results/2026-10-29c/source-rev.txt` records the git object ids of the code it ran (see
[Reproducing the published run](#reproducing-the-published-run)).

## What is measured

Each case is a small bash script plus a starting file tree. The case runs once under real GNU bash
(the oracle) and once under each subject shell, from identical starting states. shellbench then
compares:

- stdout, byte for byte;
- stderr;
- the exit status of the whole script;
- the file system afterwards: files added, changed or deleted under `/home/user` and `/tmp`, by
  content hash and entry type (file, directory, symlink).

### Environment

Every shell gets the same environment: cwd `/home/user/work`, `HOME=/home/user`, `USER=user`,
`LC_ALL=C.UTF-8`, `TZ=UTC`, `PATH=/opt/gnubin:/usr/local/bin:/usr/bin:/bin`. Every seeded file,
directory and symlink has mtime 2026-10-01 12:00 UTC. `/tmp` exists and is empty.

### Oracle

GNU bash 5.3.9 with GNU coreutils 9.7 first on `PATH`, GNU grep 3.12, GNU sed 4.9, GNU Awk 5.3.2,
GNU findutils 4.10.0, GNU diffutils 3.12, jq 1.8.1, ripgrep 15.1.0, xxd 2025-11-26 and Perl's
`shasum` 6.04, on Linux (Ubuntu 26.04, x86_64). The runner reads these versions inside the sandbox
on every run and stores them in `results/RUN/gnu.jsonl.meta.json`. Some distributions now ship
non-GNU coreutils by default, so the runner puts a directory of GNU coreutils first on `PATH` and
records `command -v ls` to show which `ls` ran.

Each case runs in its own bubblewrap 0.11 sandbox: read-only `/usr` and `/etc`, an `/etc/passwd`
that names the runner's uid `user`, a private `/tmp`, no network, new namespaces, rlimits, a 10 s
timeout, and a copy-on-write overlay over the case's tree. The script runs as `bash -c SCRIPT` with
`$0` set to `bash`. The oracle runs twice. A case that times out, fails in the harness or is
missing in either run is oracle-unusable, and a usable case whose two oracle results differ in
stdout, stderr, exit status or files is nondeterministic. Neither kind is scored. Run `2026-10-29c`
had none of either.

### Verdicts

Each subject result gets one class. The classes are checked in this order, and the first that
applies wins. "The answer differs" means that stdout, the exit status or the file changes differ.

| Class | Meaning |
|---|---|
| match | stdout, exit status, file changes and stderr all identical |
| error-text | only stderr differs |
| loud-unsupported | the answer differs, and the subject prints a not-found, unknown-option or unsupported message that GNU does not print |
| formatting | exit status and file changes identical; stdout differs only in whitespace, in line order, or in `ls -l` fields an in-memory file system cannot know (owner, group, link count, times, directory sizes, block totals) |
| loud-wrong | the answer differs, and the subject's stderr is not empty and differs from GNU's |
| silent-wrong | everything else: the answer differs in substance, and the subject printed no error that GNU did not also print |

`error-text` is the scorer's label for differences confined to stderr; these are not necessarily
wording changes. `formatting` is a heuristic tolerance category for the specified whitespace, order,
and metadata differences. Neither relaxed category establishes semantic equivalence. The strict
`match` column is the exact comparison under the documented measurement contract.

Some consequences of these rules are worth knowing:

- Differences only in padding, column widths or a missing final newline count as formatting. An
  example is `view-039`, where just-bash's `nl` omits the final newline that GNU `nl` adds.
- When the script runs `sort` and stdout differs only in line order, the case is silent-wrong, not
  formatting.
- A not-found or unsupported message takes precedence over formatting: such a case is
  loud-unsupported even if stdout differs only in whitespace.
- A subject that times out, crashes or throws an exception from its exec call counts as loud-wrong.

`score.py` implements these rules (`classify()`).

The results table gives silent-wrong counts on their own, with the subset where the subject's exit
status was 0. The loud classes look at stderr, not only at the final exit status, because scripts
often end in `echo` or a pipeline that hides a failing command's status.

## The suite

The suite has 351 cases in 15 command families. All of them run against one invented project tree of
36 entries: a small Python and JavaScript service, its notes and logs, CSV/TSV/JSON data, a
symlinked directory, a dangling symlink, executable scripts, hidden files, an empty directory, CRLF
and no-final-newline files, UTF-8 text with accents, CJK and emoji, a Latin-1 file and a binary file.

| Family | Utilities | Cases (primary) | Cases (any use) |
|---|---|---|---|
| view | cat, head, tail, nl, tac | 55 | 100 |
| sed | sed | 42 | 43 |
| shell | builtins, expansions, redirects, pipelines, `set -u/-e/-o pipefail`, traps | 51 | 88 |
| grep | grep | 38 | 44 |
| rg | ripgrep | 23 | 23 |
| ls-stat | ls, stat, du | 23 | 35 |
| fileops | cp, mv, rm, mkdir, ln, chmod, tar, readlink, realpath, ... | 22 | 24 |
| cut-tr | cut, tr, paste, column, fold | 18 | 21 |
| wc | wc | 14 | 20 |
| sort-uniq | sort, uniq | 13 | 30 |
| awk | awk | 13 | 13 |
| find-xargs | find, xargs | 11 | 12 |
| diff-bytes | diff, cmp, od, xxd, base64 | 10 | 18 |
| checksum | sha256sum, shasum, md5sum, sha1sum, cksum | 9 | 9 |
| jq | jq | 9 | 9 |

"Cases (any use)" counts every case whose script uses a utility of the family; per-family scores
use this count. Cases also carry tags for cross-cutting behaviour: `heredoc`, `write`, `non-ascii`,
`pipeline`, `exit-status`, `symlink`, `set-u`, `context` (grep/rg context lines), `missing-path` and
`host-fs`. Seven cases are tagged `host-fs`. Their GNU result depends on the oracle host's file
system, either through directory read order (which the order rule scores as formatting) or through
block allocation (`du`).

### How the size and the weights were chosen

Each family's share of cases follows the square root of how often agents used that family in the
private corpus, scaled to about 300 cases, with a floor of 9 cases per family. The square root keeps
the most common family from crowding out the others. That family is viewing files with cat, head,
tail and `sed -n`, which makes up about two thirds of all agent commands in the corpus. The final
counts depart from the formula in two places on purpose. `shell` and `grep` have extra cases,
because the corpus's largest divergence classes live there: grep context lines, redirects into
missing directories, globbing and `set -u`. Within each family, cases mix the shapes agents use
most (`sed -n 'A,Bp'`, `grep -n`, `head -n N`, `ls -la`, heredoc writes) with probes for every
divergence class the corpus study found.

The suite is small enough that the GNU oracle runs it in a few seconds with 4 workers, and each
just-bash subject below runs it in under a second in Node. A shell's authors can run it on every
change.
`tools/regression_screen.py` lists, case by case, what changed between two builds.

### Case format

`suite/cases_def.py` holds the scripts and `suite/world.py` the starting tree. `python3 -I
suite/build.py` writes `suite/cases.jsonl` and `suite/world.json`. A case line looks like this:

```json
{"id": "grep-002", "family": "grep", "families": ["grep"], "utils": ["grep"], "tags": ["context"],
 "world": "project", "files": {}, "script": "grep -n -A2 anemones notes.txt"}
```

`files` adds case-specific entries on top of the world: text, `{"b64": ...}`, `{"symlink": ...}`
or `{"dir": true}`, each with an optional `mode`. Case ids are stable, and new cases are appended.

## Results (run 2026-10-29c)

| Subject | Match | + error text | + formatting | Silent-wrong (exit 0) | Loud-wrong | Loud-unsupported |
|---|---|---|---|---|---|---|
| just-bash 3.6.0 (npm) | 70.7% | 72.4% | 76.6% | 52 (50) | 11 | 19 |
| just-bash main `7a2a7a57` | 72.1% | 73.8% | 78.1% | 47 (45) | 11 | 19 |
| just-bash 3.2.0 (npm) | 68.9% | 70.7% | 74.9% | 58 (55) | 11 | 19 |
| Cloudflare Computer worker-shell, local workerd (`071b2b2`, runs just-bash 3.2.0) | 68.7% | 70.4% | 74.4% | 57 (54) | 14 | 19 |

Percentages are of 351 scored cases. The "+" columns are cumulative: "+ formatting" counts match,
error-text and formatting together. They add the two relaxed categories, which do not establish
semantic equivalence (see [Verdicts](#verdicts)); Match is the strict comparison. The other columns
count cases. Every subject was measured as shipped, or as built from source, with default options.
"Silent" is relative to this oracle, GNU tools on Linux.

**Subjects.**

- **just-bash 3.6.0 (npm).** `just-bash@3.6.0` from the npm registry, over its `InMemoryFs`, with
  default exec options.
- **just-bash main `7a2a7a57`.** The main branch of
  [vercel-labs/just-bash](https://github.com/vercel-labs/just-bash) as of 2026-10-29, built from
  source with `pnpm build`. Its `package.json` also says 3.6.0, but its bundle differs from the npm
  release.
- **just-bash 3.2.0 (npm).** Cloudflare Computer's lockfile pins this version. It is measured on its
  own so that differences that come from Computer can be told apart from differences that come from
  the just-bash version Computer ships.
- **Cloudflare Computer worker-shell.** `ShellWorker` from `@cloudflare/computer` 0.8.0, at
  [cloudflare/computer](https://github.com/cloudflare/computer) main `071b2b2` (2026-10-28). It runs
  just-bash 3.2.0 over Computer's `WorkspaceFsAdapter` and its SQLite-backed workspace file system,
  with the `jq` and `curl` command groups enabled. The host in `runners/workerd/` follows Computer's
  own worker-backend tests: a Durable Object owns the Workspace, and the shell runs in a Dynamic
  Worker through the Worker Loader binding, in local workerd (`@cloudflare/vitest-pool-workers`).
  This is not a deployed Worker. We also ran the same `ShellWorker` (Computer commit `b681446f`) in
  Node, with an in-process stand-in for the Workers RPC hop. That adapter is not included here. It
  gave the same stdout, stderr, exit status and file changes as the workerd host on all 351 cases,
  and it is the host the corpus study used.

Paired, case by case:

- just-bash main matches GNU on 5 cases that 3.6.0 does not: four grep context cases and
  `rg -n --hidden` (`rg-018`). It loses none.
- just-bash 3.6.0 matches GNU on 6 cases that 3.2.0 does not, and loses none. It has 6 fewer
  silent-wrong results, for example `grep -e A -e B`, which 3.2.0 answers with the matches of the
  last pattern only (`grep-035`), and an extra blank line between file operands of `ls` (`ls-stat-014`).
- Cloudflare's worker-shell differs from plain just-bash 3.2.0 on 14 cases, and 8 of these change
  the verdict. Details are below.

**Per family:** match % / silent-wrong cases.

| Family | Cases | just-bash 3.6.0 | just-bash main | just-bash 3.2.0 | Cloudflare worker-shell |
|---|---|---|---|---|---|
| view | 100 | 78.0% / 11 | 79.0% / 10 | 78.0% / 11 | 77.0% / 11 |
| sed | 43 | 74.4% / 5 | 74.4% / 5 | 74.4% / 5 | 74.4% / 5 |
| grep | 44 | 61.4% / 12 | 70.5% / 8 | 56.8% / 14 | 56.8% / 14 |
| rg | 23 | 82.6% / 3 | 87.0% / 2 | 82.6% / 3 | 82.6% / 3 |
| ls-stat | 35 | 51.4% / 12 | 51.4% / 12 | 42.9% / 15 | 40.0% / 13 |
| cut-tr | 21 | 76.2% / 3 | 76.2% / 3 | 76.2% / 3 | 76.2% / 3 |
| wc | 20 | 75.0% / 1 | 75.0% / 1 | 75.0% / 1 | 70.0% / 2 |
| sort-uniq | 30 | 66.7% / 6 | 66.7% / 6 | 66.7% / 6 | 66.7% / 6 |
| checksum | 9 | 55.6% / 0 | 55.6% / 0 | 55.6% / 0 | 55.6% / 0 |
| fileops | 24 | 66.7% / 3 | 66.7% / 3 | 62.5% / 4 | 62.5% / 3 |
| awk | 13 | 61.5% / 4 | 61.5% / 4 | 61.5% / 4 | 61.5% / 4 |
| jq | 9 | 77.8% / 1 | 77.8% / 1 | 77.8% / 1 | 77.8% / 1 |
| find-xargs | 12 | 75.0% / 0 | 75.0% / 0 | 75.0% / 0 | 75.0% / 0 |
| diff-bytes | 18 | 22.2% / 6 | 22.2% / 6 | 16.7% / 7 | 16.7% / 8 |
| shell | 88 | 70.5% / 7 | 70.5% / 7 | 69.3% / 8 | 71.6% / 6 |

In the checksum and find-xargs families, no subject gave a silent-wrong answer. The checksum
utilities a shell lacks (`shasum`, `cksum`) are reported as unknown commands, which an agent can
see.

### Examples of silent differences

Each item names cases in `suite/cases.jsonl`. `results/2026-10-29c/` has every output.

In plain just-bash (3.6.0, main and 3.2.0). Cloudflare's worker-shell, which runs 3.2.0, shares all
of these except the first:

- A redirect into a missing directory creates the directory and succeeds. Bash fails with
  `No such file or directory` (`shell-004`).
- `grep -r` follows a symlink to a directory that it finds during recursion, so matches are reported
  twice. GNU grep follows only symlinks named on the command line (`grep-018`, `grep-020`,
  `grep-022`).
- Context output from several files has no `--` separator between files (`grep-006`).
- `ls -l` shows no execute bits and lists symlinks as regular files (`ls-stat-004`, `ls-stat-005`).
  `for d in */` also matches regular files (`shell-016`).
- `sort` without options does not use byte order under `LC_ALL=C.UTF-8` (`sort-uniq-001` to
  `sort-uniq-005`).
- `od -An -tx1` prints octal (`view-047`, `view-051`, `diff-bytes-006`).
- `cut -c` counts characters where GNU counts bytes (`cut-tr-004`, `cut-tr-018`).
- `printf 'caf\303\251'` writes the two octal escapes as two separate characters, so the file holds
  `c3 83 c2 a9` instead of `c3 a9` (`shell-045`).
- `grep -o '[0-9]\+'` prints nothing (`grep-013`). `\+` is a GNU extension to basic regular
  expressions.

Cloudflare Computer's worker-shell gives a different stdout, stderr, exit status or file state from
plain just-bash 3.2.0, the version it runs, on 14 of 351 cases. 8 of them change the verdict, in both
directions:

- Non-ASCII text written through a heredoc, a redirect or `tee` is stored double-encoded, so `é`
  becomes `c3 83 c2 a9` on disk (`view-046`, `view-048`; also `view-047`, `view-051` and `view-052`,
  which are already wrong in plain just-bash because of `od`). Plain just-bash 3.2.0 and 3.6.0 write
  these bytes correctly. This is open as
  [cloudflare/computer#286](https://github.com/cloudflare/computer/issues/286), labelled
  `priority: high`, with a proposed fix in [#287](https://github.com/cloudflare/computer/pull/287)
  (as of 2026-10-29).
- `cp` and `mv` onto an existing file fail with `cannot safely determine whether ... are the same
  file` (`fileops-004`, `fileops-005`). These failures are loud.
- A redirect into a missing directory fails with an error, where plain just-bash silently creates
  the directory (`shell-004`, `view-050`). The message differs from bash's, but the agent sees it.
- Writes through symlinks behave as on Linux, where plain just-bash replaces the link or throws
  (`fileops-012`, `fileops-013`). Both cases match GNU.
- `grep -r` also descends into a subdirectory of a symlinked directory, one level further than plain
  just-bash 3.2.0 does. Both differ from GNU, which does not follow such a symlink at all
  (`grep-018`, `grep-020`).
- The `mkdir` error for an existing directory contains a literal `<path>` placeholder
  (`fileops-002`; error text only).

## Relation to the private corpus

The suite's families, weights and divergence probes come from a private study. In that study,
13,950 shell-command instances (13,212 distinct commands) that coding agents ran during real work
were replayed against the same GNU oracle and against just-bash and Cloudflare Computer builds, on a
fixture that mirrored the files the commands read. The commands, paths and outputs stay private.
Only aggregate counts are published here, in `validation/corpus-rescored.json`.

Corpus instances per family (a command counts in every family it uses): view 9,057; sed 4,841;
shell 3,336; grep 2,614; rg 1,239; ls-stat 1,158; fileops 885; cut-tr 876; wc 567; checksum 161;
awk 156; sort-uniq 80; find-xargs 74; diff-bytes 46; jq 28.

### How well suite scores track corpus scores

The comparison below covers the three builds that both the suite and the corpus study measured.
The corpus was re-classified under the verdict rules above (`tools/corpus_rescore.py`). The
comparison itself is `tools/validate.py`, with output in `validation/validation-2026-10-29c.md`. For
Cloudflare, the corpus used the Node host at `b681446f` and the suite row is the workerd host at
`071b2b2`. The two gave identical results on all 351 suite cases; that does not establish that
they agree on every private-corpus command.

This comparison is in-sample: the same private study informed the suite's family weights and
divergence probes. It checks consistency with that study; it is not a held-out estimate of
performance on other agents or projects.

| Build | Suite match | Corpus match | Suite silent-wrong | Corpus silent-wrong |
|---|---|---|---|---|
| just-bash 3.6.0 (npm) | 70.7% | 88.6% | 14.8% | 4.7% |
| just-bash main `7a2a7a57` | 72.1% | 89.6% | 13.4% | 3.7% |
| Cloudflare worker-shell | 68.7% | 83.3% | 16.2% | 8.5% |

- **Order.** The suite and the corpus put the three builds in the same order, on match rate and on
  silent-wrong rate. With three builds, two of which differ by 5 suite cases, this is a weak check.
- **Absolute numbers do not carry over.** On everyday agent commands, which are mostly `cat` and
  `sed -n` on plain files, all three builds match GNU far more often than on the suite. The suite is
  harder on purpose. Reweighting the suite's family scores by corpus frequency moves just-bash
  3.6.0 only from 70.7% to 72.7% match, against 88.6% on the corpus, because within each family the
  suite also oversamples hard behaviour.
- **Per family, the agreement is weak to moderate.** Across 15 families × 3 builds, the correlation
  between suite and corpus non-match rates is Pearson 0.56 (Spearman 0.40). For silent-wrong rates
  it is Pearson 0.36 (Spearman 0.41). Treat family scores as diagnostics, not as estimates of a
  family's real-world error rate.
- **Cloudflare versus plain just-bash: the suite understates the gap.** Against just-bash 3.6.0, the
  gap is 2.0 points on the suite and 5.3 points on the corpus. Part of it comes from the just-bash
  version (3.2.0 against 3.6.0). The largest Cloudflare-specific differences in the corpus are `cp`
  and `mv` onto existing files, which fail loudly, and non-ASCII heredoc writes (#286 above). Both
  are frequent in the corpus, and the suite has only a few cases of each.

## Known limits

- **One oracle: Linux with GNU tools, the C.UTF-8 locale and UTC.** macOS/BSD behaviour differs on
  purpose in places, for example `cut -c`, `sed -i`, `stat -f` and `ls` flags. A shell that targets
  BSD semantics will score lower here without being wrong for its users. Other locales were not
  run.
- **Suite scores are not real-world error rates.** See the comparison above: the suite ranks builds
  the way the corpus does, but its absolute rates and its per-family scores do not carry over.
- **The suite overstates fixes made by its own authors.** The authors used this suite while
  developing an experimental just-bash fork aimed at GNU parity. The fork is not published and is
  not measured in this repository. On that fork, the suite's match rate rose 16.8 points over
  just-bash main (72.1% to 88.9%), while the match rate on the private corpus rose 3.2 points (89.6%
  to 92.8%). These numbers come from an earlier run of the same suite code and cannot be reproduced
  from this repository. The suite probes exactly the divergence classes those fixes targeted, so
  any fix aimed at the suite's probes will look larger here than its effect on everyday agent
  commands.
- **Things a virtual file system cannot know.** The formatting class absorbs `ls -l` ownership, link
  counts, times, directory sizes and block totals. Block-based sizes (`du`, `ls -s`) depend on the
  host file system. The oracle uses an overlay on ext4 with 4 KiB blocks.
- **File comparison.** It uses content hashes and entry types. Permission bits and symlink targets
  are compared only where a case prints them, for example with `ls -l`, `stat -c %a` or `test -x`.
- **Heuristic classification.** The loud classes depend on a pattern for "unsupported" messages and
  on whether the subject wrote anything to stderr. The order and whitespace rules can hide a real
  bug. Every verdict line records which streams differed, and `results/RUN/` keeps the raw outputs
  for checking.
- **Single synthetic world.** All cases share one small project tree. They do not cover large files,
  deep trees, many files, or binary-heavy workloads.
- **Coverage.** The suite covers file and text utilities, plus the shell language agents use with
  them. Like the corpus study, it leaves out interpreters (python, node), network tools, git,
  package managers and process control.
- **Cloudflare host.** Both Cloudflare hosts are local; no deployed Worker was measured. The workerd
  host reads stdout as UTF-8 text, so invalid UTF-8 output bytes would appear as U+FFFD. On this
  suite its results matched the byte-exact Node host exactly.

## Disclosure

The authors wrote this suite, ran the private corpus study, and developed the experimental just-bash
fork mentioned above; they have also proposed changes to just-bash upstream. They reported
cloudflare/computer#286. Neither Vercel nor Cloudflare was involved in this benchmark or reviewed
it. Corrections are welcome as issues.

## Running it

Requirements: Node (we used 26.12) and Python 3.10 or later for the subjects and scoring, plus a
Linux host with a bubblewrap that supports `--tmp-overlay` (we used 0.11.1) and the GNU tools for
the oracle.

The oracle needs a directory of GNU coreutils under their plain names (`ls`, `sort`, ...), passed
as `SB_GNUBIN`; it is mounted read-only as `/opt/gnubin`, first on `PATH`. How to provide it depends
on the oracle host:

- **(a) GNU coreutils already have ordinary names** (the default coreutils are GNU): use that
  directory as it is, usually `/usr/bin` (step 1a below).
- **(b) GNU coreutils installed under a `gnu` prefix.** Step 1b below is for this layout, which the
  published run's oracle host had: on Ubuntu 26.04 the default `ls`, `sort` and so on come from
  rust-coreutils, and the `gnu-coreutils` package installs GNU coreutils as `/usr/bin/gnuls`,
  `/usr/bin/gnusort` and so on. Step 1b assumes that package is installed and that every
  `/usr/bin/gnu*` file belongs to it (check with `dpkg -S`); it makes symlinks to absolute paths
  under `/usr`, which the sandbox also mounts. On a host with another layout, make the same kind of
  directory from wherever its GNU coreutils are.

Either way, `results/RUN/gnu.jsonl.meta.json` records the version of `ls` and other tools and
`command -v ls`, which show which tools ran.

```sh
# 1. G = the GNU coreutils directory on the oracle host (see above); run 1a or 1b there, not both
G=/usr/bin                                                                               # 1a
mkdir gnubin && for f in /usr/bin/gnu*; do ln -s "$f" "gnubin/${f##*/gnu}"; done && G=$PWD/gnubin   # 1b
# 2. a subjects file: NAME<TAB>ADAPTER<TAB>ADAPTER_OPTS_JSON
printf 'jb-3.6.0\trunners/node/adapters/just-bash.mjs\t{"package":"/path/to/node_modules/just-bash"}\n' > subjects.tsv
# 3. run: builds the suite, runs the oracle twice (here or over ssh), runs each subject, scores
SB_GNUBIN=$G tools/run.sh myrun subjects.tsv                                   # oracle on this Linux host
SB_GNUBIN=/dir/G/on/linuxbox SB_ORACLE_SSH=linuxbox tools/run.sh myrun subjects.tsv   # oracle over ssh: step 1's directory there
```

`results/myrun/` then holds the raw results, `verdicts-*.jsonl`, `scores.json` and `scores.md`.
`python3 -I score.py results/myrun` re-scores without re-running anything. `python3 -I
tests/test_score.py` is a quick check of the scorer's documented rules (verdict order, oracle
repeat check).

For the Cloudflare worker-shell in local workerd, `runners/workerd/run.sh COMPUTER_CHECKOUT
results/myrun` copies the host files in `runners/workerd/` into a prepared `cloudflare/computer`
checkout (as untracked files), runs the suite there with vitest, collects the results into
`results/myrun/cf-computer-workerd-REV.jsonl` and re-scores the run. The vitest run ends with a
deliberate, labelled failure (`SHELLBENCH-DONE`), because in this setup vitest prints a test's
console output only when the test fails; the script checks the result count instead.

### Reproducing the published run

Run `2026-10-29c` used these steps. Start in an empty directory with this repository cloned into
`shellbench/`, and a Linux host for the oracle as above:

```sh
W=$PWD
mkdir jb360 && (cd jb360 && echo '{"private":true}' > package.json && npm install just-bash@3.6.0)
mkdir jb320 && (cd jb320 && echo '{"private":true}' > package.json && npm install just-bash@3.2.0)
git clone https://github.com/vercel-labs/just-bash && git -C just-bash checkout 7a2a7a57
(cd just-bash && pnpm install --frozen-lockfile && pnpm build)
git clone https://github.com/cloudflare/computer && git -C computer checkout 071b2b2
(cd computer && npm ci --ignore-scripts && npm run build --workspace packages/rpc --workspace packages/dofs \
  && cd packages/computer && npm run build:shell-bundle)
J=runners/node/adapters/just-bash.mjs
printf 'jb-npm-3.6.0\t%s\t{"package":"%s/jb360/node_modules/just-bash"}\n' "$J" "$W" > subjects.tsv
printf 'jb-main-7a2a7a57\t%s\t{"package":"%s/just-bash/packages/just-bash"}\n' "$J" "$W" >> subjects.tsv
printf 'jb-3.2.0\t%s\t{"package":"%s/jb320/node_modules/just-bash"}\n' "$J" "$W" >> subjects.tsv
cd shellbench
SB_GNUBIN=/dir/G/on/linuxbox SB_ORACLE_SSH=linuxbox tools/run.sh myrun "$W/subjects.tsv"
runners/workerd/run.sh "$W/computer" results/myrun
python3 -I tools/validate.py results/myrun/scores.json validation/corpus-rescored.json \
  results/myrun/validation cf-computer-workerd-071b2b2=cf-computer-b681446f
```

`--ignore-scripts` skips Computer's native FUSE addon, which does not build on macOS (that
repository's `AGENTS.md` describes this) and which the workerd host does not need. For run `2026-10-29c`
the just-bash and Computer checkouts were fresh clones of those commits and the npm packages fresh
installs; the subjects ran on macOS and the oracle on Linux over ssh. `results/myrun/` should then
give the same `verdicts-*.jsonl` and `scores.md` as `results/2026-10-29c/`, and the validation output the
same as `validation/validation-2026-10-29c.md`.

The run recorded these bundle hashes: npm 3.6.0 `d769656d8dd94d59`, main `36651a9caf5f9d4d` and npm
3.2.0 `44cf67b1419905c4` (first 16 hex digits of the SHA-256 of `dist/bundle/index.js`, in each
`.meta.json`). `results/2026-10-29c/source-rev.txt` lists the git object ids of `suite`, `runners`,
`tools`, `score.py` and `families.py` in the clone that made the run. The commit it names is not in
this repository's history, because the results were added afterwards. `git rev-parse HEAD:suite`
and so on, in a checkout of this repository, give the same ids.

## Adding a shell

Write an adapter module that exports `createSubject(opts)` and returns:

```js
{
  name, version,                       // version is recorded in the results
  async load(seed, dirs, { mtime }),   // seed: Map<absPath, {content: Uint8Array, mode} | {symlink: target}>
  async run({ script, cwd, env, timeoutMs }) // -> { stdoutB64, stderr, exitCode, delta }
}
```

`delta` is `{added: {path: hash}, changed: {path: hash}, deleted: [path]}` relative to the seed,
where `hash` is the first 16 hex digits of the file's SHA-256, `"<dir>"` or `"<symlink>"`.
`runners/node/adapters/just-bash.mjs` is a complete example in about 90 lines. Adapters that live
elsewhere load through `runners/node/adapters/external.mjs` (`{"module": "/path/to/adapter.mjs"}`).
Then add a line to your subjects file and run `tools/run.sh`.

A shell that cannot run in Node, such as a Rust or Go implementation or a remote sandbox, can skip
the runner. Write `results/RUN/NAME.jsonl` with one line per case, `{"id", "stdoutB64", "stderr",
"exitCode", "delta"}`, and run `score.py`. The environment section above is the contract: same cwd,
env, mtimes and seeded tree.

## Layout

```
suite/        world.py, cases_def.py -> build.py -> world.json, cases.jsonl
runners/gnu/  oracle.py (outer, bubblewrap) and inner.py (inside the sandbox)
runners/node/ run.mjs (worker pool, per-case timeout), env.mjs, adapters/
runners/workerd/  Cloudflare Computer host for local workerd; run.sh copies it into a computer checkout and runs it
score.py      verdicts and tables;  families.py  family definitions;  tests/  scorer checks
tools/        run.sh, regression_screen.py, corpus_rescore.py, validate.py
results/2026-10-29c/  raw results, verdicts and scores for the run reported above
validation/   corpus aggregates (counts only) and the suite-vs-corpus comparison
```

## License

MIT; see `LICENSE`. `runners/workerd/` follows the structure of Cloudflare Computer's MIT-licensed
worker-backend test harness; `NOTICE` gives the attribution and Computer's license text.

## Contributors

The code, the cases and this README were written with Claude Opus 5.5 (Anthropic) as the coding
agent. Commits carry a `Co-Authored-By` trailer for each model that co-authored them.

```text
.----------------------------------------.
|   \ | /     Claude Opus 5.5            |
|  -- * --    . . . . . . . . . . . . .  |
|   / | \     measure twice, commit once |
'----------------------------------------'
```
