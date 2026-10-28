"""Small, dependency-free reproducibility helpers for Solution 01's foundation."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import random
from pathlib import Path
from typing import Iterable, Mapping, Optional


DEFAULT_SEED = 1729


def set_random_seed(seed: int = DEFAULT_SEED) -> None:
    """Set deterministic seeds for Python and NumPy when NumPy is installed."""
    random.seed(seed)
    try:
        import numpy as np  # type: ignore
    except ImportError:
        return
    np.random.seed(seed)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return a streamed SHA256 digest without loading the file into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_version(name: str) -> Optional[str]:
    """Return an installed package version, or None when the package is absent."""
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def experiment_metadata(
    input_ids: Iterable[str],
    seed: int = DEFAULT_SEED,
    input_sha256: Optional[Mapping[str, str]] = None,
) -> dict:
    """Build metadata from logical identifiers, versions, seed, and optional digests.

    Callers should use logical identifiers (for example ``synthetic.fixture``), never absolute
    paths or restricted per-frame content, in metadata intended to be retained or shared.
    """
    return {
        "schema_version": 1,
        "approach_id": "solution01",
        "random_seed": int(seed),
        "runtime": {
            "python": platform.python_version(),
            "numpy": package_version("numpy"),
            "pandas": package_version("pandas"),
        },
        "input_ids": sorted(input_ids),
        "input_sha256": dict(sorted((input_sha256 or {}).items())),
    }


def write_metadata(path: Path, metadata: Mapping[str, object]) -> None:
    """Write stable, UTF-8 JSON with a trailing newline."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
