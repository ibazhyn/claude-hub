"""List prices per model - the ONE table the spend meters read.

Read by .claude/hooks/context_budget.py and tools/burn.py. UPDATE THIS TABLE WHEN PRICES CHANGE:
a new model is one row. Values are $ per million tokens:
    (input, output, 5-minute cache write, 1-hour cache write, cache read)
Anthropic first-party list prices as of 2026-09-23. Cache writes are 1.25x (5m) / 2x (1h) of input;
cache reads are 0.1x of input except where a model lists its own rate. These are API list-price
equivalents - a proportion meter for where the tokens go, not a subscription bill.

Lookup takes the longest model-id prefix, so dated ids (claude-haiku-4-5-20251001) resolve to their row.
An id with no row is priced as the newest model of its family and flagged unpriced - burn.py prints it,
so a stale table is visible instead of silently wrong.
"""

PRICES = {
    "claude-opus-5-5":   (4.00, 20.00,  5.00,  8.00, 0.20),   # cache read is 0.05x
    "claude-opus-5":     (5.00, 25.00,  6.25, 10.00, 0.50),
    "claude-opus-4-8":   (5.00, 25.00,  6.25, 10.00, 0.50),
    "claude-opus-4-7":   (5.00, 25.00,  6.25, 10.00, 0.50),
    "claude-opus-4-6":   (5.00, 25.00,  6.25, 10.00, 0.50),
    "claude-opus-4-5":   (5.00, 25.00,  6.25, 10.00, 0.50),
    "claude-opus-4":     (15.00, 75.00, 18.75, 30.00, 1.50),  # Opus 4.0 / 4.1
    "claude-fable-5-1":  (10.00, 50.00, 12.50, 20.00, 0.25),  # cache read is 0.025x
    "claude-mythos-5-1": (10.00, 50.00, 12.50, 20.00, 0.25),
    "claude-fable-5":    (10.00, 50.00, 12.50, 20.00, 1.00),
    "claude-mythos-5":   (10.00, 50.00, 12.50, 20.00, 1.00),
    "claude-sonnet-5":   (2.00, 10.00,  2.50,  4.00, 0.20),
    "claude-sonnet-4":   (3.00, 15.00,  3.75,  6.00, 0.30),   # Sonnet 4.0 / 4.5 / 4.6
    "claude-haiku-4-5":  (1.00,  5.00,  1.25,  2.00, 0.10),
}

# Fast mode bills the whole call at a multiple of standard; only models whose fast price is known.
FAST = {"claude-opus-5-5": 2.0, "claude-opus-5": 2.0}

NEWEST = {"opus": "claude-opus-5-5", "fable": "claude-fable-5-1", "mythos": "claude-mythos-5-1",
          "sonnet": "claude-sonnet-5", "haiku": "claude-haiku-4-5"}


def resolve(model):
    """-> (PRICES key, True if the id has its own row)."""
    m = (model or "").lower()
    if "claude-" in m:
        m = m[m.index("claude-"):]          # anthropic.claude-... / us.anthropic.claude-...
    hits = [k for k in PRICES if m == k or (m.startswith(k) and m[len(k)] in "-@[")]
    if hits:
        return max(hits, key=len), True
    for fam, key in NEWEST.items():
        if fam in m:
            return key, False
    return NEWEST["opus"], False


def rates(model):
    return PRICES[resolve(model)[0]]


def call_cost(model, usage):
    """$ at list price for one assistant turn's `usage` block."""
    key = resolve(model)[0]
    pi, po, pw5, pw1, pr = PRICES[key]
    u = usage or {}
    b = u.get("cache_creation")
    if isinstance(b, dict) and ("ephemeral_5m_input_tokens" in b or "ephemeral_1h_input_tokens" in b):
        w5 = b.get("ephemeral_5m_input_tokens", 0) or 0
        w1 = b.get("ephemeral_1h_input_tokens", 0) or 0
    else:
        w5, w1 = u.get("cache_creation_input_tokens", 0) or 0, 0
    cost = ((u.get("input_tokens", 0) or 0) * pi + (u.get("output_tokens", 0) or 0) * po
            + w5 * pw5 + w1 * pw1 + (u.get("cache_read_input_tokens", 0) or 0) * pr) / 1e6
    if u.get("speed") == "fast":
        cost *= FAST.get(key, 1.0)
    return cost
