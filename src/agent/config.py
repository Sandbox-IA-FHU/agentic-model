"""Configuration du projet.

Seul module du dépôt qui lit `os.environ`. Partout ailleurs, la configuration
arrive en argument — c'est ce qui rend le reste testable sans clé d'API.
"""

import os
from dataclasses import dataclass

from agent.errors import ConfigError

VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
DEFAULT_LOG_LEVEL = "INFO"

# Politiques de validation des outils sensibles. Le défaut est le refus :
# une valeur par défaut permissive finit par être utilisée sans y penser.
APPROVAL_DENY = "refus"
APPROVAL_CONSOLE = "console"
VALID_APPROVAL_MODES = (APPROVAL_DENY, APPROVAL_CONSOLE)
DEFAULT_APPROVAL_MODE = APPROVAL_DENY


@dataclass(frozen=True)
class Config:
    """Configuration validée. Construite uniquement par `loadConfig`."""

    apiKey: str
    logLevel: str
    approvalMode: str


def loadConfig() -> Config:
    """Lit la configuration depuis l'environnement et la valide.

    Échoue immédiatement si elle est incomplète, avec un message qui dit quoi
    faire.
    """
    apiKey = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not apiKey:
        raise ConfigError(
            "ANTHROPIC_API_KEY est absente. Copier .env.exemple en .env, "
            "la renseigner, puis lancer avec : uv run --env-file .env ..."
        )

    logLevel = os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().upper()
    if logLevel not in VALID_LOG_LEVELS:
        raise ConfigError(
            f"LOG_LEVEL vaut {logLevel!r}, attendu l'un de {VALID_LOG_LEVELS}."
        )

    approvalMode = os.environ.get("APPROBATION", DEFAULT_APPROVAL_MODE).strip().lower()
    if approvalMode not in VALID_APPROVAL_MODES:
        raise ConfigError(
            f"APPROBATION vaut {approvalMode!r}, attendu l'un de "
            f"{VALID_APPROVAL_MODES}."
        )

    return Config(apiKey=apiKey, logLevel=logLevel, approvalMode=approvalMode)
