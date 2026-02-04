from dataclasses import dataclass
from typing import List, Dict, Optional
from .http import Req

@dataclass
class Step:
    method: str
    path: str
    headers: Dict[str, str]
    body: Optional[bytes] = None
    repeat: int = 1

@dataclass
class Probe:
    name: str
    steps: List[Step]

def build_probes() -> List[Probe]:
    return [
        Probe(
            name="baseline",
            steps=[Step("GET", "/", {"accept": "text/html"}, repeat=5)],
        ),
        Probe(
            name="state_cookies",
            steps=[
                Step("GET", "/", {"accept": "text/html"}, repeat=2),
                Step("GET", "/?a=", {"accept": "text/html"}, repeat=3),
            ],
        ),
        Probe(
            name="soft_burst",
            steps=[Step("GET", "/", {"accept": "text/html"}, repeat=10)],
        ),
        Probe(
            name="canonicalization",
            steps=[
                Step("GET", "/.", {"accept": "text/html"}, repeat=2),
                Step("GET", "//", {"accept": "text/html"}, repeat=2),
                Step("GET", "/?utm=", {"accept": "text/html"}, repeat=2),
            ],
        ),
    ]

def materialize(base_url: str, probe: Probe, base_headers: Dict[str, str]) -> List[Req]:
    out: List[Req] = []
    for s in probe.steps:
        for _ in range(s.repeat):
            h = dict(base_headers)
            h.update(s.headers)
            out.append(Req(s.method, base_url.rstrip("/") + s.path, h, s.body))
    return out