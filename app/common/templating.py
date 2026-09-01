from pathlib import Path
from typing import cast

from litestar.plugins.jinja import JinjaTemplateEngine

from app.core.config import settings

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

template_engine = JinjaTemplateEngine(directory=TEMPLATES_DIR)
template_engine.engine.autoescape = True
# базовый путь для ссылок (пусто — без префикса, например "/ghost")
cast(dict[str, object], template_engine.engine.globals)["base_path"] = settings.base_path


def render_fragment(name: str, **context: object) -> str:
    """Рендерит html-фрагмент без request (для sse-событий)."""
    return template_engine.engine.get_template(name).render(**context)
