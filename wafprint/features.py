from typing import Dict, List, Any
import statistics
from .http import Obs

def _lat_stats(xs: List[float]) -> Dict[str, float]:
    if not xs:
        return {"mean": 0.0, "std": 0.0}
    if len(xs) == 1:
        return {"mean": xs[0], "std": 0.0}
    return {"mean": statistics.mean(xs), "std": statistics.pstdev(xs)}

def extract(observations: Dict[str, List[Obs]]) -> Dict[str, Any]:
    feats: Dict[str, Any] = {"seq": {}}
    baseline = observations.get("baseline", [])
    base_lat = [o.total_ms for o in baseline if o.error is None]
    base_stats = _lat_stats(base_lat)
    feats["baseline"] = base_stats

    for name, obs in observations.items():
        lats = [o.total_ms for o in obs if o.error is None]
        stats = _lat_stats(lats)
        statuses: Dict[int, int] = {}
        resets = 0
        setc = 0
        body_hashes = set()
        hdr_sets = set()
        for o in obs:
            if o.error is not None:
                resets += 1
            statuses[o.status] = statuses.get(o.status, 0) + 1
            if o.set_cookie:
                setc += 1
            if o.body_hash16:
                body_hashes.add(o.body_hash16)
            for hk in o.headers.keys():
                hdr_sets.add(hk)

        drift = 0.0
        if base_stats["mean"] > 0.0:
            drift = stats["mean"] / base_stats["mean"]

        feats["seq"][name] = {
            "lat_mean": stats["mean"],
            "lat_std": stats["std"],
            "lat_drift_ratio": drift,
            "status_hist": {str(k): v for k, v in statuses.items()},
            "error_count": resets,
            "set_cookie_count": setc,
            "unique_body_hashes": len(body_hashes),
            "unique_header_keys": len(hdr_sets),
        }
    return feats