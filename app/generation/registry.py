from __future__ import annotations

from collections.abc import Iterable

from app.generation.base import MediaGeneratorProvider
from app.generation.errors import ProviderUnavailableError


class ProviderRegistry:
    def __init__(self, providers: Iterable[MediaGeneratorProvider] | None = None) -> None:
        self._providers: dict[str, MediaGeneratorProvider] = {}
        for provider in providers or ():
            self.register(provider)

    def register(self, provider: MediaGeneratorProvider) -> None:
        provider_id = provider.provider_id.strip()
        if not provider_id:
            raise ValueError("Il provider deve dichiarare un provider_id.")
        self._providers[provider_id] = provider

    def get(self, provider_id: str) -> MediaGeneratorProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise ProviderUnavailableError(
                f"Provider non registrato: {provider_id}"
            ) from exc

    def list(self) -> list[MediaGeneratorProvider]:
        return [self._providers[key] for key in sorted(self._providers)]
