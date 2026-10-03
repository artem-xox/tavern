"""HTTP transport of the card compiler: a player's card in, params proposed for confirmation out."""

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from tavern.card_compiler import RejectedParams, compile_card, offline_card
from tavern.cards import parse_card_text
from tavern.claude import ClaudeError
from tavern.questions import Ask


def card_routes(ask: Ask | None) -> APIRouter:
    """Serve `POST /api/cards/compile`.

    Args:
        ask: The model port, bound to the server's own key; None runs the labeled offline mode.
            A client never supplies a key: unknown body fields are refused.
    Returns:
        Router answering a valid card (see `cards.parse_card_text`) with a `CompiledCard`;
        422 for an invalid card, 502 when the model fails or its params are rejected.
    """
    router = APIRouter()

    @router.post("/api/cards/compile")
    async def compile_route(body: Any = Body(...)) -> dict[str, Any]:
        try:
            text = parse_card_text(body)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if ask is None:
            return dict(offline_card(text))
        try:
            return dict(await compile_card(text, ask))
        except (ClaudeError, RejectedParams) as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
    return router
