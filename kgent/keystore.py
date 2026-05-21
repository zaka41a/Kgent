"""Optional on-disk persistence for LLM API keys.

By default kgent keeps API keys in the browser (localStorage) and forwards them
on each request via the X-Kgent-Keys header. The server never writes them.

When the user sets `KGENT_PERSIST_KEYS=1`, the server also caches the keys in
`.kgent_store/keys.json` so the CLI (and the startup auto-build) can use them.
The file is created with mode 0600.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

KEYS_FILENAME = "keys.json"
TRACKED_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY")


def keys_path_for(store_path: Path) -> Path:
    return Path(store_path).parent / KEYS_FILENAME


def load_keys(store_path: Path) -> dict[str, str]:
    target = keys_path_for(store_path)
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: str(v) for k, v in data.items() if isinstance(v, str) and v}


def save_keys(store_path: Path, keys: dict[str, str]) -> Path:
    target = keys_path_for(store_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    filtered = {k: v for k, v in keys.items() if k in TRACKED_KEYS and v}
    target.write_text(json.dumps(filtered), encoding="utf-8")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def merge_request_keys(
    store_path: Path,
    request_keys: dict[str, str],
    persist: bool,
) -> dict[str, str]:
    """Combine on-disk keys with the ones sent by the browser for this request.

    Browser-sent keys always win (they are the most recent edit). When `persist`
    is true and the user provided new values, they are also written to disk.
    """
    disk = load_keys(store_path)
    merged = {**disk, **request_keys}
    if persist and request_keys:
        save_keys(store_path, merged)
    return merged
