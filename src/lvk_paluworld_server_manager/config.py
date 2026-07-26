"""Application configuration and shared helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the application."""

    title: str = "LVK Palworld Server Manager"


def create_app_message(config: AppConfig | None = None) -> str:
    """Build the ready-state message shown in the UI."""
    app_config = config or AppConfig()
    return f"{app_config.title} is ready."
