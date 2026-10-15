"""Deterministic backstop for the resume loop offer (phase 171).

The recap asks the speaking agent to end with a keep-tracking question, but code
cannot make a model comply. When the reply still lacks a closing question, one
short line in the user's language is appended.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-záàâãéêíóôõúç]+", re.IGNORECASE)

_PT_MARKERS = frozenset(
    "o os as um uma não nao sim tenho tens tem estou está estão são sou és você "
    "voce queres quero preciso ainda que é uns umas do da dos das na nos nas "
    "em aberto coisas olá obrigado obrigada bom dia mas para com por meu minha "
    "meus minhas teu tua isso isto aqui hoje amanhã vou vamos ver já pois".split()
)
_EN_MARKERS = frozenset(
    "the an is are am was i you my your me what whats do does have has on in "
    "of to and it that this for with still open anything hello thanks please "
    "not can will yes yeah".split()
)
_HISTORY_MIN_WORDS = 4

_LINES = {
    (
        "en",
        False,
    ): "Also, I noticed something that may still be open. Want me to keep tracking it?",
    (
        "en",
        True,
    ): "Also, I noticed a few things that may still be open. Want me to keep tracking them?",
    (
        "pt",
        False,
    ): "Já agora, reparei numa coisa que pode ainda estar em aberto. Queres que continue a acompanhá-la?",
    (
        "pt",
        True,
    ): "Já agora, reparei em algumas coisas que podem ainda estar em aberto. Queres que continue a acompanhá-las?",
}

_TRAILING = " \t\r\n\"'”’)]*_`"


def _vote(text: str) -> str | None:
    pt = en = 0
    for word in _WORD.findall(text.lower()):
        pt += word in _PT_MARKERS
        en += word in _EN_MARKERS
    if pt == en:
        return None
    return "pt" if pt > en else "en"


def _language(prompt: str, reply: str, history: list[dict]) -> str:
    """Vote on this turn; a tie falls back to the user's latest longer message."""
    vote = _vote(f"{prompt} {reply}")
    if vote is not None:
        return vote
    for message in reversed(history):
        text = str(message.get("content") or "")
        if message.get("role") == "user" and len(text.split()) >= _HISTORY_MIN_WORDS:
            vote = _vote(text)
            if vote is not None:
                return vote
    return "en"


def with_loop_offer_line(
    reply: str,
    prompt: str,
    offer_ids: list[str],
    history: list[dict] | None = None,
) -> str:
    """Append the offer question unless the reply already ends with a question."""
    if not offer_ids or not reply.strip():
        return reply
    if reply.rstrip(_TRAILING).endswith("?"):
        return reply
    language = _language(prompt, reply, history or [])
    line = _LINES[(language, len(offer_ids) > 1)]
    return f"{reply.rstrip()}\n\n{line}"
