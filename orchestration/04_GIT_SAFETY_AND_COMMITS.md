# 04 — Git safety and commits

## Permissions posture
Routine orchestration and implementation should not keep asking the user for approval: the user picks
Auto permission mode in Claude Desktop, and `.claude/settings.json` pre-allows read-only tools and the hub's
own tools. Background subagents (workers, QA reviewers, analysts) cannot show a permission prompt, so
without Auto mode (e.g. Accept edits) their commands are refused: the orchestrator then dispatches in the
foreground, where the user approves.
Never use a bypass mode as the normal configuration. Some prompts are platform-mandated (workspace trust,
connector sign-in, writes to Claude's own settings files) and cannot honestly be promised away.

The PreToolUse hook `.claude/hooks/safety_guard.py` is the enforcement floor (tests:
`python tools/guard_test.py`). It denies destructive operations however they are quoted or wrapped —
including `git -C <repo> …` forms — and commit messages that break the rules below. The deny and ask rules
in `.claude/settings.json` are only a backstop: they match plain command prefixes (`git reset --hard…`),
not `git -C <repo> …` — which is why the guard refuses a push in any other form (§ Pushing). Without
Python the hook is off and that backstop is all there is — the contract binds regardless. The guard is the
floor, not the standard.

**One command per tool call.** A compound line (`VAR=…; …; echo`, `cd "<repo>" && git status`) is judged
part by part, and one part that no allow rule covers makes the whole line prompt — or be refused outright
for a background subagent. Read-only checks go out one per call as `git -C "<repo>" <command>`; the allow
list carries those `git -C` forms. Independent checks go out as parallel calls in one message. Two
compound forms are deliberate: staging and committing in one command (below), and a push (§ Pushing),
which is meant to be confirmed.

## Always
- `git status` and `git diff` before editing and before staging.
- Preserve unrelated changes: anything dirty that is not yours belongs to the user or a peer until proven
  otherwise.
- Stage explicit task-owned paths only, and commit in the same command with the pathspec on both:
  `git -C <repo> add -- <paths> && git -C <repo> commit -m '<subject>' -m '<body>' -- <paths>`.
- One focused local commit per Session (or one per independent part when the Session says so).
- Read it back: `git log -1 --format=%s` and `git show --name-only <sha>`.

## Never (unless a Session MD explicitly says so, and the guard still applies)
- push (see below), reset, clean, stash (except `stash list` / `stash show`), rebase, amend, cherry-pick
  onto shared branches, `checkout -- <path>` / `checkout .` / `restore` of the working tree, `branch -D`,
  history rewriting (`filter-branch`, `filter-repo`, `update-ref`, `reflog expire`, `gc --prune`);
- `git add -A`, `git add .`, `git add -u`, `git commit -a`;
- author overrides: `--author`, `-c user.name=…`, `-c user.email=…`, writing `git config user.*`,
  `GIT_AUTHOR_*` / `GIT_COMMITTER_*` variables;
- `--no-verify`, or pointing `core.hooksPath` elsewhere;
- recursive deletion of a repository root, a `.git` directory, the home directory, a drive root, or the
  hub's own ledgers.
Allowed explicitly: `git checkout -b <name>`, `git switch <branch>` / `git switch -c <name>`,
`git restore --staged <file>` (unstage), `git worktree add`, `git worktree prune`, removal (`--force`
included) of a temporary worktree — inside the hub's `worktrees/` (QA's `qa-<SESSION-ID>`), or a `hub-wt-*`
one under the system temp directory — and a push when the user asked, in the one form § Pushing gives.

## Identity
The author is the git identity recorded at setup for that repository (`project/REPOSITORIES.md` →
`identity`, the effective `git -C <repo> config user.email`, which a repository can set differently from
the global one in `project/PROJECT_PROFILE.md`). Before committing, `git -C <repo> config user.email` must
print it. If it does not, stop and report — the user fixes it (the guard denies identity writes by design).

## Commit messages
**Everyone who reads the repository's history reads these subjects.** Our internal bookkeeping is not a
name for a change.

Subject shape, in order of precedence:
1. the repository's observed convention when it has a clear one (`project/CONVENTIONS.md`, detected at
   setup from `git log -30 --format=%s`);
2. otherwise conventional commits: `type(scope): <concise outcome>` — `type` one of
   `feat|fix|refactor|perf|test|docs|chore`, `scope` the product surface (`cart`, `auth`, `api`), never a
   wave, Session or goal.

Step 2 is always available: when the house style needs something the Session does not have (say, an
issue number in every subject), the subject falls back to the conventional form — never an invented
value. That is why the enforced `commit.subject_regex` in `control/hub-config.json` always includes the
conventional form.

About 72 characters, an imperative or plain statement of the product change. No verification figures, no
file paths, no root-cause essay, no narration. Those belong in the body and the result file.

Banned anywhere in the message, subject and body:
- hub ids: `G-YYYYMMDD-NNN`, `W###`, `S###`, `W###-S###`, `-R##`, `-A##`, `IN-YYYYMMDD-…`;
- words naming **our** units of work — "Wave", "Session" as our unit. The product's own vocabulary is
  untouched: `fix(auth): a session cookie survives logout` is a fine subject;
- the hub's own names: `claude-hub`, `Claude Hub`, `hub-orchestrator`, `hub-session-worker`, and the other
  agent and skill names;
- narration about the Session: "land the …", "the evidence for …", "this Session's …".

What the guard's check refuses — the rule above binds in full either way: the compound shapes that are
unmistakably ours (`G-YYYYMMDD-NNN`, `W###-S###`, `S###-R##` / `S###-A##`, `IN-YYYYMMDD-…`, and a
`W###` next to the word "wave"). A bare `W123`, `S300` or `-R10` can be a product term (a model number, a
flag) and passes — so never write our own ids that way either. A capitalised "Session" or "Wave" right
after one of the lowercase words this, that, our, both, previous, next, last, earlier, later, first,
second, third ("both Sessions", "this Wave"), or followed by a number ("Wave 29"), reads as our
bookkeeping; ordinary product wording ("a session cookie", "every session", "each Session field", Title
Case subjects) passes. A subject needs at least four letters or digits, so `v1.2.0` passes and `wip` does
not. Until setup has configured `commit.subject_regex`, a subject opening with a bracketed prefix
(`[hub] …`) is refused; once it is configured, the repository's own convention decides.

A commit that only records verification evidence is still a commit about the product:
`test(api): baseline for the checkout suite`, not a sentence about our process.

**Traceability without leaking our ids:** the Session id never goes into git. The result file's `commit:`
field carries the full SHA, and the file carries the Session id, so the mapping lives in the hub.

### Mechanics that have gone wrong before
- **Inline `-m` only**, one `-m` per paragraph. `-F`, `-C`, `-c`, `--fixup`, `--squash`, `--template` are
  denied: the guard must be able to read the message it checks. The form
  `-m "$(cat <<'EOF' … EOF)"` is readable and allowed.
- **Never PowerShell here-string syntax in the Bash tool.** `-m @'…'@` is not syntax in Bash: Bash passes
  the `@` through, git records the subject "@" and the real subject lands on line two — and since amend is
  forbidden, it is permanent. In the PowerShell tool a here-string is legitimate.
- **The index is shared by the whole repository.** A lock reserves the working tree; `git add` reserves
  nothing.
  Stage and commit in one command, and never leave work staged across a long step.

## Pushing
No push by default. `project/REPOSITORIES.md` records a per-repository `push_policy`:
- `never` (default) — the hub does not push. If the user asks for a push anyway, ask once whether to switch
  that repository to `on request`; record the answer (the policy line, plus a ruling in
  `project/OVERRIDES.md`).
- `on request` — push only when the user asks in the current conversation.

**The push form — the only one:** from inside the repository, `cd "<repo>" && git push <remote> <branch>`
in the Bash tool (in the PowerShell tool: `Set-Location "<repo>"`, then `git push <remote> <branch>` as a
command of its own). The `ask` rule in `.claude/settings.json` matches only a push made this way, so the
user confirms it; the guard denies every other spelling — any option between `git` and `push` (`-C`, `-c`,
`--git-dir`, `--work-tree`, `--no-pager`, …), git behind a wrapper (`env`, `command`, `exec`, `xargs`, `&`,
a nested shell or substitution), git as a path or `git.exe` — and every forced or deleting push. Never
force, never delete remote branches.

"I did not push" and "my commit is not on the remote" are different claims, and only the second is
verifiable: someone else pushing the branch sweeps up every local commit on it. So acceptance says "the
commit is not on `origin/<branch>`", verified with `git merge-base --is-ancestor <sha> origin/<branch>`
(exit 0 means it is on the remote). If a commit was swept up by someone else's push, do not try to undo it:
correct the record and tell the user. Never rewrite history to "un-push".

## Existing history
Commits that already landed with a bad subject stay exactly as they are. Rewriting published history is
forbidden; the rules bind new commits.
