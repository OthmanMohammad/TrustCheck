# Deployment

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL 14+

### Setup

```bash
# Clone repository
git clone https://github.com/OthmanMohammad/TrustCheck.git
cd TrustCheck

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Setup PostgreSQL
psql -U postgres -c "CREATE DATABASE trustcheck;"
psql -U postgres -d trustcheck -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/trustcheck
ENVIRONMENT=development
DEBUG=true
EOF

# Run migrations
alembic upgrade head

# Start server
python -m trustcheck.main serve
```

---

## Docker

### Single Container

```bash
# Build image
docker build -t trustcheck .

# Run with PostgreSQL
docker run -d \
  --name trustcheck \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/trustcheck \
  -e ENVIRONMENT=production \
  trustcheck
```

### Docker Compose with PostgreSQL

Create `docker-compose.prod.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: trustcheck
      POSTGRES_PASSWORD: changeme
      POSTGRES_DB: trustcheck
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U trustcheck"]
      interval: 5s
      timeout: 5s
      retries: 5

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://trustcheck:changeme@db:5432/trustcheck
      ENVIRONMENT: production
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

volumes:
  postgres_data:
```

Run:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

Initialize database:

```bash
# Run migrations
docker-compose exec app alembic upgrade head

# Enable pg_trgm extension
docker-compose exec db psql -U trustcheck -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# Trigger initial scrape
docker-compose exec app python -m trustcheck.main scrape
```

---

## Cloud Platforms

### Fly.io

Fly.io offers a free tier suitable for testing.

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create app (first time)
fly launch --name my-trustcheck

# Create volume for data
fly volumes create trustcheck_data --region iad --size 1

# Set secrets
fly secrets set DATABASE_URL="postgresql+asyncpg://..."

# Deploy
fly deploy

# Run migrations
fly ssh console -C "alembic upgrade head"

# Check logs
fly logs
```

Note: For production use with Fly.io, set up a managed PostgreSQL database (Fly Postgres or external).

### Railway

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and init
railway login
railway init

# Add PostgreSQL
railway add postgresql

# Deploy
railway up

# Run migrations
railway run alembic upgrade head
```

### Render

1. Create a new Web Service
2. Connect your GitHub repo
3. Set build command: `pip install -e .`
4. Set start command: `python -m trustcheck.main serve`
5. Add PostgreSQL database
6. Set environment variables

---

## Production Checklist

### Security

- [ ] Use HTTPS (handled by cloud platforms)
- [ ] Set strong database password
- [ ] Set `ENVIRONMENT=production`
- [ ] Set `DEBUG=false`
- [ ] Add authentication middleware if exposed publicly

### Database

- [ ] Use PostgreSQL (not SQLite)
- [ ] Enable `pg_trgm` extension
- [ ] Configure connection pooling
- [ ] Set up backups

### Monitoring

- [ ] Health endpoint: `GET /health`
- [ ] Check scraper status: `GET /api/admin/status`
- [ ] Monitor logs for errors

### Performance

- [ ] Adjust `DB_POOL_SIZE` based on load
- [ ] Configure `CACHE_TTL_SECONDS` appropriately
- [ ] Tune `SCRAPING_BATCH_SIZE` for your hardware

---

## Database Migrations

Always run migrations when deploying updates:

```bash
# Local
alembic upgrade head

# Docker
docker-compose exec app alembic upgrade head

# Fly.io
fly ssh console -C "alembic upgrade head"
```

Create new migrations after model changes:

```bash
alembic revision --autogenerate -m "description"
```

---

## Initial Data Load

After deployment, trigger an initial scrape to populate the database:

```bash
# CLI
python -m trustcheck.main scrape

# API
curl -X POST http://localhost:8000/api/admin/scrape/all

# Web UI
Go to /ui/admin and click "Scrape All Sources"
```

First scrape takes 5-10 minutes depending on network speed.

---

## Troubleshooting

### Database connection errors

```
connection refused
```

Check PostgreSQL is running and accessible. Verify `DATABASE_URL` is correct.

### pg_trgm extension missing

```
function similarity(unknown, unknown) does not exist
```

Run:
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Scraper 410 Gone (UK)

The UK government changes their sanctions list URL when they update it. Either:
1. Find the current URL on gov.uk and set `UK_SANCTIONS_URL` in `.env`
2. Remove `UK_SANCTIONS_URL` from `.env` to try the default

### Out of memory

Increase `DB_POOL_SIZE` and `DB_POOL_MAX_OVERFLOW` if needed. For batch operations, reduce `SCRAPING_BATCH_SIZE`.
