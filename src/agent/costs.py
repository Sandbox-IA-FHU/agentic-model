"""Conversion jetons → dollars.

Trois règles, toutes issues du même principe : un chiffre sans date est un
chiffre faux.

1. Les tarifs sont des constantes **datées**, dans ce module et nulle part
   ailleurs.
2. On compte en **dollars**, la devise de facturation du fournisseur. Convertir
   en euros demande un taux de change, qui est un deuxième chiffre à dater —
   la conversion se fait au moment du chiffrage, pas dans le code.
3. Le fichier de run consigne les jetons d'entrée et de sortie séparément. Un
   changement de tarif se recalcule alors sans relancer quoi que ce soit.
"""

from agent.errors import ModelCallError
from agent.models import Usage

# Tarifs en dollars par million de jetons, (entrée, sortie).
# Relevés le 2026-06-24 dans la table de référence Anthropic.
# À REVÉRIFIER avant tout chiffrage présenté à quelqu'un : ces valeurs bougent.
PRICES_USD_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
PRICES_DATE = "2026-06-24"

TOKENS_PER_MILLION = 1_000_000


def estimateCostUsd(usage: Usage, model: str) -> float:
    """Estime le coût d'un appel, en dollars.

    Échoue sur un modèle dont le tarif n'est pas connu, plutôt que de rendre
    zéro : un coût faussement nul passe inaperçu jusqu'à la facture.
    """
    if model not in PRICES_USD_PER_MILLION_TOKENS:
        raise ModelCallError(
            f"Aucun tarif connu pour {model!r}. Ajouter la ligne dans "
            f"costs.py avec sa date de relevé."
        )

    inputPrice, outputPrice = PRICES_USD_PER_MILLION_TOKENS[model]
    return (
        usage.inputTokens * inputPrice + usage.outputTokens * outputPrice
    ) / TOKENS_PER_MILLION
