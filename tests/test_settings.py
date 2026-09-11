"""Tests for settings."""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from omnivoice_api.settings import Settings, get_settings


class TestSettingsDefaults:
    """Tests for default settings values."""

    def test_app_name(self) -> None:
        settings = Settings()
        assert settings.APP_NAME == "OmniVoice API"

    def test_app_version(self) -> None:
        settings = Settings()
        assert settings.APP_VERSION == "0.1.0"

    def test_debug_default(self) -> None:
        settings = Settings()
        assert settings.DEBUG is False

    def test_api_prefix(self) -> None:
        settings = Settings()
        assert settings.API_PREFIX == "/api/v1"

    def test_omnivoice_device(self) -> None:
        settings = Settings()
        assert settings.OMNIVOICE_DEVICE == "cuda:0"

    def test_omnivoice_dtype(self) -> None:
        settings = Settings()
        assert settings.OMNIVOICE_DTYPE == "float16"

    def test_database_url(self) -> None:
        settings = Settings()
        assert "sqlite" in settings.DATABASE_URL

    def test_api_key_default_empty(self) -> None:
        settings = Settings()
        assert settings.API_KEY == ""

    def test_log_level_default(self) -> None:
        settings = Settings()
        assert settings.LOG_LEVEL == "INFO"

    def test_log_format_default(self) -> None:
        settings = Settings()
        assert settings.LOG_FORMAT == "json"

    def test_cors_origins_default(self) -> None:
        settings = Settings()
        assert settings.CORS_ORIGINS == "*"


class TestSettingsProperties:
    """Tests for computed properties."""

    def test_cors_origins_list_single(self) -> None:
        settings = Settings(CORS_ORIGINS="http://localhost:3000")
        assert settings.cors_origins_list == ["http://localhost:3000"]

    def test_cors_origins_list_multiple(self) -> None:
        settings = Settings(CORS_ORIGINS="http://a.com, http://b.com")
        assert settings.cors_origins_list == ["http://a.com", "http://b.com"]

    def test_cors_origins_list_wildcard(self) -> None:
        settings = Settings(CORS_ORIGINS="*")
        assert settings.cors_origins_list == ["*"]

    def test_cors_origins_list_strips_whitespace(self) -> None:
        settings = Settings(CORS_ORIGINS="  http://a.com ,  http://b.com  ")
        assert settings.cors_origins_list == ["http://a.com", "http://b.com"]

    def test_omnilang_list(self) -> None:
        settings = Settings()
        langs = settings.omnilang_list
        assert "es" in langs
        assert "en" in langs
        assert "zh" in langs
        assert len(langs) == 9


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_invalid_log_level(self) -> None:
        with pytest.raises(ValidationError):
            Settings(LOG_LEVEL="INVALID")

    def test_invalid_log_format(self) -> None:
        with pytest.raises(ValidationError):
            Settings(LOG_FORMAT="xml")

    def test_invalid_omnivoice_dtype(self) -> None:
        with pytest.raises(ValidationError):
            Settings(OMNIVOICE_DTYPE="bfloat16")


class TestGetSettings:
    """Tests for get_settings function."""

    def test_returns_settings_instance(self) -> None:
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_returns_new_instance_each_call(self) -> None:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is not s2
