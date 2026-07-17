from pathlib import Path

from app.utils.model_discovery import discover_local_models


def test_discovers_project_openvino_and_marks_active(tmp_path, monkeypatch):
    project = tmp_path / "project"
    model = project / "models" / "Qwen-7B"
    model.mkdir(parents=True)
    (model / "openvino_model.xml").write_text("<xml/>", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

    discovered = discover_local_models(project, str(model))

    assert len(discovered) == 1
    assert discovered[0]["name"] == "Qwen-7B"
    assert discovered[0]["format"] == "OpenVINO"
    assert discovered[0]["active"] is True


def test_discovers_huggingface_cache_names(tmp_path, monkeypatch):
    project = tmp_path / "project"
    cache_model = tmp_path / "home" / ".cache" / "huggingface" / "hub" / "models--Qwen--Qwen2.5-7B"
    cache_model.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

    discovered = discover_local_models(project, str(project / "missing"))

    assert discovered[0]["name"] == "Qwen/Qwen2.5-7B"
    assert discovered[0]["source"] == "Hugging Face"
    assert discovered[0]["active"] is False
