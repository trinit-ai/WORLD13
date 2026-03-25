"""
api/api_voynich.py — Voynich reader API endpoints.
"""

import os
import glob
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/api/voynich")

PAGES_DIR = "data/theatres/digital_voynich/pages"

_voynich_state = {
    "is_running": False,
    "instance_id": None,
}


@router.get("/page/{page_number}", response_class=HTMLResponse)
async def get_page(page_number: int):
    page_path = os.path.join(PAGES_DIR, f"page_{page_number:04d}.html")
    if not os.path.exists(page_path):
        raise HTTPException(status_code=404, detail=f"Page {page_number} not found")
    with open(page_path, "r") as f:
        return f.read()


@router.get("/status")
async def voynich_status():
    pages = glob.glob(os.path.join(PAGES_DIR, "page_*.html"))
    return {
        "page_count": len(pages),
        "is_running": _voynich_state["is_running"],
        "instance_id": _voynich_state.get("instance_id"),
    }


@router.post("/open")
async def open_book():
    _voynich_state["is_running"] = True
    return {"status": "open"}


@router.post("/close")
async def close_book():
    _voynich_state["is_running"] = False
    return {"status": "closed"}


@router.get("/manifest")
async def voynich_manifest():
    return {
        "instance_id": _voynich_state.get("instance_id"),
        "vault_mode": "sealed",
    }
