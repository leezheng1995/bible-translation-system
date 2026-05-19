from pydantic import BaseModel

from fastapi import APIRouter

from app.services.skill_library_service import SkillLibraryService


router = APIRouter(
    prefix="/skills/library",
    tags=["Skill Library"],
)


class CatholicPromptRequest(BaseModel):
    source_text: str
    include_dictionary: bool = True


def service() -> SkillLibraryService:
    return SkillLibraryService()


@router.get("")
def list_skills():
    return service().list_skills()


@router.get("/")
def list_skills_slash():
    return service().list_skills()


@router.get("/{name}")
def get_skill(name: str):
    return service().get_skill(name)


@router.get("/catholic-translation/dictionary")
def get_catholic_dictionary():
    return service().get_dictionary_entries()


@router.post("/catholic-translation/prompt")
def build_catholic_translation_prompt(req: CatholicPromptRequest):
    return service().build_catholic_translation_prompt(
        source_text=req.source_text,
        include_dictionary=req.include_dictionary,
    )
