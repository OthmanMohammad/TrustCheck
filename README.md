# TrustCheck

Sanctions screening platform for OFAC, UN, EU, and UK sanctions lists.

## What It Does

- Downloads and parses sanctions data from OFAC SDN, UN Consolidated, EU Financial Sanctions, and UK HMT
- Stores entities in PostgreSQL with full-text search capabilities
- Screens names against the database using fuzzy matching and phonetic algorithms
- Tracks changes (additions, modifications, removals) across all sources
- Provides a REST API and web interface

## Requirements

- Python 3.11+
- PostgreSQL 14+ (with pg_trgm extension)

## Quick Start

```bash
# Clone and install
git clone https://github.com/OthmanMohammad/TrustCheck.git
cd TrustCheck
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .

# Setup PostgreSQL
psql -U postgres -c "CREATE DATABASE trustcheck;"
psql -U postgres -d trustcheck -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# Configure database (create .env file)
echo 'DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/trustcheck' > .env

# Run migrations
alembic upgrade head

# Start the server
python -m trustcheck.main serve
```

Open http://localhost:8000/ui in your browser.

## Configuration

Create a `.env` file in the project root. See `.env.example` for all options.

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (PostgreSQL) | Database connection string |
| `DEFAULT_MATCH_THRESHOLD` | `0.80` | Minimum score for screening matches |
| `OFAC_INTERVAL_HOURS` | `6` | How often to check OFAC for updates |
| `UN_INTERVAL_HOURS` | `24` | How often to check UN |
| `EU_INTERVAL_HOURS` | `24` | How often to check EU |
| `UK_INTERVAL_HOURS` | `24` | How often to check UK |

## CLI Commands

```bash
# Start web server
python -m trustcheck.main serve

# Run a scrape manually
python -m trustcheck.main scrape              # All sources
python -m trustcheck.main scrape OFAC_SDN     # Single source

# Screen a name from terminal
python -m trustcheck.main screen "John Smith" --threshold 0.8
```

## API Endpoints

Base URL: `http://localhost:8000`

### Screening

```bash
# Screen a single name
POST /api/screen
{"name": "John Smith", "threshold": 0.8}

# Batch screening (up to 10,000 names)
POST /api/screen/batch
{"names": ["John Smith", "Jane Doe"], "threshold": 0.8}
```

### Entities

```bash
# List entities
GET /api/entities?limit=50&offset=0

# Get entity by ID
GET /api/entities/{id}

# Search entities
POST /api/entities/search
{"query": "Mohammad", "limit": 20}
```

### Changes

```bash
# Recent changes
GET /api/changes?days=7&limit=100

# Change statistics
GET /api/changes/stats
```

### Admin

```bash
# Trigger scrape
POST /api/admin/scrape
{"source": "OFAC_SDN"}

# Scrape all sources
POST /api/admin/scrape/all

# Clear screening cache
POST /api/admin/cache/clear

# System status
GET /api/admin/status
```

### Health

```bash
GET /health
```

Full API docs at `/docs` (Swagger) or `/redoc`.

## Web Interface

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/ui` | Overview and statistics |
| Entities | `/ui/entities` | Browse sanctioned entities |
| Screening | `/ui/screening` | Screen names interactively |
| Changes | `/ui/changes` | View recent changes |
| Admin | `/ui/admin` | Trigger scrapes, view status |

## Name Matching

The screening engine uses multiple algorithms:

1. **Normalization** - Unicode transliteration, diacritics removal, case folding
2. **Fuzzy matching** - Levenshtein distance, token sorting, partial matching
3. **Phonetic matching** - Soundex, Metaphone, NYSIIS for sound-alike names
4. **Trigram similarity** - PostgreSQL pg_trgm for candidate generation

Match scores range from 0.0 to 1.0. The default threshold of 0.80 catches most variations while limiting false positives.

## Data Sources

| Source | URL | Format | Typical Count |
|--------|-----|--------|---------------|
| OFAC SDN | treasury.gov | XML | ~12,000 |
| UN Consolidated | un.org | XML | ~800 |
| EU Financial | ec.europa.eu | XML | ~2,000 |
| UK HMT | gov.uk | XML | ~3,500 |

## Project Structure

```
src/trustcheck/
├── api/           # FastAPI routes and schemas
├── database/      # SQLAlchemy models, repositories
├── domain/        # Business logic models
├── matching/      # Name matching algorithms
├── scrapers/      # Data source parsers
├── services/      # Ingestion and screening services
├── scheduler/     # Background job scheduling
├── web/           # Templates and static files
├── config.py      # Settings
└── main.py        # CLI entry point
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint and format
ruff check src/
ruff format src/

# Type checking
mypy src/
```

## Docker

```bash
docker build -t trustcheck .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/trustcheck \
  trustcheck
```

## Free Cloud Deployment

Deploy TrustCheck for **$0/month** using:

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| [Neon](https://neon.tech) | PostgreSQL | 0.5 GB, serverless |
| [Render](https://render.com) | Web hosting | 750 hrs/month |

### Quick Deploy

1. **Create Neon database** at [neon.tech](https://neon.tech)
   - Enable `pg_trgm` extension: `CREATE EXTENSION IF NOT EXISTS pg_trgm;`
   - Copy connection string

2. **Deploy to Render**
   - Fork this repo to your GitHub
   - Create new Web Service at [render.com](https://render.com)
   - Set `DATABASE_URL` to your Neon connection string (change `postgresql://` to `postgresql+asyncpg://`)
   - Set start command: `sh -c 'alembic upgrade head && python -m trustcheck.main serve --host 0.0.0.0 --port $PORT'`

3. **Trigger initial scrape**
   ```bash
   curl -X POST https://your-app.onrender.com/api/admin/scrape/all
   ```

See [docs/FREE_DEPLOYMENT.md](docs/FREE_DEPLOYMENT.md) for detailed instructions.

### Alternative: Fly.io

```bash
fly launch --name my-trustcheck
fly secrets set DATABASE_URL="postgresql+asyncpg://...neon-url..."
fly deploy
```

## CI/CD

GitHub Actions workflows included:
- **CI Pipeline** (`.github/workflows/ci.yml`) - Lint, test, build on every push
- **Scheduled Scrape** (`.github/workflows/scheduled-scrape.yml`) - External cron for free-tier deployments

## License

MIT
