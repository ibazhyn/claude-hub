#!/usr/bin/env python3
"""UserPromptSubmit hook: makes context growth visible and enforces the session budget.

Every call re-reads the whole context, so a session's cost grows with the square of its length: a token
added at call N is paid again on every call after it. This hook reads the live transcript, measures the
context of the last model call (input + cache read + cache creation) and the number of calls, and:
  * below warn_tokens     -> prints nothing (a healthy session pays nothing for it);
  * from warn_tokens      -> a one-line reminder to keep raw output out of the main context;
  * from handoff_tokens   -> the handoff instruction: run the hub-handoff skill;
  * from stop_tokens      -> do not start new work in this session.
Thresholds live in control/hub-config.json -> context_budget (shipped for a 200k context window:
80k / 120k / 140k). Self-calibration: the first time it sees a context above 200k tokens, the window is
evidently larger, so it rewrites the section to a 1,000,000 window with 150k / 350k / 400k.

A spend estimate is added when tools/model_prices.py is importable. It never blocks the turn: any failure
exits 0 silently and is noted in context_budget.err beside this file. Standard library only; Python 3.8+.

Self-test (never touches the real config): python .claude/hooks/context_budget.py --selftest
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(os.path.dirname(HOOK_DIR))
CONFIG = os.environ.get("HUB_BUDGET_CONFIG") or os.path.join(HUB, "control", "hub-config.json")
ERRLOG = os.environ.get("HUB_BUDGET_ERRLOG") or os.path.join(HOOK_DIR, "context_budget.err")
MAXSCAN = 300 * 1024 * 1024
DEFAULTS = {"context_window": 200000, "warn_tokens": 80000, "handoff_tokens": 120000, "stop_tokens": 140000}
CALIBRATED = {"context_window": 1000000, "warn_tokens": 150000, "handoff_tokens": 350000, "stop_tokens": 400000}
CALIBRATE_ABOVE = 200000


def note(why):
    """A guard that fails must say so somewhere. Bounded to the last 50 lines."""
    try:
        old = []
        if os.path.exists(ERRLOG):
            with open(ERRLOG, encoding="utf-8", errors="replace") as fh:
                old = fh.readlines()[-49:]
        with open(ERRLOG, "w", encoding="utf-8") as fh:
            fh.writelines(old)
            fh.write("%s %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), why))
    except Exception:
        pass


def load(path):
    """-> (whole config dict or None when the file is missing or unreadable, budget dict with defaults)."""
    cfg = None
    try:
        with open(path, encoding="utf-8-sig") as fh:   # -sig: a file saved with a BOM still parses
            cfg = json.load(fh)
    except Exception:
        cfg = None
    if not isinstance(cfg, dict):
        cfg = None
    b = dict(DEFAULTS)
    sec = cfg.get("context_budget") if cfg else None
    if isinstance(sec, dict):
        for k in DEFAULTS:
            if isinstance(sec.get(k), (int, float)) and sec.get(k) > 0:
                b[k] = int(sec[k])
    return cfg, b


def calibrate(path, cfg):
    """Rewrite the budget for a 1M window, preserving every other key. Atomic replace."""
    sec = cfg.get("context_budget") if isinstance(cfg.get("context_budget"), dict) else {}
    sec.update(CALIBRATED)
    sec["calibrated"] = True
    sec["calibrated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    cfg["context_budget"] = sec
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return dict(CALIBRATED)


def price_fn():
    try:
        sys.path.insert(0, os.path.join(HUB, "tools"))
        from model_prices import call_cost
        return call_cost
    except Exception:
        return None


def scan(tp):
    """-> (context tokens of the last real call, number of calls, $ at list price or None).

    One API call is written as several transcript lines - one per content block - that share message.id and
    repeat its usage. So a call is a unique message id, counted once with the usage of its last line; a line
    without an id is not a call."""
    cost_of = price_fn()
    seen = {}      # message id -> (model, usage of its latest line); dicts keep first-seen order
    last = None
    with open(tp, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            m = d.get("message") if isinstance(d, dict) else None
            u = m.get("usage") if isinstance(m, dict) else None
            if not isinstance(u, dict) or d.get("type") != "assistant" or m.get("model") == "<synthetic>":
                continue  # <synthetic> = a locally written error turn: no API call, zero usage
            mid = m.get("id")
            if not isinstance(mid, str) or not mid:
                continue
            seen[mid] = (m.get("model"), u)
            last = u
    ctx = 0
    if last:
        ctx = ((last.get("input_tokens") or 0) + (last.get("cache_creation_input_tokens") or 0)
               + (last.get("cache_read_input_tokens") or 0))
    cost = None
    if cost_of:
        cost = 0.0
        for model, u in seen.values():
            try:
                cost += cost_of(model, u)
            except Exception:
                pass
    return ctx, len(seen), cost


def advise(ctx, calls, cost, b, calibrated_now):
    if ctx < b["warn_tokens"] or not calls:
        return ""
    k = ctx // 1000
    spent = (", ~$%.2f at list price" % cost) if cost is not None else ""
    head = "[context-budget] %dk of a %dk window, %d calls%s." % (k, b["context_window"] // 1000, calls, spent)
    cal = (" (Calibrated just now: this session passed 200k, so the window is 1M; control/hub-config.json now "
           "holds 150k / 350k / 400k.)") if calibrated_now else ""
    if ctx >= b["stop_tokens"]:
        return (head + " PAST THE STOP THRESHOLD (%dk). Do not start new work in this session. Finish only the "
                "step in hand, run the hub-handoff skill, and tell the user at the TOP of your reply, in their "
                "language, to open a fresh session, with the prompt pasted inline." % (b["stop_tokens"] // 1000)
                + cal)
    if ctx >= b["handoff_tokens"]:
        return (head + " HANDOFF THRESHOLD (%dk) PASSED. Run the hub-handoff skill now: refresh "
                "control/NEXT-SESSION-PROMPT.md and your goal file, then announce the handoff at the TOP of your "
                "reply with a visual marker, in the user's language, with the prompt pasted inline. Every "
                "further call re-reads the whole context; cost grows with the square of session length."
                % (b["handoff_tokens"] // 1000) + cal)
    return (head + " Keep raw output out of this context: bulk reads, suite runs and log reading go to "
            "subagents that return conclusions; pipe command output through head/grep/--stat. Keep "
            "control/NEXT-SESSION-PROMPT.md current. Handoff at %dk." % (b["handoff_tokens"] // 1000) + cal)


def evaluate(raw, config_path):
    """Hook input text -> the text to print ('' for silence). Performs calibration when due."""
    raw = raw.lstrip("﻿ \t\r\n")
    if not raw:
        return ""
    try:
        ev = json.loads(raw)
    except Exception as e:
        note("unparseable hook input (%s); first 80 chars: %r" % (e, raw[:80]))
        return ""
    tp = ev.get("transcript_path") if isinstance(ev, dict) else None
    if not isinstance(tp, str) or not tp or not os.path.isfile(tp):
        return ""
    if os.path.getsize(tp) > MAXSCAN:
        note("transcript over scan limit: %s" % tp)
        return ""
    ctx, calls, cost = scan(tp)
    cfg, b = load(config_path)
    calibrated_now = False
    if ctx > CALIBRATE_ABOVE and b["context_window"] <= CALIBRATE_ABOVE:
        if cfg is None:
            # Never rewrite a config that could not be read: that would drop every other setting in it.
            note("calibration skipped: %s is missing or not valid JSON" % config_path)
            b = dict(CALIBRATED)
        else:
            try:
                b = calibrate(config_path, cfg)
                calibrated_now = True
            except Exception as e:
                note("calibration failed: %s" % e)
    text = advise(ctx, calls, cost, b, calibrated_now)
    if not text:
        return ""
    return json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}})


def selftest():
    """Seven scenarios plus garbage input, in a temp folder with a copy of the default config."""
    global ERRLOG
    tmp = tempfile.mkdtemp(prefix="hub-budget-selftest-")
    ERRLOG = os.path.join(tmp, "err.txt")   # the self-test never writes beside the real hook
    results = []
    try:
        cfg_path = os.path.join(tmp, "hub-config.json")

        def fresh_config():
            with open(cfg_path, "w", encoding="utf-8") as fh:
                json.dump({"context_budget": dict(DEFAULTS, calibrated=False)}, fh)

        def transcript(ctx_tokens, split=1, name=None):
            """Two calls (1k, then ctx_tokens). The last one is written as `split` lines sharing its message
            id, the way Claude Code writes one line per content block; its earlier lines carry a partial
            usage (1 output token), its last line the final one."""
            p = os.path.join(tmp, name or ("t-%d.jsonl" % ctx_tokens))
            with open(p, "w", encoding="utf-8") as fh:
                for k, n in enumerate((1000, ctx_tokens)):
                    reps = split if k else 1
                    for j in range(reps):
                        fh.write(json.dumps({"type": "assistant", "message": {
                            "id": "msg_selftest_%d" % k, "model": "claude-test", "usage": {
                                "input_tokens": 10, "output_tokens": 1 if j < reps - 1 else 5,
                                "cache_read_input_tokens": n - 10, "cache_creation_input_tokens": 0}}}) + "\n")
            return p

        def run(ctx_tokens):
            return evaluate(json.dumps({"transcript_path": transcript(ctx_tokens)}), cfg_path)

        fresh_config()
        results.append(("50k: silent", run(50000) == ""))
        results.append(("90k: one-line reminder", "Keep raw output out" in run(90000)))
        results.append(("125k: handoff instruction", "hub-handoff" in run(125000)
                        and "HANDOFF THRESHOLD" in run(125000)))
        results.append(("145k: do not start new work", "Do not start new work" in run(145000)))
        single = transcript(90000, name="t-single.jsonl")
        dup = transcript(90000, split=3, name="t-dup.jsonl")
        with open(dup, "a", encoding="utf-8") as fh:   # usage on a line without a message id: not a call
            fh.write(json.dumps({"type": "assistant", "message": {"model": "claude-test", "usage": {
                "input_tokens": 7, "output_tokens": 5}}}) + "\n")
        s1, s3 = scan(single), scan(dup)
        text = evaluate(json.dumps({"transcript_path": dup}), cfg_path)
        results.append(("one call on 3 lines counts once; a line without an id is no call",
                        s3[:2] == (90000, 2) and s1[:2] == s3[:2] and ", 2 calls" in text
                        and (s1[2] is None or abs(s1[2] - s3[2]) < 1e-9)))
        out = run(250000)
        with open(cfg_path, encoding="utf-8") as fh:
            sec = json.load(fh).get("context_budget", {})
        results.append(("250k: calibrates to 1M with 150k/350k/400k",
                        sec.get("context_window") == 1000000 and sec.get("warn_tokens") == 150000
                        and sec.get("handoff_tokens") == 350000 and sec.get("stop_tokens") == 400000
                        and "Calibrated just now" in out and "Keep raw output out" in out))
        broken = '{"write_roots": ["kept"], "context_budget": {'   # a hand edit gone wrong
        with open(cfg_path, "w", encoding="utf-8") as fh:
            fh.write(broken)
        out = run(250000)
        with open(cfg_path, encoding="utf-8") as fh:
            untouched = fh.read() == broken
        results.append(("250k with an unreadable config: never rewritten", untouched and "Keep raw output" in out))
        env = dict(os.environ, HUB_BUDGET_CONFIG=cfg_path, HUB_BUDGET_ERRLOG=os.path.join(tmp, "err.txt"),
                   PYTHONDONTWRITEBYTECODE="1")
        for label, payload in (("garbage input: exit 0, silent", b"this is not json {"),
                               ("empty input: exit 0, silent", b"")):
            r = subprocess.run([sys.executable, os.path.abspath(__file__)], input=payload,
                               capture_output=True, env=env, timeout=60)
            results.append((label, r.returncode == 0 and not r.stdout.strip()))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = 0
    for label, ok in results:
        print(("PASS  " if ok else "FAIL  ") + label)
        bad += 0 if ok else 1
    print("%d/%d passed" % (len(results) - bad, len(results)))
    return 1 if bad else 0


def main():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    data = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
    out = evaluate(data.decode("utf-8", "replace"), CONFIG)
    if out:
        sys.stdout.write(out)
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        note("unhandled %s: %s" % (type(e).__name__, e))
    sys.exit(0)
