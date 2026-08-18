"""FastAPI application factory for GxPSoft POC."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gxpsoft.api.routes import router, ui_router
from gxpsoft.core.observability import flush_langfuse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager flushing observability traces on shutdown."""
    yield
    flush_langfuse()


def create_app() -> FastAPI:
    """Instantiates and configures the FastAPI application."""
    app = FastAPI(
        title="GxPSoft AI-Agent-First QMS Engine",
        description="Deterministic QMS Core, Ingestion Engine & Part 11 Audit Trail",
        version="0.1.0",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(ui_router)
    return app


app = create_app()
