"""Project-level compatibility wrapper for application configuration.

The app instantiates configuration from ``app.config.Config``. Keeping a
project-level ``Config`` re-export avoids import failures for scripts that
expect a top-level configuration module.
"""

from app.config import Config

__all__ = ["Config"]
