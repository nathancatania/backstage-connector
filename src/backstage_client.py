"""Client for interacting with Backstage Catalog API."""

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote, urljoin

import httpx
from pydantic import ValidationError

from .config import Settings
from .logging import log_debug, log_error, log_info, log_warning
from .models import Entity


class BackstageClient:
    """Async client for Backstage Catalog API."""

    def __init__(self, settings: Settings):
        """Initialize the Backstage client."""
        self.settings = settings
        self.base_url = str(settings.backstage_base_url)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if settings.backstage_api_token:
            self.headers["Authorization"] = f"Bearer {settings.backstage_api_token}"

    async def test_connection(self) -> bool:
        """Test the connection to Backstage API."""
        try:
            async with httpx.AsyncClient(verify=self.settings.verify_ssl) as client:
                url = urljoin(self.base_url, "/api/catalog/entities")
                response = await client.get(
                    url,
                    headers=self.headers,
                    params={"limit": 1},
                )
                response.raise_for_status()
                log_info("Successfully connected to Backstage API")
                return True
        except httpx.HTTPError as e:
            log_error(f"Failed to connect to Backstage API: {e}")
            return False

    async def fetch_entities(
        self,
        kind: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> AsyncIterator[Entity]:
        """Fetch entities from Backstage with pagination."""
        params: dict[str, Any] = {
            "limit": self.settings.backstage_page_size,
        }

        # Build filter query
        filter_parts = []
        if kind:
            filter_parts.append(f"kind={kind}")
        if filters:
            for key, value in filters.items():
                filter_parts.append(f"{key}={value}")

        if filter_parts:
            params["filter"] = ",".join(filter_parts)

        async with httpx.AsyncClient(
            verify=self.settings.verify_ssl,
            timeout=httpx.Timeout(30.0),
        ) as client:
            offset = 0
            total_fetched = 0

            while True:
                params["offset"] = offset
                url = urljoin(self.base_url, "/api/catalog/entities")

                try:
                    log_debug(f"Fetching entities from {url} with params: {params}")
                    response = await client.get(url, headers=self.headers, params=params)
                    response.raise_for_status()

                    data = response.json()

                    # Handle both array response and object with items
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict) and "items" in data:
                        items = data["items"]
                    else:
                        log_error(f"Unexpected API response format: {type(data)}")
                        break

                    if not items:
                        break

                    for item in items:
                        try:
                            entity = Entity(**item)
                            total_fetched += 1
                            yield entity
                        except ValidationError as e:
                            log_warning(f"Failed to parse entity: {e}")
                            continue

                    # Check if we've fetched all entities
                    if len(items) < self.settings.backstage_page_size:
                        break

                    offset += len(items)

                except httpx.HTTPError as e:
                    log_error(f"Failed to fetch entities: {e}")
                    break


    async def fetch_all_entities(self) -> list[Entity]:
        """Fetch all enabled entity types from Backstage."""
        all_entities = []

        for kind in self.settings.enabled_entity_kinds:
            async for entity in self.fetch_entities(kind=kind):
                all_entities.append(entity)

        return all_entities

    async def fetch_entity_by_ref(self, entity_ref: str) -> Entity | None:
        """Fetch a single entity by its reference."""
        # Parse entity reference (e.g., "user:default/john.doe")
        parts = entity_ref.split(":")
        if len(parts) != 2:
            log_error(f"Invalid entity reference: {entity_ref}")
            return None

        kind, namespace_name = parts
        namespace_parts = namespace_name.split("/")
        if len(namespace_parts) != 2:
            log_error(f"Invalid entity reference: {entity_ref}")
            return None

        namespace, name = namespace_parts

        # URL encode the namespace and name
        encoded_ref = f"{kind}:{namespace}/{quote(name, safe='')}"

        async with httpx.AsyncClient(verify=self.settings.verify_ssl) as client:
            url = urljoin(self.base_url, f"/api/catalog/entities/by-name/{encoded_ref}")

            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()

                data = response.json()
                return Entity(**data)

            except httpx.HTTPError as e:
                log_error(f"Failed to fetch entity {entity_ref}: {e}")
                return None

    async def fetch_users_and_groups(self) -> tuple[list[Entity], list[Entity]]:
        """Fetch all users and groups from Backstage."""
        users = []
        groups = []

        if self.settings.sync_users_enabled:
            async for entity in self.fetch_entities(kind="User"):
                users.append(entity)

        if self.settings.sync_groups_enabled:
            async for entity in self.fetch_entities(kind="Group"):
                groups.append(entity)

        return users, groups
