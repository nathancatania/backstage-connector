"""Command-line interface for Backstage to Glean sync."""

import asyncio
import sys

import click
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table

from .backstage_client import BackstageClient
from .config import get_settings
from .logging import log_error
from .sync import BackstageGleanSync
from .utils import (
    build_members_by_group,
    deduplicate_users_by_email,
    extract_name_from_ref,
    get_user_email,
    normalize_member_refs,
)

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="backstage-sync")
def cli():
    """Backstage to Glean integration for indexing catalog entities."""
    pass


@cli.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be synced without pushing to Glean",
)
@click.option(
    "--output-json",
    is_flag=True,
    help="Save JSON files of data that would be sent to Glean (requires --dry-run)",
)
def sync(dry_run: bool, output_json: bool):
    """Sync Backstage catalog entities to Glean."""
    try:
        settings = get_settings()
        if dry_run:
            settings.dry_run = True
            if output_json:
                settings.output_json = True
                console.print(f"[yellow]JSON output will be saved to: {settings.output_json_dir}/[/yellow]")
        elif output_json:
            console.print("[red]Error: --output-json requires --dry-run flag[/red]")
            sys.exit(1)

        sync_instance = BackstageGleanSync(settings)
        success = asyncio.run(sync_instance.run_sync())

        if not success:
            console.print("[bold red]Sync failed[/bold red]")
            sys.exit(1)

        console.print("[bold green]Sync completed successfully[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        log_error(f"Sync command failed: {e}", exception=e)
        sys.exit(1)


@cli.command()
def test_connection():
    """Test connections to Backstage and Glean APIs."""
    try:
        settings = get_settings()

        # Create a table for test results
        table = Table(title="Connection Test Results")
        table.add_column("Service", style="cyan", no_wrap=True)
        table.add_column("Status", style="bold")
        table.add_column("Details", style="dim")

        # Test with spinner
        with Live(
            Spinner("dots", text="Testing connections...", style="cyan"),
            console=console,
            refresh_per_second=10,
        ) as live:
            sync_instance = BackstageGleanSync(settings)

            # Test Backstage
            live.update(Spinner("dots", text="Testing Backstage connection...", style="cyan"))
            backstage_ok, backstage_msg = asyncio.run(sync_instance.test_backstage_detailed())

            # Test Glean
            live.update(Spinner("dots", text="Testing Glean connection...", style="cyan"))
            glean_ok, glean_msg = asyncio.run(sync_instance.test_glean_detailed())

        # Add results to table
        table.add_row(
            "Backstage API",
            "✅ Connected" if backstage_ok else "❌ Failed",
            backstage_msg
        )
        table.add_row(
            "Glean API",
            "✅ Connected" if glean_ok else "❌ Failed",
            glean_msg
        )

        console.print(table)

        if backstage_ok and glean_ok:
            console.print("\n[bold green]All connections successful![/bold green]")
        else:
            console.print("\n[bold red]Some connections failed[/bold red]")
            sys.exit(1)

    except Exception as e:
        log_error(f"Connection test failed: {e}", exception=e)
        sys.exit(1)


@cli.command()
@click.option(
    "--output-json",
    is_flag=True,
    help="Save JSON files of data that would be sent to Glean",
)
def dry_run(output_json: bool):
    """Preview what would be synced without pushing to Glean."""
    try:
        settings = get_settings()
        if output_json:
            settings.output_json = True
            console.print(f"[yellow]JSON output will be saved to: {settings.output_json_dir}/[/yellow]")
        sync_instance = BackstageGleanSync(settings)

        # Show what will be synced
        console.print("[bold yellow]DRY RUN MODE[/bold yellow] - No data will be pushed to Glean\n")

        with Live(
            Spinner("dots", text="Running dry run analysis...", style="cyan"),
            console=console,
            refresh_per_second=10,
        ):
            success, summary = asyncio.run(sync_instance.run_dry_run_with_summary())

        if not success:
            console.print("[bold red]Dry run failed[/bold red]")
            sys.exit(1)

    except Exception as e:
        log_error(f"Dry run failed: {e}", exception=e)
        sys.exit(1)


@cli.command()
def show_config():
    """Display current configuration settings."""
    try:
        settings = get_settings()

        # Create a table for configuration display
        table = Table(title="Backstage Sync Configuration")
        table.add_column("Setting", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        # Backstage settings
        table.add_row("Backstage URL", str(settings.backstage_base_url))
        table.add_row("Backstage API Token", "***" if settings.backstage_api_token else "Not set")
        table.add_row("Backstage Page Size", str(settings.backstage_page_size))

        # Glean settings
        table.add_row("Glean Instance", settings.glean_instance_name)
        table.add_row("Glean Datasource", settings.glean_datasource_id)
        table.add_row("Glean Indexing Key", "***" if settings.glean_indexing_api_key else "Not set")

        # Sync settings
        table.add_row("Batch Size", str(settings.sync_batch_size))
        table.add_row("Sync Users", "✓" if settings.sync_users_enabled else "✗")
        table.add_row("Sync Groups", "✓" if settings.sync_groups_enabled else "✗")
        table.add_row("Sync Components", "✓" if settings.sync_components_enabled else "✗")
        table.add_row("Sync APIs", "✓" if settings.sync_apis_enabled else "✗")
        table.add_row("Sync Systems", "✓" if settings.sync_systems_enabled else "✗")
        table.add_row("Sync Domains", "✓" if settings.sync_domains_enabled else "✗")
        table.add_row("Sync Resources", "✓" if settings.sync_resources_enabled else "✗")

        # Other settings
        table.add_row("Verify SSL", "✓" if settings.verify_ssl else "✗")

        console.print(table)

        # Show enabled entity kinds
        console.print("\n[bold]Enabled Entity Kinds:[/bold]")
        for kind in settings.enabled_entity_kinds:
            console.print(f"  - {kind}")

    except Exception as e:
        log_error(f"Failed to show config: {e}", exception=e)
        sys.exit(1)


@cli.command()
def init_env():
    """Create a sample .env file with required configuration."""
    sample_env = """# ------------------ REQUIRED ---------------- #
# Backstage Configuration
BACKSTAGE_BASE_URL=https://demos.backstage.io
BACKSTAGE_API_TOKEN=  # Optional, if your Backstage requires authentication

# Glean Configuration
GLEAN_INSTANCE_NAME=mycompany  # If your Glean backend domain is mycompany-prod-be.glean.com, your instance name will be 'mycompany-prod'
GLEAN_INDEXING_API_KEY=your-glean-indexing-api-key

# Default Permissions Settings
# What permissions to apply to Backstage items that don't have a specific permissions mapping to them.
# You will likely want to set this to 'datasource-users' or 'all-users'.
# Can be:
#    'datasource-users' -> Indexed items without explicit permissions are visible in Glean to any user with Backstage access (default).
#    'all-users'        -> Indexed items without explicit permissions are visible in Glean to ALL users; regardless of whether they have Backstage access or not.
#    'owner'            -> Indexed items without explicit permissions are visible only to the owner (if specified, and only if the owner is a user, not a group); otherwise this is the same as none.
#    'none'             -> Indexed items without explicit permissions are visible to no one (there shouldn't really be a reason why you would want this).
DEFAULT_PERMISSIONS=datasource-users


# ------------------ OPTIONAL ---------------- #

# Test Mode Configuration
# - Hides the datasource in search from all users except test users
# - Disables search ranking signals for all pushed data
GLEAN_DATASOURCE_IS_TEST_MODE=true

# Test Users
# - If TEST MODE is enabled (above), you can provide a comma-separated list of test user emails here.
# - Default: No test users defined (can also be added in the UI)
# GLEAN_DATASOURCE_TEST_USER_EMAILS=user1@company.com,user2@company.com


# ------------------ ADVANCED ---------------- #
# Don't change these unless you know what you're doing!

# Datasource Configuration
GLEAN_DATASOURCE_ID=backstage
GLEAN_DATASOURCE_DISPLAY_NAME=Backstage

# Sync Configuration
SYNC_USERS_ENABLED=true
SYNC_GROUPS_ENABLED=true
SYNC_COMPONENTS_ENABLED=true
SYNC_APIS_ENABLED=true
SYNC_SYSTEMS_ENABLED=true
SYNC_DOMAINS_ENABLED=true
SYNC_RESOURCES_ENABLED=true

# Sync batch size
SYNC_BATCH_SIZE=50

# Other Settings
VERIFY_SSL=true
BACKSTAGE_PAGE_SIZE=100


# ------------------ DATASOURCE SETUP ---------------- #
# Only needed for the initial setup of the Datasource
# Don't change these unless you have a specific reason to.

GLEAN_DATASOURCE_HOME_URL=${BACKSTAGE_BASE_URL}/home
GLEAN_DATASOURCE_URL_REGEX=${BACKSTAGE_BASE_URL}/.*
GLEAN_DATASOURCE_CATEGORY=KNOWLEDGE_HUB

# Icon Configuration (use either filenames or URLs)
# 'icon-lightmode.png' and 'icon-darkmode.png' are used by default if present
# GLEAN_DATASOURCE_ICON_FILENAME_LIGHTMODE=icon_lightmode.png
# GLEAN_DATASOURCE_ICON_URL_LIGHTMODE=https://myapp.com/logo.png
# GLEAN_DATASOURCE_ICON_FILENAME_DARKMODE=icon_darkmode.png
# GLEAN_DATASOURCE_ICON_URL_DARKMODE=https://myapp.com/logo-dark.png

# Identity Configuration
GLEAN_DATASOURCE_USER_REFERENCED_BY_EMAIL=false"""

    try:
        with open(".env", "w") as f:
            f.write(sample_env)

        console.print("[bold green]Created .env file with sample configuration[/bold green]")
        console.print("Please edit the .env file and add your actual API keys and URLs")

    except Exception as e:
        log_error(f"Failed to create .env file: {e}", exception=e)
        sys.exit(1)


@cli.group()
def show():
    """Display Backstage entities in human-readable format."""
    pass


@show.command()
@click.option("--limit", default=50, help="Maximum number of entities to display")
def users(limit: int):
    """Display users from Backstage catalog."""
    try:
        settings = get_settings()
        backstage_client = BackstageClient(settings)

        with Live(
            Spinner("dots", text=f"Fetching users (limit: {limit})...", style="cyan"),
            console=console,
            refresh_per_second=10,
        ):
            entities = []
            async def fetch():
                count = 0
                async for entity in backstage_client.fetch_entities(kind="User"):
                    entities.append(entity)
                    count += 1
                    if count >= limit:
                        break
                return entities

            users_list = asyncio.run(fetch())

        if not users_list:
            console.print("[yellow]No users found in Backstage catalog[/yellow]")
            return

        # Check for duplicates by email
        unique_users, duplicates = deduplicate_users_by_email(users_list)

        # Create table
        table = Table(title=f"Backstage Users (showing {len(users_list)} users, {len(unique_users)} unique by email)")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Namespace", style="dim")
        table.add_column("Email", style="green")
        table.add_column("Display Name", style="yellow")
        table.add_column("Member Of", style="blue")

        # Show all users (including duplicates) but mark them
        seen_emails = set()
        for user in users_list:
            spec = user.spec
            profile = spec.get("profile", {}) or {}
            member_of = spec.get("memberOf", [])
            email = get_user_email(spec)

            # Normalize member references
            normalized_members = normalize_member_refs(member_of)

            # Mark duplicates
            name_display = user.metadata.name
            if email in seen_emails:
                name_display = f"{name_display} [dim](duplicate)[/dim]"
            seen_emails.add(email)

            table.add_row(
                name_display,
                user.metadata.namespace,
                email,
                profile.get("displayName", ""),
                ", ".join(normalized_members) if normalized_members else "",
            )

        console.print(table)

        # Show duplicate summary if any
        if duplicates:
            console.print("\n[bold yellow]Duplicate Users (same email):[/bold yellow]")
            dup_table = Table()
            dup_table.add_column("Email", style="yellow")
            dup_table.add_column("Users", style="cyan")
            dup_table.add_column("Namespaces", style="dim")

            for email, dup_users in duplicates.items():
                user_names = [u.metadata.name for u in dup_users]
                namespaces = [f"{u.metadata.namespace}/{u.metadata.name}" for u in dup_users]
                dup_table.add_row(
                    email,
                    ", ".join(user_names),
                    ", ".join(namespaces)
                )

            console.print(dup_table)

    except Exception as e:
        log_error(f"Failed to show users: {e}", exception=e)
        sys.exit(1)


@show.command()
@click.option("--limit", default=50, help="Maximum number of entities to display")
def groups(limit: int):
    """Display groups from Backstage catalog."""
    try:
        settings = get_settings()
        backstage_client = BackstageClient(settings)

        with Live(
            Spinner("dots", text="Fetching groups and computing membership...", style="cyan"),
            console=console,
            refresh_per_second=10,
        ):
            # Fetch both groups and users to calculate membership
            entities = []
            users = []

            async def fetch():
                nonlocal users
                count = 0
                # Fetch groups
                async for entity in backstage_client.fetch_entities(kind="Group"):
                    entities.append(entity)
                    count += 1
                    if count >= limit:
                        break

                # Fetch all users to calculate group membership
                async for user in backstage_client.fetch_entities(kind="User"):
                    users.append(user)

                return entities

            groups_list = asyncio.run(fetch())

        if not groups_list:
            console.print("[yellow]No groups found in Backstage catalog[/yellow]")
            return

        # Build membership map from users
        members_by_group = build_members_by_group(users)

        # Create table
        table = Table(title=f"Backstage Groups (showing {len(groups_list)} of {limit} max)")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("Display Name", style="yellow")
        table.add_column("Members", style="green", justify="right")
        table.add_column("Parent", style="blue")

        for group in groups_list:
            spec = group.spec
            profile = spec.get("profile", {}) or {}

            # Get member count from the membership map
            member_count = len(members_by_group.get(group.metadata.name, set()))

            # Normalize parent reference
            parent = spec.get("parent", "")
            if parent:
                parent = extract_name_from_ref(parent)

            table.add_row(
                group.metadata.name,
                spec.get("type", "team"),
                profile.get("displayName", ""),
                str(member_count),
                parent,
            )

        console.print(table)

    except Exception as e:
        log_error(f"Failed to show groups: {e}", exception=e)
        sys.exit(1)


@show.command()
@click.option("--limit", default=50, help="Maximum number of entities to display")
def components(limit: int):
    """Display components from Backstage catalog."""
    try:
        settings = get_settings()
        backstage_client = BackstageClient(settings)

        with Live(
            Spinner("dots", text=f"Fetching components (limit: {limit})...", style="cyan"),
            console=console,
            refresh_per_second=10,
        ):
            entities = []
            async def fetch():
                count = 0
                async for entity in backstage_client.fetch_entities(kind="Component"):
                    entities.append(entity)
                    count += 1
                    if count >= limit:
                        break
                return entities

            components_list = asyncio.run(fetch())

        if not components_list:
            console.print("[yellow]No components found in Backstage catalog[/yellow]")
            return

        # Create table
        table = Table(title=f"Backstage Components (showing {len(components_list)} of {limit} max)")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("Lifecycle", style="yellow")
        table.add_column("Owner", style="green")
        table.add_column("System", style="blue")

        for component in components_list:
            spec = component.spec

            # Normalize owner and system references
            owner = spec.get("owner", "")
            if owner:
                owner = extract_name_from_ref(owner)
            system = spec.get("system", "")
            if system:
                system = extract_name_from_ref(system)

            table.add_row(
                component.metadata.name,
                spec.get("type", ""),
                spec.get("lifecycle", ""),
                owner,
                system,
            )

        console.print(table)

    except Exception as e:
        log_error(f"Failed to show components: {e}", exception=e)
        sys.exit(1)


@show.command()
@click.option("--limit", default=50, help="Maximum number of entities to display")
def apis(limit: int):
    """Display APIs from Backstage catalog."""
    try:
        settings = get_settings()
        backstage_client = BackstageClient(settings)

        with Live(
            Spinner("dots", text=f"Fetching APIs (limit: {limit})...", style="cyan"),
            console=console,
            refresh_per_second=10,
        ):
            entities = []
            async def fetch():
                count = 0
                async for entity in backstage_client.fetch_entities(kind="API"):
                    entities.append(entity)
                    count += 1
                    if count >= limit:
                        break
                return entities

            apis_list = asyncio.run(fetch())

        if not apis_list:
            console.print("[yellow]No APIs found in Backstage catalog[/yellow]")
            return

        # Create table
        table = Table(title=f"Backstage APIs (showing {len(apis_list)} of {limit} max)")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("Lifecycle", style="yellow")
        table.add_column("Owner", style="green")
        table.add_column("System", style="blue")

        for api in apis_list:
            spec = api.spec

            # Normalize owner and system references
            owner = spec.get("owner", "")
            if owner:
                owner = extract_name_from_ref(owner)
            system = spec.get("system", "")
            if system:
                system = extract_name_from_ref(system)

            table.add_row(
                api.metadata.name,
                spec.get("type", ""),
                spec.get("lifecycle", ""),
                owner,
                system,
            )

        console.print(table)

    except Exception as e:
        log_error(f"Failed to show APIs: {e}", exception=e)
        sys.exit(1)


@show.command()
@click.option("--limit", default=50, help="Maximum number of entities to display")
def systems(limit: int):
    """Display systems from Backstage catalog."""
    try:
        settings = get_settings()
        backstage_client = BackstageClient(settings)

        with Live(
            Spinner("dots", text=f"Fetching systems (limit: {limit})...", style="cyan"),
            console=console,
            refresh_per_second=10,
        ):
            entities = []
            async def fetch():
                count = 0
                async for entity in backstage_client.fetch_entities(kind="System"):
                    entities.append(entity)
                    count += 1
                    if count >= limit:
                        break
                return entities

            systems_list = asyncio.run(fetch())

        if not systems_list:
            console.print("[yellow]No systems found in Backstage catalog[/yellow]")
            return

        # Create table
        table = Table(title=f"Backstage Systems (showing {len(systems_list)} of {limit} max)")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Owner", style="green")
        table.add_column("Domain", style="magenta")
        table.add_column("Description", style="yellow")

        for system in systems_list:
            spec = system.spec

            # Normalize owner and domain references
            owner = spec.get("owner", "")
            if owner:
                owner = extract_name_from_ref(owner)
            domain = spec.get("domain", "")
            if domain:
                domain = extract_name_from_ref(domain)

            table.add_row(
                system.metadata.name,
                owner,
                domain,
                system.metadata.description or "",
            )

        console.print(table)

    except Exception as e:
        log_error(f"Failed to show systems: {e}", exception=e)
        sys.exit(1)


@show.command()
@click.option("--limit", default=50, help="Maximum number of entities to display")
def domains(limit: int):
    """Display domains from Backstage catalog."""
    try:
        settings = get_settings()
        backstage_client = BackstageClient(settings)

        with Live(
            Spinner("dots", text=f"Fetching domains (limit: {limit})...", style="cyan"),
            console=console,
            refresh_per_second=10,
        ):
            entities = []
            async def fetch():
                count = 0
                async for entity in backstage_client.fetch_entities(kind="Domain"):
                    entities.append(entity)
                    count += 1
                    if count >= limit:
                        break
                return entities

            domains_list = asyncio.run(fetch())

        if not domains_list:
            console.print("[yellow]No domains found in Backstage catalog[/yellow]")
            return

        # Create table
        table = Table(title=f"Backstage Domains (showing {len(domains_list)} of {limit} max)")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Owner", style="green")
        table.add_column("Description", style="yellow")

        for domain in domains_list:
            spec = domain.spec

            # Normalize owner reference
            owner = spec.get("owner", "")
            if owner:
                owner = extract_name_from_ref(owner)

            table.add_row(
                domain.metadata.name,
                owner,
                domain.metadata.description or "",
            )

        console.print(table)

    except Exception as e:
        log_error(f"Failed to show domains: {e}", exception=e)
        sys.exit(1)


@show.command()
@click.option("--limit", default=50, help="Maximum number of entities to display")
def resources(limit: int):
    """Display resources from Backstage catalog."""
    try:
        settings = get_settings()
        backstage_client = BackstageClient(settings)

        with Live(
            Spinner("dots", text=f"Fetching resources (limit: {limit})...", style="cyan"),
            console=console,
            refresh_per_second=10,
        ):
            entities = []
            async def fetch():
                count = 0
                async for entity in backstage_client.fetch_entities(kind="Resource"):
                    entities.append(entity)
                    count += 1
                    if count >= limit:
                        break
                return entities

            resources_list = asyncio.run(fetch())

        if not resources_list:
            console.print("[yellow]No resources found in Backstage catalog[/yellow]")
            return

        # Create table
        table = Table(title=f"Backstage Resources (showing {len(resources_list)} of {limit} max)")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("Owner", style="green")
        table.add_column("System", style="blue")

        for resource in resources_list:
            spec = resource.spec

            # Normalize owner and system references
            owner = spec.get("owner", "")
            if owner:
                owner = extract_name_from_ref(owner)
            system = spec.get("system", "")
            if system:
                system = extract_name_from_ref(system)

            table.add_row(
                resource.metadata.name,
                spec.get("type", ""),
                owner,
                system,
            )

        console.print(table)

    except Exception as e:
        log_error(f"Failed to show resources: {e}", exception=e)
        sys.exit(1)


if __name__ == "__main__":
    cli()
