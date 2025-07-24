"""Main sync orchestration logic."""

from datetime import datetime

from rich.table import Table
from uuid_extensions import uuid7

from .backstage_client import BackstageClient
from .config import Settings, get_settings
from .glean_client import GleanClient
from .logging import console, log_error, log_info, log_warning
from .mapper import BackstageToGleanMapper
from .utils import deduplicate_users_by_email


class BackstageGleanSync:
    """Orchestrates the sync from Backstage to Glean."""

    def __init__(self, settings: Settings | None = None):
        """Initialize the sync orchestrator."""
        self.settings = settings or get_settings()
        self.backstage_client = BackstageClient(self.settings)
        self.glean_client = GleanClient(self.settings)
        self.mapper = BackstageToGleanMapper(
            str(self.settings.backstage_base_url),
            self.settings.glean_datasource_id,
            self.settings,
        )

    async def test_connections(self) -> bool:
        """Test connections to both Backstage and Glean."""
        log_info("Testing connections...")

        # Test Backstage connection
        try:
            backstage_ok = await self.backstage_client.test_connection()
            if not backstage_ok:
                console.print(f"[bold red]Failed to connect to Backstage at {self.settings.backstage_base_url}[/bold red]")
                console.print("[dim]Please check your BACKSTAGE_BASE_URL and network connectivity[/dim]")
                return False
        except Exception as e:
            console.print(f"[bold red]Backstage connection error: {e}[/bold red]")
            return False

        # Test Glean connection
        try:
            glean_ok = await self.glean_client.test_connection()
            if not glean_ok:
                if self.settings.dry_run:
                    log_warning("Failed to connect to Glean (continuing in dry-run mode)")
                else:
                    console.print(f"[bold red]Failed to connect to Glean instance: {self.settings.glean_instance_name}[/bold red]")
                    console.print("[dim]Please check your GLEAN_INSTANCE_NAME and GLEAN_INDEXING_API_KEY[/dim]")
                    return False
        except Exception as e:
            if self.settings.dry_run:
                log_warning(f"Glean connection error: {e} (continuing in dry-run mode)")
            else:
                console.print(f"[bold red]Glean connection error: {e}[/bold red]")
                return False

        log_info("All connections successful")
        return True

    async def test_backstage_detailed(self) -> tuple[bool, str]:
        """Test Backstage connection with detailed message."""
        try:
            success = await self.backstage_client.test_connection()
            if success:
                return True, f"{self.settings.backstage_base_url}"
            else:
                return False, "Unable to connect to API"
        except Exception as e:
            return False, str(e)

    async def test_glean_detailed(self) -> tuple[bool, str]:
        """Test Glean connection with detailed message."""
        try:
            success = await self.glean_client.test_connection()
            if success:
                return True, f"Instance: {self.settings.glean_instance_name}"
            else:
                return False, "Unable to connect to API"
        except Exception as e:
            return False, str(e)

    async def sync_users_and_groups(self) -> bool:
        """Sync users and groups from Backstage to Glean."""
        log_info("Syncing users and groups...")

        # Fetch users and groups
        users, groups = await self.backstage_client.fetch_users_and_groups()

        if not users and not groups:
            log_info("No users or groups to sync")
            return True

        # Deduplicate users by email
        unique_users, duplicates = deduplicate_users_by_email(users)

        if duplicates:
            log_info(f"Found {len(duplicates)} duplicate user emails, deduplicating...")
            for email, dup_users in duplicates.items():
                user_info = [f"{u.metadata.namespace}/{u.metadata.name}" for u in dup_users]
                log_info(f"  Email {email} used by: {', '.join(user_info)}")

        # Map to Glean format (using deduplicated users)
        glean_users = [self.mapper.map_user_to_glean(user) for user in unique_users]
        glean_groups = [self.mapper.map_group_to_glean(group) for group in groups]
        # Pass deduplicated users for membership mapping
        memberships = self.mapper.map_group_memberships(unique_users, groups)

        # Push to Glean
        success = True

        if glean_users:
            log_info(f"Pushing {len(glean_users)} unique users to Glean...")
            success &= await self.glean_client.push_users(glean_users)

        if glean_groups:
            log_info(f"Pushing {len(glean_groups)} groups to Glean...")
            success &= await self.glean_client.push_groups(glean_groups)

        if memberships:
            log_info(f"Pushing {len(memberships)} group memberships to Glean...")
            success &= await self.glean_client.push_memberships(memberships)

        return success

    async def sync_entities(self) -> bool:
        """Sync all other entities from Backstage to Glean."""
        log_info("Syncing catalog entities...")

        # Fetch entities
        all_entities = []
        fetch_summary = {}

        entity_kinds = [
            kind for kind in self.settings.enabled_entity_kinds
            if kind not in ["User", "Group"]  # Already handled separately
        ]

        # Show fetch progress
        console.print("\n[bold]Fetching entities from Backstage:[/bold]")
        fetch_table = Table(box=None)
        fetch_table.add_column("Entity Type", style="cyan")
        fetch_table.add_column("Count", justify="right", style="green")

        for kind in entity_kinds:
            entities = []
            async for entity in self.backstage_client.fetch_entities(kind=kind):
                entities.append(entity)
                all_entities.append(entity)
            fetch_summary[kind] = len(entities)
            if len(entities) > 0:
                fetch_table.add_row(f"{kind}s", str(len(entities)))

        console.print(fetch_table)

        if not all_entities:
            log_info("No catalog entities to sync")
            return True

        # Build entity lookup map for relationship resolution
        entity_map = {}
        for entity in all_entities:
            # Store by full reference
            entity_map[entity.ref] = entity
            # Also store by name for easier lookup
            entity_map[entity.metadata.name] = entity
            # Store with namespace for unique identification
            entity_map[f"{entity.metadata.namespace}/{entity.metadata.name}"] = entity

        # Map to Glean documents
        console.print(f"\n[bold]Mapping {len(all_entities)} entities to Glean format...[/bold]")
        documents = []
        mapping_errors = []

        for entity in all_entities:
            try:
                doc = self.mapper.map_entity_to_document(entity, entity_map)
                documents.append(doc)
            except Exception as e:
                mapping_errors.append(f"{entity.kind}:{entity.metadata.name} - {str(e)}")

        if mapping_errors:
            console.print(f"\n[yellow]⚠️  Warning: {len(mapping_errors)} entities failed to map:[/yellow]")
            for error in mapping_errors[:5]:  # Show first 5 errors
                console.print(f"  - {error}")
            if len(mapping_errors) > 5:
                console.print(f"  ... and {len(mapping_errors) - 5} more")

        # Push to Glean
        if self.settings.dry_run:
            console.print(f"\n[bold]Would push {len(documents)} documents to Glean...[/bold]")
        else:
            console.print(f"\n[bold]Pushing {len(documents)} documents to Glean...[/bold]")
        success = await self.glean_client.push_documents(documents)

        # Show summary
        if success:
            if self.settings.dry_run:
                console.print(f"[yellow]✅ Would push {len(documents)} documents[/yellow]")
            else:
                console.print(f"[green]✅ Successfully pushed {len(documents)} documents[/green]")
        else:
            console.print("[red]❌ Failed to push some documents[/red]")

        return success

    async def run_sync(self) -> bool:
        """Run the full sync process."""
        start_time = datetime.now()
        log_info(f"Starting Backstage to Glean sync at {start_time.isoformat()}")

        try:
            # Validate configuration
            if not self._validate_configuration():
                return False
            
            # Test connections
            if not await self.test_connections():
                return False

            # Setup datasource
            if not self.settings.dry_run:
                if not await self.glean_client.setup_datasource():
                    return False

            # Sync users and groups first (needed for permissions)
            if not await self.sync_users_and_groups():
                log_error("Failed to sync users and groups")
                return False

            # Sync all other entities
            if not await self.sync_entities():
                log_error("Failed to sync entities")
                return False

            # Trigger process all documents to remove stale content
            if not self.settings.dry_run:
                await self.glean_client.trigger_process_all_documents()

            duration = (datetime.now() - start_time).total_seconds()

            # Show final summary
            console.print("\n" + "="*50)
            if self.settings.dry_run:
                console.print("[bold yellow]✅ Dry run completed successfully![/bold yellow]")
                console.print("[dim]This was a preview - no data was pushed to Glean[/dim]")
            else:
                console.print("[bold green]✅ Sync completed successfully![/bold green]")
            console.print(f"[dim]Total time: {duration:.1f} seconds[/dim]")
            console.print("="*50)
            return True

        except Exception as e:
            log_error(f"Sync failed with error: {e}", exception=e)
            return False

        finally:
            # Cleanup
            await self.glean_client.close()

    async def run_dry_run(self) -> bool:
        """Run a dry run to preview what would be synced."""
        self.settings.dry_run = True
        console.print("[bold yellow]Running in DRY RUN mode - no data will be pushed to Glean[/bold yellow]")
        return await self.run_sync()

    async def run_dry_run_with_summary(self) -> tuple[bool, dict]:
        """Run a dry run and return summary information."""
        # Preserve the original output_json setting
        original_output_json = self.settings.output_json
        self.settings.dry_run = True
        # Restore output_json if it was set
        if original_output_json:
            self.settings.output_json = True
        start_time = datetime.now()

        try:
            # Test connections first
            connection_table = Table(title="Connection Status")
            connection_table.add_column("Service", style="cyan")
            connection_table.add_column("Status", style="bold")
            connection_table.add_column("Details")

            backstage_ok, backstage_msg = await self.test_backstage_detailed()
            glean_ok, glean_msg = await self.test_glean_detailed()

            connection_table.add_row(
                "Backstage API",
                "✅ Connected" if backstage_ok else "❌ Failed",
                backstage_msg
            )
            connection_table.add_row(
                "Glean API",
                "✅ Connected" if glean_ok else "❌ Failed",
                glean_msg
            )

            console.print(connection_table)
            console.print()

            # Only require Backstage connection for dry run
            if not backstage_ok:
                console.print("\n[bold red]Cannot proceed without Backstage connection[/bold red]")
                return False, {}

            if not glean_ok:
                console.print("\n[bold yellow]⚠️  Glean connection failed - showing Backstage data only[/bold yellow]")

            # Fetch and analyze entities
            console.print("Analyzing Backstage catalog...")

            try:
                # Count entities by type
                entity_counts = {}
                users, groups = await self.backstage_client.fetch_users_and_groups()
                entity_counts["Users"] = len(users)
                entity_counts["Groups"] = len(groups)

                # Count other entities
                other_entities = []
                for kind in ["Component", "API", "System", "Domain", "Resource"]:
                    if kind in self.settings.enabled_entity_kinds:
                        count = 0
                        async for _ in self.backstage_client.fetch_entities(kind=kind):
                            count += 1
                        entity_counts[f"{kind}s"] = count
                        other_entities.extend([kind] * count)
            except Exception as e:
                console.print(f"\n[red]Error fetching entities: {e}[/red]")
                return False, {}

            # Create summary table
            summary_table = Table(title="Entities to Sync")
            summary_table.add_column("Entity Type", style="cyan")
            summary_table.add_column("Count", justify="right", style="green")
            summary_table.add_column("Status", justify="center")

            total_entities = 0
            for entity_type, count in entity_counts.items():
                if count > 0:
                    summary_table.add_row(
                        entity_type,
                        str(count),
                        "✅ Enabled"
                    )
                    total_entities += count

            console.print(summary_table)
            console.print()

            # Show sync details
            details_table = Table(title="Sync Configuration")
            details_table.add_column("Setting", style="cyan")
            details_table.add_column("Value", style="yellow")

            details_table.add_row("Datasource", self.settings.glean_datasource_id)
            details_table.add_row("Batch Size", str(self.settings.sync_batch_size))
            details_table.add_row("Total Entities", str(total_entities))

            # Calculate estimated batches
            doc_count = len(other_entities)
            if doc_count > 0:
                estimated_batches = (doc_count + self.settings.sync_batch_size - 1) // self.settings.sync_batch_size
                details_table.add_row("Document Batches", str(estimated_batches))

            console.print(details_table)

            duration = (datetime.now() - start_time).total_seconds()
            console.print(f"\n[dim]Analysis completed in {duration:.1f} seconds[/dim]")

            # If output_json is enabled, actually run the sync to generate JSON files
            if self.settings.output_json:
                console.print("\n[bold]Running sync to generate JSON output files...[/bold]")
                sync_success = await self.run_sync()
                if sync_success:
                    console.print(f"[green]✅ JSON files saved to: {self.settings.output_json_dir}/[/green]")
                return sync_success, entity_counts
            
            return True, entity_counts

        except Exception as e:
            log_error(f"Dry run failed: {e}", exception=e)
            return False, {}
    
    def _validate_configuration(self) -> bool:
        """Validate required configuration settings."""
        errors = []
        
        # Check Backstage configuration
        if not self.settings.backstage_base_url:
            errors.append("BACKSTAGE_BASE_URL is not set")
        
        # Check Glean configuration
        if not self.settings.glean_instance_name:
            errors.append("GLEAN_INSTANCE_NAME is not set")
        
        if not self.settings.glean_indexing_api_key:
            errors.append("GLEAN_INDEXING_API_KEY is not set")
        
        if not self.settings.glean_datasource_id:
            errors.append("GLEAN_DATASOURCE_ID is not set")
        
        # Check if any entity types are enabled
        if not self.settings.enabled_entity_kinds:
            errors.append("No entity types are enabled for sync")
        
        if errors:
            console.print("[bold red]Configuration Error:[/bold red]")
            for error in errors:
                console.print(f"  ❌ {error}")
            console.print("\n[dim]Please check your .env file or environment variables[/dim]")
            return False
        
        return True
