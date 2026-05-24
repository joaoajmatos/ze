import httpx

from ze.browser.types import BrowserResult
from ze.errors import BrowserError
from ze.logging import get_logger

log = get_logger(__name__)


class BrowserClient:
    def __init__(self, base_url: str, timeout: int = 20) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def extract(self, url: str) -> BrowserResult:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/extract",
                    json={"url": url},
                )
        except httpx.TimeoutException as exc:
            raise BrowserError(f"Browser service timed out: {exc}") from exc
        except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            raise BrowserError(f"Cannot reach browser service: {exc}") from exc

        if resp.status_code >= 500:
            raise BrowserError(
                f"Browser service error {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()
        return BrowserResult(
            url=data["url"],
            title=data.get("title", ""),
            text=data.get("text", ""),
            status_code=data.get("status_code", resp.status_code),
        )

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/health")
            return resp.status_code == 200
        except Exception:
            return False
