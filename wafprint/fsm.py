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

def _status_count(seq_feat: Dict[str, Any], code: str) -> int:
    return int(seq_feat.get("status_hist", {}).get(code, 0))

def _has_status(seq_feat: Dict[str, Any], code: str) -> bool:
    return _status_count(seq_feat, code) > 0

def _corroborates_throttle(seq_feat: Dict[str, Any]) -> bool:
    return (
        _has_status(seq_feat, "429")
        or seq_feat.get("error_count", 0) > 0
        or seq_feat.get("lat_drift_ratio", 0.0) >= 1.5
    )

def _is_throttled(name: str, seqs: Dict[str, Dict[str, Any]]) -> bool:
    seq_feat = seqs.get(name, {})
    if _has_status(seq_feat, "429"):
        return True

    if name != "soft_burst":
        return False

    if seq_feat.get("lat_drift_ratio", 0.0) < 2.0:
        return False

    if seq_feat.get("error_count", 0) > 0:
        return True

    for other_name, other_feat in seqs.items():
        if other_name in ("baseline", name):
            continue
        if _corroborates_throttle(other_feat):
            return True
    return False

def _is_challenged(name: str, seq_feat: Dict[str, Any]) -> bool:
    if name == "baseline":
        return False
    return (
        seq_feat.get("set_cookie_count", 0) >= 2
        and seq_feat.get("unique_body_hashes", 0) >= 2
        and seq_feat.get("lat_drift_ratio", 0.0) >= 1.2
    )

def _is_blocked(seq_feat: Dict[str, Any], prior_state: str) -> bool:
    hard_403 = _status_count(seq_feat, "403")
    return hard_403 >= 2 or (hard_403 >= 1 and prior_state in ("throttled", "challenged", "blocked_soft"))

# --- principal inference ------------------------------------------------

def infer_fsm(features: Dict[str, Any]) -> Dict[str, Any]:
    seqs: Dict[str, Dict[str, Any]] = features.get("seq", {})
    order = [name for name in seqs.keys() if name != "baseline"]

    state = "neutral"
    transitions: List[Transition] = []
    state_props: Dict[str, Dict[str, Any]] = {}
    signals: List[str] = []

    def transition(event: str, new_state: str):
        nonlocal state
        if state != new_state:
            transitions.append(Transition(event, state, new_state))
            state = new_state

    for name in order:
        feat = seqs[name]

        if state == "neutral":
            if _is_throttled(name, seqs):
                transition(name, "throttled")
            elif _is_challenged(name, feat):
                transition(name, "challenged")
            elif feat.get("lat_drift_ratio", 0.0) >= 1.3 and (
                feat.get("error_count", 0) > 0
                or feat.get("set_cookie_count", 0) > 0
                or _has_status(feat, "403")
            ):
                transition(name, "observed")

        elif state == "observed":
            if _is_throttled(name, seqs):
                transition(name, "throttled")
            elif _is_challenged(name, feat):
                transition(name, "challenged")

        elif state == "throttled":
            if _is_blocked(feat, state):
                transition(name, "blocked_soft")
            elif feat.get("lat_drift_ratio", 0.0) < 1.1:
                transition(name, "neutral")

        elif state == "challenged":
            if _is_blocked(feat, state):
                transition(name, "blocked_soft")

        elif state == "blocked_soft":
            if not _is_blocked(feat, state) and feat.get("lat_drift_ratio", 0.0) < 1.1:
                transition(name, "neutral")

    if state == "blocked_soft" and order:
        last = seqs[order[-1]]
        if _status_count(last, "403") >= 2:
            transition("terminal", "blocked_hard")

    # properties and derived signals
    if any(t.to_state in ("throttled", "challenged", "blocked_soft", "blocked_hard") for t in transitions):
        signals.append("stateful_edge_detected")

    if any(t.to_state == "throttled" for t in transitions):
        signals.append("adaptive_rate_limit_detected")

    if state == "blocked_hard":
        signals.append("non_recoverable_block")

    scope = "unknown"

    total_cookies = sum(seqs[n].get("set_cookie_count", 0) for n in order)

    if state == "challenged" and total_cookies >= 2:
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
