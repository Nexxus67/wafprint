from dataclasses import dataclass
from typing import Dict, List
import asyncio
import random
import httpx
from .http import Req, Obs, send

@dataclass
class RunCfg:
    timeout_s: float
    concurrency: int
    jitter_ms_min: int
    jitter_ms_max: int

async def run_sequence(reqs: List[Req], cfg: RunCfg) -> List[Obs]:
    limits = httpx.Limits(max_connections=cfg.concurrency, max_keepalive_connections=cfg.concurrency)
    timeout = httpx.Timeout(cfg.timeout_s)
    async with httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=False) as client:
        obs: List[Obs] = []
        i = 0
        while i < len(reqs):
            r = reqs[i]
            j = random.randint(cfg.jitter_ms_min, cfg.jitter_ms_max)
            if j > 0:
                await asyncio.sleep(j / 1000.0)

            if r.burst_group:
                batch = [r]
                i += 1
                while i < len(reqs) and reqs[i].burst_group == r.burst_group:
                    batch.append(reqs[i])
                    i += 1
                obs.extend(await asyncio.gather(*(send(client, item) for item in batch)))
                continue

            obs.append(await send(client, r))
            i += 1
        return obs

async def run_all(seqs: Dict[str, List[Req]], cfg: RunCfg) -> Dict[str, List[Obs]]:
    out: Dict[str, List[Obs]] = {}
    for name, reqs in seqs.items():
        out[name] = await run_sequence(reqs, cfg)
    return out
