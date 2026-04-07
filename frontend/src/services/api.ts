/**
 * api.ts — typed client for the Music Compass FastAPI backend
 * All calls go through /api which Vite proxies to http://localhost:8000
 */

const BASE = (import.meta as any).env?.VITE_API_URL || '/api';

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => `HTTP ${res.status}`);
    throw new Error(msg);
  }
  return res.json();
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────────────
export interface ScoredSong {
  track:       string;
  artist:      string;
  total_ms:    number;
  energy:      number | null;
  valence:     number | null;
  source:      'kaggle_exact' | 'kaggle_fuzzy' | 'supabase_cache' | 'gemini_predicted' | 'default';
  genre:       string;
  match_score: number | null;
  matched_key: string | null;
}

export interface ImportResult {
  user_id:     string;
  name:        string;
  raw_count:   number;
  total_songs: number;
  total_ms:    number;
  songs:       { track: string; artist: string; total_ms: number }[];
}

export interface RegressionResult {
  slope:          number;
  intercept:      number;
  r_squared:      number;
  x_mean:         number;
  y_mean:         number;
  n_songs:        number;
  interpretation: string;
  error?:         string;
}

export interface AstrologyResult {
  user_name:  string;
  centroid:   { energy: number; valence: number };
  quadrant:   string;
  regression: RegressionResult;
  reading: {
    archetype: string;
    headline:  string;
    reading:   string;
    element:   string;
    hz:        string;
  };
}

// ── Endpoints ─────────────────────────────────────────────────────────────
export const api = {
  /** Step 1 – Parse Spotify JSON, returns unique songs with total_ms */
  async importSpotify(files: File[], name: string): Promise<ImportResult> {
    const form = new FormData();
    files.forEach(f => form.append('files', f));
    form.append('user_id', name.toLowerCase().replace(/\s+/g, '_'));
    form.append('name', name);
    const res = await fetch(`${BASE}/spotify/import`, { method: 'POST', body: form });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  /** Step 2 – Score every song: Kaggle → Gemini → fallback */
  async lookupBatch(
    songs: { track: string; artist: string; total_ms: number }[],
    userId: string,
  ): Promise<ScoredSong[]> {
    return post('/scores/lookup-batch', { songs, user_id: userId });
  },

  /** Weighted linear regression between two axes */
  async getRegression(songs: ScoredSong[]): Promise<RegressionResult> {
    return post('/analysis/regression', { songs, x_axis: 'energy', y_axis: 'valence' });
  },

  /** Gemini music astrology reading */
  async getAstrology(userName: string, songs: ScoredSong[], dateOfBirth?: string): Promise<AstrologyResult> {
    return post('/analysis/astrology', { user_name: userName, songs, date_of_birth: dateOfBirth ?? '' });
  },

  /** Cache + index stats */
  async getStats(): Promise<unknown> {
    return get('/scores/stats');
  },

  /** Health check */
  async health(): Promise<{ status: string }> {
    return get('/health');
  },
};
