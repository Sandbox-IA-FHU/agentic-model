"""Tests de la configuration."""

import pytest

from agent.config import APPROVAL_DENY, loadConfig
from agent.errors import ConfigError


def setValidKey(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pose une clé de test et efface le reste."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("APPROBATION", raising=False)


def test_missingApiKeyFailsImmediately(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        loadConfig()


def test_invalidLogLevelIsRefused(monkeypatch: pytest.MonkeyPatch) -> None:
    setValidKey(monkeypatch)
    monkeypatch.setenv("LOG_LEVEL", "BAVARD")

    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        loadConfig()


def test_invalidApprovalModeIsRefused(monkeypatch: pytest.MonkeyPatch) -> None:
    setValidKey(monkeypatch)
    monkeypatch.setenv("APPROBATION", "toujours")

    with pytest.raises(ConfigError, match="APPROBATION"):
        loadConfig()


def test_approvalDefaultsToRefusal(monkeypatch: pytest.MonkeyPatch) -> None:
    # Une valeur par défaut permissive finit par être utilisée sans y penser.
    setValidKey(monkeypatch)

    assert loadConfig().approvalMode == APPROVAL_DENY
