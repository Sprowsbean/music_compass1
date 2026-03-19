"""
spotify_parser.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Parses Spotify StreamingHistory JSON files.

Handles both export formats:
  OLD: { endTime, artistName, trackName, msPlayed }
  NEW: { ts, master_metadata_track_name,
         master_metadata_album_artist_name, ms_played }

Pipeline:
  1. Read every play event
  2. Skip skips (< 10 seconds) and null entries
  3. Group by trackName + artistName
  4. Sum msPlayed per unique song
  5. Return sorted by total_ms descending
"""

import json
import logging
from pathlib import Path
from typing import Union
from collections import defaultdict

log = logging.getLogger("spotify_parser")

MIN_MS = 10_000  # ignore plays under 10 seconds


def parse_spotify_history(source: Union[list, str, Path]) -> dict:
    """
    Accept raw JSON list, file path string, or Path object.

    Returns:
      {
        raw_count:   int   – total events in file
        total_songs: int   – unique track/artist pairs
        total_ms:    int   – total listening time in ms
        songs:       list  – unique songs sorted by total_ms desc
                             each: { track, artist, total_ms, play_count }
      }
    """
    # ── Load ──────────────────────────────────────────────────────
    if isinstance(source, (str, Path)):
        path = Path(source)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = source

    if not isinstance(data, list):
        raise ValueError("Expected a JSON array at top level")

    # ── Parse & aggregate ─────────────────────────────────────────
    song_map: dict = defaultdict(lambda: {
        "track": "", "artist": "", "total_ms": 0, "play_count": 0
    })

    for entry in data:
        # Detect format
        track  = (entry.get("trackName")
               or entry.get("master_metadata_track_name") or "").strip()
        artist = (entry.get("artistName")
               or entry.get("master_metadata_album_artist_name") or "").strip()
        ms     = int(entry.get("msPlayed") or entry.get("ms_played") or 0)

        if not track or not artist or ms < MIN_MS:
            continue

        key = f"{track}|||{artist}"
        song_map[key]["track"]      = track
        song_map[key]["artist"]     = artist
        song_map[key]["total_ms"]  += ms
        song_map[key]["play_count"] += 1

    songs = sorted(song_map.values(), key=lambda s: s["total_ms"], reverse=True)

    log.info(
        f"Parsed {len(data)} events → {len(songs)} unique songs, "
        f"{sum(s['total_ms'] for s in songs) / 3_600_000:.1f}h total"
    )

    return {
        "raw_count":   len(data),
        "total_songs": len(songs),
        "total_ms":    sum(s["total_ms"] for s in songs),
        "songs":       list(songs),
    }


def to_lookup_list(songs: list) -> list:
    """Convert parsed songs to lookup format: [{track, artist, total_ms}]"""
    return [
        {"track": s["track"], "artist": s["artist"], "total_ms": s["total_ms"]}
        for s in songs
    ]
