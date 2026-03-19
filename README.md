# 🌌 Music Compass

> Upload your Spotify history → Match against Kaggle DB → Predict unknowns with Gemini AI → Plot your galactic sound map

---

## Quick Start (2 terminals)

### Prerequisites
- Python 3.11+
- Node.js 18+
- Kaggle `dataset.csv` (100k Spotify tracks)
- Google Gemini API key (free at aistudio.google.com)

---

### 1 · Backend

```bash
cd backend

# Create virtualenv (recommended)
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and edit .env
cp .env.example .env
# → Add your GEMINI_API_KEY

# Place Kaggle CSV
mkdir -p data/kaggle
cp /path/to/your/dataset.csv data/kaggle/dataset.csv

# Start API server
uvicorn app.main:app --reload --port 8000
```

Backend runs at: http://localhost:8000  
API docs at:     http://localhost:8000/docs

---

### 2 · Frontend

```bash
cd frontend

npm install
npm run dev
```

Frontend runs at: http://localhost:5173

---

## Project Structure

```
music-compass/
├── backend/
│   ├── app/
│   │   ├── main.py                        # FastAPI entry point
│   │   ├── api/routes/
│   │   │   ├── spotify.py                 # POST /spotify/import
│   │   │   ├── scores.py                  # POST /scores/lookup-batch
│   │   │   └── analysis.py                # POST /analysis/regression + /astrology
│   │   └── services/
│   │       ├── spotify_parser.py           # Parse StreamingHistory JSON
│   │       ├── kaggle_lookup.py            # Kaggle index + fuzzy + Gemini
│   │       └── analysis_service.py         # Regression, centroid, astrology
│   ├── data/
│   │   ├── kaggle/dataset.csv              # ← Place here
│   │   └── cache/score_cache.json          # Auto-created, persists across runs
│   ├── .env.example
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── App.tsx                         # Main app with all views
    │   ├── index.css                       # Galactic nebula theme
    │   ├── hooks/
    │   │   └── usePipeline.ts              # All pipeline state management
    │   ├── services/
    │   │   └── api.ts                      # Typed API client
    │   └── components/
    │       ├── UploadZone.tsx              # File upload with name input
    │       ├── MusicMap.tsx                # Scatter plot (dot size = ms_played)
    │       ├── RadarChart.tsx              # Taste fingerprint
    │       ├── TopSongsTable.tsx           # Ranked songs with source badges
    │       └── AstrologyCard.tsx           # Gemini personality reading
    ├── index.html
    ├── package.json
    └── vite.config.ts                      # Proxies /api → localhost:8000
```

---

## Pipeline Flow

```
StreamingHistory_music_0.json
          │
          ▼
  spotify_parser.py
  • Read every event: { trackName, artistName, msPlayed }
  • Skip plays < 10 seconds
  • GROUP BY trackName + artistName
  • SUM(msPlayed) per unique song
  • Sort by total_ms descending
          │
          ▼
  Unique song list: [{ track, artist, total_ms }]
          │
          ▼
  kaggle_lookup.py  (per song)
  ┌─────────────────────────────────────┐
  │ 1. Check JSON cache (instant)        │
  │ 2. Kaggle exact match on track_name  │
  │ 3. Kaggle fuzzy match (RapidFuzz ≥80)│
  │ 4. Gemini AI prediction              │
  │    - 10 genre-matched examples       │
  │    - Returns energy + valence        │
  │ 5. Default 0.5/0.5 (last resort)    │
  └─────────────────────────────────────┘
          │
          ▼
  Scored songs: [{ ..., energy, valence, source, total_ms }]
          │
          ▼
  analysis_service.py
  • Weighted linear regression (weight = total_ms)
  • Centroid calculation
  • Gemini music astrology reading
          │
          ▼
  Frontend: MusicMap
  • X = Energy, Y = Valence
  • Dot size ∝ total_ms  (most-played = biggest dot)
  • Color = source (cyan=Kaggle, pink=Gemini, gold=Fuzzy)
  • Gold dashed regression line
  • Quadrant labels
```

---

## Kaggle Dataset

Download from:
https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset

The CSV has columns: `track_name, artists, energy, valence, track_genre, ...`

Place it at: `backend/data/kaggle/dataset.csv`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/spotify/import` | Parse history JSON → unique songs |
| POST | `/scores/lookup-batch` | Score list of songs |
| POST | `/scores/lookup` | Score single song |
| POST | `/analysis/regression` | Weighted linear regression |
| POST | `/analysis/astrology` | Gemini personality reading |
| GET  | `/scores/stats` | Cache statistics |
| GET  | `/health` | Health check |

---

## Environment Variables

```env
GEMINI_API_KEY=AIzaSy...                    # Required for unmatched songs
GEMINI_MODEL=gemini-2.5-flash-preview-04-17             # Or gemini-1.5-flash

KAGGLE_CSV_PATH=backend/data/kaggle/dataset.csv
CACHE_PATH=backend/data/cache/score_cache.json
```

---

## Notes

- The **cache** (`score_cache.json`) persists forever — songs are never re-scored once cached
- ~55% of typical Spotify histories will match Kaggle exactly by track name
- `rapidfuzz` is optional — install it for better fuzzy matching performance
- The backend reads from `backend/data/kaggle/dataset.csv` relative to where you run `uvicorn` (i.e., from inside the `backend/` folder or set `KAGGLE_CSV_PATH` as an absolute path)
