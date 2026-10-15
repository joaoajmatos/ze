"""Deterministic backstop for the resume loop offer (phase 171).

The recap asks the speaking agent to end with a keep-tracking question, but code
cannot make a model comply. When the reply still lacks a closing question, one
short line in the user's language is appended.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-záàâãéêíóôõúç]+", re.IGNORECASE)

_PT_MARKERS = frozenset(
    "o a os as um uma não nao tenho tens tem estou está estão são sou és você "
    "voce queres quero preciso ainda que é uns umas do da dos das no na nos nas "
    "em aberto coisas olá obrigado obrigada bom dia mas para com por meu minha "
    "meus minhas teu tua isso isto aqui hoje amanhã".split()
)
_EN_MARKERS = frozenset(
    "the a an is are am was i you my your me what whats do does have has on in "
    "of to and it that this for with still open anything hello thanks please "
    "not can will".split()
)

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


def _language(*texts: str) -> str:
    pt = en = 0
    for text in texts:
        for word in _WORD.findall(text.lower()):
            pt += word in _PT_MARKERS
            en += word in _EN_MARKERS
    return "pt" if pt > en else "en"


def with_loop_offer_line(reply: str, prompt: str, offer_ids: list[str]) -> str:
    """Append the offer question unless the reply already ends with a question."""
    if not offer_ids or not reply.strip():
        return reply
    if reply.rstrip(_TRAILING).endswith("?"):
        return reply
    line = _LINES[(_language(prompt, reply), len(offer_ids) > 1)]
    return f"{reply.rstrip()}\n\n{line}"
