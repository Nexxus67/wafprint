from typing import Dict, Any, List

def score(features: Dict[str, Any]) -> Dict[str, Any]:
    seq = features.get("seq", {})

    # --- FSM -------------------------------------------------------------
    fsm = features.get("fsm", {})
    fsm_signals: List[str] = fsm.get("signals", [])
    fsm_final = fsm.get("final_state")
    state_props = fsm.get("state_properties", {})

    scope = None
    if fsm_final in state_props:
        scope = state_props[fsm_final].get("scope")

    signals: List[str] = []
    s = 0.0

    def get(name: str, key: str, default=0.0):
        return seq.get(name, {}).get(key, default)

    cookie = sum(seq.get(n, {}).get("set_cookie_count", 0) for n in seq.keys())
    errors = sum(seq.get(n, {}).get("error_count", 0) for n in seq.keys())
    drift_soft = get("soft_burst", "lat_drift_ratio", 0.0)
    uniq_hash_can = get("canonicalization", "unique_body_hashes", 0)

    status_soft = seq.get("soft_burst", {}).get("status_hist", {})
    status_codes = set(status_soft.keys())

    # --- Heurísticas base ------------------------------------------------
    if cookie >= 3:
        s += 1.0
        signals.append("cookie_activity_high")

    if errors >= 1:
        s += 0.7
        signals.append("resets_or_timeouts")

    if drift_soft >= 1.5:
        s += 1.0
        signals.append("latency_drift_on_burst")

    if "429" in status_codes:
        s += 1.2
        signals.append("rate_limit_429")

    if "403" in status_codes and drift_soft >= 1.2:
        s += 0.8
        signals.append("block_on_behavior_change")

    baseline_hashes = get("baseline", "unique_body_hashes", 1)

    if uniq_hash_can >= 2 and uniq_hash_can > baseline_hashes:
        s += 0.6
        signals.append("interstitial_or_rewrite_suspected")

    # --- FSM signals -----------------------------------------------------
    if "stateful_edge_detected" in fsm_signals:
        s += 0.8
        signals.append("stateful_edge_detected")

    if "adaptive_rate_limit_detected" in fsm_signals:
        s += 1.0
        signals.append("adaptive_rate_limit_detected")

    if "non_recoverable_block" in fsm_signals:
        s += 1.5
        signals.append("non_recoverable_block")

    if fsm_final == "blocked_hard":
        s += 1.2
        signals.append("hard_block_state")

    # --- Scope weighting -------------------------------------------------
    if scope == "connection_scoped":
        s += 0.3
        signals.append("connection_scoped_state")

    elif scope == "cookie_scoped":
        s += 0.8
        signals.append("cookie_scoped_state")

    elif scope == "ip_scoped":
        s += 1.2
        signals.append("ip_scoped_state")

    # --- Family ----------------------------------------------------------
    family = "unknown"

    if fsm_final in ("blocked_hard", "blocked_soft"):
        family = "policy_enforced_edge"

    elif "adaptive_rate_limit_detected" in signals:
        family = "adaptive_rate_limit"

    elif fsm_final == "challenged":
        family = "challenge_based_edge"

    elif "rate_limit_429" in signals:
        family = "rate_limit_focused"

    return {"score": s, "signals": signals, "family": family}