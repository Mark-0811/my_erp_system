from __future__ import annotations


def render_html_to_pdf(html: str, base_url: str | None = None) -> bytes:
    try:
        from weasyprint import HTML

        return HTML(string=html, base_url=base_url).write_pdf()
    except Exception as exc:  # pragma: no cover - graceful fallback for missing PDF stack
        raise RuntimeError("WeasyPrint is not available. Install requirements to enable PDF export.") from exc
