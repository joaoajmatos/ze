from __future__ import annotations

import hashlib


def article_ref_id(url: str) -> str:
    """Screen-ref id of an article: hex md5 of its UTF-8 url (32 chars, under the 64-char ref cap).

    Not a security use. `NewsStore.get_by_ref` resolves it with `md5(url)` in SQL, so the two agree;
    every emitter of a `news_article` ScreenRef must build its id here.
    """
    return hashlib.md5(url.encode("utf-8"), usedforsecurity=False).hexdigest()
