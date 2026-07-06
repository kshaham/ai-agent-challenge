"""The request hash must be identical across processes and hash seeds.

If it isn't, recorded fixtures miss on a fresh clone (FixtureMissingError). This
guards the invariant by hashing the same transcript in two subprocesses started
with different PYTHONHASHSEED values.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_SNIPPET = (
    "from app.model.base import ModelMessage;"
    "from app.model.hashing import canonical_request_key;"
    "msgs=[ModelMessage(role='system', content='S'),"
    "ModelMessage(role='user', content='the quick brown fox')];"
    "print(canonical_request_key(msgs))"
)


def _hash_with_seed(seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    out = subprocess.check_output(
        [sys.executable, "-c", _SNIPPET], env=env, cwd=str(ROOT)
    )
    return out.decode().strip()


def test_request_hash_is_stable_across_hash_seeds():
    assert _hash_with_seed("0") == _hash_with_seed("13") == _hash_with_seed("98765")
