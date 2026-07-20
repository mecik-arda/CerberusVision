import json

from app import config


def test_persistent_settings_store_preferences_without_api_keys(tmp_path, monkeypatch):
    settings_path = tmp_path / ".cerberus-settings.json"
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_path)
    monkeypatch.setattr(config.settings.interface, "theme", "dark")
    monkeypatch.setattr(config.settings.interface, "interface_language", "en")
    monkeypatch.setattr(config.settings.interface, "document_language", "auto")
    monkeypatch.setattr(config.settings.interface, "output_language", "tr")
    monkeypatch.setattr(config.settings.interface, "translation_enabled", False)
    monkeypatch.setattr(config.settings.deepseek, "api_key", "secret")

    config.save_persistent_settings()
    payload = json.loads(settings_path.read_text(encoding="utf-8"))

    assert payload["interface"] == {
        "theme": "dark",
        "interface_language": "en",
        "document_language": "auto",
        "output_language": "tr",
        "translation_enabled": False,
    }
    assert "api_key" not in json.dumps(payload)
