"""Tests du calcul de coût."""

import pytest

from agent.costs import PRICES_USD_PER_MILLION_TOKENS, estimateCostUsd
from agent.errors import ModelCallError
from agent.models import Usage


def test_costIsProportionalToTokens() -> None:
    inputPrice, outputPrice = PRICES_USD_PER_MILLION_TOKENS["claude-opus-5"]
    usage = Usage(inputTokens=1_000_000, outputTokens=1_000_000)

    cost = estimateCostUsd(usage, "claude-opus-5")

    assert cost == pytest.approx(inputPrice + outputPrice)


def test_inputAndOutputArePricedSeparately() -> None:
    # Compter les deux ensemble sous-estime le coût d'un système bavard :
    # la sortie est plusieurs fois plus chère que l'entrée.
    onlyInput = estimateCostUsd(Usage(1_000, 0), "claude-opus-5")
    onlyOutput = estimateCostUsd(Usage(0, 1_000), "claude-opus-5")

    assert onlyOutput > onlyInput


def test_emptyUsageCostsNothing() -> None:
    assert estimateCostUsd(Usage(0, 0), "claude-opus-5") == 0.0


def test_unknownModelFailsInsteadOfReturningZero() -> None:
    # Un coût faussement nul passe inaperçu jusqu'à la facture.
    with pytest.raises(ModelCallError):
        estimateCostUsd(Usage(100, 100), "modele-inconnu")
