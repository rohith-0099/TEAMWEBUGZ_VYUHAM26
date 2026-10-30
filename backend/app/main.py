"""FastAPI entry point. Owner: Backend Core. Run with exactly 1 worker (events live in memory)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.db import close_db, init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
    close_db()


app = FastAPI(title="TRINETRA API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","),
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")
