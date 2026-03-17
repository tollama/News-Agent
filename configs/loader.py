"""Configuration loader and application bootstrap."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from agents.news_agent import NewsAgent
from connectors.factory import create_news_connector
from schemas.enums import NewsProvider

logger = logging.getLogger(__name__)


def load_config(path: str = "configs/default.yaml") -> dict[str, Any]:
    """Load configuration from a YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        logger.warning("Config file not found at %s, using defaults", path)
        return {}

    with config_path.open() as f:
        config: dict[str, Any] = yaml.safe_load(f) or {}

    logger.info("Loaded config from %s", path)
    return config


def bootstrap_agent(config: dict[str, Any]) -> NewsAgent:
    """Create a NewsAgent with connectors from config.

    Reads the ``providers`` section, creates connectors for enabled
    providers, and returns a wired ``NewsAgent``.
    """
    providers_cfg = config.get("providers", {})
    connectors = []

    for provider_name, pcfg in providers_cfg.items():
        if not pcfg.get("enabled", False):
            continue

        try:
            provider = NewsProvider(provider_name)
        except ValueError:
            logger.warning("Unknown provider '%s', skipping", provider_name)
            continue

        # Resolve API key from environment variable if configured
        connector_config: dict[str, Any] = dict(pcfg)
        api_key_env = connector_config.pop("api_key_env", None)
        if api_key_env:
            connector_config["api_key"] = os.environ.get(api_key_env, "")

        connector_config.pop("enabled", None)
        connector_config.pop("rate_limit_per_day", None)

        connector = create_news_connector(provider, connector_config)
        connectors.append(connector)
        logger.info("Created connector for %s", provider_name)

    agent = NewsAgent(connectors=connectors)
    logger.info("Bootstrapped NewsAgent with %d connector(s)", len(connectors))
    return agent


__all__ = ["bootstrap_agent", "load_config"]
