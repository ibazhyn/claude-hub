#!/usr/bin/env python3
"""Runs tools/guard_cases.json against .claude/hooks/safety_guard.py. Usage: python tools/guard_test.py [-v]

Each case pipes one PreToolUse payload through the guard, exactly as Claude Code does, and compares the
decision (deny = the guard printed permissionDecision "deny"; allow = it printed nothing).

The run is hermetic: a sandbox under the system temp directory holds a fake repository (a folder with a
.git directory) and a private copy of control/hub-config.json with subject_regex and write_roots cleared,
so the verdicts do not depend on how this hub was configured. A case may merge its own "config" into that
copy. Placeholders in commands and paths: {HUB} {TEMP} {REPO} {HOME} {ROOT} {SANDBOX} {CLAUDE_PROJECT}.

It also checks coverage: every deny family and every explicit allow that the contract requires must have
at least one case with that expectation. Exits 1 on any mismatch or gap. Standard library only.
"""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(HUB, ".claude", "hooks", "safety_guard.py")
CASES = os.path.join(HUB, "tools", "guard_cases.json")

REQUIRED_DENY = [
    "reset-hard", "clean-force", "checkout-discard", "restore-worktree", "stash", "rebase", "commit-amend",
    "push-force", "push-delete", "push-plus-refspec", "push-colon-refspec", "push-redirected", "push-indirect",
    "branch-D", "filter-branch",
    "filter-repo", "update-ref-d", "reflog-expire", "gc-prune", "author-flag", "author-config-flag",
    "author-config-write", "author-env", "no-verify", "rm-rf-repo-root", "rm-rf-dot-git", "rm-rf-home",
    "rm-rf-drive-root", "msg-file", "msg-reuse", "msg-fixup", "msg-squash", "here-string-in-bash",
    "banned-id", "banned-hub-name", "banned-unit-word", "subject-regex", "write-dot-git",
    "write-outside-roots",
]
REQUIRED_ALLOW = [
    "push-plain", "git-options-not-push", "stash-list", "worktree-add", "worktree-remove-temp",
    "worktree-remove-hub", "worktree-prune", "restore-staged", "checkout-b", "conventional-commit", "fail-open",
]


def fwd(p):
    return p.replace("\\", "/")


def deep_merge(base, extra):
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def substitute(value, subst):
    if isinstance(value, str):
        for k, v in subst.items():
            value = value.replace(k, v)
        return value
    if isinstance(value, list):
        return [substitute(x, subst) for x in value]
    if isinstance(value, dict):
        return dict((k, substitute(v, subst)) for k, v in value.items())
    return value


def payload_for(case, subst):
    if "raw" in case:
        return case["raw"].encode("utf-8")
    tool = case.get("tool", "Bash")
    if tool in ("Bash", "PowerShell"):
        ti = {"command": substitute(case["command"], subst)}
    elif tool == "NotebookEdit":
        ti = {"notebook_path": substitute(case["path"], subst), "new_source": "x"}
    elif tool == "Edit":
        ti = {"file_path": substitute(case["path"], subst), "old_string": "a", "new_string": "b"}
    else:
        ti = {"file_path": substitute(case["path"], subst), "content": "x"}
    ev = {"session_id": "guard-test", "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti,
          "cwd": substitute(case.get("cwd", "{HUB}"), subst)}
    return json.dumps(ev).encode("utf-8")


def main():
    verbose = "-v" in sys.argv
    with open(CASES, encoding="utf-8") as fh:
        cases = json.load(fh)
    try:
        with open(os.path.join(HUB, "control", "hub-config.json"), encoding="utf-8-sig") as fh:
            base_cfg = json.load(fh)
    except Exception:
        base_cfg = {}
    base_cfg["write_roots"] = []
    base_cfg.setdefault("commit", {})["subject_regex"] = None

    sandbox = tempfile.mkdtemp(prefix="hub-guard-test-")
    try:
        repo = os.path.join(sandbox, "repo")
        os.makedirs(os.path.join(repo, ".git"))
        os.makedirs(os.path.join(repo, "src"))
        drive = os.path.splitdrive(HUB)[0]
        claude_base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
        subst = {
            "{HUB}": fwd(HUB), "{TEMP}": fwd(tempfile.gettempdir()), "{REPO}": fwd(repo),
            "{HOME}": fwd(os.path.expanduser("~")), "{ROOT}": (drive + "/") if drive else "/",
            "{SANDBOX}": fwd(sandbox),
            "{CLAUDE_PROJECT}": fwd(os.path.join(claude_base, "projects", re.sub(r"[^A-Za-z0-9]", "-", HUB))),
        }
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        fails = 0
        covered = {"deny": set(), "allow": set()}
        for n, case in enumerate(cases, 1):
            cfg = deep_merge(copy.deepcopy(base_cfg), substitute(case.get("config") or {}, subst))
            cfg_path = os.path.join(sandbox, "config-%d.json" % n)
            # "config_bom": the file is saved with a byte-order mark, as some Windows editors do.
            with open(cfg_path, "w", encoding="utf-8-sig" if case.get("config_bom") else "utf-8") as fh:
                json.dump(cfg, fh)
            env["HUB_GUARD_CONFIG"] = cfg_path
            r = subprocess.run([sys.executable, "-B", GUARD], input=payload_for(case, subst),
                               capture_output=True, env=env, timeout=60)
            out = r.stdout.decode("utf-8", "replace").strip()
            got = "allow"
            reason = ""
            if out:
                try:
                    hso = json.loads(out).get("hookSpecificOutput", {})
                    got = "deny" if hso.get("permissionDecision") == "deny" else "allow"
                    reason = hso.get("permissionDecisionReason", "")
                except Exception:
                    got = "garbled"
                    reason = out[:200]
            err = r.stderr.decode("utf-8", "replace").strip()
            ok = got == case["expect"] and r.returncode == 0 and not err
            if err:
                reason = "stderr: " + err[:200]
            if ok:
                covered[case["expect"]].add(case.get("family", ""))
            else:
                fails += 1
            if verbose or not ok:
                print("%s %-5s (want %-5s) %-24s | %s" % ("  ok " if ok else "FAIL ", got, case["expect"],
                                                          case.get("family", ""), case.get("name", "")))
                if reason and (verbose or not ok):
                    print("        -> " + reason[:220])
        missing = ["deny:" + f for f in REQUIRED_DENY if f not in covered["deny"]]
        missing += ["allow:" + f for f in REQUIRED_ALLOW if f not in covered["allow"]]
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)

    print()
    print("%d/%d cases passed" % (len(cases) - fails, len(cases)))
    print("families: %d deny + %d allow required; %s" % (
        len(REQUIRED_DENY), len(REQUIRED_ALLOW), ("MISSING " + ", ".join(missing)) if missing else "all covered"))
    return 1 if (fails or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
