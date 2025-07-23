"""Tests for the configuration module."""

import pytest

from backstage_connector.config import Settings


def test_settings_from_env(monkeypatch):
    """Test loading settings from environment variables."""
    # Set required environment variables
    monkeypatch.setenv("BACKSTAGE_BASE_URL", "https://backstage.test.com")
    monkeypatch.setenv("GLEAN_INSTANCE_NAME", "test-instance")
    monkeypatch.setenv("GLEAN_INDEXING_API_KEY", "test-api-key")

    settings = Settings()

    assert str(settings.backstage_base_url) == "https://backstage.test.com/"
    assert settings.glean_instance_name == "test-instance"
    assert settings.glean_indexing_api_key == "test-api-key"
    assert settings.glean_datasource_id == "backstage"  # default value


def test_settings_defaults():
    """Test default values for optional settings."""
    # Create settings with minimal required values
    settings = Settings(
        backstage_base_url="https://backstage.example.com",
        glean_instance_name="example",
        glean_indexing_api_key="key",
    )

    # Check defaults
    assert settings.backstage_page_size == 100
    assert settings.sync_batch_size == 50
    assert settings.sync_users_enabled is True
    assert settings.sync_groups_enabled is True
    assert settings.sync_components_enabled is True
    assert settings.dry_run is False
    assert settings.verify_ssl is True


def test_enabled_entity_kinds():
    """Test the enabled_entity_kinds property."""
    settings = Settings(
        backstage_base_url="https://backstage.example.com",
        glean_instance_name="example",
        glean_indexing_api_key="key",
        sync_users_enabled=True,
        sync_groups_enabled=True,
        sync_components_enabled=True,
        sync_apis_enabled=False,
        sync_systems_enabled=False,
        sync_domains_enabled=True,
        sync_resources_enabled=False,
    )

    kinds = settings.enabled_entity_kinds
    assert "User" in kinds
    assert "Group" in kinds
    assert "Component" in kinds
    assert "Domain" in kinds
    assert "API" not in kinds
    assert "System" not in kinds
    assert "Resource" not in kinds


def test_settings_validation():
    """Test settings validation."""
    # Test invalid URL
    with pytest.raises(ValueError):
        Settings(
            backstage_base_url="not-a-url",
            glean_instance_name="example",
            glean_indexing_api_key="key",
        )

    # Test page size validation
    with pytest.raises(ValueError):
        Settings(
            backstage_base_url="https://backstage.example.com",
            glean_instance_name="example",
            glean_indexing_api_key="key",
            backstage_page_size=0,  # Must be >= 1
        )

    with pytest.raises(ValueError):
        Settings(
            backstage_base_url="https://backstage.example.com",
            glean_instance_name="example",
            glean_indexing_api_key="key",
            backstage_page_size=1001,  # Must be <= 1000
        )
