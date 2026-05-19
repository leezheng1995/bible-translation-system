import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class SkillLibraryService:
    def __init__(self, skills_dir: str = "skills") -> None:
        self.skills_dir = Path(skills_dir)

    def list_skills(self) -> Dict[str, Any]:
        skills: List[Dict[str, Any]] = []

        if not self.skills_dir.exists():
            return {
                "status": "ok",
                "count": 0,
                "skills": [],
            }

        for skill_file in sorted(self.skills_dir.glob("*/SKILL.md")):
            content = skill_file.read_text(encoding="utf-8")
            meta = self._parse_frontmatter(content)
            skill_name = meta.get("name") or skill_file.parent.name

            skills.append(
                {
                    "name": skill_name,
                    "description": meta.get("description", ""),
                    "path": str(skill_file),
                    "size": skill_file.stat().st_size,
                }
            )

        return {
            "status": "ok",
            "count": len(skills),
            "skills": skills,
        }

    def get_skill(self, name: str) -> Dict[str, Any]:
        skill_file = self.skills_dir / name / "SKILL.md"

        if not skill_file.exists():
            return {
                "status": "not_found",
                "name": name,
                "message": f"Skill not found: {name}",
            }

        content = skill_file.read_text(encoding="utf-8")
        meta = self._parse_frontmatter(content)

        return {
            "status": "ok",
            "name": name,
            "metadata": meta,
            "content": content,
        }

    def get_dictionary_entries(self) -> Dict[str, Any]:
        skill = self.get_skill("catholic_translation_dictionary")

        if skill.get("status") != "ok":
            return {
                "status": "not_found",
                "count": 0,
                "entries": [],
            }

        content = skill["content"]
        entries = []

        in_dictionary = False

        for raw_line in content.splitlines():
            line = raw_line.strip()

            if line == "## Dictionary":
                in_dictionary = True
                continue

            if not in_dictionary:
                continue

            if not line or line.startswith("#") or "=" not in line:
                continue

            source, target = line.split("=", 1)
            source = source.strip()
            target = target.strip()

            if source and target:
                entries.append(
                    {
                        "source": source,
                        "target": target,
                    }
                )

        entries.sort(key=lambda x: len(x["source"]), reverse=True)

        return {
            "status": "ok",
            "count": len(entries),
            "entries": entries,
            "match_order": "longest_source_first",
            "note": "Use complete phrases first, then names / places / church terms.",
        }

    def build_catholic_translation_prompt(
        self,
        source_text: str,
        include_dictionary: bool = True,
    ) -> Dict[str, Any]:
        role_skill = self.get_skill("catholic_translation_role")
        dictionary_skill = self.get_skill("catholic_translation_dictionary")

        if role_skill.get("status") != "ok":
            return {
                "status": "error",
                "message": "Missing catholic_translation_role skill.",
            }

        sections = [
            "# Active Skill: catholic_translation_role",
            role_skill["content"],
        ]

        if include_dictionary:
            if dictionary_skill.get("status") != "ok":
                return {
                    "status": "error",
                    "message": "Missing catholic_translation_dictionary skill.",
                }

            sections.extend(
                [
                    "# Active Skill: catholic_translation_dictionary",
                    dictionary_skill["content"],
                ]
            )

        sections.extend(
            [
                "# Source Text",
                source_text,
                "# Output Requirement",
                "只輸出完整繁體中文譯文，不要輸出說明、註解、分析、Markdown 標題或開場白。",
            ]
        )

        prompt = "\n\n".join(sections)

        return {
            "status": "ok",
            "skill_chain": [
                "catholic_translation_role",
                "catholic_translation_dictionary",
            ]
            if include_dictionary
            else ["catholic_translation_role"],
            "prompt": prompt,
            "source_text_length": len(source_text),
            "prompt_length": len(prompt),
        }

    def _parse_frontmatter(self, content: str) -> Dict[str, str]:
        if not content.startswith("---"):
            return {}

        match = re.match(r"^---\n(.*?)\n---", content, flags=re.DOTALL)
        if not match:
            return {}

        raw = match.group(1)
        meta: Dict[str, str] = {}

        for line in raw.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()

        return meta
