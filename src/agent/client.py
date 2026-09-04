"""Accès au fournisseur de modèle.

Seul module qui connaît le SDK. La boucle ne manipule que le protocole
`AgentClient` — c'est ce qui permet aux tests de rejouer des scénarios
d'agent complets, avec plusieurs tours et des appels d'outils, sans réseau,
sans clé et sans facture.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

import anthropic

from agent.errors import ModelCallError
from agent.models import ToolCall, Usage

# Identifiant de modèle figé, jamais écrit en ligne dans le code appelant.
# Les identifiants Anthropic actuels ne portent pas de suffixe de date : la
# reproductibilité repose sur le fichier de run, qui consigne l'identifiant ET
# la date d'exécution. Voir CONVENTIONS-PYTHON.md § 5.
AGENT_MODEL = "claude-opus-5"

MAX_OUTPUT_TOKENS = 4096
REQUEST_TIMEOUT_SECONDS = 120.0
MAX_RETRIES = 2

STOP_END_TURN = "end_turn"
STOP_TOOL_USE = "tool_use"
STOP_MAX_TOKENS = "max_tokens"
STOP_REFUSAL = "refusal"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelTurn:
    """Un tour de modèle, réduit à ce dont la boucle a besoin.

    `assistantContent` est renvoyé tel quel dans l'historique du tour suivant.
    On ne le reconstruit pas : le contenu d'une réponse peut porter des blocs
    que la boucle n'a pas à comprendre, et les réécrire les casserait.
    """

    text: str
    toolCalls: tuple[ToolCall, ...]
    assistantContent: object
    usage: Usage
    stopReason: str


class AgentClient(Protocol):
    """Ce que la boucle attend d'un client. Rien de plus."""

    def respond(
        self,
        system: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> ModelTurn:
        """Un tour : consignes, historique, outils disponibles."""
        ...


class AnthropicAgentClient:
    """Implémentation réelle, au-dessus du SDK Anthropic."""

    def __init__(
        self,
        apiKey: str,
        model: str = AGENT_MODEL,
        maxOutputTokens: int = MAX_OUTPUT_TOKENS,
        timeoutSeconds: float = REQUEST_TIMEOUT_SECONDS,
        maxRetries: int = MAX_RETRIES,
    ) -> None:
        # Délai et réessais explicites. Le SDK réessaie déjà : on ne rajoute
        # jamais une boucle de réessai maison par-dessus, elles se multiplient.
        self._client = anthropic.Anthropic(
            api_key=apiKey,
            timeout=timeoutSeconds,
            max_retries=maxRetries,
        )
        self.model = model
        self.maxOutputTokens = maxOutputTokens

    def respond(
        self,
        system: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> ModelTurn:
        """Appelle le modèle et rend le tour normalisé."""
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.maxOutputTokens,
                system=system,
                tools=tools,
                messages=messages,
            )
        except anthropic.AuthenticationError as error:
            raise ModelCallError(
                "Authentification refusée. Vérifier ANTHROPIC_API_KEY."
            ) from error
        except anthropic.RateLimitError as error:
            raise ModelCallError(
                "Quota atteint chez le fournisseur. Réessayer plus tard."
            ) from error
        except anthropic.APIStatusError as error:
            raise ModelCallError(
                f"Appel modèle refusé (HTTP {error.status_code})."
            ) from error
        except anthropic.APIConnectionError as error:
            raise ModelCallError("Le fournisseur est injoignable.") from error

        text = "".join(block.text for block in response.content if block.type == "text")
        toolCalls = tuple(
            ToolCall(callId=block.id, toolName=block.name, arguments=dict(block.input))
            for block in response.content
            if block.type == "tool_use"
        )
        usage = Usage(
            inputTokens=response.usage.input_tokens,
            outputTokens=response.usage.output_tokens,
        )

        logger.info(
            "tour modele model=%s arret=%s outils=%d jetons_entree=%d jetons_sortie=%d",
            self.model,
            response.stop_reason,
            len(toolCalls),
            usage.inputTokens,
            usage.outputTokens,
        )

        return ModelTurn(
            text=text,
            toolCalls=toolCalls,
            assistantContent=response.content,
            usage=usage,
            stopReason=response.stop_reason or STOP_END_TURN,
        )
