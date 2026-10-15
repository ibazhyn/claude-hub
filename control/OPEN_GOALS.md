# OPEN GOALS — register of every goal and the session that drives it

One row per goal. The goal's own file `control/goals/current-goal-<G>.md` is the authority on its state;
this register is how several sessions in one hub see each other. `python tools/hub.py status` reads it and
lists the LIVE goals with owner and areas.

- **owner** — the label of the session driving the goal (its title when a session tool exposes one,
  otherwise a label the session chose and stated in its first reply).
- **areas** — the repositories and product areas the goal owns. A new problem in one of these areas, while
  the goal is `LIVE` in another session, is handed over (`orchestration/01_ORCHESTRATION_PROTOCOL.md`
  § "Several sessions in one hub").
- **status** — `LIVE` (a session is driving it), `PAUSED` (no session driving; its handoff is written —
  owner `setup` means the first guarded session takes it over), `DONE` (every requested outcome QA-passed,
  legs only the user can verify named, or cancelled by the user — say which in the next step column).
- A `LIVE` row whose last update is many hours old may have lost its driver: check before routing to it,
  and take it over (update owner and status) if nobody drives it.

Update your row whenever the status changes and at every handoff. Append rows; never rewrite another
session's row except to take over a goal whose driver is verifiably gone — and then say so in its goal file.

| goal | title | owner | areas / repositories | status | opened | last update | next step |
|---|---|---|---|---|---|---|---|
