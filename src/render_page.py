"""Render one PDF page to PNG (to read a table by eye and cite its page). Usage: render_page.py <pdf> <page> <out.png>"""
import sys
import pypdfium2 as pdfium
doc = pdfium.PdfDocument(sys.argv[1])
doc[int(sys.argv[2]) - 1].render(scale=float(sys.argv[4]) if len(sys.argv) > 4 else 1.4).to_pil().save(sys.argv[3])
