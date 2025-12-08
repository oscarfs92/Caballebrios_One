# Caballebrios One - Deployment Guide

## Overview
Caballebrios One is a Streamlit game-night tracking application with support for both SQLite (local) and PostgreSQL/Neon (cloud production).

## Local Development

### Setup
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The app will automatically use SQLite (`caballebrios.db`) stored in the system temp directory.

### Database
- **Local**: SQLite database in `/tmp/caballebrios.db`
- **Features**: Player profiles, season management, game nights, scores, penalties

## Streamlit Cloud Deployment (Recommended)

### Prerequisites
1. GitHub repository with the code (already setup)
2. Streamlit Cloud account (free tier available)
3. PostgreSQL/Neon database (for data persistence)

### Step 1: Create Neon PostgreSQL Database
1. Go to [neon.tech](https://neon.tech) and sign up
2. Create a new project (free tier is sufficient)
3. Copy the full connection string (looks like: `postgresql://user:password@host/dbname`)

### Step 2: Deploy to Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click "New app" → select `oscarfs92/Caballebrios_One` repository
4. Set main file path to `streamlit_app.py`
5. Click "Deploy"

### Step 3: Add Database Secret
1. Once deployed, click "Manage app" (bottom right)
2. Go to "Secrets"
3. Add this secret:
   ```
   DATABASE_URL = postgresql://user:password@host/dbname
   ```
   (Replace with your actual Neon connection string)
4. Save and refresh app

### Private Access (Optional)
To restrict access to your app:
1. In Streamlit Cloud dashboard, find your app
2. Click settings (gear icon)
3. Set "Visibility" to "Private"
4. Share the private link with specific users

## How It Works

### Database Selection
- **PostgreSQL/Neon** (preferred in production):
  - Set `DATABASE_URL` environment variable
  - App automatically detects and uses PostgreSQL
  - Data persists across restarts
  
- **SQLite** (fallback/local):
  - Used when `DATABASE_URL` is not set or unavailable
  - Stored in system temp directory (requires nothing to configure)

### SQL Compatibility Layer
The app includes automatic SQL dialect conversion:
- Converts SQLite `?` placeholders to PostgreSQL `%s`
- Converts `GROUP_CONCAT()` to `string_agg()` for PostgreSQL
- Detects actual connection type to apply correct conversions

## Features

### Core Functionality
- ✅ Player management (with profile pictures)
- ✅ Season tracking (active/inactive)
- ✅ Game definitions with point values
- ✅ Game nights recording (date, notes)
- ✅ Round results (winners, penalties)
- ✅ Statistics dashboard (leaderboards, charts)
- ✅ Admin panel (edit/delete data)

### Statistics Available
- Player leaderboards (points, wins)
- Game popularity (frequency, winners)
- Player attendance rates
- Penalty tracking
- Seasonal comparisons
- Recent activity

## Troubleshooting

### App Won't Start
**Error**: `FileNotFoundError: No such file or directory: '/mount/src/caballebrios_one/caballebrios.db'`

**Solution**: This error is normal on Streamlit Cloud (read-only filesystem). The app now automatically:
1. Uses temp directory for SQLite
2. Prefers PostgreSQL if `DATABASE_URL` is set
3. Falls back gracefully to SQLite if PostgreSQL unavailable

### Missing Data After Restart
**Cause**: Using SQLite on Streamlit Cloud (data not persisted)

**Solution**: Set `DATABASE_URL` secret with a Neon PostgreSQL connection string

### Pandas Warning About psycopg2
**Warning**: `pandas only supports SQLAlchemy connectable or database string URI`

**Solution**: The app now handles this by using DATABASE_URL URI string with pandas when PostgreSQL is detected

### SQL Syntax Errors
The app includes automatic conversion for common SQL differences:
- SQLite `?` → PostgreSQL `%s` (parameter placeholders)
- SQLite `GROUP_CONCAT()` → PostgreSQL `string_agg()` (aggregate functions)
- Boolean handling (SQLite uses 0/1 instead of BOOLEAN)

## Performance Notes

### Local Development
- SQLite is fast and requires no setup
- Perfect for testing new features
- All data stored in temp directory

### Production (Streamlit Cloud)
- Neon PostgreSQL free tier: 3GB storage, 1 GB/month transfer
- Sufficient for small to medium usage
- Automatic backups available in Neon dashboard
- Can scale up anytime with paid tier

## File Structure
```
Caballebrios_One/
├── streamlit_app.py          # Main application
├── requirements.txt          # Python dependencies
├── caballebrios.db          # Local SQLite (git ignored, created on first run)
├── DEPLOYMENT_GUIDE.md      # This file
├── README.md                # User guide
└── .gitignore              # Git ignore rules
```

## Development Tips

### Testing Locally
```bash
# Test with SQLite (default)
streamlit run streamlit_app.py

# Test with PostgreSQL (if you have a local instance)
export DATABASE_URL="postgresql://localhost/caballebrios"
streamlit run streamlit_app.py
```

### Adding New Features
1. Test locally with SQLite first
2. Ensure SQL syntax works in both SQLite and PostgreSQL
3. Use parameterized queries (with `?` for SQLite)
4. App will auto-convert for PostgreSQL

### Database Inspection
```bash
# Local SQLite
sqlite3 /tmp/caballebrios.db ".tables"
sqlite3 /tmp/caballebrios.db ".schema"

# Neon PostgreSQL (from psql)
psql "your_connection_string"
\dt                    # List tables
\d table_name         # Describe table
```

## Support

For issues or questions:
1. Check logs in Streamlit Cloud dashboard ("Manage app" → "Logs")
2. Review this guide's troubleshooting section
3. Check GitHub issues repository

---
Last Updated: December 2025
Version: 1.0 (Neon PostgreSQL ready)
