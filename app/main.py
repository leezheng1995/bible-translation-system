from fastapi import FastAPI

from app.routers.drive_router import router as drive_router
from app.routers.health_router import router as health_router
from app.routers.ollama_router import router as ollama_router


app = FastAPI(
    title="Bible Translation System",
    description="Local AI-assisted Bible translation workflow system",
    version="0.1.0",
)


app.include_router(health_router)
app.include_router(ollama_router)
app.include_router(drive_router)


@app.get("/")
def root():
    return {
        "message": "Bible Translation System API is running."
    }


@app.get("/healthcheck")
def healthcheck():
    return {
        "status": "ok"
    }
