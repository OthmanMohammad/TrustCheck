# TrustCheck

**Real-Time Sanctions Screening Platform**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3.40+-lightblue.svg)](https://sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A lightweight, zero-cost sanctions screening platform that monitors global sanctions lists (OFAC, UN, EU, UK) and provides real-time name matching with fuzzy search and phonetic algorithms.

---

## Features

- **Multi-Source Monitoring**: Automatically scrapes OFAC SDN, UN Consolidated, EU Financial Sanctions, and UK HMT lists
- **Advanced Name Matching**: Fuzzy matching with phonetic algorithms (Soundex, Metaphone, NYSIIS) and Unicode transliteration
- **Change Detection**: Tracks additions, modifications, and removals across all sources
- **REST API**: Full-featured API with OpenAPI documentation
- **Professional Web UI**: Dashboard, entity browser, screening interface, and monitoring pages
- **Zero Cost**: Runs on SQLite with free Fly.io deployment
- **Lightweight**: ~15 dependencies, single process architecture

---

## Quick Start

### Prerequisites

- Python 3.12+
- pip or uv package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/trustcheck.git
cd trustcheck

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Initialize database
alembic upgrade head

# Run the application
python -m trustcheck.main serve
```

The application will be available at:
- **Web UI**: http://localhost:8000/ui
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Docker

```bash
# Build and run with Docker
docker build -t trustcheck .
docker run -p 8000:8000 -v trustcheck_data:/app/data trustcheck

# Or use Docker Compose
docker-compose up -d
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Sources                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │   OFAC   │ │    UN    │ │    EU    │ │  UK HMT  │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Scraping Layer                            │
│  • Async HTTP downloads with retry logic                     │
│  • XML/Excel parsing for each source format                  │
│  • Content hashing for change detection                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Ingestion Service                          │
│  • Entity normalization and deduplication                    │
│  • Change detection (added/modified/removed)                 │
│  • Audit logging for all changes                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 SQLite Database                              │
│  • Entities, names, addresses, identifiers                   │
│  • Source records with raw data                              │
│  • Change events for monitoring                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Application                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  REST API   │  │   Web UI    │  │  Scheduler  │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
trustcheck/
├── src/trustcheck/
│   ├── api/                 # FastAPI routes and schemas
│   │   ├── routes/          # API endpoints
│   │   ├── app.py           # Application factory
│   │   └── schemas.py       # Pydantic models
│   ├── database/            # Database layer
│   │   ├── connection.py    # Async SQLite connection
│   │   ├── models.py        # SQLAlchemy ORM models
│   │   └── repositories.py  # Data access patterns
│   ├── domain/              # Domain models and exceptions
│   │   ├── enums.py         # Business enumerations
│   │   ├── models.py        # Domain entities
│   │   └── exceptions.py    # Custom exceptions
│   ├── matching/            # Name matching engine
│   │   ├── normalizer.py    # Unicode transliteration
│   │   ├── phonetic.py      # Soundex, Metaphone, NYSIIS
│   │   └── scorer.py        # Fuzzy matching scorer
│   ├── scrapers/            # Data source scrapers
│   │   ├── base.py          # Abstract scraper
│   │   ├── ofac.py          # OFAC SDN scraper
│   │   ├── un.py            # UN Consolidated scraper
│   │   ├── eu.py            # EU Financial Sanctions
│   │   └── uk.py            # UK HMT scraper
│   ├── services/            # Business logic
│   │   ├── ingestion.py     # Data ingestion
│   │   └── screening.py     # Name screening
│   ├── scheduler/           # Background jobs
│   │   └── jobs.py          # APScheduler configuration
│   ├── web/                 # Web UI
│   │   ├── templates/       # Jinja2 templates
│   │   └── static/          # CSS and JavaScript
│   ├── config.py            # Configuration settings
│   └── main.py              # CLI entry point
├── migrations/              # Alembic migrations
├── tests/                   # Test suite
├── Dockerfile               # Container image
├── fly.toml                 # Fly.io deployment
└── pyproject.toml           # Project configuration
```

---

## API Reference

### Screening

```bash
# Screen a single name
curl -X POST http://localhost:8000/api/screen \
  -H "Content-Type: application/json" \
  -d '{"name": "John Smith", "threshold": 0.8}'

# Batch screening
curl -X POST http://localhost:8000/api/screen/batch \
  -H "Content-Type: application/json" \
  -d '{"names": ["John Smith", "Jane Doe"], "threshold": 0.8}'
```

### Entities

```bash
# List entities with pagination
curl "http://localhost:8000/api/entities?limit=50&offset=0"

# Get entity details
curl "http://localhost:8000/api/entities/{entity_id}"

# Search entities
curl -X POST http://localhost:8000/api/entities/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Mohammad Ali", "limit": 20}'
```

### Changes

```bash
# List recent changes
curl "http://localhost:8000/api/changes?days=7"

# Get change statistics
curl "http://localhost:8000/api/changes/stats"
```

### Admin

```bash
# Trigger manual scrape
curl -X POST http://localhost:8000/api/admin/scrape \
  -H "Content-Type: application/json" \
  -d '{"source": "OFAC_SDN"}'

# Get system status
curl "http://localhost:8000/api/admin/status"
```

Full API documentation available at `/docs` (Swagger UI) or `/redoc` (ReDoc).

---

## Name Matching

TrustCheck uses a multi-algorithm approach for accurate name matching:

### Normalization
- Unicode transliteration (Cyrillic, Arabic, etc. to Latin)
- Diacritics removal (José → JOSE)
- Title and suffix removal (Dr., Jr., PhD)
- Whitespace normalization

### Matching Algorithms
| Algorithm | Weight | Purpose |
|-----------|--------|---------|
| Exact Match | 1.0 | Identical names |
| Fuzzy Ratio | 0.25 | Levenshtein similarity |
| Partial Ratio | 0.20 | Substring matching |
| Token Sort | 0.20 | Order-independent matching |
| Token Set | 0.15 | Subset matching |
| Phonetic | 0.10 | Sound-alike matching |
| N-gram | 0.10 | Character sequence matching |

### Example Matches
```
Query: "Mohammad Ali Khan"
├── "Mohammed Ali Khan"  → 0.95 (phonetic match)
├── "Mohammad A. Khan"   → 0.88 (partial match)
├── "Khan, Mohammad Ali" → 0.92 (token sort)
└── "John Smith"         → 0.15 (no match)
```

---

## Configuration

Environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///data/trustcheck.db` | Database connection |
| `ENVIRONMENT` | `development` | Environment name |
| `DEBUG` | `false` | Debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DEFAULT_MATCH_THRESHOLD` | `0.80` | Minimum match score |
| `SCRAPING_INTERVAL_OFAC` | `6` | OFAC scrape interval (hours) |
| `SCRAPING_INTERVAL_UN` | `24` | UN scrape interval (hours) |
| `SCRAPING_INTERVAL_EU` | `24` | EU scrape interval (hours) |
| `SCRAPING_INTERVAL_UK` | `24` | UK scrape interval (hours) |

---

## Deployment

### Fly.io (Free Tier)

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login to Fly.io
flyctl auth login

# Deploy (first time)
flyctl launch --name trustcheck-sanctions

# Create persistent volume for database
flyctl volumes create trustcheck_data --region iad --size 1

# Deploy updates
flyctl deploy
```

Or use the deployment script:
```bash
./scripts/deploy.sh
```

### Other Platforms

TrustCheck is a standard Python application and can be deployed to any platform that supports:
- Python 3.12+
- Persistent storage for SQLite
- Outbound HTTPS connections

Platforms: Railway, Render, DigitalOcean App Platform, Heroku, etc.

---

## Data Sources

| Source | Organization | Format | Update Frequency | Entities |
|--------|-------------|--------|------------------|----------|
| **OFAC SDN** | US Treasury | XML | Every 6 hours | ~12,000 |
| **UN Consolidated** | United Nations | XML | Daily | ~800 |
| **EU Financial** | European Union | XML | Daily | ~2,000 |
| **UK HMT** | UK Treasury | ODS | Daily | ~3,500 |

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=trustcheck --cov-report=html

# Run specific test categories
pytest tests/unit/
pytest tests/integration/

# Run matching tests only
pytest tests/unit/test_matching.py -v
```

---

## CLI Commands

```bash
# Start the server
python -m trustcheck.main serve --host 0.0.0.0 --port 8000

# Run a manual scrape
python -m trustcheck.main scrape --source OFAC_SDN
python -m trustcheck.main scrape --all

# Screen a name from command line
python -m trustcheck.main screen "John Smith" --threshold 0.8
```

---

## Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/your-username/trustcheck.git
cd trustcheck
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run linting
ruff check src/
ruff format src/

# Run type checking
mypy src/

# Create a new migration
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Web Framework** | FastAPI | Async REST API |
| **Database** | SQLite + aiosqlite | Data persistence |
| **ORM** | SQLAlchemy 2.0 | Database abstraction |
| **Migrations** | Alembic | Schema versioning |
| **Validation** | Pydantic v2 | Request/response validation |
| **Fuzzy Matching** | rapidfuzz | String similarity |
| **Phonetic** | jellyfish | Sound-alike matching |
| **Scheduling** | APScheduler | Background jobs |
| **HTTP Client** | httpx | Async HTTP requests |
| **XML Parsing** | lxml | XML/HTML parsing |
| **Excel Parsing** | openpyxl | ODS/Excel files |
| **Templates** | Jinja2 | Web UI rendering |

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Author

**Mohammad Othman** - [mohammadothman.com](https://mohammadothman.com/)
