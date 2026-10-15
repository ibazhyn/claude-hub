# control/locks/ — who may edit a repository right now

One file per repository with work in flight: `TREE_LOCK-<repo-key>.md` (the key from
`project/REPOSITORIES.md`). A worker claims before its first edit and releases right after its commit. The
orchestrator reads the lock before dispatching into a repository; `python tools/hub.py status` lists held
locks with their age.

This is a convention, not a mechanism: it works because everyone reads it before acting. It reserves the
**working tree** — one holder at a time. A claim still lists its files so every reader can see what is
changing. And even a held lock says nothing about what a pathspec-less `git add` would sweep up — the index
is shared — which is why commits always name their paths.

## File format

```markdown
---
repo: <repo-key>
holder: <SESSION-ID> | none
goal: <G> | none
started_at: <ISO> | none
---

# TREE LOCK — <repo-key>

## Log (append-only, newest at the bottom)
- <ISO> CLAIM <SESSION-ID> (goal <G>) — takes: <paths> — not taking: <paths> — next: <SESSION-ID or unclaimed>
- <ISO> RELEASE <SESSION-ID> — committed <full SHA> — next: <SESSION-ID or unclaimed>
```

Every `<ISO>` — `started_at` and each log line — is read from the clock at the moment you write it:
`python -c "import datetime; print(datetime.datetime.now().astimezone().isoformat(timespec='seconds'))"`,
or `date -Iseconds` in Bash, `Get-Date -Format o` in PowerShell. Never estimate a time, never copy one from
another line or file: a RELEASE stamped later than it happened misleads everyone who judges staleness.

## Rules
1. **Claim:** set the front matter (`holder`, `goal`, `started_at`) and append a CLAIM line naming the files
   you take **and** the neighbouring files you deliberately do not take. A claim that names its exclusions
   is checkable; one that names only what it takes leaves every reader guessing.
2. **One holder per working tree.** Disjoint files are not isolation: two Sessions building or testing in
   one tree corrupt each other's results. A second Session in the same repository runs only in its own git
   worktree, and only when `project/OVERRIDES.md` explicitly enables worktrees for that repository
   (`orchestration/01_ORCHESTRATION_PROTOCOL.md` § Dispatch); that worktree is its own tree and takes no
   share of this lock.
3. **Name the successor at claim time** when it is known, so the queue is readable while the lock is held.
4. **Release** right after the commit: `holder: none` and a RELEASE line with the full SHA. A lock still held
   by a context that has stopped blocks peers who cannot know it is gone.
5. **Stale lock:** reclaim only after checking that its holder is no longer running and that
   `git status` shows no orphaned work of it; if it left work, save it first (`git diff` into
   `results/<SESSION-ID>-salvage.patch`) and record the takeover in the log.
6. **Re-read after writing.** The file is appended concurrently; confirm your line is there.
