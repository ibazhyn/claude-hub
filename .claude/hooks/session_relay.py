#!/usr/bin/env python3
"""Stop / PreCompact hook: autonomous session handoff ("relay").

When the orchestrator session is past its stop threshold (control/hub-config.json -> context_budget.stop_tokens)
or Claude Code is about to auto-compact, this hook:
  1. takes the relay lock control/locks/RELAY.lock (atomic create; one relay at a time, stale after
     relay.stale_minutes) and a per-session marker, so a session is relayed at most once and two runners never start;
  2. writes control/handoff/RELAY-<stamp>.md: old session id, context size, trigger, hub git status, pointer to
     control/NEXT-SESSION-PROMPT.md (which the hub-handoff skill keeps current);
  3. starts the continuation as a background Claude Code session (`claude --bg`, see `claude --help`) in the hub,
     with a prompt that resumes from those files;
  4. tells the old session to stop (`continue: false`; on PreCompact also blocks the compaction).
Stop only relays when the handoff is fresh (NEXT-SESSION-PROMPT.md modified within relay.fresh_minutes), so the
model always writes the real handoff first; PreCompact is the mechanical fallback and relays regardless.

Config (all optional) in control/hub-config.json -> "relay":
  enabled (true), command (["claude","--bg"]), extra_args ([]), stale_minutes (30), fresh_minutes (20).
HUB_RELAY_DRY_RUN=1 -> do everything except launching; the command is written to the relay file.
Never raises: failures go to session_relay.err beside this file and the session continues normally.
Self-test: python .claude/hooks/session_relay.py --selftest
"""
import datetime, json, os, shutil, subprocess, sys, tempfile, time

sys.dont_write_bytecode = True
HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HOOK_DIR)
DEFAULT_HUB = os.path.dirname(os.path.dirname(HOOK_DIR))
RELAY_DEFAULTS = {"enabled": True, "command": ["claude", "--bg"], "extra_args": [], "stale_minutes": 30,
                  "fresh_minutes": 20}


def note(hub, why):
    try:
        p = os.path.join(hub, ".claude", "hooks", "session_relay.err")
        with open(p, "a", encoding="utf-8") as fh:
            fh.write("%s %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), why))
    except Exception:
        pass


def load_cfg(hub):
    try:
        with open(os.path.join(hub, "control", "hub-config.json"), encoding="utf-8-sig") as fh:
            cfg = json.load(fh)
    except Exception:
        cfg = {}
    r = dict(RELAY_DEFAULTS)
    if isinstance(cfg.get("relay"), dict):
        r.update({k: v for k, v in cfg["relay"].items() if k in RELAY_DEFAULTS})
    b = cfg.get("context_budget") if isinstance(cfg.get("context_budget"), dict) else {}
    stop = b.get("stop_tokens") if isinstance(b.get("stop_tokens"), int) else 140000
    return r, stop


def context_tokens(tp):
    try:
        import context_budget
        return context_budget.scan(tp)[0]
    except Exception:
        return 0


def take_lock(hub, session, stale_min):
    locks = os.path.join(hub, "control", "locks")
    os.makedirs(locks, exist_ok=True)
    marker = os.path.join(locks, "RELAYED-%s" % session)
    if os.path.exists(marker):
        return None, "session already relayed"
    lock = os.path.join(locks, "RELAY.lock")
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) > stale_min * 60:
        try:
            os.remove(lock)
        except OSError:
            pass
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None, "another relay is in progress (RELAY.lock)"
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps({"session": session, "at": datetime.datetime.now().isoformat(timespec="seconds")}))
    open(marker, "w").close()
    return lock, ""


def git_status(hub):
    try:
        r = subprocess.run(["git", "-C", hub, "status", "--short"], capture_output=True, text=True, timeout=10)
        return (r.stdout or "").strip()[:3000] or "(clean or not a git repo)"
    except Exception:
        return "(git unavailable)"


def relay(ev, hub, dry):
    event = ev.get("hook_event_name")
    session = str(ev.get("session_id") or "unknown")
    tp = ev.get("transcript_path") or ""
    r, stop = load_cfg(hub)
    if not r.get("enabled") or ev.get("agent_id"):   # never relay a subagent
        return ""
    if event == "PreCompact":
        if ev.get("trigger", "auto") != "auto":
            return ""                                 # a manual /compact is the user's choice
        trigger = "auto-compact"
    elif event == "Stop":
        ctx = context_tokens(tp) if tp and os.path.isfile(tp) else 0
        if ctx < stop:
            return ""
        nsp = os.path.join(hub, "control", "NEXT-SESSION-PROMPT.md")
        if not os.path.exists(nsp) or time.time() - os.path.getmtime(nsp) > r["fresh_minutes"] * 60:
            if ev.get("stop_hook_active"):
                return ""                             # already asked once this turn: never loop
            return json.dumps({"decision": "block", "reason": "[session-relay] Past the stop threshold. Run the "
                               "hub-handoff skill now (refresh control/NEXT-SESSION-PROMPT.md and the goal file), "
                               "then end the turn: the relay starts the next session automatically."})
        trigger = "stop-threshold (%dk)" % (ctx // 1000)
    else:
        return ""
    lock, why = take_lock(hub, session, r["stale_minutes"])
    if not lock:
        note(hub, "relay skipped: " + why)
        return ""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    hdir = os.path.join(hub, "control", "handoff")
    os.makedirs(hdir, exist_ok=True)
    rel = "control/handoff/RELAY-%s.md" % stamp
    prompt = ("Continue as the hub orchestrator. The previous session (%s) was stopped by the session relay (%s). "
              "Run the CLAUDE.md section 1 state check, then read control/NEXT-SESSION-PROMPT.md, the goal files it "
              "names, and %s. Resume every open goal; do not re-dispatch anything in tasks/running/; keep all git "
              "and safety rules." % (session, trigger, rel))
    cmd = list(r["command"]) + list(r["extra_args"]) + ["--name", "hub-relay-" + stamp, prompt]
    body = ("# Session relay %s\n\n- Old session: %s\n- Trigger: %s\n- Transcript: %s\n- Handoff: "
            "control/NEXT-SESSION-PROMPT.md\n- Command: `%s`\n\n## Hub git status\n```\n%s\n```\n"
            % (stamp, session, trigger, tp, " ".join(cmd[:-1]) + " <prompt>", git_status(hub)))
    launched = "dry run, not launched"
    if not dry:
        try:
            log = open(os.path.join(hdir, "RELAY-%s.log" % stamp), "w")
            subprocess.Popen(cmd, cwd=hub, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             start_new_session=True)
            launched = "launched"
        except Exception as e:
            launched = "LAUNCH FAILED: %s" % e
            note(hub, launched)
            os.remove(lock)                           # let a later trigger retry
    with open(os.path.join(hub, rel), "w", encoding="utf-8") as fh:
        fh.write(body + "\n- Launch: %s\n" % launched)
    if launched.startswith("LAUNCH FAILED"):
        return ""
    out = {"continue": False, "stopReason": "[session-relay] Context limit reached; handoff in %s, a new "
           "background session continues (`claude agents` lists it). This session stops here." % rel}
    if event == "PreCompact":
        out.update({"decision": "block", "reason": "relayed to a fresh session instead of compacting"})
    return json.dumps(out)


def selftest():
    import context_budget  # noqa: F401  (must import beside this file)
    tmp = tempfile.mkdtemp(prefix="relay-selftest-")
    res = []
    try:
        os.makedirs(os.path.join(tmp, "control"))
        os.makedirs(os.path.join(tmp, ".claude", "hooks"))
        with open(os.path.join(tmp, "control", "hub-config.json"), "w") as fh:
            json.dump({"context_budget": {"stop_tokens": 100000}}, fh)

        def tr(n, name):
            p = os.path.join(tmp, name)
            with open(p, "w") as fh:
                fh.write(json.dumps({"type": "assistant", "message": {"id": "m1", "model": "x", "usage": {
                    "input_tokens": n, "output_tokens": 1}}}) + "\n")
            return p
        low, high = tr(5000, "low.jsonl"), tr(150000, "high.jsonl")
        R = lambda ev: relay(ev, tmp, True)
        res.append(("below threshold: silent", R({"hook_event_name": "Stop", "session_id": "a", "transcript_path": low}) == ""))
        o = R({"hook_event_name": "Stop", "session_id": "a", "transcript_path": high})
        res.append(("past threshold, stale handoff: asks for hub-handoff", '"block"' in o and "hub-handoff" in o))
        open(os.path.join(tmp, "control", "NEXT-SESSION-PROMPT.md"), "w").close()
        o = R({"hook_event_name": "Stop", "session_id": "a", "transcript_path": high})
        res.append(("fresh handoff: relays and stops old session", '"continue": false' in o))
        files = os.listdir(os.path.join(tmp, "control", "handoff"))
        res.append(("relay file written", any(f.startswith("RELAY-") for f in files)))
        res.append(("same session never relays twice", R({"hook_event_name": "Stop", "session_id": "a", "transcript_path": high}) == ""))
        res.append(("second runner blocked by lock", R({"hook_event_name": "PreCompact", "trigger": "auto", "session_id": "b"}) == ""))
        os.utime(os.path.join(tmp, "control", "locks", "RELAY.lock"), (0, 0))
        o = R({"hook_event_name": "PreCompact", "trigger": "auto", "session_id": "c"})
        res.append(("stale lock reclaimed; auto-compact relays and blocks compaction", '"block"' in o and '"continue": false' in o))
        res.append(("manual /compact untouched", R({"hook_event_name": "PreCompact", "trigger": "manual", "session_id": "d"}) == ""))
        res.append(("subagent never relayed", R({"hook_event_name": "PreCompact", "trigger": "auto", "session_id": "e", "agent_id": "x"}) == ""))
        os.utime(os.path.join(tmp, "control", "NEXT-SESSION-PROMPT.md"), (0, 0))
        res.append(("stop_hook_active + stale handoff: no loop", R({"hook_event_name": "Stop", "session_id": "f", "transcript_path": high, "stop_hook_active": True}) == ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = sum(0 if ok else 1 for _, ok in res)
    for label, ok in res:
        print(("PASS  " if ok else "FAIL  ") + label)
    print("%d/%d passed" % (len(res) - bad, len(res)))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    hub = os.environ.get("CLAUDE_PROJECT_DIR") or DEFAULT_HUB
    raw = sys.stdin.read().lstrip("\ufeff \t\r\n")
    if not raw:
        return
    try:
        ev = json.loads(raw)
    except Exception:
        return
    try:
        out = relay(ev, hub, os.environ.get("HUB_RELAY_DRY_RUN") == "1")
    except Exception as e:
        note(hub, "unhandled %s: %s" % (type(e).__name__, e))
        out = ""
    if out:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()
    sys.exit(0)
