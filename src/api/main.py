from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import router

app = FastAPI(
    title="APOLLO - Systematic Literature Review Screening Tool",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

dist = Path("frontend/dist")
if dist.is_dir():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")
