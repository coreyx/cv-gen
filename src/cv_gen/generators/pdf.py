"""PDF output: the HTML page, printed by a PDF engine."""

from __future__ import annotations

from cv_gen.generators.base import Generator, RenderRequest
from cv_gen.generators.html import render_html
from cv_gen.model import Resume
from cv_gen.pdf.engines import render_pdf


class PdfGenerator(Generator):
    """PDF (``.pdf``), identical in design to the HTML output."""

    name = "pdf"
    extension = "pdf"
    binary = True
    description = "PDF printed from the HTML page (Chrome/Edge, Playwright or WeasyPrint)."

    def render(self, resume: Resume, request: RenderRequest) -> bytes:
        """Render the HTML page and print it with the requested engine."""
        return render_pdf(render_html(resume, request), request.pdf_engine)
