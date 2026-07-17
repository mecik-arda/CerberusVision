from __future__ import annotations

from pathlib import Path


_MODEL_MARKERS = {
    "openvino_model.xml": "OpenVINO",
    "config.json": "Transformers",
    "model_index.json": "Diffusers",
}


def _resolved(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _directory_format(path: Path) -> str | None:
    for marker, model_format in _MODEL_MARKERS.items():
        if (path / marker).is_file():
            return model_format
    if any(path.glob("*.gguf")):
        return "GGUF"
    return None


def _scan_model_directory(root: Path, source: str, max_depth: int = 2) -> list[dict]:
    if not root.is_dir():
        return []
    models: list[dict] = []
    pending = [(root, 0)]
    while pending:
        path, depth = pending.pop()
        model_format = _directory_format(path)
        if model_format:
            models.append({
                "name": path.name,
                "path": _resolved(path),
                "source": source,
                "format": model_format,
            })
            continue
        if depth >= max_depth:
            continue
        try:
            children = [child for child in path.iterdir() if child.is_dir()]
        except OSError:
            continue
        pending.extend((child, depth + 1) for child in children[:200])
    return models


def _scan_huggingface_cache(root: Path) -> list[dict]:
    if not root.is_dir():
        return []
    models = []
    try:
        entries = list(root.glob("models--*"))
    except OSError:
        return []
    for path in entries[:200]:
        if not path.is_dir():
            continue
        name = path.name.removeprefix("models--").replace("--", "/")
        models.append({
            "name": name,
            "path": _resolved(path),
            "source": "Hugging Face",
            "format": "Cache",
        })
    return models


def _scan_ollama_manifests(root: Path) -> list[dict]:
    if not root.is_dir():
        return []
    models = []
    try:
        manifests = [path for path in root.glob("*/*/*") if path.is_file()]
    except OSError:
        return []
    for path in manifests[:200]:
        relative = path.relative_to(root)
        models.append({
            "name": ":".join((relative.parts[-2], relative.parts[-1])),
            "path": _resolved(path),
            "source": "Ollama",
            "format": "Manifest",
        })
    return models


def discover_local_models(base_dir: Path, active_model_path: str) -> list[dict]:
    user_home = Path.home()
    candidates = []
    candidates.extend(_scan_model_directory(base_dir / "models", "CerberusVision", 2))
    candidates.extend(_scan_model_directory(user_home / "models", "WSL Home", 2))
    candidates.extend(_scan_huggingface_cache(user_home / ".cache" / "huggingface" / "hub"))
    candidates.extend(_scan_ollama_manifests(
        user_home / ".ollama" / "models" / "manifests" / "registry.ollama.ai"
    ))
    active_path = _resolved(Path(active_model_path))
    unique: dict[str, dict] = {}
    for candidate in candidates:
        candidate["active"] = candidate["path"] == active_path
        unique[candidate["path"]] = candidate
    if active_path not in unique and Path(active_model_path).exists():
        active = Path(active_model_path)
        unique[active_path] = {
            "name": active.name,
            "path": active_path,
            "source": "Configured",
            "format": _directory_format(active) or "Unknown",
            "active": True,
        }
    return sorted(
        unique.values(),
        key=lambda item: (not item["active"], item["source"].casefold(), item["name"].casefold()),
    )
