"""
api/app.py — FastAPI app for WORLD13 simulation API.
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager
from .routes import router
from engine.world_vault import WorldVault

vault: WorldVault = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global vault
    vault = WorldVault()
    yield


app = FastAPI(
    title="WORLD13 API",
    description="Persistent civilization simulation governed by the Ventura Recursion",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "NOMINAL", "world": "WORLD13", "version": "0.1.0"}
