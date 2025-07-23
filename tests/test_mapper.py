"""Tests for the data mapper module."""

# Mock the Glean models before importing mapper
import sys
from unittest.mock import MagicMock, Mock

import pytest

# Create a more comprehensive mock for the models module
class MockModels:
    DatasourceUserDefinition = Mock(side_effect=lambda **kwargs: f"User({kwargs['user_id']})")
    DatasourceGroupDefinition = Mock(side_effect=lambda **kwargs: f"Group({kwargs['name']})")
    DocumentDefinition = Mock(side_effect=lambda **kwargs: Mock(custom_metadata=None, **kwargs))
    ContentDefinition = Mock(side_effect=lambda **kwargs: f"Content({kwargs.get('mime_type', 'text/plain')})")
    PermissionsDefinition = Mock(side_effect=lambda **kwargs: Mock(allowed_users=None, **kwargs))
    UserReferenceDefinition = Mock(side_effect=lambda **kwargs: f"UserRef({kwargs['datasource_user_id']})")
    DatasourceBulkMembershipDefinition = Mock(side_effect=lambda **kwargs: f"BulkMembership({kwargs['group_name']})")
    DatasourceMembershipDefinition = Mock(side_effect=lambda **kwargs: f"Membership({kwargs['user_id']})")

mock_models = MockModels()
sys.modules['glean'] = MagicMock()
sys.modules['glean.api_client'] = MagicMock()
sys.modules['glean.api_client'].models = mock_models

from backstage_connector.mapper import BackstageToGleanMapper  # noqa: E402
from backstage_connector.models import Entity, EntityMetadata  # noqa: E402


@pytest.fixture
def mapper():
    """Create a mapper instance for testing."""
    return BackstageToGleanMapper(
        backstage_base_url="https://backstage.example.com",
        datasource_name="test-datasource",
    )


def test_map_user_to_glean(mapper):
    """Test mapping a Backstage user to Glean format."""
    user_entity = Entity(
        apiVersion="backstage.io/v1alpha1",
        kind="User",
        metadata=EntityMetadata(
            name="john.doe",
            namespace="default",
        ),
        spec={
            "profile": {
                "displayName": "John Doe",
                "email": "john.doe@example.com",
                "picture": "https://example.com/john.jpg",
            },
            "memberOf": ["team-a", "team-b"],
        },
    )

    result = mapper.map_user_to_glean(user_entity)

    # Verify the mock was called with correct arguments
    mock_models.DatasourceUserDefinition.assert_called_once_with(
        email="john.doe@example.com",
        name="John Doe",
        user_id="john.doe",
        profile_url="https://backstage.example.com/catalog/default/user/john.doe",
        photo_url="https://example.com/john.jpg",
        datasource="test-datasource",
    )
    assert result == "User(john.doe)"


def test_map_user_without_email(mapper):
    """Test mapping a user without an email address."""
    user_entity = Entity(
        apiVersion="backstage.io/v1alpha1",
        kind="User",
        metadata=EntityMetadata(
            name="jane.doe",
            namespace="default",
        ),
        spec={
            "profile": {
                "displayName": "Jane Doe",
            },
            "memberOf": [],
        },
    )

    result = mapper.map_user_to_glean(user_entity)

    # Verify placeholder email was used
    mock_models.DatasourceUserDefinition.assert_called_with(
        email="jane.doe@backstage.local",
        name="Jane Doe",
        user_id="jane.doe",
        profile_url="https://backstage.example.com/catalog/default/user/jane.doe",
        photo_url=None,
        datasource="test-datasource",
    )
    assert result == "User(jane.doe)"


def test_map_group_to_glean(mapper):
    """Test mapping a Backstage group to Glean format."""
    group_entity = Entity(
        apiVersion="backstage.io/v1alpha1",
        kind="Group",
        metadata=EntityMetadata(
            name="team-a",
            namespace="default",
        ),
        spec={
            "type": "team",
            "profile": {
                "displayName": "Team A",
                "email": "team-a@example.com",
            },
        },
    )

    result = mapper.map_group_to_glean(group_entity)

    mock_models.DatasourceGroupDefinition.assert_called_once_with(
        name="team-a",
        display_name="Team A",
        datasource="test-datasource",
    )
    assert result == "Group(team-a)"


def test_map_component_to_document(mapper):
    """Test mapping a component entity to a Glean document."""
    component_entity = Entity(
        apiVersion="backstage.io/v1alpha1",
        kind="Component",
        metadata=EntityMetadata(
            name="backend-service",
            namespace="default",
            description="Main backend service for the application",
            tags=["backend", "python", "api"],
            links=[
                {"title": "Documentation", "url": "https://docs.example.com"},
                {"title": "GitHub", "url": "https://github.com/example/backend"},
            ],
            annotations={
                "github.com/project-slug": "example/backend",
                "backstage.io/techdocs-ref": "dir:.",
            },
        ),
        spec={
            "type": "service",
            "lifecycle": "production",
            "owner": "team-a",
            "system": "main-system",
        },
    )

    result = mapper.map_entity_to_document(component_entity)

    # Verify DocumentDefinition was called
    assert mock_models.DocumentDefinition.called
    
    # Check that the document was created with expected values
    call_kwargs = mock_models.DocumentDefinition.call_args.kwargs
    assert call_kwargs['title'] == "backend-service (Component)"
    assert call_kwargs['datasource'] == "test-datasource"
    assert call_kwargs['id'] == "component-default-backend-service"
    assert call_kwargs['url'] == "https://backstage.example.com/catalog/default/component/backend-service"
    
    # Verify custom metadata was set on the mock document
    assert result.custom_metadata == {
        "entity_kind": "Component",
        "entity_namespace": "default",
        "entity_type": "service",
        "entity_lifecycle": "production",
        "entity_ref": "component:default/backend-service",
        "tags": "backend,python,api",
    }


def test_map_group_memberships(mapper):
    """Test mapping user-group memberships."""
    # Reset call counts
    mock_models.DatasourceMembershipDefinition.reset_mock()
    mock_models.DatasourceMembershipDefinition.reset_mock()
    
    users = [
        Entity(
            apiVersion="backstage.io/v1alpha1",
            kind="User",
            metadata=EntityMetadata(name="user1"),
            spec={"memberOf": ["team-a", "team-b"]},
        ),
        Entity(
            apiVersion="backstage.io/v1alpha1",
            kind="User",
            metadata=EntityMetadata(name="user2"),
            spec={"memberOf": ["team-a"]},
        ),
    ]

    groups = [
        Entity(
            apiVersion="backstage.io/v1alpha1",
            kind="Group",
            metadata=EntityMetadata(name="team-a"),
            spec={},
            relations=[],
        ),
        Entity(
            apiVersion="backstage.io/v1alpha1",
            kind="Group",
            metadata=EntityMetadata(name="team-b"),
            spec={},
            relations=[],
        ),
    ]

    result = mapper.map_group_memberships(users, groups)

    # Should have created 3 membership definitions (one per user-group relationship)
    assert len(result) == 3

    # Verify membership definitions were created for each user
    assert mock_models.DatasourceMembershipDefinition.call_count == 3  # user1 in team-a, user1 in team-b, user2 in team-a
    
    # Verify the membership definitions have correct parameters
    mock_models.DatasourceMembershipDefinition.assert_any_call(
        group_name="team-a",
        member_user_id="user1"
    )
    mock_models.DatasourceMembershipDefinition.assert_any_call(
        group_name="team-b",
        member_user_id="user1"
    )
    mock_models.DatasourceMembershipDefinition.assert_any_call(
        group_name="team-a",
        member_user_id="user2"
    )
    
    # Verify the results
    assert "BulkMembership(team-a)" in result
    assert "BulkMembership(team-b)" in result