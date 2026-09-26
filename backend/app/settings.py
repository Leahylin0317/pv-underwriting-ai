import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self
from urllib.parse import urlparse

from dotenv import load_dotenv


class ProviderConfigurationError(ValueError):
    """外部模型 Provider 配置不完整或不合法。"""


def _required_environment_value(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise ProviderConfigurationError(
            f"{name} is not configured"
        )

    return value


def _positive_float_environment_value(
    name: str,
    default: str,
) -> float:
    raw_value = os.getenv(name, default).strip()

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ProviderConfigurationError(
            f"{name} must be a number"
        ) from exc

    if value <= 0:
        raise ProviderConfigurationError(
            f"{name} must be greater than zero"
        )

    return value


def _validate_http_url(name: str, value: str) -> str:
    parsed = urlparse(value)

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
    ):
        raise ProviderConfigurationError(
            f"{name} must be a valid HTTP(S) URL"
        )

    return value.rstrip("/")


@dataclass(frozen=True, slots=True)
class VlmSettings:
    """多模态视觉模型 Provider 的运行配置。"""

    base_url: str
    api_key: str = field(repr=False)
    model: str
    timeout_seconds: float = 60.0

    @classmethod
    def from_environment(
        cls,
        env_file: str | Path = ".env",
    ) -> Self:
        """从进程环境和本地 .env 文件读取配置。"""

        load_dotenv(
            dotenv_path=env_file,
            override=False,
        )

        base_url = _validate_http_url(
            "PV_VLM_BASE_URL",
            _required_environment_value(
                "PV_VLM_BASE_URL"
            ),
        )

        return cls(
            base_url=base_url,
            api_key=_required_environment_value(
                "PV_VLM_API_KEY"
            ),
            model=_required_environment_value(
                "PV_VLM_MODEL"
            ),
            timeout_seconds=(
                _positive_float_environment_value(
                    "PV_VLM_TIMEOUT_SECONDS",
                    "60",
                )
            ),
        )
