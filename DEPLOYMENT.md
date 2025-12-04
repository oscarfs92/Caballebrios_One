# Caballebrios One - Deployment Guide

## 🚀 Quick Deployment Options

### **Option 1: Streamlit Community Cloud (Easiest - FREE)**
Best for: Quick, free hosting without worrying about infrastructure.

1. Push your code to GitHub:
   ```bash
   git add streamlit_app.py requirements.txt caballebrios.db
   git commit -m "Initial commit"
   git push origin main
   ```

2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click "Create app" and connect your GitHub repo (`oscarfs92/Caballebrios_One`)
4. Point to `streamlit_app.py` as the main file
5. The app will be live at `https://caballebrios-one.streamlit.app` (or similar)

**Note:** Your SQLite database (`caballebrios.db`) will be included but will reset if the app restarts on Community Cloud. For persistent data, consider upgrading to Streamlit+ or use the "Advanced" option below.

---

### **Option 2: Railway / Heroku (Free Tier + Low Cost - Recommended)**
Best for: Custom domain, persistent database, more control.

#### Using **Railway** (simpler, modern):

1. Create a `Procfile` in your repo root:
   ```
   web: streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
   ```

2. Push code to GitHub (same as Option 1, step 1)

3. Go to [railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub"
   - Select `oscarfs92/Caballebrios_One`
   - Add a `PORT` environment variable (Railway auto-assigns it)

4. Your app will be live with a Railway domain or custom domain

---

### **Option 3: Docker + Cloud Run / AWS / DigitalOcean (Most Control)**
Best for: Production-grade deployment, scaling, custom domain.

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY streamlit_app.py .
COPY caballebrios.db .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Then deploy to:
- **Google Cloud Run** (free tier, auto-scale)
- **AWS Lightsail** (~$3–5/month)
- **DigitalOcean App Platform** (~$5–12/month)

---

## 🗄️ Database Persistence Notes

**Current setup:** SQLite (`caballebrios.db`)
- ✅ Works offline
- ✅ No server setup needed
- ❌ Data resets on Community Cloud restarts
- ❌ Not ideal for multi-user concurrent access

**For production persistence, consider:**

1. **PostgreSQL** (via Heroku Postgres, Railway, or AWS RDS)
   - Replace `sqlite3` with `psycopg2` or `sqlalchemy`
   - Connection string: `postgresql://user:password@host/db`
   - Estimated cost: $0–15/month

2. **Keep SQLite** but mount persistent storage (Railway, DigitalOcean, AWS EBS)

---

## 📋 Deployment Checklist

- [ ] Add `requirements.txt` ✅ (done)
- [ ] Create `Procfile` or `Dockerfile` (if needed)
- [ ] Push code to GitHub
- [ ] Add `.gitignore` to exclude backups:
  ```
  .venv/
  __pycache__/
  *.pyc
  *.db.bak.*
  streamlit.log
  ```
- [ ] Choose hosting platform
- [ ] Deploy and test

---

## 🔗 Recommended Path

**For quickest launch:** Streamlit Community Cloud (Option 1)
- No payment, instant deployment
- Suitable for a game-night tracker for friends

**For production with your own domain:** Railway (Option 2)
- $5–10/month for reliable hosting + database
- Easy GitHub integration, auto-deploys on push

---

## Need Help?

- **Streamlit docs:** https://docs.streamlit.io/deploy/streamlit-community-cloud
- **Railway docs:** https://docs.railway.app/
- **Database migration guide:** I can help migrate to PostgreSQL if needed

Which option interests you most?
