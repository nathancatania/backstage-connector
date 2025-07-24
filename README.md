# Backstage Connector for Glean

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![UV](https://img.shields.io/badge/package%20manager-uv-purple.svg)](https://github.com/astral-sh/uv)

This is a custom Glean connector for Backstage.io.

It will push your catalog to Glean for indexing; making your entire software ecosystem searchable and discoverable through Glean's enterprise search and AI features.

![banner](img/banner.webp)

## TOC
- [🚀 Quick Start](#-quick-start)
- [📋 Overview](#-overview)
  - [Key Benefits](#key-benefits)
  - [What Gets Synced](#what-gets-synced)
- [🏗️ Architecture](#️-architecture)
- [🛠️ Installation](#️-installation)
  - [Prerequisites](#prerequisites)
  - [Configuring Backstage](#configuring-backstage)
  - [Verify Backstage User Format](#verify-backstage-user-format)
  - [Connector Setup](#connector-setup)
- [⚙️ Configuration](#️-configuration)
  - [Required Settings](#required-settings)
  - [Optional Settings](#optional-settings)
- [📘 CLI Reference](#-cli-reference)
  - [`test-connection`](#test-connection)
  - [`show-config`](#show-config)
  - [`dry-run`](#dry-run)
  - [`sync`](#sync)
- [🔄 Sync Process](#-sync-process)
  - [How It Works](#how-it-works)
- [🚨 Troubleshooting](#-troubleshooting)
  - [Common Issues](#common-issues)
  - [Getting Help](#getting-help)
- [🔒 Security Considerations](#-security-considerations)
- [💡 Example Use Cases](#-example-use-cases)
  - [Automated Daily Sync](#automated-daily-sync)
  - [CI/CD Integration](#cicd-integration)
  - [Selective Sync](#selective-sync)
- [🤝 Contributing](#-contributing)
  - [Development Setup](#development-setup)
  - [Code Standards](#code-standards)
  - [Submitting Changes](#submitting-changes)
- [📝 License](#-license)


## 🚀 Quick Start

* You will need a Backstage API key and Glean Indexing API key.
* Your Glean Indexing API key must have the scope `backstage`

```bash
# Clone and install
git clone https://github.com/nathancatania/backstage-connector.git
cd backstage-connector
uv sync

# Configure
cp .env.example .env
# Edit .env with your credentials

# Setup the datasource config in Glean
uv run https://raw.githubusercontent.com/nathancatania/glean-datasource-manager/refs/heads/main/manage.py setup --silent

# Test API credentials
uv run backstage-sync test-connection

# Do a test pull from Backstage
uv run backstage-sync sync --dry-run

# Sync to Glean
uv run backstage-sync sync
```

## 📋 Overview

The Backstage to Glean Connector bridges your Backstage software catalog with Glean's enterprise search platform. It automatically syncs your components, APIs, systems, teams, and documentation, making them instantly searchable with proper access controls.

### Key Benefits

- **Unified Search**: Find any service, API, or system across your organization through Glean
- **Access Control**: Respects Backstage ownership and permissions in Glean search results
- **Real-time Sync**: Keep your Glean index up-to-date with scheduled or on-demand syncs
- **Zero Code Changes**: Works with existing Backstage deployments without modifications

### What Gets Synced

- **Catalog Entities**: Components, APIs, Systems, Domains, Resources
- **Identity & Access**: Users, Groups, and their relationships
- **Metadata**: Descriptions, tags, links, documentation, and custom attributes
- **Permissions**: Ownership and group memberships for secure search

## 🏗️ Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌───────────────┐
│                 │         │                  │         │               │
│   Backstage     │ ──API──▶│    Connector     │ ──API──▶│    Glean      │
│                 │         │                  │         │               │
│ • Components    │         │ • Fetch Entities │         │ • Documents   │
│ • APIs          │         │ • Map Data       │         │ • Identity    │
│ • Domains       │         │ • Sync Identity  │         │ • Permissions │
│ • Resources     │         │ • Push Entities  │         │               │
│ • Systems       │         │ • Handle Errors  │         │               │
│ • Users/Groups  │         │                  │         │               │
│                 │         │                  │         │               │
└─────────────────┘         └──────────────────┘         └───────────────┘
```

## 🛠️ Installation

### Prerequisites

- Backstage Static Auth Token (see Configuring Backstage below)
- Glean Indexing API key with `backstage` scope
  - Link: [Creating Indexing API Tokens (developers.glean.com)](https://developers.glean.com/api-info/indexing/authentication/overview#creating-indexing-api-tokens)
- Python 3.13 or higher
- [UV package manager](https://github.com/astral-sh/uv)
  ```bash
  # macOS
  brew install uv

  # Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Windows
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```


### Configuring Backstage

A Static Auth token will be created in Backstage for the connector to use. This token will be scoped for READ access to the Catalog only.

1. **Generate a secure auth token**
    ```bash
    # Generate a token using Python
    python -c "import secrets; print(secrets.token_urlsafe(32))"

    # OR

    # Generate a token using node
    node -p 'require("crypto").randomBytes(32).toString("base64")'
    ```

2. **Add the auth token to the Backstage app config**
    ```yaml
    backend:
      auth:
        externalAccess:
          - type: static
            options:
              token: token-generated-in-step-1-above
              subject: "glean-backstage-connector"
            accessRestrictions:
              - plugin: catalog
                permissionAttribute:
                  action:
                    - read
    ```
    * This will either be in `app-config.yml`, or `app-config.production.yaml` depending on how your Backstage deployment is configured.
    * The `subject` can be whatever you like. It is used for logging purposes within Backstage.
    * The `accessRestrictions` only permit the token to READ from the Catalog plugin. It is not able to perform any other action, or access any other data.

> [!IMPORTANT]
> There may be multiple `auth` sections in the config! Ensure you add the configuration at the right level!

   * It is important that the `externalAccess` section is placed under `auth` underneath the root `backend` section: You may need to add this if it is not there already.

   * Do not get confused with the `auth` section that contains the sign-in settings for the frontend! Placing the `externalAccess` section here will mean your token will not work! An example is below:

     ```yaml
     auth:
       # NOT THIS AUTH STANZA!!
       providers:
         guest: {}
         github:
           development:
             clientId: redacted
             clientSecret: redacted
             signIn:
               resolvers:
                 - resolver: usernameMatchingUserEntityName
     backend:
       auth:
         # THIS ONE below 'backend'. You might need to add this if it isn't there already!
         externalAccess:
           - type: static
             options:
               token: token-generated-in-step-1-above
               subject: "glean-backstage-connector"
             accessRestrictions:
               - plugin: catalog
                 permissionAttribute:
                   action:
                     - read
     ```

3. **Start Backstage**
     ```bash
     yarn start
     ```

4. **Verify the token works**
      ```bash
      curl -X GET "{your_backstage_base_url}/api/catalog/entities" -H "Authorization: Bearer token-generated-in-step-1-above"
      ```

   * If you get a response that is just an empty list, `[]`, the access restrictions/permissions for the token are set incorrectly.

### Verify Backstage User Format
In Backstage, all of your users must have an email address associated with them. Without this, the connector will not be able to match your Backstage user accounts to accounts in your corporate directory when syncing to Glean.

To check this, you can make a call to the Backstage API yourself using Postman/Bruno/Curl and the auth token created. Check whether there is an `email` parameter under the `spec` section for each user record returned.
```
curl -X GET "{your_backstage_base_url}/api/catalog/entities/by-query?filter=kind=user&limit=1" -H "Authorization: Bearer token-generated-in-step-1-above"

...
{
  "metadata": {
    ...
    "name": "samsample",
    ...
  },
  "apiVersion": "backstage.io/v1alpha1",
  "kind": "User",
  "spec": {
    "memberOf": [...],
    "profile": {
      "displayName": "Sam Sample",
      "email": "sam@company.com"    <--- You want to look for this
    }
  },
  "relations": [...]
},
...
```

If your users do not have an email address associated with them, a workaround for this is to set the `DEFAULT_PERMISSIONS` variable for the connector (see below) to `all-users`. This tells the connector not to care about user identities & permissions, and make Backstage content available to all Glean users.

### Connector Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd backstage-connector
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Configure environment**
   ```bash
   # Generate template .env file
   uv run backstage-sync init-env
   
   # Edit .env with your credentials
   nano .env
   ```

4. **Verify setup**
   ```bash
   uv run backstage-sync test-connection
   ```

5. **Perform a test pull from Backstage**
   ```bash
   uv run backstage-sync sync --dry-run
   ```

5. **Sync to Glean**
   ```bash
   uv run backstage-sync sync
   ```

## ⚙️ Configuration

### Required Settings

| Variable                 | Description                              | Example                         |
| ------------------------ | ---------------------------------------- | ------------------------------- |
| `BACKSTAGE_BASE_URL`     | Your Backstage instance URL              | `https://backstage.example.com` |
| `GLEAN_INSTANCE_NAME`    | Your Glean instance identifier           | `mycompany`                     |
| `GLEAN_INDEXING_API_KEY` | API key for Glean Indexing API           | -                               |
| `BACKSTAGE_API_TOKEN`    | Static Auth Token for the Backstage API. | -                               |

The Backstage Auth token can be ommitted if your Backstage API does not require authentication (not typical).


### Optional Settings

| Variable                  | Description                                    | Default            |
| ------------------------- | ---------------------------------------------- | ------------------ |
| `DEFAULT_PERMISSIONS`     | Default permissions to fallback to (see below) | `datasource-users` |
| `SYNC_BATCH_SIZE`         | Documents per batch                            | `50`               |
| `SYNC_COMPONENTS_ENABLED` | Sync Component entities                        | `true`             |
| `SYNC_APIS_ENABLED`       | Sync API entities                              | `true`             |
| `SYNC_SYSTEMS_ENABLED`    | Sync System entities                           | `true`             |
| `SYNC_DOMAINS_ENABLED`    | Sync Domain entities                           | `true`             |
| `SYNC_RESOURCES_ENABLED`  | Sync Resource entities                         | `true`             |
| `SYNC_USERS_ENABLED`      | Sync User entities                             | `true`             |
| `SYNC_GROUPS_ENABLED`     | Sync Group entities                            | `true`             |
| `SYNC_LOCATIONS_ENABLED`  | Sync Location entities                         | `true`             |
| `VERIFY_SSL`              | Verify SSL certificates                        | `true`             |
| `LOG_LEVEL`               | Logging verbosity                              | `INFO`             |

The `DEFAULT_PERMISSIONS` variable defines what permissions should be assigned to any entity in Backstage that has no permissions associated with it.

You likely will **not** want to change this, but the following values can be set:

| Value              | Description                                                                                                                                                               |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `all-users`        | Indexed items without explicit permissions are visible in Glean to ALL users; regardless of whether they have Backstage access or not                                     |
| `datasource-users` | Indexed items without explicit permissions are visible in Glean to any user with Backstage access (default)                                                               |
| `owner`            | Indexed items without explicit permissions are visible only to the owner (if specified, and only if the owner is a user, not a group); otherwise this is the same as none |
| `none`             | Indexed items without explicit permissions are visible to no one                                                                                                          |


## 📘 CLI Reference

### `test-connection`
Verify connectivity to both Backstage and Glean APIs.

```bash
uv run backstage-sync test-connection

# Output:
# ✓ Connected to Backstage at https://backstage.example.com
# ✓ Connected to Glean instance 'mycompany'
# ✓ All connections successful!
```

### `show-config`
Display current configuration (with secrets redacted).

```bash
uv run backstage-sync show-config

# Output:
# Current Configuration:
# ├── Backstage URL: https://backstage.example.com
# ├── Glean Instance: mycompany
# ├── Batch Size: 50
# └── Enabled Types: Components, APIs, Systems, Users, Groups
```

### `dry-run`
Preview what would be synced without pushing to Glean.

```bash
uv run backstage-sync sync --dry-run

# Output:
# Dry Run Results:
# ├── Components: 156 entities found
# ├── APIs: 42 entities found
# ├── Systems: 12 entities found
# ├── Users: 89 entities found
# └── Groups: 23 entities found
# Total: 322 documents would be synced
```

### `sync`
Run the full synchronization process.

```bash
uv run backstage-sync sync

# Output:
# Starting Backstage to Glean sync...
# ├── Syncing identities...
# │   ├── Users: 89/89 [████████████] 100%
# │   └── Groups: 23/23 [████████████] 100%
# ├── Syncing catalog entities...
# │   ├── Components: 156/156 [████████████] 100%
# │   ├── APIs: 42/42 [████████████] 100%
# │   └── Systems: 12/12 [████████████] 100%
# └── ✓ Sync completed successfully!
```

## 🔄 Sync Process

### How It Works

1. **Identity Sync**: Users and Groups are synced first to establish identity mappings
2. **Entity Fetch**: Catalog entities are fetched from Backstage in batches
3. **Data Mapping**: Entities are transformed to Glean's document format
4. **Permission Assignment**: Ownership and access controls are mapped
5. **Batch Upload**: Documents are pushed to Glean in configurable batches
6. **Cleanup**: Glean removes any stale content not in the latest sync

## 🚨 Troubleshooting

### Common Issues

#### Connection Errors
```
Error: Failed to connect to Backstage
```
**Solution**: Verify `BACKSTAGE_BASE_URL` is correct and accessible. Check if API token is required.

#### Authentication Failures
```
Error: 401 Unauthorized from Glean API
```
**Solution**: Ensure `GLEAN_INDEXING_API_KEY` has write permissions to the datasource.

#### Missing Entities
```
Warning: No components found in Backstage
```
**Solution**: 
- Check if entity type is enabled in configuration
- Verify Backstage catalog contains the expected entities
- Ensure API token has read permissions for all entity types

### Getting Help

1. Verify all credentials and URLs
2. Test each service independently with `test-connection`
3. Review Glean's indexing logs for errors

## 🔒 Security Considerations

- The connector only reads data, never modifies Backstage
- Respects Backstage visibility and access controls
- Synced data inherits Glean's security model
- No data is stored locally in the connector after sync completes

## 💡 Example Use Cases

### Automated Daily Sync
```bash
# Add to crontab for daily sync at 2 AM
0 2 * * * cd /path/to/backstage-connector && uv run backstage-sync sync
```

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Sync Backstage to Glean
  run: |
    uv sync
    uv run backstage-sync sync
  env:
    BACKSTAGE_BASE_URL: ${{ secrets.BACKSTAGE_URL }}
    GLEAN_INDEXING_API_KEY: ${{ secrets.GLEAN_API_KEY }}
```

### Selective Sync
```bash
# Only sync components and APIs
SYNC_COMPONENTS_ENABLED=true \
SYNC_APIS_ENABLED=true \
SYNC_SYSTEMS_ENABLED=false \
SYNC_USERS_ENABLED=false \
SYNC_GROUPS_ENABLED=false \
uv run backstage-sync sync
```

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Setup
```bash
# Clone your fork
git clone https://github.com/nathancatania/backstage-connector.git
cd backstage-connector

# Create virtual environment
uv sync --dev

# Run tests
uv run pytest

# Run linting
uv run ruff check src tests
```

### Code Standards

- Follow PEP 8 style guide
- Add type hints to all functions
- Write tests for new features
- Update documentation as needed

### Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to your fork (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

> [!NOTE]
>
> This project is not affiliated with Glean, Backstage, or Spotify.

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**You use this tool at your own risk!**
If it somehow deletes all of your company's data, burns down your house, and nukes your dog from orbit - it will be your own fault.

*That being said, I don't recall adding any code that would do this...* 🤷‍♂️