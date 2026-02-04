from typing import Dict, Any

def build_report(target: str, features: Dict[str, Any], fsm: Dict[str, Any], verdict: Dict[str, Any]) -> Dict[str, Any]:
    summary = {
        "final_state": fsm.get("final_state"),
        "scope": None,
        "signals": verdict.get("signals", []),
        "score": verdict.get("score"),
        "family": verdict.get("family"),
    }

    state_props = fsm.get("state_properties", {})
    fs = fsm.get("final_state")
    if fs in state_props:
        summary["scope"] = state_props[fs].get("scope")

    return {
        "target": target,
        "summary": summary,
        "edge_fsm": fsm,
        "features": features,
    }