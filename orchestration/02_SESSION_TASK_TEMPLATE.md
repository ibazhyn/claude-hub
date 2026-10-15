# 02 — Session task template (the quality bar)

A Session MD is a complete implementation prompt for a worker who never saw the conversation. Not a ticket
stub. File: `tasks/queued/<SESSION-ID>-<short-slug>.md`.

**The operating principle: high autonomy inside a small, explicit safety box.** Every substantial Session
defines the final outcome, the observed evidence, the exact repository boundary, the invariants that
apply, measurable acceptance, code-first verification, and traceability. Inside that box the worker makes
routine implementation decisions itself after inspecting the repository; it does not ask for preferences
that the architecture, existing patterns, the user's evidence or the acceptance criteria already answer.

**Code first, runtime optional.** The evidence chain is: the user's description and screenshots → the
repository's code and current diff → the affected component, service, API contract and storage → the
relevant tests → implementation → verification by code, tests, typecheck, build. A browser or running app
is used only when one narrow check settles something code and tests cannot, without creating, editing or
deleting data anyone relies on. For stateful work, clicks never replace tracing the real data chain.

---

## Template (copy from here)

```markdown
---
id: W001-S001
goal: G-YYYYMMDD-NNN
wave: W001
attempt: 1
title: <the product outcome in plain words>
status: QUEUED
repository: <key from project/REPOSITORIES.md>
repository_path: <absolute path>
branch: <working branch the commit lands on>
request_class: DEFECT | FEATURE | INVESTIGATION | OPERATIONAL
inbox: [IN-YYYYMMDD-SLUG]
depends_on: []
parallel_safe: false
claims: <files/directories this Session expects to edit>
not_taken: <neighbouring files it must not touch, and why>
qa: FULL | DIFF+TESTS — <why>
model_note: <only if a mechanical helper runs on a lighter model: which, for what>
result: results/<SESSION-ID>.md
created_at: <ISO local time>
---

# <SESSION-ID> — <OUTCOME>

## GOAL
One to three sentences: the final user-visible or system outcome, and the property that must hold when it
is done.

## CONTEXT
- The user's words, verbatim, in their language (from the INBOX row).
- Screenshot transcription: what is visible, exact texts, numbers, error messages, which element is wrong.
- Where / observed / expected.
- Current-state facts, each with how to check it (a command, a file to open) — mechanisms, not symptoms.
- What is already known: prior Sessions, commits, LEARNINGS entries, defects this codebase already named.

## SCOPE
The exact surfaces, workflows, files and consumers that belong to this problem.

## NON-GOALS
Unrelated redesign, refactor or cleanup; problems owned by other Sessions (name them).

## GUARDRAILS
- Obey the repository's instruction files: <list from REPOSITORIES.md>.
- Invariants that apply, quoted from `project/INVARIANTS.md` by id: <B1, B4, P2 …>.
- Standing rulings that apply, quoted verbatim from `project/OVERRIDES.md`: <…>.
- Repository hazards from `project/LEARNINGS.md`, quoted: <…>.
- `git status` first; preserve unrelated human or peer changes; never stage them.
- `git config user.email` must print <the `identity` of this repository's record>; otherwise stop.
- Tree lock `control/locks/TREE_LOCK-<repo-key>.md`: claim before editing, release right after the commit.
- No fabricated, mock, seed or placeholder data presented as real. No hardcoded user, role, tenant,
  customer. No unrelated cleanup. No push.
- <PASTE THE STANDING CLAUSE HERE — verbatim, from the section below. A Session MD without it is
  incomplete.>

## DEPENDENCY MAP
`entry point (route / command / screen) -> component -> state / service -> contract (DTO, schema) ->
API / handler -> persistence -> permissions / tenant scope -> every current consumer`

## PLAN -> IMPLEMENT -> VERIFY
### PLAN
Read instructions, git state, the dependency chain, the tests. Resolve routine details from repository
reality. Name the natural commit boundaries if the Session has independent parts.
### IMPLEMENT
Deliver only this Session's outcome. Fail-first test when feasible.
### VERIFY
The repository's commands (<test / typecheck / lint / build from REPOSITORIES.md>), the consumer checks,
and the persistence / permission checks that apply. Capture full output to a file when its detail is the
evidence.

## ACCEPTANCE
1. [ ] <observable criterion, with how it is checked> — red before, green after where a test can show it.
2. [ ] Persistence / permission / consumer criteria as applicable.
3. [ ] No regression: <suite> at the commit has no failures that the parent does not have.
4. [ ] Commit legal (subject per CONVENTIONS, no hub ids); `git show --name-only` lists only this Session's
   files; the commit is not on `origin/<branch>`.
5. [ ] <If part of the outcome cannot be verified locally (see PROJECT_PROFILE): the locally provable part
   as its own criterion; the rest stated as "verified by the user on <environment>".>

## VERIFICATION
The exact commands, from which directory, and what counts as pass.

## COMMIT / TRACEABILITY
- Suggested subject: `<type(scope): outcome>` (<n> characters) — or the repository's convention.
- Body: cause and behaviour; no hub ids, no figures, no narration about the Session.
- Stage and commit in one command, pathspec on both; read back `git log -1 --format=%s` and
  `git show --name-only <sha>`.
- The result file carries the full SHA, the Session id and the INBOX ids. Git carries none of our ids.

## STOP / ROLLBACK
Stop and report if: <the only fix is outside SCOPE / a claimed file is held / the premise correction changes
what should be built / a destructive step would be needed / credentials are missing>. Rollback is your own
local commit only; never reset or revert anyone else's work.

## RESULT
Write the skeleton of `results/<SESSION-ID>.md` first (check it does not exist), then fill it per
`orchestration/03_RESULT_TEMPLATE.md`. Order: green → commit → release lock → wide verification → result
file.
```

---

## STANDING CLAUSE — paste verbatim into every GUARDRAILS

```markdown
**The repository outranks this task file.**
Every file:line reference here is a HINT ABOUT WHERE TO LOOK, never an address. Re-derive each one from
current source before you touch it — including in files no commit has modified since this task was
written. A citation that was wrong when the task was written survives a no-op diff untouched, so "has this
file changed?" is not a sufficient trigger for re-verification.

The same applies to prose. If this task asserts something behaves a certain way and the code says
otherwise, the code wins. Correcting the task is EXPECTED, not insubordination; state the correct facts
plainly in your result. The genuine failure mode is output that is internally consistent with a wrong
premise — worse than stopping, and much worse than saying "the task is wrong here".

Know which kind of correction you are making:
- the premise is wrong and the prescribed remedy is still right → fix the premise, implement, report the
  correction; do not stop;
- the correction makes the prescribed remedy wrong, or changes what should be delivered → STOP and report.
  Do not redesign the Session around your own finding: the user asked for a specific outcome, and a
  corrected diagnosis does not carry authority to change what gets built.
```

---

## Pre-dispatch checklist
- [ ] One distinct problem (or one well-formed backlog cluster); repository and path exact.
- [ ] The user's words verbatim; every screenshot transcribed.
- [ ] Facts stated as mechanisms with a way to check them; properties, not remembered values.
- [ ] Standing clause pasted; applicable invariants, rulings and repository hazards quoted.
- [ ] Acceptance measurable; the locally provable part separable from anything only the user can verify.
- [ ] Sized to the budget: if it stopped two thirds of the way, something committed would survive.
- [ ] Commit subject suggestion legal; no hub ids anywhere in it.
- [ ] `claims` and `not_taken` filled when other Sessions touch the same repository.
- [ ] No criterion that can only be met by something impossible here (a paid call, production data).

---

# FOR ORCHESTRATORS ONLY — do not copy anything below into a Session MD

Everything above is worker-facing. Below are the standing lessons for whoever writes the task. Each one was
learned from a real incident in the hub this template descends from; the incident shape is kept, the
project is not.

### 1. Cite the mechanism, not the symptom
"There is no test renderer here" is a symptom claim a worker can disprove with one grep — and disproving it
teaches the worker the whole task file is unreliable, at the moment it most needs to be believed. "The unit
config sets `environment: node`, so there is no DOM to render into" is the mechanism: checkable, correct,
and it survives the grep. Write task facts so that verifying them CONFIRMS them. When a worker corrects
you, fix the goal file **in place** — a correction appended below a wrong sentence leaves it readable to
anyone who stops there.

### 2. Name the property, not the token that satisfies it today
"Use the canonical permission module" failed where that module had a test-mode bypass; "the safe function"
failed where it fell through to a forgeable header; a version tripwire fired on a valid run. State the
property the caller needs and how to check it holds; only then name something that satisfies it today, as
an example. A property-shaped instruction also survives your own later refinements; a value-shaped one goes
stale in minutes.

### 3. A remedy hint states the property the fix must preserve
"Make the create succeed" is a hint; "make the create succeed without weakening any assertion about what
survives a re-read" is a property — and it is what lets a worker see when the hint is wrong. Rules that
cover several sites get compressed to one site and read as complete: name every site or none; for a rule
spanning N sites × M attributes, quote the assertion that pins each cell or point to the spec. Prose about
a mechanism produces a plausible wrong cell every time. When you correct someone, run your correction
through the same check that caught their error.

### 4. Ask whether the codebase already named the defect class
A defect visible in two places is usually one somebody already diagnosed, named and built a canonical fix
for — often documented in the header of the module created to end it. Grep for it before prescribing; carry
the existing remedy's invariants, not your own reasoning. Then ask the follow-up: is the code in front of
you an instance of the remedy, or another instance of the defect wearing the remedy's vocabulary?

### 5. Test the boring explanation before positing an actor
A branch moving under you, a file changing that you did not touch, a refusal with no reason: first suspect a
missing capability (no credentials, a stale cache, a path this context cannot read, the user's own desktop
client syncing) before an unknown agent. Capability hypotheses are cheaper to test and more likely.

### 6. Absence is not evidence; adjacency is not ownership
No notification does not mean a worker is alive; a file sitting next to someone's logs is not theirs.
Before attributing, escalating or reassuring on what you did *not* see, run the cheap probe:
`git log -- <path>`, `git status <path>`, a session-list tool. Retract at the same volume you asserted.

### 7. Size the Session to the budget, and name its commit boundaries
Workers stop without warning at their turn limit. Ask: if this stops two thirds of the way through, what is
recoverable? If "nothing", split it or name the commit boundaries inside it. Independent parts commit per
part — tidiness is the wrong objective when the budget binds. Uncommitted is not the worst state; staged is,
because the index is shared by everyone who commits next.

### 8. Verify the effect, not the call — through an independent channel
A tool reported a successful click that never reached the window; another reported a resize that never
happened; a committed test figure could not have been measured. A success response is a statement about the
request, not the world. Read back through a channel that does not depend on the one that wrote: an API read
after a UI write, the DOM after a click, the file after an append. On files several contexts edit, neither
an error nor a clean exit tells you the write was right — only reading it back does.

### 9. When the output IS the evidence, capture it to a file
A suite piped through `tail` keeps the summary line and discards the failure list — the entire point of
running it. A summary is not a small version of the evidence; it is a different artefact. Capture the whole
output to a file, then read the file. And `head` can never establish a negative: to claim "there are none",
count or read everything. Report the command you ran, not only the verdict, whenever someone may rely on it;
an agreement that does not say what it ran is an echo, not corroboration.

### 10. Find the number that would have moved if you had cheated
Deleting, skipping or hollowing out assertions produces the same green headline as a real fix. Before
reporting an improvement, name the quantity that would have moved — test totals, file counts, a
`git diff --stat` bounded to the allowed files — and show it did not. Ask for this in the task; do not hope
a worker invents it.

### 11. Prove "no behaviour change" mechanically
Reading a diff is not proof. Compare what the tooling emits: token streams of the parsed file before and
after (comments are not tokens — but pragma comments change behaviour and must be grepped separately),
compiled CSS bytes, generated artefacts. Run the instrument against a deliberate counterexample to
show it fires, and put both in the result.

### 12. A style or accessibility claim reasoned from source is not verified
The declaration is present, so the source reads as correct — and cascade order, specificity or
accessible-name precedence decided otherwise. You cannot predict the winner from either axis alone: read
what was emitted, or render it. Where no runtime is reachable, say the claim is unproven.

### 13. Do not fix one consumer by making a private thing global
Promoting a component-scoped definition to global fixes the visible symptom and silently restyles its owner,
turning a contained defect into an undocumented shared contract. Define it in the consumer, or use the
genuine shared primitive. Ask: is this shared because someone decided it, or because it happens to be the
only definition?

### 14. "Report it if X changes" is worthless unless X is visible from inside
A reviewer measuring while another context reinstalls dependencies gets numbers that are not obviously wrong
and nothing in its transcript shows the toolchain moved. Before relying on self-reporting, ask whether the
change would be visible to the observer. If not, remove the condition: sequence the work or hold it.

### 15. A brief goes stale when you refine it, and the worker wears the blame
If you refine guidance an in-flight Session already carries and cannot reach it, write the exposure into the
goal file before the result arrives: what the stale wording says, what the corrected wording says, and what
the symptom will look like — so the reviewer recognises it instead of ordering a repair.

### 16. Persistence needs a verifier who is allowed to write
Proving that a write survives means creating real data, and a reviewer must not create product data. When
acceptance turns on durability, the Session itself proves it — through the product's own write path, into a
store no peer is using, confirmed by re-reading the authoritative store (the UI agreeing with itself is not
persistence) — and says what it created and where.

### 17. Isolation for runtime checks
When several Sessions share a working tree, a server started on it serves everyone's half-saved state: a red
build may be someone else's edit and a green one may be luck. Serve from a clean worktree at your own commit,
or say what was dirty when you measured.

### 18. A documented trap is still a trap
An accurate warning in a config docblock did not stop a worker from running the natural command, because the
dangerous invocation had a name in the task runner and the safe one did not. Fix the reachable path — make
the safe thing the default, or give it a name — before writing the warning a third time.

### 19. Housekeeping is the dangerous step
Destructive incidents cluster at the end of a context — removing worktrees, clearing caches, deleting
"leftover" data — when the context is finishing and least inclined to check. Prefer a named leftover over an
unexamined cleanup. Never link a dependency folder from the real tree into a temporary worktree: removing
the worktree can delete through the link.

### 20. A retraction is a claim too
Corrections inherit no credibility from being self-critical; two successive corrections of one finding were
both wrong in the flattering direction. Check the correction against the source like any other claim, and
record outcomes, not process narratives you cannot verify.
