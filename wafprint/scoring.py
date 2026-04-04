from typing import Dict, Any, List

def score(features: Dict[str, Any]) -> Dict[str, Any]:
    seq = features.get("seq", {})

    fsm = features.get("fsm", {})
    fsm_signals: List[str] = fsm.get("signals", [])
    fsm_final = fsm.get("final_state")
    state_props = fsm.get("state_properties", {})

    scope = None
    if fsm_final in state_props:
        scope = state_props[fsm_final].get("scope")

    signals: List[str] = []
    s = 0.0
    evidence = 0

    def get(name: str, key: str, default=0.0):
        return seq.get(name, {}).get(key, default)

    errors = sum(seq.get(n, {}).get("error_count", 0) for n in seq.keys())
    drift_soft = get("soft_burst", "lat_drift_ratio", 0.0)
    state_cookie_count = get("state_cookies", "set_cookie_count", 0)
    state_body_hashes = get("state_cookies", "unique_body_hashes", 0)

    status_soft = seq.get("soft_burst", {}).get("status_hist", {})
    status_state = seq.get("state_cookies", {}).get("status_hist", {})
    soft_429 = int(status_soft.get("429", 0))
    soft_403 = int(status_soft.get("403", 0))
    state_403 = int(status_state.get("403", 0))

    if soft_429 >= 1:
        s += 1.8
        evidence += 1
        signals.append("rate_limit_429")

    if drift_soft >= 2.0 and errors >= 1:
        s += 1.2
        evidence += 1
        signals.append("burst_latency_with_errors")

    if drift_soft >= 2.0 and fsm_final in ("throttled", "blocked_soft", "blocked_hard"):
        s += 1.0
        evidence += 1
        signals.append("corroborated_burst_latency")

    if soft_403 >= 2 or state_403 >= 2:
        s += 1.5
        evidence += 1
        signals.append("repeated_403")

    if state_cookie_count >= 2 and state_body_hashes >= 2 and fsm_final == "challenged":
        s += 1.2
        evidence += 1
        signals.append("challenge_pattern")

    if errors >= 1 and fsm_final in ("throttled", "blocked_soft", "blocked_hard"):
        s += 0.7
        evidence += 1
        signals.append("resets_or_timeouts")

    if "stateful_edge_detected" in fsm_signals:
        s += 0.8
        evidence += 1
        signals.append("stateful_edge_detected")

    if "adaptive_rate_limit_detected" in fsm_signals:
        s += 1.0
        evidence += 1
        signals.append("adaptive_rate_limit_detected")

    if "non_recoverable_block" in fsm_signals:
        s += 1.5
        evidence += 1
        signals.append("non_recoverable_block")

    if fsm_final == "blocked_hard":
        s += 1.2
        evidence += 1
        signals.append("hard_block_state")

    if scope == "connection_scoped":
        s += 0.3
        signals.append("connection_scoped_state")

    elif scope == "cookie_scoped":
        s += 0.8
        evidence += 1
        signals.append("cookie_scoped_state")

    elif scope == "ip_scoped":
        s += 1.2
        evidence += 1
        signals.append("ip_scoped_state")

    family = "unknown"

    if fsm_final in ("blocked_hard", "blocked_soft"):
        family = "policy_enforced_edge"

    elif "adaptive_rate_limit_detected" in signals:
        family = "adaptive_rate_limit"

    elif fsm_final == "challenged":
        family = "challenge_based_edge"

    elif "rate_limit_429" in signals:
        family = "rate_limit_focused"

    confidence = "low"
    if evidence >= 5 and s >= 5.0:
        confidence = "high"
    elif evidence >= 3 and s >= 3.0:
        confidence = "medium"

    return {
        "score": s,
        "signals": signals,
        "family": family,
        "confidence": confidence,
        "evidence_count": evidence,
    }
