"""OCR the scanned Companies House PDFs (no text layer) with the Windows built-in OCR engine (winocr), one text file
per document with a marker per PDF page, so every figure typed in src/extract_accounts.py can be cited by page and
checked again. Output: data/raw/companies_house/txt/<name>.txt (not redistributed)."""
import asyncio
import sys
from pathlib import Path

import pypdfium2 as pdfium
import winocr

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "companies_house"
OUT = RAW / "txt"


async def ocr_pdf(pdf: Path) -> str:
    doc = pdfium.PdfDocument(str(pdf))
    parts = []
    for i in range(len(doc)):
        img = doc[i].render(scale=2.2).to_pil()
        res = await winocr.recognize_pil(img, "en")
        parts.append(f"\n===== PDF PAGE {i + 1} =====\n" + "\n".join(l.text for l in res.lines))
    return "".join(parts)


def main(names):
    OUT.mkdir(exist_ok=True)
    for pdf in sorted(RAW.glob("*.pdf")):
        if names and pdf.stem not in names:
            continue
        target = OUT / (pdf.stem + ".txt")
        if target.exists() and target.stat().st_size > 5000:
            continue
        text = asyncio.run(ocr_pdf(pdf))
        target.write_text(text, encoding="utf-8")
        print(pdf.name, len(text), "chars", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
