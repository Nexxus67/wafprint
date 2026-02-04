from typing import Dict, Any, List, Optional
from dataclasses import dataclass

STATES = (
    "neutral",
    "observed",
    "throttled",
    "challenged",
    "blocked_soft",
    "blocked_hard",
)

@dataclass
class Transition:
    event: str
    from_state: str
    to_state: str

@dataclass
class FSMResult:
    initial_state: str
    final_state: str
    transitions: List[Transition]
    state_properties: Dict[str, Dict[str, Any]]
    signals: List[str]

# --- helpers -------------------------------------------------------------

def _status_codes(seq_feat: Dict[str, Any]) -> set:
    hist = seq_feat.get("status_hist", {})
    return set(hist.keys())

def _is_throttled(seq_feat: Dict[str, Any]) -> bool:
    return (
        "429" in _status_codes(seq_feat)
        or seq_feat.get("lat_drift_ratio", 0.0) >= 1.5
    )

def _is_challenged(seq_feat: Dict[str, Any]) -> bool:
    return (
        seq_feat.get("set_cookie_count", 0) > 0
        and seq_feat.get("unique_body_hashes", 0) >= 2
    )

def _is_blocked(seq_feat: Dict[str, Any]) -> bool:
    return "403" in _status_codes(seq_feat)

# --- principal inference ------------------------------------------------

def infer_fsm(features: Dict[str, Any]) -> Dict[str, Any]:
    seqs: Dict[str, Dict[str, Any]] = features.get("seq", {})
    order = list(seqs.keys())

    state = "neutral"
    transitions: List[Transition] = []
    state_props: Dict[str, Dict[str, Any]] = {}
    signals: List[str] = []

    def transition(event: str, new_state: str):
        nonlocal state
        if state != new_state:
            transitions.append(Transition(event, state, new_state))
            state = new_state

    baseline = seqs.get("baseline", {})
    if _is_blocked(baseline):
        state = "blocked_hard"

    
    for name in order:
        feat = seqs[name]

        if state == "neutral":
            if _is_throttled(feat):
                transition(name, "throttled")
            elif _is_challenged(feat):
                transition(name, "challenged")
            elif feat.get("lat_drift_ratio", 0.0) >= 1.2:
                transition(name, "observed")

        elif state == "observed":
            if _is_throttled(feat):
                transition(name, "throttled")
            elif _is_challenged(feat):
                transition(name, "challenged")

        elif state == "throttled":
            if _is_blocked(feat):
                transition(name, "blocked_soft")
            elif feat.get("lat_drift_ratio", 0.0) < 1.1:
                transition(name, "neutral")

        elif state == "challenged":
            if _is_blocked(feat):
                transition(name, "blocked_soft")

        elif state == "blocked_soft":
            if feat.get("recovery", False):
                transition(name, "neutral")


    if state == "blocked_soft":
        last = seqs[order[-1]]
        if _is_blocked(last) and not last.get("recovery", False):
            transition("terminal", "blocked_hard")

    # properties and derived signals
    if any(t.to_state in ("throttled", "challenged", "blocked_soft", "blocked_hard") for t in transitions):
        signals.append("stateful_edge_detected")

    if any(t.to_state == "throttled" for t in transitions):
        signals.append("adaptive_rate_limit_detected")

    if state == "blocked_hard":
        signals.append("non_recoverable_block")

    scope = "unknown"

    total_cookies = sum(
        seqs[n].get("set_cookie_count", 0) for n in seqs.keys()
    )

    if total_cookies > 0:
        scope = "cookie_scoped"
    elif state in ("blocked_soft", "blocked_hard", "throttled"):
        scope = "ip_scoped"
    else:
        scope = "connection_scoped"

    state_props[state] = {
        "scope": scope
    }

    return {
        "initial_state": "neutral",
        "final_state": state,
        "transitions": [t.__dict__ for t in transitions],
        "state_properties": state_props,
        "signals": signals,
    }