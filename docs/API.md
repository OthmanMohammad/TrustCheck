# API Reference

Base URL: `http://localhost:8000`

Interactive docs: `/docs` (Swagger) or `/redoc`

## Authentication

No authentication required for local development. Add authentication middleware for production deployments.

---

## Screening

### Screen a Name

```
POST /api/screen
```

Screen a single name against all sanctions lists.

**Request:**
```json
{
  "name": "John Smith",
  "threshold": 0.80,
  "date_of_birth": "1970-01-15",
  "country": "US",
  "include_inactive": false,
  "max_results": 100
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| name | string | Yes | - | Name to screen (1-500 chars) |
| threshold | float | No | 0.80 | Minimum match score (0.0-1.0) |
| date_of_birth | string | No | null | ISO date for DOB matching |
| country | string | No | null | ISO 3166 country code |
| include_inactive | bool | No | false | Include delisted entities |
| max_results | int | No | 100 | Max results (1-1000) |

**Response:**
```json
{
  "success": true,
  "request_id": "abc123",
  "query": "John Smith",
  "matches": [
    {
      "entity_id": "uuid",
      "entity_name": "SMITH, John",
      "entity_type": "INDIVIDUAL",
      "score": 0.92,
      "match_type": "FUZZY",
      "matched_fields": [
        {
          "field_name": "primary_name",
          "query_value": "John Smith",
          "matched_value": "SMITH, John",
          "score": 0.92,
          "match_type": "TOKEN_SORT"
        }
      ],
      "sources": ["OFAC_SDN"],
      "programs": ["SDGT"]
    }
  ],
  "screened_at": "2024-01-15T10:30:00Z",
  "processing_time_ms": 45.2
}
```

### Batch Screen

```
POST /api/screen/batch
```

Screen multiple names in one request.

**Request:**
```json
{
  "names": ["John Smith", "Jane Doe"],
  "threshold": 0.80,
  "include_inactive": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| names | string[] | Yes | - | Names to screen (1-10,000) |
| threshold | float | No | 0.80 | Minimum match score |
| include_inactive | bool | No | false | Include delisted entities |

**Response:**
```json
{
  "success": true,
  "total_names": 2,
  "total_matches": 1,
  "results": {
    "John Smith": [...matches...],
    "Jane Doe": []
  }
}
```

---

## Batch File Upload

### Upload File

```
POST /api/batch/upload
Content-Type: multipart/form-data
```

Upload CSV or Excel file for batch screening.

**Parameters:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| file | file | Yes | - | CSV, XLSX, or XLS file (max 10MB) |
| threshold | float | No | 0.80 | Match threshold |
| start_processing | bool | No | true | Start immediately |

**Expected columns:**
- `name` (required) - Name to screen
- `dob` or `date_of_birth` - Date of birth
- `country` or `nationality` - Country code
- `id` or `reference` - Your reference ID

**Response:**
```json
{
  "success": true,
  "job_id": "abc123",
  "message": "Batch job created and processing started",
  "status_url": "/api/batch/abc123/status"
}
```

### Check Status

```
GET /api/batch/{job_id}/status
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "abc123",
    "status": "PROCESSING",
    "filename": "customers.csv",
    "total_rows": 1000,
    "processed_rows": 450,
    "matches_found": 12,
    "created_at": "2024-01-15T10:00:00Z"
  }
}
```

Status values: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`

### Download Results

```
GET /api/batch/{job_id}/download
```

Returns CSV file with screening results.

### List Jobs

```
GET /api/batch?status=COMPLETED&limit=50&offset=0
```

### Delete Job

```
DELETE /api/batch/{job_id}
```

---

## Entities

### List Entities

```
GET /api/entities
```

**Parameters:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| source | string | null | Filter: OFAC_SDN, UN, EU, UK |
| entity_type | string | null | Filter: INDIVIDUAL, ORGANIZATION, VESSEL, AIRCRAFT |
| active_only | bool | true | Only active entities |
| limit | int | 50 | Results per page (1-500) |
| offset | int | 0 | Pagination offset |

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "primary_name": "SMITH, John",
      "entity_type": "INDIVIDUAL",
      "is_active": true,
      "programs": ["SDGT"],
      "sources": ["OFAC_SDN"],
      "updated_at": "2024-01-10T00:00:00Z"
    }
  ],
  "pagination": {
    "total": 15000,
    "limit": 50,
    "offset": 0,
    "returned": 50
  }
}
```

### Get Entity

```
GET /api/entities/{entity_id}
```

Returns full entity details including names, addresses, and identifiers.

### Search Entities

```
GET /api/entities/search?query=mohammad&limit=50&active_only=true
```

### Entity History

```
GET /api/entities/{entity_id}/history
```

Returns change history for an entity.

---

## Changes

### List Changes

```
GET /api/changes
```

**Parameters:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| source | string | null | Filter by source |
| change_type | string | null | ADDED, MODIFIED, REMOVED |
| days | int | 7 | Look back period (1-90) |
| limit | int | 100 | Results (1-1000) |
| offset | int | 0 | Pagination offset |

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "entity_id": "uuid",
      "entity_name": "SMITH, John",
      "source": "OFAC_SDN",
      "change_type": "ADDED",
      "field_changes": {},
      "detected_at": "2024-01-15T06:00:00Z"
    }
  ],
  "pagination": {...}
}
```

### Change Statistics

```
GET /api/changes/stats
```

**Response:**
```json
{
  "success": true,
  "data": {
    "changes_last_24h": 45,
    "changes_last_7d": 312,
    "changes_by_source": {
      "OFAC_SDN": 150,
      "UN": 50,
      "EU": 80,
      "UK": 32
    },
    "changes_by_type": {
      "ADDED": 100,
      "MODIFIED": 180,
      "REMOVED": 32
    }
  }
}
```

---

## Watchlists

Watchlists let you monitor specific names and receive alerts when sanctions data changes.

### Create Watchlist

```
POST /api/watchlists
```

**Request:**
```json
{
  "name": "Customer Watchlist",
  "description": "High-risk customers",
  "threshold": 0.85,
  "webhook_url": "https://example.com/webhook",
  "email_recipients": ["compliance@example.com"]
}
```

### List Watchlists

```
GET /api/watchlists?active_only=true&limit=50
```

### Update Watchlist

```
PUT /api/watchlists/{watchlist_id}
```

### Delete Watchlist

```
DELETE /api/watchlists/{watchlist_id}
```

### Add Entry

```
POST /api/watchlists/{watchlist_id}/entries
```

**Request:**
```json
{
  "name": "John Smith",
  "date_of_birth": "1970-01-15",
  "country": "US",
  "reference_id": "CUST-12345"
}
```

### Bulk Add Entries

```
POST /api/watchlists/{watchlist_id}/entries/bulk
```

**Request:**
```json
{
  "entries": [
    {"name": "John Smith", "reference_id": "CUST-001"},
    {"name": "Jane Doe", "reference_id": "CUST-002"}
  ]
}
```

### List Entries

```
GET /api/watchlists/{watchlist_id}/entries?limit=100
```

### Delete Entry

```
DELETE /api/watchlists/{watchlist_id}/entries/{entry_id}
```

---

## Alerts

### List Alerts

```
GET /api/alerts?watchlist_id=uuid&status=NEW&limit=100
```

### Dismiss Alert

```
POST /api/alerts/{alert_id}/dismiss
```

### Send Notifications

```
POST /api/alerts/send-notifications
```

Triggers webhook/email delivery for pending alerts.

### Alerts Digest

```
GET /api/alerts/digest?watchlist_id=uuid
```

---

## Admin

### System Status

```
GET /api/admin/status
```

**Response:**
```json
{
  "success": true,
  "version": "4.0.0",
  "environment": "production",
  "database_connected": true,
  "scheduler_running": true,
  "jobs": [...],
  "scraper_statuses": [...]
}
```

### Trigger Scrape

```
POST /api/admin/scrape
```

**Request:**
```json
{
  "source": "OFAC_SDN"
}
```

Valid sources: `OFAC_SDN`, `UN`, `EU`, `UK`

### Scrape All Sources

```
POST /api/admin/scrape/all
```

### Dashboard Stats

```
GET /api/admin/dashboard
```

### Clear Cache

```
POST /api/admin/cache/clear
```

---

## Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "4.0.0",
  "environment": "production",
  "database": "connected",
  "scheduler": "running",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## WebSocket

### Progress Updates

```
ws://localhost:8000/ws/progress
```

Receive real-time progress updates for background tasks.

**Message format:**
```json
{
  "task_id": "abc123",
  "task_name": "Scraping OFAC_SDN",
  "status": "running",
  "progress": 0.45,
  "message": "Processing entities...",
  "details": {
    "processed": 4500,
    "total": 10000
  }
}
```

Status values: `pending`, `running`, `success`, `failed`

---

## Error Responses

All errors return:
```json
{
  "detail": "Error message here"
}
```

HTTP status codes:
- `400` - Bad request (invalid parameters)
- `404` - Not found
- `500` - Internal server error
