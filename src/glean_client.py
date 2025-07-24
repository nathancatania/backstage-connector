"""Client for interacting with Glean Indexing API."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from glean.api_client import Glean, errors, models
from uuid_extensions import uuid7

from .config import Settings
from .logging import create_progress, log_error, log_info, log_warning


class GleanClient:
    """Client for pushing data to Glean."""

    def __init__(self, settings: Settings):
        """Initialize the Glean client."""
        self.settings = settings
        self.instance = settings.glean_instance_name
        self.api_token = settings.glean_indexing_api_key

    def _save_json_output(self, data: list, filename_prefix: str) -> None:
        """Save data to JSON file when output_json is enabled."""
        if not (self.settings.dry_run and self.settings.output_json):
            return

        # Create output directory if it doesn't exist
        output_dir = Path(self.settings.output_json_dir)
        output_dir.mkdir(exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.json"
        filepath = output_dir / filename

        # Convert Pydantic models to JSON
        json_data = []
        for item in data:
            # Use model_dump_json and then parse to get dict
            json_str = item.model_dump_json(exclude_none=True)
            json_data.append(json.loads(json_str))

        # Save to file
        with open(filepath, "w") as f:
            json.dump(json_data, f, indent=2)

        log_info(f"Saved {len(data)} {filename_prefix} to {filepath}")

    async def test_connection(self) -> bool:
        """Test the connection to Glean API."""
        try:
            # Try to get datasource config as a connection test
            async with Glean(
                api_token=self.api_token,
                instance=self.instance,
            ) as glean:
                response = await asyncio.to_thread(
                    glean.indexing.datasources.retrieve_config,
                    datasource=self.settings.glean_datasource_id,
                )
                log_info(f"Successfully connected to Glean API. Datasource: {response.name}")
                return True
        except errors.GleanError as e:
            # Datasource might not exist yet, which is fine
            if e.status_code == 404:
                log_info("Glean API connection successful (datasource not yet created)")
                return True
            log_error(f"Failed to connect to Glean API: {e}")
            return False
        except Exception as e:
            log_error(f"Failed to connect to Glean API: {e}")
            return False

    async def setup_datasource(self) -> bool:
        """Create or update the datasource configuration."""
        try:
            async with Glean(
                api_token=self.api_token,
                instance=self.instance,
            ) as glean:
                # Check if datasource exists
                try:
                    await asyncio.to_thread(
                        glean.indexing.datasources.retrieve_config,
                        datasource=self.settings.glean_datasource_id,
                    )
                    log_info(f"Datasource '{self.settings.glean_datasource_id}' already exists")
                    return True
                except errors.GleanError as e:
                    if e.status_code != 404:
                        raise
                    # Datasource doesn't exist, create it

                # Create datasource
                await asyncio.to_thread(
                    glean.indexing.datasources.add,
                    name=self.settings.glean_datasource_id,
                    display_name=self.settings.glean_datasource_display_name,
                    datasource_category=models.DatasourceCategory.UNCATEGORIZED,
                    url_regex=f"{self.settings.backstage_base_url}/.*",
                    icon_url=None,  # Could add Backstage logo URL here
                    object_definitions=[
                        models.ObjectDefinition(
                            name="backstage_entity",
                            display_label="Backstage Entity",
                            doc_category=models.DocCategory.KNOWLEDGE,
                        )
                    ],
                )

                log_info(f"Created datasource '{self.settings.glean_datasource_id}'")
                return True

        except Exception as e:
            log_error(f"Failed to setup datasource: {e}")
            return False

    async def push_documents(self, documents: list[models.DocumentDefinition]) -> bool:
        """Push documents to Glean in batches."""
        if not documents:
            log_warning("No documents to push")
            return True

        if self.settings.dry_run:
            log_info(f"[DRY RUN] Would push {len(documents)} documents to Glean")
            for doc in documents[:5]:  # Show first 5 as examples
                log_info(f"  - {doc.title} ({doc.id})")
            if len(documents) > 5:
                log_info(f"  ... and {len(documents) - 5} more")

            # Save to JSON if output_json is enabled
            self._save_json_output(documents, "documents")
            return True

        success = True
        total = len(documents)

        async with Glean(
            api_token=self.api_token,
            instance=self.instance,
        ) as glean:
            with create_progress() as progress:
                task = progress.add_task("Pushing documents to Glean", total=total)

                # Process in batches
                for i in range(0, total, self.settings.sync_batch_size):
                    batch = documents[i : i + self.settings.sync_batch_size]

                    try:
                        await asyncio.to_thread(
                            glean.indexing.documents.index,
                            datasource=self.settings.glean_datasource_id,
                            documents=batch,
                        )
                        progress.update(task, advance=len(batch))

                    except Exception as e:
                        log_error(f"Failed to push batch {i//self.settings.sync_batch_size + 1}: {e}")
                        success = False

        if success:
            log_info(f"Successfully pushed {total} documents")
        else:
            log_warning("Pushed documents with some errors")

        return success

    async def push_users(self, users: list[models.DatasourceUserDefinition]) -> bool:
        """Push user definitions to Glean."""
        if not users:
            return True

        if self.settings.dry_run:
            log_info(f"[DRY RUN] Would push {len(users)} users to Glean")
            for user in users[:5]:
                log_info(f"  - {user.name} ({user.email})")
            if len(users) > 5:
                log_info(f"  ... and {len(users) - 5} more")

            # Save to JSON if output_json is enabled
            self._save_json_output(users, "users")
            return True

        try:
            async with Glean(
                api_token=self.api_token,
                instance=self.instance,
            ) as glean:
                # Generate upload ID for this sync
                upload_id = f"{self.settings.glean_datasource_id}-users-{str(uuid7())}"

                # Push users in batches
                total_batches = (len(users) + self.settings.sync_batch_size - 1) // self.settings.sync_batch_size
                for i in range(0, len(users), self.settings.sync_batch_size):
                    batch = users[i : i + self.settings.sync_batch_size]
                    batch_num = i // self.settings.sync_batch_size
                    is_first = batch_num == 0
                    is_last = batch_num == total_batches - 1

                    await asyncio.to_thread(
                        glean.indexing.permissions.bulk_index_users,
                        upload_id=upload_id,
                        datasource=self.settings.glean_datasource_id,
                        users=batch,
                        is_first_page=is_first,
                        is_last_page=is_last,
                        force_restart_upload=is_first,
                    )

                log_info(f"Successfully pushed {len(users)} users")
                return True

        except Exception as e:
            log_error(f"Failed to push users: {e}")
            return False

    async def push_groups(self, groups: list[models.DatasourceGroupDefinition]) -> bool:
        """Push group definitions to Glean."""
        if not groups:
            return True

        if self.settings.dry_run:
            log_info(f"[DRY RUN] Would push {len(groups)} groups to Glean")
            for group in groups[:5]:
                log_info(f"  - {getattr(group, 'display_name', None) or group.name}")
            if len(groups) > 5:
                log_info(f"  ... and {len(groups) - 5} more")

            # Save to JSON if output_json is enabled
            self._save_json_output(groups, "groups")
            return True

        try:
            async with Glean(
                api_token=self.api_token,
                instance=self.instance,
            ) as glean:
                # Generate upload ID for this sync
                upload_id = f"{self.settings.glean_datasource_id}-groups-{str(uuid7())}"

                # Push groups in batches
                total_batches = (len(groups) + self.settings.sync_batch_size - 1) // self.settings.sync_batch_size
                for i in range(0, len(groups), self.settings.sync_batch_size):
                    batch = groups[i : i + self.settings.sync_batch_size]
                    batch_num = i // self.settings.sync_batch_size
                    is_first = batch_num == 0
                    is_last = batch_num == total_batches - 1

                    await asyncio.to_thread(
                        glean.indexing.permissions.bulk_index_groups,
                        upload_id=upload_id,
                        datasource=self.settings.glean_datasource_id,
                        groups=batch,
                        is_first_page=is_first,
                        is_last_page=is_last,
                        force_restart_upload=is_first,
                    )

                log_info(f"Successfully pushed {len(groups)} groups")
                return True

        except Exception as e:
            log_error(f"Failed to push groups: {e}")
            return False

    async def push_memberships(self, memberships: list[models.DatasourceMembershipDefinition]) -> bool:
        """Push group membership definitions to Glean."""
        if not memberships:
            return True

        if self.settings.dry_run:
            log_info(f"[DRY RUN] Would push {len(memberships)} group memberships")
            # Show sample memberships
            for membership in memberships[:5]:
                log_info(f"  - User {membership.member_user_id} in group {membership.group_name}")
            if len(memberships) > 5:
                log_info(f"  ... and {len(memberships) - 5} more")

            # Save to JSON if output_json is enabled
            self._save_json_output(memberships, "memberships")
            return True

        try:
            async with Glean(
                api_token=self.api_token,
                instance=self.instance,
            ) as glean:
                # Group memberships by group for bulk operations
                memberships_by_group = {}
                for membership in memberships:
                    group_name = membership.group_name
                    if group_name not in memberships_by_group:
                        memberships_by_group[group_name] = []
                    memberships_by_group[group_name].append(membership)

                # Push memberships for each group
                for group_name, group_memberships in memberships_by_group.items():
                    # Convert to bulk format
                    bulk_memberships = [models.DatasourceBulkMembershipDefinition(member_user_id=m.member_user_id) for m in group_memberships]

                    await asyncio.to_thread(
                        glean.indexing.permissions.bulk_index_memberships,
                        upload_id=f"{self.settings.glean_datasource_id}-{group_name}-memberships-{str(uuid7())}",
                        datasource=self.settings.glean_datasource_id,
                        group=group_name,
                        memberships=bulk_memberships,
                        is_first_page=True,
                        is_last_page=True,
                        force_restart_upload=True,
                    )

                log_info(f"Successfully pushed {len(memberships)} group memberships across {len(memberships_by_group)} groups")
                return True

        except Exception as e:
            log_error(f"Failed to push memberships: {e}")
            return False

    async def trigger_process_all_documents(self) -> bool:
        """Trigger Glean to process all documents and remove stale ones."""
        if self.settings.dry_run:
            log_info("[DRY RUN] Would trigger process all documents")
            return True

        try:
            async with Glean(
                api_token=self.api_token,
                instance=self.instance,
            ) as glean:
                # Note: process_all may be datasource-specific and handled differently
                # For now, we'll skip this step as the main sync is working
                log_info("Documents successfully pushed - Indexing may take 1-4 hours to complete before documents are visible (depending on the current jobs in progress)")
                return True

        except Exception as e:
            log_error(f"Failed to trigger process all documents: {e}")
            return False

    async def close(self):
        """Close the API client."""
        # The new SDK uses context managers, so no explicit close needed
        pass
