"""PDF engines: headless Chrome/Edge, Playwright or WeasyPrint."""

from cv_gen.pdf.engines import AUTO_ORDER, ENGINES, PdfEngine, render_pdf

__all__ = ["AUTO_ORDER", "ENGINES", "PdfEngine", "render_pdf"]
