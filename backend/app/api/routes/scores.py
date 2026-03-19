"""
POST /scores/lookup-batch  →  score a full list of songs
POST /scores/lookup        →  score one song
GET  /scores/stats         →  cache stats
"""

from fastapi import APIRouter
from pydantic import BaseModel
from app.services.kaggle_lookup import get_engine

router = APIRouter(prefix="/scores", tags=["scores"])


class SongIn(BaseModel):
    track:    str
    artist:   str
    total_ms: int = 0


class BatchIn(BaseModel):
    songs:   list[SongIn]
    user_id: str = "anonymous"


@router.post("/lookup-batch")
def lookup_batch(payload: BatchIn):
    """Main scoring endpoint. Accepts songs from /spotify/import response."""
    return get_engine().lookup_batch([s.dict() for s in payload.songs])


@router.post("/lookup")
def lookup_single(song: SongIn):
    return get_engine().lookup(song.track, song.artist, song.total_ms)


@router.get("/stats")
def cache_stats():
    return get_engine().stats()