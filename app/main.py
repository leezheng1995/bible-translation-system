from fastapi import FastAPI

from app.routers.drive_router import router as drive_router
from app.routers.file_router import router as file_router
from app.routers.db_router import router as db_router
from app.routers.health_router import router as health_router
from app.routers.job_router import router as job_router
from app.routers.ollama_router import router as ollama_router
from app.routers.segment_router import router as segment_router
from app.routers.note_router import router as note_router
from app.routers.prompt_router import router as prompt_router
from app.routers.retrieval_router import router as retrieval_router
from app.routers.rag_router import router as rag_router
from app.routers.model_router import router as model_router
from app.routers.translation_router import router as translation_router
from app.routers.review_router import router as review_router
from app.routers.human_review_router import router as human_review_router
from app.routers.memory_router import router as memory_router
from app.routers.rule_router import router as rule_router
from app.routers.glossary_router import router as glossary_router


app = FastAPI(
    title="Bible Translation System",
    description="Local AI-assisted Bible translation workflow system",
    version="0.1.0",
)


app.include_router(health_router)
app.include_router(job_router)
app.include_router(ollama_router)
app.include_router(segment_router)
app.include_router(note_router)
app.include_router(prompt_router)
app.include_router(retrieval_router)
app.include_router(rag_router)
app.include_router(model_router)
app.include_router(translation_router)
app.include_router(review_router)
app.include_router(human_review_router)
app.include_router(memory_router)
app.include_router(rule_router)
app.include_router(glossary_router)
app.include_router(drive_router)
app.include_router(file_router)
app.include_router(db_router)


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


# Day 22 - Skill Library router
try:
    from app.routers import skill_library
    app.include_router(skill_library.router)
except Exception as exc:
    import logging
    logging.getLogger(__name__).exception("Failed to include skill_library router: %s", exc)


# Day 22 - 小龍蝦 Skill / OpenClaw router
try:
    from app.routers import claw_skill
    app.include_router(claw_skill.router)
except Exception as exc:
    import logging
    logging.getLogger(__name__).exception("Failed to include claw_skill router: %s", exc)


# Day 24 - OpenClaw Task Management router
try:
    from app.routers import claw_task_management
    app.include_router(claw_task_management.router)
except Exception as exc:
    import logging
    logging.getLogger(__name__).exception("Failed to include claw_task_management router: %s", exc)

