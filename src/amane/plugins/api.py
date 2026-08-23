"""Host-side film-source plugin contract.

Plugin authors should import these types from ``amane.plugin``, not this module.
The first API version exposes only the film metadata boundary: a plugin receives
the shared HTTP clients and returns an object implementing ``fetch``; it does not
receive the repository, task worker, or FastAPI application.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, ConfigDict

from .models import PluginConfig, SourceDescriptor

if TYPE_CHECKING:
    from ..crawlers.http import HttpClient
    from ..crawlers.models import FetchOptions, MediaMetadata, SearchQuery
    from ..net.http import WebClient


class EmptyPluginConfig(BaseModel):
    """Default configuration model for plugins without user settings."""

    model_config = ConfigDict(extra="forbid")


class FilmSourceProvider(ABC):
    """Minimal runtime contract consumed by the aggregate engine."""

    @abstractmethod
    async def fetch(self, query: SearchQuery, options: FetchOptions | None = None) -> MediaMetadata | None:
        """Fetch metadata for one structured search query."""
        ...


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Core services intentionally available to an in-process plugin.

    ``data_dir`` is a per-plugin subdirectory of the process data dir
    (``{data_dir}/plugins/<plugin_id>``). Plugins must not write outside it.
    """

    source_id: str
    http_client: HttpClient
    web_client: WebClient
    data_dir: Path


class FilmSourcePlugin(ABC):
    """Base class implemented by third-party film metadata plugins.

    Each drop-in directory ``{data_dir}/plugins/sources/<id>/`` must contain
    ``plugin.py`` exporting a subclass of this class named ``Plugin``.
    Authors import the subclass from ``amane.plugin``. The class is instantiated
    when the source catalog is discovered (startup, install, uninstall, or reload);
    providers are then cached by ``CrawlerFactory`` until the next rebuild.
    """

    config_model: ClassVar[type[BaseModel]] = EmptyPluginConfig

    @classmethod
    @abstractmethod
    def descriptor(cls) -> SourceDescriptor:
        """Return the stable source descriptor."""
        ...

    @classmethod
    def configuration_model(cls) -> type[BaseModel]:
        """Return the Pydantic model used to validate the plugin ``config`` object."""
        return cls.config_model

    @abstractmethod
    def build(self, context: PluginContext, config: BaseModel) -> FilmSourceProvider:
        """Build a provider using core services and validated plugin configuration."""
        ...

    def validate_config(self, value: dict[str, object]) -> BaseModel:
        """Validate a persisted plugin config envelope and return the typed settings."""
        envelope = PluginConfig.model_validate(value)
        return self.configuration_model().model_validate(envelope.config)
