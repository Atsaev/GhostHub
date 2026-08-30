from pathlib import Path

from litestar.plugins.jinja import JinjaTemplateEngine

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

template_engine = JinjaTemplateEngine(directory=str(TEMPLATES_DIR))
template_engine.engine.autoescape = True


def render_fragment(name: str, **context: object) -> str:
    """Рендерит html-фрагмент без request (для sse-событий)."""
    return template_engine.engine.get_template(name).render(**context)
