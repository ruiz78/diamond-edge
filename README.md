# Diamond Edge — MLB Betting Prediction App
## Deploy to Railway (free, ~5 minutes)

### Step 1 — Push files to GitHub
1. Go to github.com → click "+" → "New repository"
2. Name it: diamond-edge
3. Click "Create repository"
4. Click "uploading an existing file"
5. Drag and drop ALL these files:
   - app.py
   - Procfile
   - requirements.txt
   - README.md
   - static/index.html  ← make sure this goes inside a folder called "static"
6. Click "Commit changes"

### Step 2 — Get your Anthropic API key
1. Go to console.anthropic.com
2. Click "API Keys" → "Create Key"
3. Copy the key (save it somewhere safe)

### Step 3 — Deploy on Railway
1. Go to railway.app → sign up with GitHub (free)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your "diamond-edge" repo
4. Click "Deploy Now" — Railway auto-detects Python + Procfile
5. Once deployed, click your service → "Variables" tab
6. Click "New Variable":
   - Name:  ANTHROPIC_API_KEY
   - Value: (paste your key from Step 2)
7. Railway redeploys automatically

### Step 4 — Get your URL + open on phone
1. Click "Settings" tab → "Networking" → "Generate Domain"
2. You'll get a URL like: https://diamond-edge-production.up.railway.app
3. Open that on your phone and bookmark it to your home screen

## Done! The app will:
- Auto-load tonight's MLB games from The Odds API
- Pull live stats from Baseball Reference when you tap a game
- Run AI analysis and show full pick + value angles
- No copy/pasting or Python script needed ever again
