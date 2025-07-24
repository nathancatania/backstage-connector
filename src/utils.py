"""Utility functions for Backstage data processing."""

from typing import Any


def parse_entity_ref(ref: str) -> tuple[str, str]:
    """Parse an entity reference into type and name.

    Examples:
        "user:default/john.doe" -> ("user", "john.doe")
        "group:default/team-a" -> ("group", "team-a")
        "team-a" -> ("", "team-a")
    """
    if ":" in ref:
        # Format: type:namespace/name or type:name
        type_part, rest = ref.split(":", 1)
        if "/" in rest:
            # Has namespace
            namespace, name = rest.split("/", 1)
            return type_part, name
        else:
            # No namespace
            return type_part, rest
    else:
        # Plain name
        return "", ref


def extract_name_from_ref(ref: str) -> str:
    """Extract just the name from an entity reference.

    Examples:
        "user:default/john.doe" -> "john.doe"
        "group:default/team-a" -> "team-a"
        "team-a" -> "team-a"
    """
    _, name = parse_entity_ref(ref)
    return name


def normalize_member_refs(member_refs: list[str]) -> list[str]:
    """Normalize a list of member references to just names.

    Examples:
        ["team-a", "group:default/team-b"] -> ["team-a", "team-b"]
    """
    return [extract_name_from_ref(ref) for ref in member_refs]


def get_user_email(user_spec: dict[str, Any]) -> str:
    """Get email from user spec, generating one if needed.

    Args:
        user_spec: The user entity spec containing profile

    Returns:
        Email address (existing or generated)
    """
    profile = user_spec.get("profile", {}) or {}
    email = profile.get("email")

    if not email:
        # This shouldn't happen in the current data, but handle it
        user_name = user_spec.get("name", "unknown")
        email = f"{user_name}@backstage.local"

    return email


def build_members_by_group(users: list[Any]) -> dict[str, set[str]]:
    """Build a map of group names to member emails.

    This processes users' memberOf fields to determine group membership,
    using email as the unique identifier for users.

    Args:
        users: List of user entities

    Returns:
        Dict mapping group name to set of member emails
    """
    members_by_group = {}

    for user in users:
        email = get_user_email(user.spec)
        member_of = user.spec.get("memberOf", [])

        for group_ref in member_of:
            group_name = extract_name_from_ref(group_ref)
            if group_name not in members_by_group:
                members_by_group[group_name] = set()
            members_by_group[group_name].add(email)

    return members_by_group


def deduplicate_users_by_email(users: list[Any]) -> tuple[list[Any], dict[str, list[Any]]]:
    """Deduplicate users by email address.

    When multiple users have the same email, the first one is kept and
    group memberships are merged.

    Args:
        users: List of user entities

    Returns:
        Tuple of (deduplicated users, dict of email to duplicate users)
    """
    seen_emails = {}
    unique_users = []
    duplicates = {}

    for user in users:
        email = get_user_email(user.spec)

        if email not in seen_emails:
            # First time seeing this email
            seen_emails[email] = user
            unique_users.append(user)
        else:
            # Duplicate email - merge memberships
            if email not in duplicates:
                duplicates[email] = [seen_emails[email]]
            duplicates[email].append(user)

            # Merge memberOf into the first user
            first_user = seen_emails[email]
            first_member_of = set(first_user.spec.get("memberOf", []))
            new_member_of = set(user.spec.get("memberOf", []))

            # Normalize and merge
            all_groups = first_member_of | new_member_of
            normalized_groups = list(set(normalize_member_refs(list(all_groups))))
            first_user.spec["memberOf"] = normalized_groups

    return unique_users, duplicates
