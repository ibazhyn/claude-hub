# 03 — Worker result template

File: `results/<SESSION-ID>.md` (a continuation writes `results/<SESSION-ID>-A02.md`, a repair
`results/<SESSION-ID>-R01.md`). The worker writes the skeleton **first**, before any edit — after checking
that the file does not exist — and fills it as the work proceeds. Never overwrite another Session's result:
a name clash is an id collision to report, not an obstacle.

The result is the one record of the Session. Keep it to one screen of header plus the evidence below it;
do not also write a second, duplicate verification document unless the repository's own conventions ask
for one (then point to it).

Every timestamp in it — `started_at`, `finished_at`, the lock-release time under PEER SAFETY — is read from
the clock at the moment you write it: `python -c "import datetime; print(datetime.datetime.now().astimezone().isoformat(timespec='seconds'))"`,
or `date -Iseconds` in Bash, `Get-Date -Format o` in PowerShell. Never estimated, never copied.

```markdown
---
session: W001-S001
attempt: 1
status: IN_PROGRESS | done | partial | failed | blocked
repository: <key>
repository_path: <absolute path>
branch: <branch>
parent: <full SHA of HEAD before the first commit>
commit: <full SHA, or null>          # several commits: list them in order
subject: <exact subject, or null>
inbox: [IN-YYYYMMDD-SLUG]
needs_user: false
started_at: <ISO>                    # read from the clock when you write it
finished_at: <ISO>                   # read from the clock when you write it, never estimated
---

# <SESSION-ID> — <outcome>

## HEADER — the first thing QA reads, and the only thing it is guaranteed to read

| # | Acceptance criterion (verbatim from the Session MD) | Met | Evidence a reader can check without trusting me |
|---|---|---|---|
| 1 | … | yes / no / not-verifiable-here | test name + result, `path:line`, command + output file, SHA — never prose |

INVARIANTS TOUCHED: shared contract / auth / permission / tenant / persistence / deletion / none — name them
TESTS: `<command>` → passed/failed counts at the commit vs the parent, or: not run, and why
NOT DONE: anything asked for and not delivered, stated plainly
PEER SAFETY: unrelated dirty files untouched? foreign files in the commit? lock released at <time>?

## PRODUCT OUTCOME
One or two sentences, in product terms.

## ROOT CAUSE + FIX
Verified facts only, with file references.

## FILES CHANGED
- `path` — what and why

## VERIFICATION
- `<exact command>` (from `<dir>`) → result; full output in `<file>` when the detail is the evidence
- fail-first: red at the parent, green at the commit → evidence
- persistence / API / permission / consumer checks → evidence
- what cannot be verified locally → "verified by the user on <environment>"

## GIT
- subject: `<exact>` (read back with `git log -1 --format=%s`)
- full SHA:
- `git show --name-only` lists exactly: …
- on `origin/<branch>`: no (`git merge-base --is-ancestor` exit code 1)

## CORRECTIONS TO THE TASK
Premises in the Session MD that the repository contradicted, with the correct facts.

## LEARNINGS CANDIDATES
Durable repository facts for `project/LEARNINGS.md`: commands that work (and from where), quirks, flaky
tests, hazards. The orchestrator merges them.

## DISCOVERED DEFECTS
Real problems found outside this Session's scope, one line each with evidence — they become INBOX rows.
```

## Header rules
- A criterion is `yes` only with evidence a reader can verify independently. "Verified manually", "should
  work", "looks correct" are `no`.
- `partial`, `failed` and `blocked` are legitimate outcomes, reported plainly. A dressed-up `done` is a
  defect, and QA catches it anyway — at the cost of a repair round nobody needed.
- If the header and the body disagree, the header is wrong: fix the header; never soften the body.
- Never describe a write as done before it is done, and never describe a pending write as done. If a row is
  still to be appended, write "pending", or append it first — that is cheaper than describing it.
- Keep the header to one screen. QA reads one screen instead of thirty.
