"""Data mapper for converting Backstage entities to Glean format."""

import re
from urllib.parse import urljoin

from glean.api_client import models

from .config import Settings
from .logging import log_warning
from .models import Entity


class BackstageToGleanMapper:
    """Maps Backstage entities to Glean document and identity formats."""

    def __init__(self, backstage_base_url: str, datasource_id: str, settings: Settings | None = None):
        """Initialize the mapper."""
        self.backstage_base_url = backstage_base_url
        self.datasource_id = datasource_id
        self.settings = settings

    def map_user_to_glean(self, user: Entity) -> models.DatasourceUserDefinition:
        """Map a Backstage User entity to Glean user format."""
        user_spec = user.spec
        profile = user_spec.get("profile", {})

        # Extract email and name
        email = profile.get("email")
        display_name = profile.get("displayName", user.metadata.name)

        if not email:
            # Generate a placeholder email if none exists
            email = f"{user.metadata.name}@backstage.local"
            log_warning(f"No email found for user {user.metadata.name}, using placeholder: {email}")

        return models.DatasourceUserDefinition(
            email=email,
            name=display_name,
            user_id=user.metadata.name,
            profile_url=self._get_entity_url(user),
            photo_url=profile.get("picture"),
            datasource=self.datasource_id,
        )

    def map_group_to_glean(self, group: Entity) -> models.DatasourceGroupDefinition:
        """Map a Backstage Group entity to Glean group format."""
        group_spec = group.spec
        profile = group_spec.get("profile", {})

        return models.DatasourceGroupDefinition(
            name=group.metadata.name,
            display_name=profile.get("displayName", group.metadata.name),
            datasource=self.datasource_id,
        )

    def map_group_memberships(self, users: list[Entity], groups: list[Entity]) -> list[models.DatasourceMembershipDefinition]:
        """Map user-group relationships to Glean membership format."""
        memberships = []

        # Create a map of group names to their members
        group_members: dict[str, list[str]] = {}

        # Process user memberOf relationships
        for user in users:
            member_of = user.spec.get("memberOf", [])
            for group_ref in member_of:
                # Extract group name from reference
                group_name = group_ref.split("/")[-1] if "/" in group_ref else group_ref
                if group_name not in group_members:
                    group_members[group_name] = []
                group_members[group_name].append(user.metadata.name)

        # Process group member relationships
        for group in groups:
            # Check relations for hasMember relationships
            for relation in group.relations:
                if relation.type == "hasMember":
                    # Extract user name from targetRef
                    user_name = relation.targetRef.split("/")[-1] if "/" in relation.targetRef else relation.targetRef
                    if group.metadata.name not in group_members:
                        group_members[group.metadata.name] = []
                    if user_name not in group_members[group.metadata.name]:
                        group_members[group.metadata.name].append(user_name)

        # Convert to Glean membership format
        for group_name, members in group_members.items():
            for member in members:
                memberships.append(
                    models.DatasourceMembershipDefinition(
                        group_name=group_name,
                        member_user_id=member,
                    )
                )

        return memberships

    def map_entity_to_document(self, entity: Entity, entity_map: dict[str, Entity] | None = None) -> models.DocumentDefinition:
        """Map a Backstage catalog entity to Glean document format."""
        # Build document URL
        doc_url = self._get_entity_url(entity)

        # Extract owner information
        owner_ref = entity.spec.get("owner")
        owner_type = None
        owner_id = None
        if owner_ref:
            # Parse owner reference (could be user:default/john.doe or group:default/team-a)
            owner_type, owner_id = self._parse_entity_ref(owner_ref)

        # Build content from entity data
        content_parts = []

        # Skip description from content if we're adding it to summary
        # (We'll handle description as summary below)

        # Add metadata
        content_parts.append("## Details")
        content_parts.append(f"- **Kind**: {entity.kind}")
        content_parts.append(f"- **Type**: {entity.spec.get('type', 'N/A')}")
        content_parts.append(f"- **Lifecycle**: {entity.spec.get('lifecycle', 'N/A')}")
        if owner_ref:
            content_parts.append(f"- **Owner**: {owner_ref}")
        if entity.spec.get("system"):
            content_parts.append(f"- **System**: {entity.spec.get('system')}")
        if entity.spec.get("domain"):
            content_parts.append(f"- **Domain**: {entity.spec.get('domain')}")

        # Add tags
        if entity.metadata.tags:
            content_parts.append("")
            content_parts.append(f"**Tags**: {', '.join(entity.metadata.tags)}")

        # Add links
        if entity.metadata.links:
            content_parts.append("")
            content_parts.append("## Links")
            for link in entity.metadata.links:
                content_parts.append(f"- [{link.get('title', 'Link')}]({link.get('url')})")

        # Add annotations (selected ones)
        important_annotations = {
            "backstage.io/techdocs-ref": "Documentation",
            "github.com/project-slug": "GitHub Project",
            "backstage.io/source-location": "Source Location",
        }

        annotations_to_show = {}
        for key, label in important_annotations.items():
            if key in entity.metadata.annotations:
                annotations_to_show[label] = entity.metadata.annotations[key]

        if annotations_to_show:
            content_parts.append("")
            content_parts.append("## Annotations")
            for label, value in annotations_to_show.items():
                content_parts.append(f"- **{label}**: {value}")

        # Skip API definition from content if we're adding it to body
        # (We'll handle definition as body below)

        # Build permissions based on settings
        permissions = models.DocumentPermissionsDefinition()

        if self.settings and self.settings.default_permissions:
            if self.settings.default_permissions == "none":
                # Empty permissions - no access
                pass
            elif self.settings.default_permissions == "owner":
                # Assign to owner if exists
                if owner_type and owner_id:
                    if owner_type == "user":
                        permissions.allowed_users = [
                            models.UserReferenceDefinition(
                                datasource_user_id=owner_id,
                                datasource=self.datasource_id,
                            )
                        ]
                    elif owner_type == "group":
                        permissions.allowed_groups = [owner_id]
                # If no owner, permissions remain empty (none)
            elif self.settings.default_permissions == "datasource-users":
                permissions.allow_all_datasource_users_access = True
            elif self.settings.default_permissions == "all-users":
                permissions.allow_anonymous_access = True
        else:
            # Fallback to datasource-users if no settings
            permissions.allow_all_datasource_users_access = True

        # Create document
        doc = models.DocumentDefinition(
            datasource=self.datasource_id,
            id=f"{entity.kind.lower()}-{entity.metadata.namespace}-{entity.metadata.name}",
            title=entity.metadata.name,
            view_url=doc_url,  # Fixed field name from url to view_url
            content=models.ContentDefinition(
                mime_type="text/plain",
                text_content="\n".join(content_parts),
            ),
            permissions=permissions,
            object_type=self._get_object_type(entity),
        )

        # Add owner field if owner is a user
        if owner_type == "user" and owner_id:
            doc.owner = models.UserReferenceDefinition(
                datasource_user_id=owner_id,
                datasource=self.datasource_id,
            )

        # Add summary from description if available
        if entity.metadata.description:
            # Convert markdown to plain text if needed
            summary_text = self._convert_markdown_to_plain_text(entity.metadata.description)
            doc.summary = models.ContentDefinition(
                mime_type="text/plain",
                text_content=summary_text,
            )

        # Add body from spec.definition if available
        if entity.spec.get("definition"):
            definition = entity.spec.get("definition", "")
            mime_type = self._detect_definition_mime_type(entity, definition)
            doc.body = models.ContentDefinition(
                mime_type=mime_type,
                text_content=definition,
            )

        # Add container info if entity_map provided
        if entity_map:
            container_info = self._get_container_info(entity, entity_map)
            if container_info:
                doc.container_object_type = container_info["type"]
                doc.container_datasource_id = container_info["id"]

        # Add custom properties as list of CustomProperty objects
        custom_props = []

        # Add entity metadata as custom properties
        custom_props.append(models.CustomProperty(name="namespace", value=entity.metadata.namespace))

        if entity.spec.get("type"):
            custom_props.append(models.CustomProperty(name="kind", value=entity.spec.get("type")))
        if entity.spec.get("lifecycle"):
            custom_props.append(models.CustomProperty(name="lifecycle", value=entity.spec.get("lifecycle").title()))

        custom_props.append(models.CustomProperty(name="ref", value=entity.ref))

        doc.custom_properties = custom_props

        # Add tags as document tags field (not custom property)
        if entity.metadata.tags:
            doc.tags = entity.metadata.tags

        return doc

    def _get_entity_url(self, entity: Entity) -> str:
        """Get the Backstage UI URL for an entity."""
        # Always construct URL from base URL using Backstage's URL format
        namespace = entity.metadata.namespace or "default"
        return urljoin(self.backstage_base_url, f"/catalog/{namespace}/{entity.kind.lower()}/{entity.metadata.name}")

    def _parse_entity_ref(self, ref: str) -> tuple[str, str]:
        """Parse an entity reference like 'user:default/john.doe' into (type, name)."""
        if ":" in ref:
            parts = ref.split(":", 1)  # Split only on first colon
            if len(parts) == 2:
                entity_type = parts[0]
                # Handle both "user:guest" and "user:default/john.doe" formats
                if "/" in parts[1]:
                    entity_name = parts[1].split("/")[-1]
                else:
                    entity_name = parts[1]
                return entity_type, entity_name

        # Fallback - assume it's just a name
        return "unknown", ref

    def _get_object_type(self, entity: Entity) -> str:
        """Map Backstage kind to Glean object type."""
        kind_mapping = {
            "Domain": "domain",
            "System": "system",
            "Component": "component",
            "API": "api",
            "Resource": "resource",
        }
        return kind_mapping.get(entity.kind, entity.kind.lower())

    def _get_container_info(self, entity: Entity, entity_map: dict[str, Entity]) -> dict[str, str] | None:
        """Determine parent container for entity."""
        # Component/API/Resource -> System
        if entity.kind in ["Component", "API", "Resource"]:
            system_ref = entity.spec.get("system")
            if system_ref:
                parent_entity = self._resolve_entity_ref(system_ref, entity_map)
                if parent_entity:
                    return {
                        "type": "system",
                        "id": f"system-{parent_entity.metadata.namespace}-{parent_entity.metadata.name}",
                    }

        # System -> Domain
        elif entity.kind == "System":
            domain_ref = entity.spec.get("domain")
            if domain_ref:
                parent_entity = self._resolve_entity_ref(domain_ref, entity_map)
                if parent_entity:
                    return {
                        "type": "domain",
                        "id": f"domain-{parent_entity.metadata.namespace}-{parent_entity.metadata.name}",
                    }

        # Group -> Parent Group
        elif entity.kind == "Group":
            parent_ref = entity.spec.get("parent")
            if parent_ref:
                parent_entity = self._resolve_entity_ref(parent_ref, entity_map)
                if parent_entity:
                    return {
                        "type": "group",
                        "id": f"group-{parent_entity.metadata.namespace}-{parent_entity.metadata.name}",
                    }

        return None

    def _resolve_entity_ref(self, ref: str, entity_map: dict[str, Entity]) -> Entity | None:
        """Resolve an entity reference to an actual entity."""
        # Try full reference first
        if ref in entity_map:
            return entity_map[ref]

        # Parse the reference
        entity_type, entity_name = self._parse_entity_ref(ref)

        # Try various combinations
        # 1. With default namespace
        full_ref = f"{entity_type}:default/{entity_name}"
        if full_ref in entity_map:
            return entity_map[full_ref]

        # 2. Try without type prefix for same-kind references
        for _key, entity in entity_map.items():
            if entity.metadata.name == entity_name:
                # If type is specified, it must match
                if entity_type != "unknown" and entity.kind.lower() != entity_type.lower():
                    continue
                return entity

        # 3. Try to find by name only (for plain references like "team-a")
        if entity_type == "unknown":
            # Look for exact name match
            for _key, entity in entity_map.items():
                if entity.metadata.name == ref:
                    return entity

        return None

    def _convert_markdown_to_plain_text(self, text: str) -> str:
        """Convert markdown text to plain text."""
        # Basic markdown to plain text conversion
        # Remove markdown formatting but keep the content readable

        # Remove code blocks
        text = re.sub(r"```[^`]*```", lambda m: m.group(0).replace("```", ""), text)
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # Remove headers (keep text)
        text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)

        # Remove bold/italic
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        text = re.sub(r"_([^_]+)_", r"\1", text)

        # Remove links but keep text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

        # Remove images
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"", text)

        # Remove horizontal rules
        text = re.sub(r"^[-*_]{3,}$", "", text, flags=re.MULTILINE)

        # Clean up extra whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _detect_definition_mime_type(self, entity: Entity, definition: str) -> str:
        """Detect the MIME type of an API definition."""
        # See: https://developers.glean.com/api-info/indexing/documents/supported-mimetypes
        # All map to text/plain currently until types like JSON, YAML, etc are supported explicitly

        # Check spec type hint first
        spec_type = entity.spec.get("type", "").lower()

        # Map spec types to MIME types
        type_mapping = {
            "openapi": "text/plain",  # Usually YAML
            "asyncapi": "text/plain",
            "graphql": "text/plain",
            "grpc": "text/plain",  # Protocol buffers
            "trpc": "text/plain",
        }

        if spec_type in type_mapping:
            # Verify if it's JSON instead of YAML for openapi/asyncapi
            if spec_type in ["openapi", "asyncapi"] and definition.strip().startswith("{"):
                return "text/plain"
            return type_mapping[spec_type]

        # Try to detect from content
        definition_lower = definition[:200].lower()

        # Check for specific patterns
        if "openapi:" in definition_lower or "swagger:" in definition_lower:
            return "text/plain"
        elif "asyncapi:" in definition_lower:
            return "text/plain"
        elif definition.strip().startswith("{") and "openapi" in definition_lower:
            return "text/plain"
        elif 'syntax = "proto' in definition_lower:
            return "text/plain"  # Protocol buffers
        elif "type Query" in definition or "type Mutation" in definition:
            return "text/plain"
        elif definition.strip().startswith("{"):
            return "text/plain"
        elif definition.strip().startswith("---") or ":" in definition[:50]:
            return "text/plain"
        else:
            return "text/plain"
