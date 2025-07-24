"""Tests for CLI show commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli import show
from src.models import Entity, EntityMetadata


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_backstage_client():
    """Create a mock BackstageClient."""
    client = MagicMock()
    return client


@pytest.fixture
def sample_users():
    """Create sample user entities."""
    return [
        Entity(
            apiVersion="backstage.io/v1alpha1",
            kind="User",
            metadata=EntityMetadata(name="john.doe", namespace="default"),
            spec={
                "profile": {
                    "displayName": "John Doe",
                    "email": "john@example.com",
                },
                "memberOf": ["team-a", "team-b"],
            },
        ),
        Entity(
            apiVersion="backstage.io/v1alpha1",
            kind="User",
            metadata=EntityMetadata(name="jane.smith", namespace="default"),
            spec={
                "profile": {
                    "displayName": "Jane Smith",
                    "email": "jane@example.com",
                },
                "memberOf": ["team-c"],
            },
        ),
    ]


@pytest.fixture
def sample_groups():
    """Create sample group entities."""
    return [
        Entity(
            apiVersion="backstage.io/v1alpha1",
            kind="Group",
            metadata=EntityMetadata(name="team-a", namespace="default"),
            spec={
                "type": "team",
                "profile": {"displayName": "Team A"},
                "members": ["john.doe", "alice.wonder"],
                "parent": "engineering",
            },
        ),
        Entity(
            apiVersion="backstage.io/v1alpha1",
            kind="Group",
            metadata=EntityMetadata(name="engineering", namespace="default"),
            spec={
                "type": "department",
                "profile": {"displayName": "Engineering Department"},
                "members": [],
            },
        ),
    ]


@pytest.fixture
def sample_components():
    """Create sample component entities."""
    return [
        Entity(
            apiVersion="backstage.io/v1alpha1",
            kind="Component",
            metadata=EntityMetadata(
                name="backend-service",
                namespace="default",
                description="Main backend service",
            ),
            spec={
                "type": "service",
                "lifecycle": "production",
                "owner": "team-a",
                "system": "main-system",
            },
        ),
    ]


def test_show_users_command(runner, mock_backstage_client, sample_users):
    """Test the show users command."""
    async def mock_fetch_entities(kind=None):
        if kind == "User":
            for user in sample_users:
                yield user

    mock_backstage_client.fetch_entities = mock_fetch_entities

    with patch("src.cli.get_settings") as mock_settings:
        with patch("src.cli.BackstageClient") as mock_client_class:
            mock_client_class.return_value = mock_backstage_client

            result = runner.invoke(show, ["users"])

            assert result.exit_code == 0
            assert "john.doe" in result.output
            assert "John Doe" in result.output
            assert "john@example.com" in result.output
            assert "team-a, team-b" in result.output
            assert "jane.smith" in result.output


def test_show_users_with_limit(runner, mock_backstage_client, sample_users):
    """Test the show users command with limit."""
    async def mock_fetch_entities(kind=None):
        if kind == "User":
            for user in sample_users[:1]:  # Only yield first user
                yield user

    mock_backstage_client.fetch_entities = mock_fetch_entities

    with patch("src.cli.get_settings") as mock_settings:
        with patch("src.cli.BackstageClient") as mock_client_class:
            mock_client_class.return_value = mock_backstage_client

            result = runner.invoke(show, ["users", "--limit", "1"])

            assert result.exit_code == 0
            assert "john.doe" in result.output
            assert "jane.smith" not in result.output  # Limited to 1
            assert "showing 1 of 1 max" in result.output


def test_show_groups_command(runner, mock_backstage_client, sample_groups):
    """Test the show groups command."""
    async def mock_fetch_entities(kind=None):
        if kind == "Group":
            for group in sample_groups:
                yield group

    mock_backstage_client.fetch_entities = mock_fetch_entities

    with patch("src.cli.get_settings") as mock_settings:
        with patch("src.cli.BackstageClient") as mock_client_class:
            mock_client_class.return_value = mock_backstage_client

            result = runner.invoke(show, ["groups"])

            assert result.exit_code == 0
            assert "team-a" in result.output
            assert "Team A" in result.output
            assert "engineering" in result.output
            assert "2" in result.output  # Member count


def test_show_components_command(runner, mock_backstage_client, sample_components):
    """Test the show components command."""
    async def mock_fetch_entities(kind=None):
        if kind == "Component":
            for component in sample_components:
                yield component

    mock_backstage_client.fetch_entities = mock_fetch_entities

    with patch("src.cli.get_settings") as mock_settings:
        with patch("src.cli.BackstageClient") as mock_client_class:
            mock_client_class.return_value = mock_backstage_client

            result = runner.invoke(show, ["components"])

            assert result.exit_code == 0
            assert "backend-service" in result.output
            assert "service" in result.output
            assert "production" in result.output
            assert "team-a" in result.output
            assert "main-system" in result.output


def test_show_empty_results(runner, mock_backstage_client):
    """Test show command with no results."""
    async def mock_fetch_entities(kind=None):
        return
        yield  # Empty generator

    mock_backstage_client.fetch_entities = mock_fetch_entities

    with patch("src.cli.get_settings") as mock_settings:
        with patch("src.cli.BackstageClient") as mock_client_class:
            mock_client_class.return_value = mock_backstage_client

            result = runner.invoke(show, ["users"])

            assert result.exit_code == 0
            assert "No users found in Backstage catalog" in result.output


def test_show_command_error_handling(runner):
    """Test error handling in show commands."""
    with patch("backstage_connector.cli.get_settings") as mock_settings:
        mock_settings.side_effect = Exception("Configuration error")

        result = runner.invoke(show, ["users"])

        assert result.exit_code == 1