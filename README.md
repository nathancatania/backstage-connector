# Backstage to Glean Connector

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![UV](https://img.shields.io/badge/package%20manager-uv-purple.svg)](https://github.com/astral-sh/uv)

This is a custom Glean connector for Backstage.io. It will push your catalog to Glean for indexing; making your entire software ecosystem searchable and discoverable through Glean's enterprise search and AI features.

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

- **Catalog Entities**: Components, APIs, Systems, Domains, Resources, Locations
- **Identity & Access**: Users, Groups, and their relationships
- **Metadata**: Descriptions, tags, links, documentation, and custom attributes
- **Permissions**: Ownership and group memberships for secure search

## 🏗️ Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌───────────────┐
│                 │         │                  │         │               │
│   Backstage     │ ──API──▶│  Connector       │ ──API──▶│    Glean      │
│   Catalog       │         │                  │         │    Search     │
│                 │         │ • Fetch Entities │         │               │
│ • Components    │         │ • Map Data       │         │ • Documents   │
│ • APIs          │         │ • Sync Identity  │         │ • Identity    │
│ • Systems       │         │ • Push Documents │         │ • Permissions │
│ • Users/Groups  │         │ • Handle Errors  │         │               │
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

### Setup Steps

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

| Variable                 | Description                    | Example                         |
| ------------------------ | ------------------------------ | ------------------------------- |
| `BACKSTAGE_BASE_URL`     | Your Backstage instance URL    | `https://backstage.example.com` |
| `GLEAN_INSTANCE_NAME`    | Your Glean instance identifier | `mycompany`                     |
| `GLEAN_INDEXING_API_KEY` | API key for Glean Indexing API | `glean_api_...`                 |

### Optional Settings

| Variable                  | Description                        | Default |
| ------------------------- | ---------------------------------- | ------- |
| `BACKSTAGE_API_TOKEN`     | Auth token for protected Backstage | None    |
| `SYNC_BATCH_SIZE`         | Documents per batch                | `50`    |
| `SYNC_COMPONENTS_ENABLED` | Sync Component entities            | `true`  |
| `SYNC_APIS_ENABLED`       | Sync API entities                  | `true`  |
| `SYNC_SYSTEMS_ENABLED`    | Sync System entities               | `true`  |
| `SYNC_DOMAINS_ENABLED`    | Sync Domain entities               | `true`  |
| `SYNC_RESOURCES_ENABLED`  | Sync Resource entities             | `true`  |
| `SYNC_USERS_ENABLED`      | Sync User entities                 | `true`  |
| `SYNC_GROUPS_ENABLED`     | Sync Group entities                | `true`  |
| `SYNC_LOCATIONS_ENABLED`  | Sync Location entities             | `true`  |
| `VERIFY_SSL`              | Verify SSL certificates            | `true`  |
| `LOG_LEVEL`               | Logging verbosity                  | `INFO`  |

### Advanced Configuration

```bash
# Custom datasource name
GLEAN_DATASOURCE_NAME="backstage-catalog"

# Sync specific entity kinds only
SYNC_COMPONENTS_ENABLED=true
SYNC_APIS_ENABLED=true
SYNC_SYSTEMS_ENABLED=false
# ... etc

# Performance tuning
SYNC_BATCH_SIZE=100
REQUEST_TIMEOUT=30
```

## 📘 CLI Reference

### `init-env`
Generate a template `.env` file with all available configuration options.

```bash
uv run backstage-sync init-env
# Creates: .env.template
```

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
uv run backstage-sync dry-run

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

### Options

All commands support these global options:

- `--log-level`: Set logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `--config`: Path to custom .env file

```bash
uv run backstage-sync --log-level DEBUG sync
uv run backstage-sync --config /path/to/custom.env sync
```

## 🔄 Sync Process

### How It Works

1. **Identity Sync**: Users and Groups are synced first to establish identity mappings
2. **Entity Fetch**: Catalog entities are fetched from Backstage in batches
3. **Data Mapping**: Entities are transformed to Glean's document format
4. **Permission Assignment**: Ownership and access controls are mapped
5. **Batch Upload**: Documents are pushed to Glean in configurable batches
6. **Cleanup**: Glean removes any stale content not in the latest sync

### Data Mapping

#### Users → Employees
```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "profileUrl": "https://backstage.example.com/catalog/default/user/john.doe"
}
```

#### Groups → Teams
```json
{
  "name": "platform-team",
  "description": "Platform Engineering Team",
  "members": ["user1@example.com", "user2@example.com"],
  "profileUrl": "https://backstage.example.com/catalog/default/group/platform-team"
}
```

#### Components → Documents
```json
{
  "title": "Payment Service",
  "description": "Handles payment processing",
  "type": "SERVICE",
  "owner": "platform-team",
  "tags": ["backend", "payments", "critical"],
  "links": {
    "repository": "https://github.com/company/payment-service",
    "documentation": "https://docs.company.com/payment-service"
  }
}
```

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

#### SSL Certificate Errors
```
Error: SSL: CERTIFICATE_VERIFY_FAILED
```
**Solution**: For self-signed certificates, set `VERIFY_SSL=false` (not recommended for production).

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Via environment variable
LOG_LEVEL=DEBUG uv run backstage-sync sync

# Via CLI option
uv run backstage-sync --log-level DEBUG sync
```

### Getting Help

1. Check logs in debug mode
2. Verify all credentials and URLs
3. Test each service independently with `test-connection`
4. Review Glean's indexing logs for errors

## 🔒 Security Considerations

### API Keys and Tokens

- Store credentials in `.env` file (never commit to version control)
- Use environment-specific credentials for dev/staging/prod
- Rotate API keys regularly
- Limit API key permissions to minimum required

### Network Security

- Always use HTTPS for API communications
- Verify SSL certificates in production (`VERIFY_SSL=true`)
- Consider using VPN or private networking for sensitive data
- Implement rate limiting to avoid overwhelming APIs

### Data Privacy

- The connector only reads data, never modifies Backstage
- Respects Backstage visibility and access controls
- Synced data inherits Glean's security model
- No data is stored locally after sync completes

### Audit and Monitoring

- All sync operations are logged with timestamps
- Monitor sync job execution for failures
- Set up alerts for authentication failures
- Review Glean access logs regularly

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

### Multi-Environment Setup
```bash
# Development
uv run backstage-sync --config .env.dev sync

# Production
uv run backstage-sync --config .env.prod sync
```

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Setup
```bash
# Clone your fork
git clone https://github.com/yourusername/backstage-connector
cd backstage-connector

# Create virtual environment
uv sync --dev

# Run tests
uv run pytest

# Run linting
uv run ruff check backstage_connector tests
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

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Backstage.io](https://backstage.io) for the amazing developer portal
- [Glean](https://glean.com) for enterprise search capabilities
- The open source community for invaluable tools and libraries