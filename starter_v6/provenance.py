"""Local-only content fingerprints and runtime provenance for E04 runs."""
import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_sha256(paths):
    digest = hashlib.sha256()
    for path in sorted((Path(item) for item in paths), key=lambda item: str(item)):
        digest.update(str(path).encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def effective_config(config):
    """Return a JSON-compatible effective config without data paths or contents."""
    return {
        key: asdict(value) if is_dataclass(value) else value
        for key, value in config.items()
        if key != "data_dir"
    }


def config_sha256(config):
    run_controls = {"output", "diagnostics", "metadata"}
    model_config = {
        key: value for key, value in effective_config(config).items()
        if key not in run_controls
    }
    encoded = json.dumps(model_config, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def atomic_write_text(path, text):
    """Write a local report atomically so failed runs do not leave partial JSON."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
