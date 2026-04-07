"""
kaggle_lookup.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Song Feature Lookup Engine

Lookup priority per song:
  1. Kaggle exact match      (O(1) HashMap — instant, in-memory)
  2. Kaggle fuzzy match      (RapidFuzz ≥ 80 — instant, in-memory)
  3. Supabase cache          (shared across ALL users/deployments — Gemini results only)
  4. Gemini AI batch         (50 unknowns per call — last resort)
     └─ writes results back to Supabase so next user never pays this cost again
  5. Neutral fallback 0.5/0.5

Why no local JSON cache:
  On Vercel (serverless), every function invocation starts with a fresh filesystem.
  A local file cache resets on every cold start and is never shared across users.
  Supabase is the only persistent, cross-user cache that actually works here.

Supabase table (run once in your Supabase SQL editor):
  create table song_scores (
    norm_key   text primary key,
    energy     float not null,
    valence    float not null,
    genre      text  not null default 'unknown',
    created_at timestamptz default now()
  );

Kaggle CSV columns used:
  track_name, artists, energy, valence, track_genre
"""

import os, re, json, logging, unicodedata, threading
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

log = logging.getLogger("kaggle_lookup")

# ── Config ────────────────────────────────────────────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # .../backend/

def _resolve_path(env_var: str, default_relative: str) -> Path:
    raw = os.getenv(env_var, "")
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (_BACKEND_DIR / p).resolve()
    return (_BACKEND_DIR / default_relative).resolve()

KAGGLE_CSV_PATH = _resolve_path("KAGGLE_CSV_PATH", "data/kaggle/dataset.csv")
SUPABASE_URL    = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY", "")   # use service_role key for backend

FUZZY_THRESHOLD  = 80
MIN_TOTAL_MS     = 60_000   # skip songs under 1 min total listening time
TOP_N_SONGS      = 500      # never score more than 500 songs per user
GEMINI_CHUNK     = 50       # songs per Gemini API call
PARALLEL_WORKERS = 20       # threads for Kaggle lookups

SOURCE_EXACT    = "kaggle_exact"
SOURCE_FUZZY    = "kaggle_fuzzy"
SOURCE_SUPABASE = "supabase_cache"
SOURCE_GEMINI   = "gemini_predicted"
SOURCE_DEFAULT  = "default"


# ── Normalizer ────────────────────────────────────────────────────────────────
def normalize(text: str) -> str:
    """
    Lowercase, strip accents, remove feat./bracket content, collapse spaces.
    This is the primary key used in Supabase — must never change once deployed.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"\s*(feat\.?|ft\.?|featuring|with)\s+.*", "", text)
    text = re.sub(r"[\(\[\{].*?[\)\]\}]", "", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


# ── Supabase Client ───────────────────────────────────────────────────────────
class SupabaseCache:
    """
    Thin wrapper around the Supabase Python client.
    Only stores Gemini-predicted results — Kaggle hits are never written here.

    If SUPABASE_URL or SUPABASE_KEY are missing, all methods become no-ops
    so the app degrades gracefully without Supabase configured.
    """

    def __init__(self):
        self._client = None
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                from supabase import create_client
                self._client = create_client(SUPABASE_URL, SUPABASE_KEY)
                log.info("Supabase cache connected")
            except Exception as e:
                log.warning(f"Supabase init failed — running without cloud cache: {e}")
        else:
            log.info("SUPABASE_URL/KEY not set — running without cloud cache")

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def fetch_batch(self, norm_keys: list) -> dict:
        """
        Fetch multiple norm_keys in ONE query.
        Returns dict: norm_key -> {energy, valence, genre}
        """
        if not self.enabled or not norm_keys:
            return {}
        try:
            resp = (
                self._client.table("song_scores")
                .select("norm_key, energy, valence, genre")
                .in_("norm_key", norm_keys)
                .execute()
            )
            return {row["norm_key"]: row for row in (resp.data or [])}
        except Exception as e:
            log.warning(f"Supabase fetch failed: {e}")
            return {}

    def upsert_batch(self, rows: list):
        """
        Write Gemini results to Supabase in one upsert.
        rows = [{"norm_key": str, "energy": float, "valence": float, "genre": str}]
        """
        if not self.enabled or not rows:
            return
        try:
            self._client.table("song_scores").upsert(
                rows, on_conflict="norm_key"
            ).execute()
            log.info(f"Supabase: upserted {len(rows)} Gemini results")
        except Exception as e:
            log.warning(f"Supabase upsert failed: {e}")


# ── Kaggle Index ──────────────────────────────────────────────────────────────
class KaggleIndex:
    """
    Builds in-memory lookup structures from dataset.csv at startup (once).
      exact_map:    normalized_track_name -> {energy, valence, genre}
      genre_pools:  genre -> list of calibration examples
      artist_genre: normalized_artist -> genre
    """

    def __init__(self, csv_path: Path):
        self.exact_map:    dict = {}
        self.genre_pools:  dict = {}
        self.artist_genre: dict = {}
        self.all_keys:     list = []
        self._build(csv_path)

    def _build(self, csv_path: Path):
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Kaggle CSV not found at: {csv_path}\n"
                f"Download dataset.csv and place it at {csv_path}"
            )
        log.info(f"Building Kaggle index from {csv_path} ...")
        df = pd.read_csv(csv_path, low_memory=False)

        built = 0
        for _, row in df.iterrows():
            raw_track  = str(row.get("track_name", "") or "").strip()
            raw_artist = str(row.get("artists",    "") or "").strip()
            genre      = str(row.get("track_genre", "unknown") or "unknown").strip()

            if not raw_track:
                continue
            try:
                energy  = round(float(row["energy"]),  4)
                valence = round(float(row["valence"]), 4)
            except (ValueError, TypeError):
                continue

            norm = normalize(raw_track)
            if not norm:
                continue

            if norm not in self.exact_map:
                self.exact_map[norm] = {"energy": energy, "valence": valence, "genre": genre}
                self.all_keys.append(norm)
                built += 1

            pool = self.genre_pools.setdefault(genre, [])
            if len(pool) < 200:
                pool.append({
                    "track":   raw_track,
                    "artist":  raw_artist.split(";")[0],
                    "energy":  energy,
                    "valence": valence,
                })

            primary = normalize(raw_artist.split(";")[0])
            if primary and primary not in self.artist_genre:
                self.artist_genre[primary] = genre

        log.info(f"Kaggle index: {built} tracks, {len(self.genre_pools)} genres")

    def exact_lookup(self, norm: str) -> Optional[dict]:
        return self.exact_map.get(norm)

    def fuzzy_lookup(self, norm: str, threshold: int = FUZZY_THRESHOLD) -> Optional[tuple]:
        """Returns (entry, score, matched_key) or None."""
        try:
            from rapidfuzz import process, fuzz
            result = process.extractOne(
                norm, self.all_keys,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=threshold,
            )
            if result:
                matched_key, score, _ = result
                return self.exact_map[matched_key], int(score), matched_key
        except ImportError:
            for key in self.all_keys:
                if norm in key or key in norm:
                    return self.exact_map[key], 75, key
        return None

    def detect_genre(self, artist: str) -> str:
        norm = normalize(artist.split(";")[0])
        return self.artist_genre.get(norm, "pop")


# ── Gemini Predictor ──────────────────────────────────────────────────────────
class GeminiPredictor:
    SYSTEM = (
        "You are a music audio feature analyst. "
        "Predict Spotify-style energy and valence scores (0.0-1.0) for songs. "
        "Be consistent - the same song should always receive the same score. "
        "Respond with ONLY valid JSON - no markdown, no explanation."
    )

    def __init__(self):
        self._client = None
        self._lock   = threading.Lock()

    def _get_client(self):
        with self._lock:
            if not self._client:
                api_key = os.getenv("GEMINI_API_KEY", "")
                if not api_key:
                    raise ValueError("GEMINI_API_KEY not set in .env")
                from google import genai
                self._client = genai.Client(api_key=api_key)
        return self._client

    def predict_batch(self, unknowns: list) -> dict:
        """
        Predict energy+valence for a list of songs in ONE Gemini API call.
        unknowns = [{"track": str, "artist": str, "genre": str}, ...]
        Returns dict: "track|||artist" -> {"energy": float, "valence": float}
        """
        if not unknowns:
            return {}

        lines = "\n".join(
            f'{i+1}. "{s["track"]}" by {s["artist"]} (genre: {s.get("genre", "unknown")})'
            for i, s in enumerate(unknowns)
        )
        prompt = (
            f"Predict Spotify audio features (energy, valence 0.0-1.0) "
            f"for these {len(unknowns)} songs.\n"
            f"Be consistent - same song always gets same score.\n\n"
            f"{lines}\n\n"
            f"Return ONLY a JSON array in the exact same order, no extra fields:\n"
            f'[{{"energy": 0.0, "valence": 0.0}}, ...]'
        )

        try:
            from google.genai import types as gtypes
            resp = self._get_client().models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                contents=prompt,
                config=gtypes.GenerateContentConfig(system_instruction=self.SYSTEM),
            )
            raw   = re.sub(r"```json|```", "", resp.text).strip()
            preds = json.loads(raw)

            return {
                f"{unknowns[i]['track']}|||{unknowns[i]['artist']}": {
                    "energy":  max(0.0, min(1.0, float(p["energy"]))),
                    "valence": max(0.0, min(1.0, float(p["valence"]))),
                }
                for i, p in enumerate(preds)
                if i < len(unknowns)
            }
        except Exception as e:
            log.error(f"Gemini batch predict error: {e}")
            return {}


# ── Main Lookup Engine ────────────────────────────────────────────────────────
class SongLookupEngine:
    """
    6-step pipeline per batch:
      1. Deduplicate      — score each unique (track, artist) only once
      2. Filter & cap     — skip <1min songs, top 500 only
      3. Parallel Kaggle  — exact + fuzzy, in-memory, zero API cost
      4. Supabase SELECT  — one query for all Kaggle misses
      5. Gemini batch     — only songs Supabase didn't have
                            results written back to Supabase for all future users
      6. Fan out          — copy results back to every original list position

    Over time, step 5 approaches zero as Supabase fills up across all users.
    """

    def __init__(self):
        self.kaggle   = KaggleIndex(KAGGLE_CSV_PATH)
        self.supabase = SupabaseCache()
        self.gemini   = GeminiPredictor()
        log.info("SongLookupEngine ready")

    def lookup_batch(self, songs: list) -> list:
        total_input = len(songs)

        # ── Step 1: Deduplicate ───────────────────────────────────────────────
        seen_keys:     dict = {}   # norm_key -> first song object
        dedup_indices: dict = {}   # norm_key -> [original indices]
        for i, s in enumerate(songs):
            key = f"{normalize(s['track'])}|||{normalize(s['artist'])}"
            dedup_indices.setdefault(key, []).append(i)
            if key not in seen_keys:
                seen_keys[key] = s

        unique_songs = list(seen_keys.values())
        log.info(f"Dedup: {total_input} input -> {len(unique_songs)} unique songs")

        # ── Step 2: Filter & cap ──────────────────────────────────────────────
        scored_set = set()
        to_score   = []
        for s in sorted(unique_songs, key=lambda x: x.get("total_ms", 0), reverse=True):
            if s.get("total_ms", 0) >= MIN_TOTAL_MS and len(to_score) < TOP_N_SONGS:
                to_score.append(s)
                scored_set.add(id(s))

        log.info(
            f"Filter: {len(unique_songs)} unique -> {len(to_score)} to score, "
            f"{len(unique_songs) - len(to_score)} skipped"
        )

        results:       list = [None] * total_input
        unique_result: dict = {}   # norm_key -> scored dict

        def _fan_out():
            for key, indices in dedup_indices.items():
                r = unique_result.get(key)
                if r is not None:
                    for idx in indices:
                        results[idx] = {**r, "total_ms": songs[idx].get("total_ms", 0)}

        # Default-fill filtered-out songs
        for s in unique_songs:
            key = f"{normalize(s['track'])}|||{normalize(s['artist'])}"
            if id(s) not in scored_set:
                unique_result[key] = self._build(
                    s["track"], s["artist"], s.get("total_ms", 0),
                    0.5, 0.5, SOURCE_DEFAULT, "unknown"
                )

        # ── Step 3: Parallel Kaggle lookups ──────────────────────────────────
        kaggle_unknowns = []

        def _kaggle_lookup(song):
            norm      = normalize(song["track"])
            cache_key = f"{norm}|||{normalize(song['artist'])}"

            exact = self.kaggle.exact_lookup(norm)
            if exact:
                return cache_key, self._build(
                    song["track"], song["artist"], song.get("total_ms", 0),
                    exact["energy"], exact["valence"], SOURCE_EXACT, exact["genre"]
                )

            fuzzy = self.kaggle.fuzzy_lookup(norm)
            if fuzzy:
                entry, score, matched = fuzzy
                return cache_key, self._build(
                    song["track"], song["artist"], song.get("total_ms", 0),
                    entry["energy"], entry["valence"], SOURCE_FUZZY, entry["genre"],
                    match_score=score, matched_key=matched
                )

            return cache_key, None   # needs Supabase / Gemini

        completed = 0
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            futures = {executor.submit(_kaggle_lookup, s): s for s in to_score}
            for future in as_completed(futures):
                song            = futures[future]
                cache_key, result = future.result()
                completed      += 1
                if result:
                    unique_result[cache_key] = result
                else:
                    genre = self.kaggle.detect_genre(song["artist"])
                    kaggle_unknowns.append({
                        **song,
                        "genre":      genre,
                        "_cache_key": cache_key,
                    })
                if completed % 100 == 0:
                    log.info(f"Kaggle: {completed}/{len(to_score)} done")

        log.info(
            f"Kaggle complete - {len(to_score) - len(kaggle_unknowns)} hits, "
            f"{len(kaggle_unknowns)} need Supabase/Gemini"
        )

        # ── Step 4: Supabase batch SELECT for all Kaggle misses ───────────────
        # One single query - never one query per song.
        gemini_unknowns = []

        if kaggle_unknowns:
            norm_keys = [s["_cache_key"] for s in kaggle_unknowns]
            supa_hits = self.supabase.fetch_batch(norm_keys)

            for song in kaggle_unknowns:
                hit = supa_hits.get(song["_cache_key"])
                if hit:
                    unique_result[song["_cache_key"]] = self._build(
                        song["track"], song["artist"], song.get("total_ms", 0),
                        hit["energy"], hit["valence"], SOURCE_SUPABASE, hit["genre"]
                    )
                else:
                    gemini_unknowns.append(song)

            log.info(
                f"Supabase: {len(supa_hits)} hits, "
                f"{len(gemini_unknowns)} still need Gemini"
            )

        # ── Step 5: Gemini for anything Supabase didn't have ──────────────────
        # After all chunks, bulk-upsert every new result to Supabase once.
        # Next user who has the same song skips Gemini entirely.
        if gemini_unknowns:
            supabase_rows = []

            for chunk_start in range(0, len(gemini_unknowns), GEMINI_CHUNK):
                chunk = gemini_unknowns[chunk_start: chunk_start + GEMINI_CHUNK]
                preds = self.gemini.predict_batch(chunk)

                for song in chunk:
                    pred_key = f"{song['track']}|||{song['artist']}"
                    pred     = preds.get(pred_key)

                    if pred:
                        r = self._build(
                            song["track"], song["artist"], song.get("total_ms", 0),
                            pred["energy"], pred["valence"], SOURCE_GEMINI, song["genre"]
                        )
                        supabase_rows.append({
                            "norm_key": song["_cache_key"],
                            "energy":   pred["energy"],
                            "valence":  pred["valence"],
                            "genre":    song["genre"],
                        })
                    else:
                        log.warning(f"Gemini missed '{song['track']}' - using default")
                        r = self._build(
                            song["track"], song["artist"], song.get("total_ms", 0),
                            0.5, 0.5, SOURCE_DEFAULT, "unknown"
                        )

                    unique_result[song["_cache_key"]] = r

                log.info(
                    f"Gemini batch: "
                    f"{min(chunk_start + GEMINI_CHUNK, len(gemini_unknowns))}"
                    f"/{len(gemini_unknowns)} done"
                )

            # Persist all new Gemini results to Supabase in one upsert
            self.supabase.upsert_batch(supabase_rows)

        # ── Step 6: Fan all results back to original positions ────────────────
        _fan_out()

        # Safety net
        for i, r in enumerate(results):
            if r is None:
                s = songs[i]
                results[i] = self._build(
                    s["track"], s["artist"], s.get("total_ms", 0),
                    0.5, 0.5, SOURCE_DEFAULT, "unknown"
                )

        log.info(f"lookup_batch complete: {total_input} songs processed")
        return results

    # ── Single lookup (for /scores/lookup endpoint) ───────────────────────────
    def lookup(self, track: str, artist: str, total_ms: int = 0) -> dict:
        norm      = normalize(track)
        cache_key = f"{norm}|||{normalize(artist)}"

        exact = self.kaggle.exact_lookup(norm)
        if exact:
            return self._build(track, artist, total_ms,
                               exact["energy"], exact["valence"],
                               SOURCE_EXACT, exact["genre"])

        fuzzy = self.kaggle.fuzzy_lookup(norm)
        if fuzzy:
            entry, score, matched = fuzzy
            return self._build(track, artist, total_ms,
                               entry["energy"], entry["valence"],
                               SOURCE_FUZZY, entry["genre"],
                               match_score=score, matched_key=matched)

        # Check Supabase before calling Gemini
        supa_hits = self.supabase.fetch_batch([cache_key])
        if cache_key in supa_hits:
            hit = supa_hits[cache_key]
            return self._build(track, artist, total_ms,
                               hit["energy"], hit["valence"],
                               SOURCE_SUPABASE, hit["genre"])

        # Last resort: Gemini, then save result to Supabase
        genre = self.kaggle.detect_genre(artist)
        preds = self.gemini.predict_batch([{
            "track": track, "artist": artist,
            "genre": genre, "_cache_key": cache_key,
        }])
        pred_key = f"{track}|||{artist}"
        if pred_key in preds:
            p = preds[pred_key]
            self.supabase.upsert_batch([{
                "norm_key": cache_key,
                "energy":   p["energy"],
                "valence":  p["valence"],
                "genre":    genre,
            }])
            return self._build(track, artist, total_ms,
                               p["energy"], p["valence"], SOURCE_GEMINI, genre)

        log.warning(f"All methods failed: '{track}' - using neutral 0.5/0.5")
        return self._build(track, artist, total_ms, 0.5, 0.5, SOURCE_DEFAULT, "unknown")

    def stats(self) -> dict:
        return {
            "kaggle_index_size": len(self.kaggle.exact_map),
            "supabase_enabled":  self.supabase.enabled,
        }

    @staticmethod
    def _build(track, artist, total_ms, energy, valence, source, genre,
               match_score=None, matched_key=None) -> dict:
        return {
            "track":       track,
            "artist":      artist,
            "total_ms":    total_ms,
            "energy":      round(energy,  4),
            "valence":     round(valence, 4),
            "source":      source,
            "genre":       genre,
            "match_score": match_score,
            "matched_key": matched_key,
        }


# ── Module-level singleton ────────────────────────────────────────────────────
_ENGINE_INSTANCE: Optional[SongLookupEngine] = None
_ENGINE_LOCK = threading.Lock()


def get_engine() -> SongLookupEngine:
    global _ENGINE_INSTANCE
    if _ENGINE_INSTANCE is None:
        with _ENGINE_LOCK:
            if _ENGINE_INSTANCE is None:
                _ENGINE_INSTANCE = SongLookupEngine()
    return _ENGINE_INSTANCE
