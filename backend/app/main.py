# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time

from app.core.config import settings
from app.core.version import VERSION
from app.api.routes.health import router as health_router
# # Stubs you’ll flesh out:
# from app.api.routes.run import router as run_router
# from app.api.routes.sandbox import router as sandbox_router
# from app.api.routes.tmp import router as tmp_router
# from app.api.routes.cel import router as cel_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.start_time = time.time()
    yield
    # Shutdown (noop for now)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Backend for ArrowAI",
        version=VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS (open by default for demos; lock down later)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health_router, tags=["health"])
    # app.include_router(run_router, prefix="/run", tags=["run"])
    # app.include_router(sandbox_router, prefix="/sandbox", tags=["sandbox"])
    # app.include_router(tmp_router, prefix="/tmp", tags=["tmp"])
    # app.include_router(cel_router, prefix="/cel", tags=["cel"])

    return app


app = create_app()



# uvicorn app.main:app --reload
