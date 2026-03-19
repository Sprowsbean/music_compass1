"""
POST /analysis/regression  →  weighted linear regression
POST /analysis/astrology   →  Gemini personality reading
"""

from fastapi import APIRouter
from pydantic import BaseModel
from app.services.analysis_service import (
    linear_regression, calculate_centroid,
    dominant_quadrant, generate_astrology,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])


class RegressionReq(BaseModel):
    songs:  list[dict]
    x_axis: str = "energy"
    y_axis: str = "valence"


class AstrologyReq(BaseModel):
    user_name:     str
    songs:         list[dict]
    date_of_birth: str = ""


@router.post("/regression")
def regression(req: RegressionReq):
    return linear_regression(req.songs, req.x_axis, req.y_axis)


@router.post("/astrology")
def astrology(req: AstrologyReq):
    centroid   = calculate_centroid(req.songs)
    quadrant   = dominant_quadrant(centroid)
    regression = linear_regression(req.songs)
    reading    = generate_astrology(
        req.user_name, req.songs, centroid, quadrant, regression,
        date_of_birth=req.date_of_birth,
    )
    return {
        "user_name":  req.user_name,
        "centroid":   centroid,
        "quadrant":   quadrant,
        "regression": regression,
        "reading":    reading,
    }


@router.post("/centroid")
def centroid_endpoint(body: dict):
    songs    = body.get("songs", [])
    centroid = calculate_centroid(songs)
    return {"centroid": centroid, "quadrant": dominant_quadrant(centroid)}
