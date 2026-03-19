"""
main.py — Music Compass API Entry Point
Run: uvicorn app.main:app --reload --port 8000
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import spotify, scores, analysis

app = FastAPI(title="Music Compass API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(spotify.router)
app.include_router(scores.router)
app.include_router(analysis.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Music Compass API v2"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/debug/env")
def debug_env():
    """LOCAL DEBUG — visit http://localhost:8000/debug/env to verify setup."""
    import os
    key        = os.getenv("GEMINI_API_KEY", "")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    result = {
        "GEMINI_API_KEY_set":     bool(key),
        "GEMINI_API_KEY_preview": key[:8] + "..." if key else "MISSING",
        "GEMINI_MODEL":           model_name,
    }

    if key:
        try:
            from google import genai
            client = genai.Client(api_key=key)
            resp   = client.models.generate_content(
                model=model_name,
                contents="Reply with just the word WORKING",
            )
            result["gemini_live_test"] = "PASS — " + resp.text.strip()[:60]
        except Exception as e:
            result["gemini_live_test"] = f"FAIL — {e}"
    else:
        result["gemini_live_test"] = "SKIPPED — no key"

    return result
