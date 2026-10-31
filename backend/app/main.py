"""FastAPI entry point. Owner: Backend Core. Run with exactly 1 worker (events live in memory)."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.db import close_db, init_db


# Our own INFO logs (one line per LLM call: provider, model, tokens, latency, rate-limit wait).
logging.getLogger("app").setLevel(logging.INFO)
if not logging.getLogger("app").handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
    logging.getLogger("app").addHandler(_handler)
    logging.getLogger("app").propagate = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
    close_db()


app = FastAPI(title="TRINETRA API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","),
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")
