from dataclasses import dataclass
from typing import Dict, Optional
import time
import httpx
import hashlib

@dataclass
class Req:
    method: str
    url: str
    headers: Dict[str, str]
    body: Optional[bytes] = None

@dataclass
class Obs:
    url: str
    method: str
    status: int
    ttfb_ms: float
    total_ms: float
    headers: Dict[str, str]
    set_cookie: str
    body_len: int
    body_hash16: str
    error: Optional[str] = None

async def send(client: httpx.AsyncClient, req: Req) -> Obs:
    t0 = time.perf_counter()
    try:
        r = await client.request(req.method, req.url, headers=req.headers, content=req.body)
        t1 = time.perf_counter()
        b = r.content or b""
        h = hashlib.sha256(b[:4096]).hexdigest()[:16]
        sc = r.headers.get("set-cookie", "")
        return Obs(
            url=req.url,
            method=req.method,
            status=r.status_code,
            ttfb_ms=(t1 - t0) * 1000.0,
            total_ms=(t1 - t0) * 1000.0,
            headers={k.lower(): v for k, v in r.headers.items()},
            set_cookie=sc,
            body_len=len(b),
            body_hash16=h,
        )
    except Exception as e:
        t1 = time.perf_counter()
        return Obs(
            url=req.url,
            method=req.method,
            status=0,
            ttfb_ms=(t1 - t0) * 1000.0,
            total_ms=(t1 - t0) * 1000.0,
            headers={},
            set_cookie="",
            body_len=0,
            body_hash16="",
            error=str(e),
        )