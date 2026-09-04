"""Tests du registre d'outils."""

import pytest

from agent.errors import UnknownToolError
from agent.models import ToolSpec
from agent.tools import ToolRegistry

SCHEMA = {"type": "object", "properties": {}, "required": []}


def buildSpec(name: str, sensitive: bool = False) -> ToolSpec:
    """Outil minimal pour les tests."""
    return ToolSpec(
        name=name,
        description="Outil de test.",
        inputSchema=SCHEMA,
        handler=lambda arguments: "ok",
        isSensitive=sensitive,
    )


def test_registryExposesSchemas(registry: ToolRegistry) -> None:
    schemas = registry.schemas()
    names = [schema["name"] for schema in schemas]

    assert names == registry.names()
    assert all("input_schema" in schema for schema in schemas)
    # Le schéma envoyé au modèle et la fonction exécutée viennent du même
    # objet : c'est ce qui les empêche de diverger.
    assert all("description" in schema for schema in schemas)


def test_sensitiveToolsAreListed(registry: ToolRegistry) -> None:
    assert registry.sensitiveNames() == ["deleteNote"]


def test_unknownToolIsNamedInTheError(registry: ToolRegistry) -> None:
    with pytest.raises(UnknownToolError, match="sendEmail"):
        registry.get("sendEmail")


def test_duplicateToolsAreRefused() -> None:
    with pytest.raises(ValueError, match="double"):
        ToolRegistry([buildSpec("listNotes"), buildSpec("listNotes")])


def test_sensitiveToolDescriptionWarnsTheModel(registry: ToolRegistry) -> None:
    # Le modèle doit pouvoir tenir compte du caractère irréversible AVANT de
    # demander l'action, pas seulement après un refus.
    description = registry.get("deleteNote").description.lower()

    assert "irréversible" in description
    assert "validation" in description
