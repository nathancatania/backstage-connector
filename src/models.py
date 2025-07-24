"""Pydantic models for Backstage entities."""

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class EntityMetadata(BaseModel):
    """Metadata for a Backstage entity."""

    namespace: str = Field(default="default")
    name: str
    uid: str | None = None
    etag: str | None = None
    description: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    links: list[dict[str, str]] = Field(default_factory=list)


class EntityRelation(BaseModel):
    """Relationship between entities."""

    type: str
    targetRef: str
    target: dict[str, Any] | None = None


class UserProfile(BaseModel):
    """User profile information."""

    displayName: str | None = None
    email: EmailStr | None = None
    picture: str | None = None


class UserSpec(BaseModel):
    """User entity specification."""

    profile: UserProfile | None = None
    memberOf: list[str] = Field(default_factory=list)


class GroupProfile(BaseModel):
    """Group profile information."""

    displayName: str | None = None
    email: EmailStr | None = None
    picture: str | None = None


class GroupSpec(BaseModel):
    """Group entity specification."""

    type: str = "team"
    profile: GroupProfile | None = None
    parent: str | None = None
    children: list[str] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)


class ComponentSpec(BaseModel):
    """Component entity specification."""

    type: str  # service, website, library, etc.
    lifecycle: str  # production, experimental, deprecated
    owner: str
    system: str | None = None
    subcomponentOf: str | None = None
    providesApis: list[str] = Field(default_factory=list)
    consumesApis: list[str] = Field(default_factory=list)
    dependsOn: list[str] = Field(default_factory=list)


class ApiSpec(BaseModel):
    """API entity specification."""

    type: str  # openapi, asyncapi, graphql, grpc
    lifecycle: str
    owner: str
    system: str | None = None
    definition: str | None = None


class SystemSpec(BaseModel):
    """System entity specification."""

    owner: str
    domain: str | None = None


class DomainSpec(BaseModel):
    """Domain entity specification."""

    owner: str


class ResourceSpec(BaseModel):
    """Resource entity specification."""

    type: str
    owner: str
    system: str | None = None
    dependsOn: list[str] = Field(default_factory=list)


class Entity(BaseModel):
    """Base Backstage entity."""

    apiVersion: str = "backstage.io/v1alpha1"
    kind: str
    metadata: EntityMetadata
    spec: dict[str, Any] = Field(default_factory=dict)
    relations: list[EntityRelation] = Field(default_factory=list)

    @property
    def ref(self) -> str:
        """Get entity reference string."""
        namespace = self.metadata.namespace or "default"
        return f"{self.kind.lower()}:{namespace}/{self.metadata.name}"


class EntitiesResponse(BaseModel):
    """Response from Backstage entities API."""

    items: list[Entity] = Field(default_factory=list)
    totalItems: int | None = None
    pageInfo: dict[str, Any] | None = None
