"""Configuration management for Backstage to Glean connector."""

from functools import lru_cache

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Backstage configuration
    backstage_base_url: HttpUrl = Field(
        ...,
        description="Base URL for Backstage instance (e.g., https://backstage.example.com)",
    )
    backstage_api_token: str | None = Field(
        None,
        description="Optional API token for Backstage authentication",
    )
    backstage_page_size: int = Field(
        100,
        description="Number of entities to fetch per page from Backstage",
        ge=1,
        le=1000,
    )

    # Glean configuration
    glean_instance_name: str = Field(
        ...,
        description="Glean instance name (e.g., mycompany)",
    )
    glean_indexing_api_key: str = Field(
        ...,
        description="API key for Glean Indexing API",
    )
    glean_client_api_key: str | None = Field(
        None,
        description="API key for Glean Client API (if different from indexing key)",
    )
    glean_datasource_id: str = Field(
        "backstage",
        description="ID of the datasource in Glean",
    )
    glean_datasource_display_name: str = Field(
        "Backstage Catalog",
        description="Display name for the datasource in Glean",
    )

    # Sync configuration
    sync_batch_size: int = Field(
        50,
        description="Number of documents to push to Glean in a single batch",
        ge=1,
        le=100,
    )
    sync_users_enabled: bool = Field(
        True,
        description="Whether to sync User entities from Backstage",
    )
    sync_groups_enabled: bool = Field(
        True,
        description="Whether to sync Group entities from Backstage",
    )
    sync_components_enabled: bool = Field(
        True,
        description="Whether to sync Component entities from Backstage",
    )
    sync_apis_enabled: bool = Field(
        True,
        description="Whether to sync API entities from Backstage",
    )
    sync_systems_enabled: bool = Field(
        True,
        description="Whether to sync System entities from Backstage",
    )
    sync_domains_enabled: bool = Field(
        True,
        description="Whether to sync Domain entities from Backstage",
    )
    sync_resources_enabled: bool = Field(
        True,
        description="Whether to sync Resource entities from Backstage",
    )

    # Feature flags
    dry_run: bool = Field(
        False,
        description="If true, fetch data but don't push to Glean",
    )
    output_json: bool = Field(
        False,
        description="If true, save JSON files of data that would be sent to Glean (only works with dry_run)",
    )
    output_json_dir: str = Field(
        "backstage-sync-output",
        description="Directory to save JSON output files when output_json is enabled",
    )
    verify_ssl: bool = Field(
        True,
        description="Whether to verify SSL certificates",
    )
    
    # Permissions settings
    default_permissions: str = Field(
        "datasource-users",
        description="Default permissions for documents: 'none', 'owner', 'datasource-users', 'all-users'",
        pattern="^(none|owner|datasource-users|all-users)$",
    )

    @property
    def enabled_entity_kinds(self) -> list[str]:
        """Return list of enabled entity kinds based on sync settings."""
        kinds = []
        if self.sync_users_enabled:
            kinds.append("User")
        if self.sync_groups_enabled:
            kinds.append("Group")
        if self.sync_components_enabled:
            kinds.append("Component")
        if self.sync_apis_enabled:
            kinds.append("API")
        if self.sync_systems_enabled:
            kinds.append("System")
        if self.sync_domains_enabled:
            kinds.append("Domain")
        if self.sync_resources_enabled:
            kinds.append("Resource")
        return kinds


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
