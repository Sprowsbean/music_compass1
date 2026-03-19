"""
POST /spotify/import
  Upload StreamingHistory JSON → returns aggregated unique songs with total_ms.
  Pass the returned `songs` list directly to POST /scores/lookup-batch.
"""

import json, tempfile, os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.spotify_parser import parse_spotify_history, to_lookup_list

router = APIRouter(prefix="/spotify", tags=["spotify"])


@router.post("/import")
async def import_spotify(
    files:   list[UploadFile] = File(...),
    user_id: str              = Form(default="anonymous"),
    name:    str              = Form(default=""),
):
    if not files:
        raise HTTPException(400, "No files uploaded.")

    all_events = []
    for file in files:
        if not file.filename.endswith(".json"):
            raise HTTPException(400, f"'{file.filename}' must be a .json file")
        raw = await file.read()
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            raise HTTPException(400, f"Could not parse '{file.filename}' as JSON")
        if isinstance(data, list):
            all_events.extend(data)

    if not all_events:
        raise HTTPException(400, "No play events found.")

    # Write to temp file and parse
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(all_events, tmp, ensure_ascii=False)
        tmp_path = tmp.name

    try:
        parsed = parse_spotify_history(tmp_path)
    finally:
        os.unlink(tmp_path)

    return {
        "user_id":     user_id,
        "name":        name or user_id,
        "raw_count":   parsed["raw_count"],
        "total_songs": parsed["total_songs"],
        "total_ms":    parsed["total_ms"],
        "songs":       to_lookup_list(parsed["songs"]),
    }
