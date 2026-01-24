# Free Deployment Guide

Deploy TrustCheck completely free using **Neon** (PostgreSQL) + **Render** (Web Service).

**Total Cost: $0/month**

---

## Architecture

```
┌─────────────────────┐      ┌─────────────────────┐
│      Render         │      │        Neon         │
│   (Web Service)     │─────▶│    (PostgreSQL)     │
│   Free Tier         │      │    Free Tier        │
│   750 hrs/month     │      │    0.5 GB storage   │
│   Auto-sleep        │      │    Serverless       │
└─────────────────────┘      └─────────────────────┘
```

---

## Step 1: Create Neon PostgreSQL Database

Neon provides a generous free tier with serverless PostgreSQL that includes the `pg_trgm` extension needed for fuzzy matching.

### 1.1 Sign Up for Neon

1. Go to [neon.tech](https://neon.tech)
2. Sign up with GitHub, Google, or email
3. Create a new project:
   - **Project name**: `trustcheck`
   - **Database name**: `trustcheck`
   - **Region**: Choose closest to your Render region (e.g., US West for Oregon)

### 1.2 Enable pg_trgm Extension

In the Neon SQL Editor, run:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### 1.3 Get Connection String

1. Go to your project dashboard
2. Click "Connection Details"
3. Copy the connection string (pooled endpoint recommended)
4. **Important**: Change the protocol from `postgresql://` to `postgresql+asyncpg://`

Example:
```
# Neon gives you:
postgresql://user:password@ep-cool-name-123456.us-west-2.aws.neon.tech/trustcheck?sslmode=require

# Change to:
postgresql+asyncpg://user:password@ep-cool-name-123456.us-west-2.aws.neon.tech/trustcheck?sslmode=require
```

---

## Step 2: Deploy to Render

### 2.1 Fork/Push Repository

Ensure your code is on GitHub (public or private).

### 2.2 Create Web Service

1. Go to [render.com](https://render.com) and sign up
2. Click **New** → **Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `trustcheck`
   - **Region**: Oregon (or same as Neon)
   - **Branch**: `main`
   - **Runtime**: Docker
   - **Instance Type**: Free

### 2.3 Set Environment Variables

Add these environment variables in Render dashboard:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | `postgresql+asyncpg://...` (from Neon) |
| `ENVIRONMENT` | `production` |
| `LOG_LEVEL` | `INFO` |
| `DB_POOL_SIZE` | `5` |
| `DB_POOL_MAX_OVERFLOW` | `10` |

### 2.4 Set Start Command

```bash
sh -c 'alembic upgrade head && python -m trustcheck.main serve --host 0.0.0.0 --port $PORT'
```

### 2.5 Deploy

Click **Create Web Service**. First deploy takes 3-5 minutes.

---

## Step 3: Initialize Data

After deployment, trigger the initial sanctions data scrape:

### Option A: Web UI

1. Go to `https://your-app.onrender.com/ui/admin`
2. Click **Scrape All Sources**
3. Wait 5-10 minutes for completion

### Option B: API

```bash
curl -X POST https://your-app.onrender.com/api/admin/scrape/all
```

---

## Free Tier Limits

### Neon (PostgreSQL)
- **Storage**: 0.5 GB (enough for ~500K sanctions records)
- **Compute**: 0.25 vCPU, scales to zero
- **Branching**: 10 branches
- **No time limit** - truly free forever

### Render (Web Service)
- **Hours**: 750/month (auto-sleep after 15 min inactivity)
- **Bandwidth**: 100 GB/month
- **Build minutes**: 500/month
- **Auto-sleep**: Wakes on request (~30s cold start)

---

## Dealing with Auto-Sleep

Render's free tier sleeps after 15 minutes of inactivity. This affects:
- First request takes ~30 seconds (cold start)
- Scheduled jobs may not run while sleeping

### Solutions

#### 1. External Cron Service (Recommended)

Use a free external cron service to keep the app awake and trigger scrapes:

**cron-job.org** (Free):
1. Sign up at [cron-job.org](https://cron-job.org)
2. Create jobs:

| Job Name | URL | Schedule |
|----------|-----|----------|
| Keep Alive | `https://your-app.onrender.com/health` | Every 14 minutes |
| Scrape OFAC | `https://your-app.onrender.com/api/admin/scrape` (POST, body: `{"source": "ofac_sdn"}`) | Every 6 hours |
| Scrape Others | `https://your-app.onrender.com/api/admin/scrape/all` (POST) | Daily at 01:00 UTC |

#### 2. UptimeRobot (Free)

Use [UptimeRobot](https://uptimerobot.com) to ping `/health` every 5 minutes. This keeps the app awake 24/7.

#### 3. GitHub Actions (Free)

Add this workflow to trigger scrapes:

```yaml
# .github/workflows/scrape.yml
name: Scheduled Scrape

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Scrape
        run: |
          curl -X POST https://your-app.onrender.com/api/admin/scrape/all
```

---

## Alternative: Fly.io + Neon

Fly.io also has a free tier that's better for always-on workloads.

### Deploy to Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Launch (uses fly.toml)
fly launch --name trustcheck-app

# Set secrets
fly secrets set DATABASE_URL="postgresql+asyncpg://...your-neon-url..."

# Deploy
fly deploy

# Run migrations
fly ssh console -C "alembic upgrade head"

# Enable pg_trgm (done in Neon already)
```

### Fly.io Free Tier
- 3 shared-cpu-1x VMs
- 256 MB RAM per VM
- 3 GB persistent storage
- No auto-sleep (better for scheduled jobs!)

---

## Monitoring

### Health Check
```bash
curl https://your-app.onrender.com/health
```

### System Status
```bash
curl https://your-app.onrender.com/api/admin/status
```

### Check Scheduled Jobs
```bash
curl https://your-app.onrender.com/api/admin/jobs
```

---

## Troubleshooting

### "Connection refused" to database

1. Check `DATABASE_URL` is set correctly
2. Ensure Neon project is active (not paused)
3. Verify SSL mode: `?sslmode=require`

### "pg_trgm extension not found"

Run in Neon SQL Editor:
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Slow first request

This is normal - Render free tier sleeps after 15 min. Use UptimeRobot or cron-job.org to keep it awake.

### Build fails

Check Render logs. Common issues:
- Missing `asyncpg` - should be in dependencies
- Wrong Python version - needs 3.11+

### Scraper fails with 403/429

Some sanctions sources rate-limit. Wait and retry, or reduce scrape frequency.

---

## Upgrading

When free tier limits are reached:

| Service | Free Limit | Paid Option |
|---------|-----------|-------------|
| Neon | 0.5 GB | Pro ($19/mo, 10 GB) |
| Render | 750 hrs | Starter ($7/mo, always-on) |

---

## Security Notes

1. Never commit `.env` files with secrets
2. Use Render's secret management for `DATABASE_URL`
3. Consider adding authentication for production use
4. Enable HTTPS (automatic on Render/Fly.io)
