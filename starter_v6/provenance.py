"""Local-only content fingerprints and runtime provenance for E04 runs."""
import hashlib
import importlib.metadata
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_manifest(paths, root=None):
    """Return stable, sorted source names for files executed by this run."""
    root = Path(root).resolve() if root is not None else None
    names = []
    for item in paths:
        path = Path(item).resolve()
        names.append(str(path.relative_to(root) if root is not None else path))
    return sorted(set(names))


def source_sha256(paths, root=None):
    digest = hashlib.sha256()
    root = Path(root).resolve() if root is not None else None
    for path in sorted((Path(item).resolve() for item in paths), key=lambda item: str(item)):
        name = path.relative_to(root) if root is not None else path
        digest.update(str(name).encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def runtime_source_files(project_root):
    """Find project Python files actually loaded by the current interpreter."""
    root = Path(project_root).resolve()
    files = set()
    for module in tuple(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if not path or not str(path).endswith(".py"):
            continue
        candidate = Path(path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if not {"__pycache__", ".venv", "venv"}.intersection(candidate.parts) and candidate.is_file():
            files.add(candidate)
    if not files:
        raise ValueError("no project source files were loaded")
    return sorted(files, key=lambda item: str(item))


def dependency_manifest():
    """Record versions for loaded third-party top-level modules."""
    distributions = importlib.metadata.packages_distributions()
    result = {}
    for module_name in sys.modules:
        top_level = module_name.split(".", 1)[0]
        for distribution in distributions.get(top_level, ()):
            try:
                result[distribution] = importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError:
                continue
    return dict(sorted(result.items()))


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
