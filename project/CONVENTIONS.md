# Conventions

> How work is shaped in the user's repositories. `hub-setup` records the observed commit convention per
> repository; `hub-context-analyst` adds what `context/` and the repositories' docs state, with sources.
> Where the two disagree, both are recorded and flagged. Rules the user states later go to
> `project/OVERRIDES.md`, which wins over this file.

## Commit subjects

_Per repository, recorded at setup:_

| repository | observed convention | regex | examples |
|---|---|---|---|
| _none yet_ | | | |

Default when a repository has no clear convention: conventional commits `type(scope): outcome`
(`orchestration/04_GIT_SAFETY_AND_COMMITS.md`). Conventional commits stay available in every repository —
a Session that cannot fill the house style never invents a value — so the enforced regex in
`control/hub-config.json` → `commit.subject_regex` always includes that form.

## Branches
Default: work on the branch that is current at setup (`working_branch` in `project/REPOSITORIES.md`); never
switch, create or push branches unless the user asks. _Project-specific policy: none recorded._

## Code
_None recorded yet._ (style guides, architecture rules, patterns to follow or avoid — with sources)

## Tests
_None recorded yet._ (what must be tested, where tests live, how they are run, what counts as green)

## Reviews and definition of done
Default: the hub's QA (`orchestration/06_QA_AND_REPAIR.md`). _Project-specific additions: none recorded._
