# 06 — QA and repair

Every Session is verified by a fresh `hub-qa-reviewer` that reads the original acceptance criteria and the
real evidence — never the worker's summary of itself. A failed criterion creates a repair Session
automatically. Nothing is called done without evidence.

## When QA is full, and when diff plus tests suffices
**Full QA — no exceptions** when the change touches shared contracts or consumers,
auth/permission/tenant/role boundaries, persistence or deletion behaviour, or any item of
`project/INVARIANTS.md`. The reviewer widens beyond the diff for exactly those and says which criterion
forced it.

**Diff + test evidence** is a sufficient basis for an isolated cosmetic or single-file change with passing
tests. The reviewer still writes the report and says plainly that this was the basis.

Narrow scope means fewer files, never a softer standard.

## Dispatch
The orchestrator gives the reviewer: the Session MD path, the result file path, the repository path, the
commit SHA(s), the parent SHA and the hub root. One reviewer per Session, or one per repository when
several Sessions of a wave touched it. Different repositories: reviewers in parallel, in the background —
unless the session is not in Auto mode (`01_ORCHESTRATION_PROTOCOL.md` § Dispatch, item 6).

## Procedure
1. **Report skeleton first** — `results/QA-<SESSION-ID>.md`, one PENDING row per criterion, a
   `## Not yet reached` list. Rewrite the whole file after each settled criterion.
2. **Acceptance first**, verbatim from the Session MD. Then the result HEADER as a map of claims to check.
3. **The real change:** `git show --stat`, `git show --name-only`, `git show <sha>`. Foreign files, unsafe
   git behaviour, mocks, placeholders, shadow state, hardcoded users/roles/tenants and unrelated edits are
   findings.
4. **Commit hygiene:** author identity, subject per `project/CONVENTIONS.md` and
   `04_GIT_SAFETY_AND_COMMITS.md`, no hub ids or narration; "not on `origin/<branch>`" verified with
   `git merge-base --is-ancestor`. A landed violation is a finding; history is never rewritten.
5. **Fail-first:** in a temporary worktree at the parent commit, inside the hub — the hub is always
   writable, the system temp directory is not —
   `git -C <repo> worktree add "<hub>/worktrees/qa-<SESSION-ID>" <parent-sha>` — bring in the Session's new
   or changed tests (`git -C <repo> show <sha>:<test-path> > "<worktree>/<test-path>"`) and run them: they
   must fail at the parent and pass at the commit. Install dependencies inside the worktree if needed;
   never link dependency folders from the real tree into it (removing the worktree can delete through the
   link). Remove it at the end, **also when the review fails or stops early**:
   `git -C <repo> worktree remove --force "<hub>/worktrees/qa-<SESSION-ID>"` (`git -C <repo> worktree prune`
   if the folder is already gone), and delete its `qa-<SESSION-ID>-*.txt` output files.
   If it cannot run here, the verdict for fail-first is NOT-VERIFIABLE-HERE with the reason.
6. **Criteria:** each one PASS / FAIL / NOT-VERIFIABLE-HERE with evidence a reader can re-run. Prose where
   evidence belongs is FAIL. NOT-VERIFIABLE-HERE names the environment where it can be verified and who
   verifies it (for anything `PROJECT_PROFILE.md` lists under *cannot be verified locally*: the user, on the
   environment named there).
7. **Invariants** in full whenever touched (see above).
8. **Regression:** the relevant suite at the commit versus the parent, as a property ("no failure at the
   commit that the parent does not have"), never against a remembered count. Full output captured to
   `<hub>/worktrees/qa-<SESSION-ID>-<label>.txt` and read from the file.
9. **Findings** outside the Session become INBOX candidates, each with evidence and a severity.

## Report — `results/QA-<SESSION-ID>.md`

```markdown
# QA — <SESSION-ID> · PASS | FAIL | PARTIAL-VERIFIED
Commit `<full SHA>` (parent `<SHA>`), repository `<key>`, branch `<branch>`, on origin/<branch>: no.
Basis: FULL | DIFF+TESTS — <why>.

| # | Criterion (verbatim) | Verdict | Evidence |
|---|---|---|---|
| 1 | … | PASS | command → result; output file; `path:line` |

## Fail-first
<parent: N failed / commit: N passed — how it was run>

## Commit hygiene
<author, subject, files in the commit>

## Findings
- F1 — severity; introduced by this commit or pre-existing; evidence; suggested INBOX row.

## Repair specification (only on FAIL)
Per distinct issue: the failed criterion, the evidence, and the property the fix must preserve.

## Not yet reached
<delete lines as they are settled; empty when final>
```

## Hazards that produced false verdicts before
- **A working tree records what changed, never who changed it.** In a tree shared by concurrent work, a
  dirty file is not attributable to the Session under review and a clean tree proves nothing. Judge from
  `git show` / `git log -p` on the Session's own commits. In `git status --porcelain`, column one is the
  index and column two the working tree.
- **Evidence files can be younger than what they prove.** A committed report regenerated by any later test
  run is a fresh measurement of a later tree wearing an older name. Read such files with
  `git show <sha>:<path>`, never from disk.
- **A success response is not an effect.** Verify through a channel that does not depend on the one under
  test.
- **Persistence:** the reviewer never creates product data. A criterion that needs it is
  NOT-VERIFIABLE-HERE, with who can verify it and how — which is why the Session itself must plan that proof.
- **Ignored names:** if the repository ignores `*.log`, a file named `.log` is invisible to `git status`;
  name temporary evidence `.txt` and keep it outside the repository, in the hub's `worktrees/`.

## After the reviewer returns — the orchestrator
- Confirm `results/QA-<SESSION-ID>.md` exists. If the reviewer could not write it, transcribe the returned
  verdict into that file yourself and mark it "transcribed from the reviewer's reply", not as your own
  endorsement. A verdict that exists only in a chat reply is lost at the next handoff.
- `hub.py status` still lists that reviewer's `worktrees/qa-<SESSION-ID>` → remove it yourself (step 5's
  commands): a leftover stays registered in the repository and blocks the same path for the next review.
- PASS → INBOX rows `done`, goal file updated, LEARNINGS candidates merged.
- FAIL → repair, below.
- PARTIAL-VERIFIED (some criteria NOT-VERIFIABLE-HERE, none failed):
  - a leg only the user can verify (listed in `PROJECT_PROFILE.md` under *cannot be verified locally*) is
    not a gap: the INBOX row becomes `done` with the leg named in its note ("verified by the user on
    <environment>: <what>"), and the goal file and the status to the user list it;
  - any other NOT-VERIFIABLE-HERE is a gap: dispatch a Session that can verify it (for example one allowed
    to create data in an isolated store), or ask the user if only a human decision can close it. The row
    stays `session` until then.

## Repair loop
1. `python tools/hub.py next-id repair --session <SESSION-ID>` → `<SESSION-ID>-R01`.
2. A repair Session MD in `tasks/queued/`: the failed criteria verbatim, the QA evidence, the repair
   specification with the property each fix must preserve, and the original Session's GUARDRAILS.
   One distinct failed issue per repair Session when they are independent.
3. Fresh `hub-session-worker` → fresh `hub-qa-reviewer` (never the one that failed it).
4. After two consecutive failed repairs on the same criterion, stop and report to the user with the
   evidence: what was tried, what failed, what decision is needed.
5. Never accept a partially met criterion. Never close a goal while a requested outcome is unresolved.
