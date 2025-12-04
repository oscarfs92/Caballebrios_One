# Persistent Database Setup for Streamlit Cloud

## 🗄️ Option A: Neon (Recommended - Easiest)

### 1. Create Free PostgreSQL Database

1. Go to [neon.tech](https://neon.tech)
2. Sign up with GitHub (click "Sign up")
3. Create a new project:
   - Name: `caballebrios`
   - Region: Choose closest to you
4. Click "Create project"
5. You'll see a connection string like:
   ```
   postgresql://user:password@neon_host/caballebrios
   ```

### 2. Add Database URL to Streamlit Secrets

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Find your deployed app
3. Click the **⋮ menu** → **Settings**
4. Go to **"Secrets"** tab
5. Paste this into the text box:
   ```
   DATABASE_URL="postgresql://user:password@neon_host/caballebrios"
   ```
   (Replace with your actual connection string from Neon)
6. Click **Save**

### 3. App Auto-Migrates on First Run
- The app will automatically create all tables in PostgreSQL
- Your data persists forever! ✅

---

## 🗄️ Option B: Render (Alternative)

1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Create new PostgreSQL database:
   - Click **"New"** → **"PostgreSQL"**
   - Name: `caballebrios`
   - Region: Your preference
4. Copy the **"External Database URL"**
5. Add to Streamlit Secrets (same as Neon above)

---

## 🔐 Security Note

**Keep your DATABASE_URL secret!**
- ✅ Stored securely in Streamlit Secrets (not visible in code)
- ✅ Never commit to GitHub
- ❌ Never share the connection string publicly

---

## 📊 Testing Locally

To test PostgreSQL locally:

1. Install psycopg2:
   ```bash
   pip install psycopg2-binary
   ```

2. Create `.streamlit/secrets.toml` in your workspace:
   ```
   DATABASE_URL="postgresql://user:password@localhost/caballebrios"
   ```

3. Run app:
   ```bash
   streamlit run streamlit_app.py
   ```

---

## ✅ Verification

Once deployed:
1. Open your Streamlit app
2. Go to **👥 Gestión de Jugadores**
3. Add a test player
4. Refresh the page
5. Player should still be there ✅ (data persisted!)

---

## 🆘 Troubleshooting

- **"DATABASE_URL not found"** → Add it to Streamlit Secrets
- **"Connection refused"** → Check Neon/Render database is running
- **"psycopg2 not found"** → Already added to `requirements.txt`, will install on deploy

---

## Next Steps

1. ✅ Code is ready (see `db_handler.py`)
2. Push to GitHub (I can do this)
3. Create Neon database (2 min)
4. Add DATABASE_URL to Streamlit Secrets (1 min)
5. Redeploy app (auto-updates from GitHub)
6. Done! Data is now persistent 🎉
