"""
kaggle_lookup.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Song Feature Lookup Engine

Lookup priority per song:
  1. Persistent JSON cache         (free, instant)
  2. Kaggle exact match            (O(1) HashMap on normalized track_name)
  3. Kaggle fuzzy match            (RapidFuzz ≥ 80 score)
  4. Gemini AI batch prediction    (50 unknowns per API call — much faster)
  5. Neutral fallback 0.5/0.5

Optimizations vs original:
  - Parallel Kaggle lookups via ThreadPoolExecutor (20 workers)
  - Song filtering: skip <60s total, cap at top 500 by listen time
  - Gemini batch prediction: 50 songs per call instead of 1
  - Module-level singleton: Kaggle CSV only loads once per server lifetime
  - Thread-safe cache writes via Lock
  - Cache bulk-flush instead of writing on every single set()

Kaggle CSV columns used:
  track_name, artists, energy, valence, track_genre
"""

import os, re, json, time, logging, unicodedata, threading
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

log = logging.getLogger("kaggle_lookup")

# ── Config ────────────────────────────────────────────────────────────────────
# Anchor to backend/ dir so paths work regardless of where uvicorn is launched from
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # .../backend/

def _resolve_path(env_var: str, default_relative: str) -> Path:
    raw = os.getenv(env_var, "")
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (_BACKEND_DIR / p).resolve()
    return (_BACKEND_DIR / default_relative).resolve()

KAGGLE_CSV_PATH  = _resolve_path("KAGGLE_CSV_PATH", "data/kaggle/dataset.csv")
CACHE_PATH       = _resolve_path("CACHE_PATH",      "data/cache/score_cache.json")
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL     = os.getenv("GEMINI_MODEL",   "gemini-1.5-flash")

FUZZY_THRESHOLD  = 80
MIN_TOTAL_MS     = 60_000   # skip songs with less than 1 min total listening time
TOP_N_SONGS      = 500      # never score more than 500 songs per user
GEMINI_CHUNK     = 50       # songs per Gemini batch call
PARALLEL_WORKERS = 20       # ThreadPoolExecutor workers for Kaggle lookups

SOURCE_EXACT   = "kaggle_exact"
SOURCE_FUZZY   = "kaggle_fuzzy"
SOURCE_GEMINI  = "gemini_predicted"
SOURCE_DEFAULT = "default"


# ── Normalizer ────────────────────────────────────────────────────────────────
def normalize(text: str) -> str:
    """
    Lowercase, strip accents, remove feat./bracket content, collapse spaces.
    Works correctly for CJK and accented characters.
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


# ── Cache ─────────────────────────────────────────────────────────────────────
class ScoreCache:
    """
    Thread-safe JSON cache with bulk flush.
    Instead of writing to disk on every set(), we flush every FLUSH_EVERY writes
    to avoid hammering disk during parallel batch operations.
    """

    FLUSH_EVERY = 25

    def __init__(self, path: Path):
        self.path         = path
        self._lock        = threading.Lock()
        self._dirty_count = 0
        self._data: dict  = {}

        self.path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            log.info(f"Cache: {len(self._data)} entries loaded")

    def get(self, key: str) -> Optional[dict]:
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, entry: dict):
        with self._lock:
            self._data[key]   = {**entry, "cached_at": time.time()}
            self._dirty_count += 1
            if self._dirty_count >= self.FLUSH_EVERY:
                self._flush_unsafe()
                self._dirty_count = 0

    def flush(self):
        """Force a full flush to disk — call this after a batch is complete."""
        with self._lock:
            self._flush_unsafe()
            self._dirty_count = 0

    def _flush_unsafe(self):
        """Must be called with self._lock held."""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def stats(self) -> dict:
        with self._lock:
            by_source: dict = {}
            for e in self._data.values():
                s = e.get("source", "unknown")
                by_source[s] = by_source.get(s, 0) + 1
            return {"total": len(self._data), "by_source": by_source}


# ── Kaggle Index ──────────────────────────────────────────────────────────────
class KaggleIndex:
    """
    Builds lookup structures from dataset.csv at startup (once).
      exact_map:    normalized_track_name → {energy, valence, genre, artists}
      genre_pools:  genre → list of {track, artist, energy, valence}
      artist_genre: normalized_artist → genre
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
        log.info(f"Building Kaggle index from {csv_path} …")
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

            # First occurrence wins (dataset has duplicates across genres)
            if norm not in self.exact_map:
                self.exact_map[norm] = {
                    "energy":  energy,
                    "valence": valence,
                    "genre":   genre,
                    "_track":  raw_track,
                    "_artist": raw_artist,
                }
                self.all_keys.append(norm)
                built += 1

            # Genre pools for Gemini calibration (capped at 200 per genre)
            pool = self.genre_pools.setdefault(genre, [])
            if len(pool) < 200:
                pool.append({
                    "track":   raw_track,
                    "artist":  raw_artist.split(";")[0],
                    "energy":  energy,
                    "valence": valence,
                })

            # Artist → genre mapping
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

    def calibration_examples(self, genre: str, n: int = 10) -> list:
        import random
        pool = self.genre_pools.get(genre) or []
        if not pool:
            pool = [s for p in self.genre_pools.values() for s in p]
        return random.sample(pool, min(n, len(pool)))


# ── Gemini Predictor ──────────────────────────────────────────────────────────
class GeminiPredictor:
    SYSTEM = (
        "You are a music audio feature analyst. "
        "Predict Spotify-style energy and valence scores (0.0–1.0) for songs. "
        "Be consistent — the same song should always receive the same score. "
        "Respond with ONLY valid JSON — no markdown, no explanation."
    )

    def __init__(self):
        self._model = None
        self._lock  = threading.Lock()

    def _get_client(self):
        with self._lock:
            if not self._model:
                api_key = os.getenv("GEMINI_API_KEY", "")
                if not api_key:
                    raise ValueError("GEMINI_API_KEY not set in .env")
                from google import genai
                self._model = genai.Client(api_key=api_key)
        return self._model

    def predict_batch(self, unknowns: list) -> dict:
        """
        Predict energy+valence for a list of songs in ONE Gemini API call.

        unknowns = [{"track": str, "artist": str, "genre": str, "_cache_key": str}, ...]
        Returns dict keyed by "track|||artist" → {"energy": float, "valence": float}
        """
        if not unknowns:
            return {}

        lines = "\n".join(
            f'{i+1}. "{s["track"]}" by {s["artist"]} (genre: {s.get("genre","unknown")})'
            for i, s in enumerate(unknowns)
        )
        prompt = (
            f"Predict Spotify audio features (energy, valence 0.0–1.0) "
            f"for these {len(unknowns)} songs.\n"
            f"Be consistent — same song always gets same score.\n\n"
            f"{lines}\n\n"
            f"Return ONLY a JSON array in the exact same order, no extra fields:\n"
            f'[{{"energy": 0.0, "valence": 0.0}}, ...]'
        )

        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            from google.genai import types as gtypes
            resp  = self._get_client().models.generate_content(
                model=model_name,
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

    def predict(self, track: str, artist: str, examples: list) -> Optional[dict]:
        """Single-song predict — used by the non-batch lookup() path."""
        ex_text = "\n".join(
            f'  "{e["track"]}" by {e["artist"]} → energy={e["energy"]}, valence={e["valence"]}'
            for e in examples
        )
        prompt = (
            f"Calibration examples from Spotify's audio features dataset:\n{ex_text}\n\n"
            f'Predict energy and valence for:\n  Track:  "{track}"\n  Artist: "{artist}"\n\n'
            f'Return ONLY JSON: {{"energy": <0.0-1.0>, "valence": <0.0-1.0>}}'
        )
        try:
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            from google.genai import types as gtypes
            resp = self._get_client().models.generate_content(
                model=model_name,
                contents=prompt,
                config=gtypes.GenerateContentConfig(system_instruction=self.SYSTEM),
            )
            raw  = re.sub(r"```json|```", "", resp.text).strip()
            data = json.loads(raw)
            return {
                "energy":  max(0.0, min(1.0, float(data["energy"]))),
                "valence": max(0.0, min(1.0, float(data["valence"]))),
            }
        except Exception as e:
            log.error(f"Gemini single predict error for '{track}': {e}")
            return None


# ── Main Lookup Engine ────────────────────────────────────────────────────────
class SongLookupEngine:
    """
    Optimized 5-step pipeline:
      cache → kaggle exact → kaggle fuzzy → gemini batch → default

    Key differences from original:
      - lookup_batch() runs Kaggle steps in parallel (ThreadPoolExecutor)
      - All Gemini unknowns are batched into chunks of 50 (one API call each)
      - Songs under MIN_TOTAL_MS are skipped; only top TOP_N_SONGS are scored
      - Cache writes are batched and flushed once at end of batch

    Single lookup() is unchanged — works identically for one-off calls.
    """

    def __init__(self):
        self.cache  = ScoreCache(CACHE_PATH)
        self.kaggle = KaggleIndex(KAGGLE_CSV_PATH)
        self.gemini = GeminiPredictor()
        log.info("SongLookupEngine ready")

    # ── Single lookup (unchanged behaviour) ───────────────────────────────────
    def lookup(self, track: str, artist: str, total_ms: int = 0) -> dict:
        norm      = normalize(track)
        cache_key = f"{norm}|||{normalize(artist)}"

        cached = self.cache.get(cache_key)
        if cached:
            return {**cached, "track": track, "artist": artist, "total_ms": total_ms}

        exact = self.kaggle.exact_lookup(norm)
        if exact:
            result = self._build(track, artist, total_ms,
                                 exact["energy"], exact["valence"],
                                 SOURCE_EXACT, exact["genre"])
            self.cache.set(cache_key, result)
            return result

        fuzzy = self.kaggle.fuzzy_lookup(norm)
        if fuzzy:
            entry, score, matched = fuzzy
            result = self._build(track, artist, total_ms,
                                 entry["energy"], entry["valence"],
                                 SOURCE_FUZZY, entry["genre"],
                                 match_score=score, matched_key=matched)
            self.cache.set(cache_key, result)
            return result

        genre    = self.kaggle.detect_genre(artist)
        examples = self.kaggle.calibration_examples(genre, n=10)
        pred     = self.gemini.predict(track, artist, examples)
        if pred:
            result = self._build(track, artist, total_ms,
                                 pred["energy"], pred["valence"],
                                 SOURCE_GEMINI, genre)
            self.cache.set(cache_key, result)
            return result

        log.warning(f"All methods failed: '{track}' — using neutral 0.5/0.5")
        result = self._build(track, artist, total_ms, 0.5, 0.5, SOURCE_DEFAULT, "unknown")
        self.cache.set(cache_key, result)
        return result

    # ── Optimized batch lookup ─────────────────────────────────────────────────
    def lookup_batch(self, songs: list) -> list:
        """
        Optimized batch pipeline:
          1. Filter songs below MIN_TOTAL_MS, cap at TOP_N_SONGS
          2. Parallel cache + Kaggle lookups across 20 threads
          3. Collect unknowns → send to Gemini in chunks of 50
          4. Flush cache to disk once at the end

        Always returns a list the same length as input — filtered songs
        get a default 0.5/0.5 entry rather than being dropped.
        """
        total_input = len(songs)

        # ── Step 1: Filter & cap ──────────────────────────────────────────────
        scored_set = set()
        to_score   = []
        for s in sorted(songs, key=lambda x: x.get("total_ms", 0), reverse=True):
            if s.get("total_ms", 0) >= MIN_TOTAL_MS and len(to_score) < TOP_N_SONGS:
                to_score.append(s)
                scored_set.add(id(s))

        log.info(
            f"Batch filter: {total_input} input → "
            f"{len(to_score)} to score, "
            f"{total_input - len(to_score)} skipped (low playtime or capped)"
        )

        # Build index map so we can place results back in original order
        id_to_original_idx = {id(s): i for i, s in enumerate(songs)}
        results = [None] * total_input

        # Default-fill everything not being scored
        for s in songs:
            if id(s) not in scored_set:
                results[id_to_original_idx[id(s)]] = self._build(
                    s["track"], s["artist"], s.get("total_ms", 0),
                    0.5, 0.5, SOURCE_DEFAULT, "unknown"
                )

        # ── Step 2: Parallel cache + Kaggle ──────────────────────────────────
        unknowns = []

        def _fast_lookup(song):
            norm      = normalize(song["track"])
            cache_key = f"{norm}|||{normalize(song['artist'])}"

            cached = self.cache.get(cache_key)
            if cached:
                return song, {**cached, "track": song["track"],
                              "artist": song["artist"],
                              "total_ms": song.get("total_ms", 0)}

            exact = self.kaggle.exact_lookup(norm)
            if exact:
                r = self._build(song["track"], song["artist"], song.get("total_ms", 0),
                                exact["energy"], exact["valence"],
                                SOURCE_EXACT, exact["genre"])
                self.cache.set(cache_key, r)
                return song, r

            fuzzy = self.kaggle.fuzzy_lookup(norm)
            if fuzzy:
                entry, score, matched = fuzzy
                r = self._build(song["track"], song["artist"], song.get("total_ms", 0),
                                entry["energy"], entry["valence"],
                                SOURCE_FUZZY, entry["genre"],
                                match_score=score, matched_key=matched)
                self.cache.set(cache_key, r)
                return song, r

            return song, None  # needs Gemini

        completed = 0
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            futures = {executor.submit(_fast_lookup, s): s for s in to_score}
            for future in as_completed(futures):
                song, result = future.result()
                completed   += 1
                if result:
                    results[id_to_original_idx[id(song)]] = result
                else:
                    genre = self.kaggle.detect_genre(song["artist"])
                    unknowns.append({
                        **song,
                        "genre":      genre,
                        "_cache_key": (
                            f"{normalize(song['track'])}|||{normalize(song['artist'])}"
                        ),
                        "_orig_idx":  id_to_original_idx[id(song)],
                    })
                if completed % 100 == 0:
                    log.info(
                        f"Fast lookup: {completed}/{len(to_score)} "
                        f"({len(unknowns)} need Gemini so far)"
                    )

        log.info(f"Fast lookup complete. {len(unknowns)} songs need Gemini.")

        # ── Step 3: Batch Gemini for unknowns ────────────────────────────────
        for chunk_start in range(0, len(unknowns), GEMINI_CHUNK):
            chunk = unknowns[chunk_start: chunk_start + GEMINI_CHUNK]
            preds = self.gemini.predict_batch(chunk)

            for song in chunk:
                pred_key = f"{song['track']}|||{song['artist']}"
                pred     = preds.get(pred_key)

                if pred:
                    r = self._build(song["track"], song["artist"], song.get("total_ms", 0),
                                    pred["energy"], pred["valence"],
                                    SOURCE_GEMINI, song["genre"])
                else:
                    log.warning(f"Gemini missed '{song['track']}' — using default")
                    r = self._build(song["track"], song["artist"], song.get("total_ms", 0),
                                    0.5, 0.5, SOURCE_DEFAULT, "unknown")

                self.cache.set(song["_cache_key"], r)
                results[song["_orig_idx"]] = r

            log.info(
                f"Gemini batch: "
                f"{min(chunk_start + GEMINI_CHUNK, len(unknowns))}/{len(unknowns)} done"
            )

        # ── Step 4: Flush cache once ──────────────────────────────────────────
        self.cache.flush()

        # Safety net: fill any remaining None slots
        for i, r in enumerate(results):
            if r is None:
                s = songs[i]
                results[i] = self._build(
                    s["track"], s["artist"], s.get("total_ms", 0),
                    0.5, 0.5, SOURCE_DEFAULT, "unknown"
                )

        log.info(f"lookup_batch complete: {total_input} songs processed")
        return results

    def stats(self) -> dict:
        return {
            "kaggle_index_size": len(self.kaggle.exact_map),
            "cache":             self.cache.stats(),
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
# The Kaggle CSV (100k rows) only loads ONCE when the server starts.
# All requests share this engine — no repeated disk reads ever.

_ENGINE_INSTANCE: Optional[SongLookupEngine] = None
_ENGINE_LOCK = threading.Lock()


def get_engine() -> SongLookupEngine:
    """
    Returns the shared SongLookupEngine singleton.
    Thread-safe via double-checked locking.

    Usage in your routes:
        from app.services.kaggle_lookup import get_engine
        engine  = get_engine()
        results = engine.lookup_batch(songs)
    """
    global _ENGINE_INSTANCE
    if _ENGINE_INSTANCE is None:
        with _ENGINE_LOCK:
            if _ENGINE_INSTANCE is None:
                _ENGINE_INSTANCE = SongLookupEngine()
    return _ENGINE_INSTANCE