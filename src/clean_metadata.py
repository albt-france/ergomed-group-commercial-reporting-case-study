"""Empty the document metadata of every Office file in the repository (author, last modified by, company, ...).
Run last (src/run_all.py does). Usage: python src/clean_metadata.py"""
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ["dc:creator", "cp:lastModifiedBy", "cp:keywords", "dc:description", "cp:category", "dc:subject"]
APP = ["Company", "Manager", "HyperlinkBase"]


def clean(path: Path):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename in ("docProps/core.xml", "docProps/app.xml"):
                s = data.decode("utf-8")
                for tag in CORE + APP:
                    s = re.sub(rf"<{tag}(\s[^>]*)?>.*?</{tag}>", lambda m: f"<{tag}{m.group(1) or ''}></{tag}>", s, flags=re.S)
                data = s.encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, path)


def main():
    files = [p for ext in ("*.xlsx", "*.pptx", "*.docx") for p in ROOT.rglob(ext)
             if ".venv" not in p.parts and "raw" not in p.parts and ".tmp" not in p.parts]
    for f in files:
        clean(f)
    print("metadata emptied:", [str(f.relative_to(ROOT)) for f in files])


if __name__ == "__main__":
    main()
