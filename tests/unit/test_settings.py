import os

import pytest
from app.settings import (
    ProviderConfigurationError,
    VlmSettings,
)

ENVIRONMENT_NAMES = (
    "PV_VLM_BASE_URL",
    "PV_VLM_API_KEY",
    "PV_VLM_MODEL",
    "PV_VLM_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def clean_provider_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    for name in ENVIRONMENT_NAMES:
        monkeypatch.delenv(name, raising=False)

    yield

    for name in ENVIRONMENT_NAMES:
        os.environ.pop(name, None)


def test_reads_settings_from_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PV_VLM_BASE_URL",
        "https://api.example.com/v1/",
    )
    monkeypatch.setenv(
        "PV_VLM_API_KEY",
        "secret-test-key",
    )
    monkeypatch.setenv(
        "PV_VLM_MODEL",
        "example-vision-model",
    )
    monkeypatch.setenv(
        "PV_VLM_TIMEOUT_SECONDS",
        "45.5",
    )

    settings = VlmSettings.from_environment(
        env_file="missing.env"
    )

    assert settings.base_url == (
        "https://api.example.com/v1"
    )
    assert settings.api_key == "secret-test-key"
    assert settings.model == "example-vision-model"
    assert settings.timeout_seconds == 45.5
    assert "secret-test-key" not in repr(settings)


def test_reads_settings_from_dotenv_file(
    tmp_path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """PV_VLM_BASE_URL=https://api.example.com/v1
PV_VLM_API_KEY=dotenv-secret
PV_VLM_MODEL=dotenv-vision-model
PV_VLM_TIMEOUT_SECONDS=30
""",
        encoding="utf-8",
    )

    settings = VlmSettings.from_environment(
        env_file=env_file
    )

    assert settings.base_url == (
        "https://api.example.com/v1"
    )
    assert settings.api_key == "dotenv-secret"
    assert settings.model == "dotenv-vision-model"
    assert settings.timeout_seconds == 30.0


def test_process_environment_takes_priority_over_dotenv(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """PV_VLM_BASE_URL=https://file.example.com/v1
PV_VLM_API_KEY=file-secret
PV_VLM_MODEL=file-model
""",
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "PV_VLM_BASE_URL",
        "https://process.example.com/v1",
    )
    monkeypatch.setenv(
        "PV_VLM_API_KEY",
        "process-secret",
    )
    monkeypatch.setenv(
        "PV_VLM_MODEL",
        "process-model",
    )

    settings = VlmSettings.from_environment(
        env_file=env_file
    )

    assert settings.base_url == (
        "https://process.example.com/v1"
    )
    assert settings.api_key == "process-secret"
    assert settings.model == "process-model"


def test_rejects_missing_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PV_VLM_BASE_URL",
        "https://api.example.com/v1",
    )
    monkeypatch.setenv(
        "PV_VLM_MODEL",
        "example-model",
    )

    with pytest.raises(
        ProviderConfigurationError,
        match="PV_VLM_API_KEY is not configured",
    ):
        VlmSettings.from_environment(
            env_file="missing.env"
        )


@pytest.mark.parametrize(
    "value",
    ["invalid", "0", "-1"],
)
def test_rejects_invalid_timeout(
    value: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PV_VLM_BASE_URL",
        "https://api.example.com/v1",
    )
    monkeypatch.setenv(
        "PV_VLM_API_KEY",
        "secret",
    )
    monkeypatch.setenv(
        "PV_VLM_MODEL",
        "example-model",
    )
    monkeypatch.setenv(
        "PV_VLM_TIMEOUT_SECONDS",
        value,
    )

    with pytest.raises(ProviderConfigurationError):
        VlmSettings.from_environment(
            env_file="missing.env"
        )


def test_rejects_invalid_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PV_VLM_BASE_URL",
        "not-a-url",
    )
    monkeypatch.setenv(
        "PV_VLM_API_KEY",
        "secret",
    )
    monkeypatch.setenv(
        "PV_VLM_MODEL",
        "example-model",
    )

    with pytest.raises(
        ProviderConfigurationError,
        match=(
            r"PV_VLM_BASE_URL must be "
            r"a valid HTTP\(S\) URL"
        ),
    ):
        VlmSettings.from_environment(
            env_file="missing.env"
        )
