from typing import Dict, Any, List, Tuple

def score(features: Dict[str, Any]) -> Dict[str, Any]:
    seq = features.get("seq", {})
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
    if uniq_hash_can >= 2:
        s += 0.6
        signals.append("interstitial_or_rewrite_suspected")

    family = "unknown"
    if "rate_limit_429" in signals:
        family = "rate_limit_focused"
    elif "cookie_activity_high" in signals and "interstitial_or_rewrite_suspected" in signals:
        family = "challenge_based_edge"
    elif "block_on_behavior_change" in signals:
        family = "policy_blocking"

    return {"score": s, "signals": signals, "family": family}
