"""Command-line entry point for launching the GUI application."""

from __future__ import annotations

from .gui import main as start_app


def main() -> None:
    """Launch the application."""
    start_app()


if __name__ == "__main__":
    main()
