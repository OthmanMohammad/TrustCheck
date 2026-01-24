# Configuration

All configuration is done through environment variables. Create a `.env` file in the project root or set variables in your environment.

## Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Database connection string |
| `DB_POOL_SIZE` | `10` | Connection pool size |
| `DB_POOL_MAX_OVERFLOW` | `20` | Extra connections allowed |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for connection |
| `DB_ECHO` | `false` | Log SQL statements |

### PostgreSQL Setup

```bash
# Create database
psql -U postgres -c "CREATE DATABASE trustcheck;"

# Enable trigram extension (required for fuzzy search)
psql -U postgres -d trustcheck -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

Connection string format:
```
postgresql+asyncpg://username:password@host:port/database
```

Examples:
```bash
# Local
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/trustcheck

# Docker
DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/trustcheck

# Remote
DATABASE_URL=postgresql+asyncpg://user:pass@db.example.com:5432/trustcheck
```

### SQLite (Development Only)

SQLite works for testing but is not recommended for production due to concurrency limitations.

```bash
DATABASE_URL=sqlite+aiosqlite:///data/trustcheck.db
```

---

## Application

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development`, `staging`, or `production` |
| `DEBUG` | `false` | Enable debug mode and auto-reload |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |

---

## Screening

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_MATCH_THRESHOLD` | `0.80` | Minimum score for matches (0.0-1.0) |
| `MAX_SCREENING_RESULTS` | `100` | Max results per screening request |
| `BATCH_SCREENING_LIMIT` | `10000` | Max names in batch request |
| `TRIGRAM_SIMILARITY_THRESHOLD` | `0.3` | PostgreSQL pg_trgm threshold |

### Threshold Guidelines

| Threshold | Use Case |
|-----------|----------|
| 0.95+ | Exact/near-exact matches only |
| 0.85-0.95 | High confidence, low false positives |
| 0.75-0.85 | Balanced (recommended default) |
| 0.60-0.75 | Higher recall, more false positives |
| <0.60 | Not recommended |

---

## Scraping

| Variable | Default | Description |
|----------|---------|-------------|
| `OFAC_INTERVAL_HOURS` | `6` | OFAC update check interval |
| `UN_INTERVAL_HOURS` | `24` | UN update check interval |
| `EU_INTERVAL_HOURS` | `24` | EU update check interval |
| `UK_INTERVAL_HOURS` | `24` | UK update check interval |
| `SCRAPING_TIMEOUT` | `120` | HTTP timeout in seconds |
| `SCRAPING_MAX_RETRIES` | `3` | Retry attempts on failure |
| `SCRAPING_BATCH_SIZE` | `500` | Database batch insert size |

### Custom Source URLs

Override default URLs if needed (rarely necessary):

```bash
OFAC_SDN_URL=https://www.treasury.gov/ofac/downloads/sdn.xml
UN_CONSOLIDATED_URL=https://scsanctions.un.org/resources/xml/en/consolidated.xml
EU_SANCTIONS_URL=https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw
UK_SANCTIONS_URL=https://assets.publishing.service.gov.uk/media/.../UK_Sanctions_List.xml
```

Note: UK government changes their URL when they update the list. If UK scraping fails with 410 Gone, check the gov.uk website for the current URL or remove `UK_SANCTIONS_URL` from your `.env` to use the default.

---

## Cache

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_TTL_SECONDS` | `300` | Cache time-to-live (5 minutes) |
| `CACHE_MAX_SIZE` | `10000` | Maximum cached items |

---

## Example .env Files

### Development

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/trustcheck
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
```

### Production

```bash
DATABASE_URL=postgresql+asyncpg://user:strongpassword@db.example.com:5432/trustcheck
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
DB_POOL_SIZE=20
DB_POOL_MAX_OVERFLOW=30
DEFAULT_MATCH_THRESHOLD=0.85
```

### Docker Compose

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/trustcheck
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
```
