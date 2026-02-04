import argparse
import asyncio
import json
from .probes import build_probes, materialize
from .runner import run_all, RunCfg
from .features import extract
from .scoring import score

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--jitter-min", type=int, default=50)
    ap.add_argument("--jitter-max", type=int, default=150)
    ap.add_argument("--ua", default="wafprint/0.1")
    args = ap.parse_args()

    base_headers = {"user-agent": args.ua, "accept": "text/html"}
    probes = build_probes()

    seqs = {}
    for p in probes:
        seqs[p.name] = materialize(args.url, p, base_headers)

    cfg = RunCfg(args.timeout, args.concurrency, args.jitter_min, args.jitter_max)
    obs = asyncio.run(run_all(seqs, cfg))
    feats = extract(obs)
    sc = score(feats)

    out = {"target": args.url, "features": feats, "verdict": sc}
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()