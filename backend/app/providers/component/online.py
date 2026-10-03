"""Find manufacturer documents for manual component-profile verification."""

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.providers.common import ProviderError

_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 /_.+-]{1,99}$")
_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


@dataclass(frozen=True)
class ManufacturerDocument:
    title: str
    url: str
    description: str


class ManufacturerDocumentFinder:
    """Search approved manufacturer domains; results are leads, not verified specs."""

    def __init__(
        self,
        api_key: str,
        *,
        manufacturer_domain: str = "jasolar.com",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        domain = manufacturer_domain.strip().lower()
        if not domain or not re.fullmatch(r"[a-z0-9.-]+", domain):
            raise ValueError("invalid manufacturer domain")
        if not api_key.strip():
            raise ValueError("search API key is required")
        self.api_key = api_key
        self.domain = domain
        self.transport = transport

    def search(self, model: str) -> list[ManufacturerDocument]:
        if not _MODEL_PATTERN.fullmatch(model.strip()):
            raise ValueError("invalid component model")
        query = f'site:{self.domain} "{model.strip()}" photovoltaic datasheet'
        try:
            with httpx.Client(timeout=15.0, transport=self.transport) as client:
                response = client.get(
                    _SEARCH_URL,
                    params={"q": query, "count": 10},
                    headers={"X-Subscription-Token": self.api_key},
                )
                response.raise_for_status()
                results = response.json().get("web", {}).get("results", [])
        except (httpx.HTTPError, ValueError, AttributeError, TypeError) as exc:
            raise ProviderError("manufacturer document search failed") from exc

        documents: list[ManufacturerDocument] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str):
                continue
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or not (
                host == self.domain or host.endswith("." + self.domain)
            ):
                continue
            documents.append(
                ManufacturerDocument(
                    title=str(item.get("title") or "")[:300],
                    url=url,
                    description=str(item.get("description") or "")[:600],
                )
            )
        return documents
