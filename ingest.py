import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

import pdfplumber

MAX_URL_BYTES = 5 * 1024 * 1024
MAX_FILE_BYTES = 30 * 1024 * 1024
MAX_PAGES = 300
SKIP_TAGS = {"script", "style", "nav", "header", "footer"}
BLOCK_TAGS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6",
              "tr", "td", "th", "section", "article", "ul", "ol", "table",
              "blockquote"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def flat(cell):
    if cell is None:
        return ""
    if isinstance(cell, str):
        return cell
    if isinstance(cell, (list, tuple)):
        return " ".join(flat(x) for x in cell)
    return str(cell)


def fail(msg):
    sys.exit(f"error: {msg}")


class BodyText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.in_body = False
        self.chunks = []  # finished lines
        self.line = []  # inline fragments of the current line

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self.line)).strip()
        if text:
            self.chunks.append(text)
        self.line = []

    def lines(self):  # flush any trailing unclosed line
        self._flush()
        return self.chunks

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.in_body = True
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        elif tag in BLOCK_TAGS and self.in_body and self.skip_depth == 0:
            self._flush()

    def handle_endtag(self, tag):
        if tag == "body":
            self._flush()
            self.in_body = False
        if tag in SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag in BLOCK_TAGS and self.in_body and self.skip_depth == 0:
            self._flush()

    def handle_data(self, data):
        # Raw fragments: spacing between inline tags survives the join.
        if self.in_body and self.skip_depth == 0 and data.strip():
            self.line.append(data)


def title_of(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else "untitled"


def html_to_text(html):
    p = BodyText()
    p.feed(html)
    text = "\n".join(p.lines())
    if len(text.strip()) < 200:  # likely JS-rendered, no usable text
        fail("almost no text extracted; page may need JavaScript rendering")
    return text


def pdf_to_text(path):
    try:
        pdf = pdfplumber.open(path)
    except Exception as e:
        fail(f"cannot read PDF {path}: {e}")
    with pdf:
        if len(pdf.pages) > MAX_PAGES:
            fail(f"PDF over {MAX_PAGES}-page cap: {path}")
        parts = []
        for i, page in enumerate(pdf.pages, 1):
            try:
                t = (page.extract_text() or "").strip()
            except Exception:
                t = "[unreadable page]"  # complex stream; keep marker, keep going
            block = f"[page {i}]\n{t}"
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            for table in tables:
                for row in table:
                    # Cells are str/None, but nested content can surface as a list.
                    cells = [" ".join(flat(c).split()) for c in row]
                    if any(cells):
                        block += "\n" + " | ".join(cells)
            parts.append(block)
        title = (pdf.metadata.get("Title") if pdf.metadata else None) or path.name
        npages = len(pdf.pages)
    text = "\n\n".join(parts).strip()
    body = re.sub(r"\[page \d+\]", "", text).replace("[unreadable page]", "")
    if not body.strip():
        fail(f"no text in PDF (possibly scanned): {path}")
    return text, title, npages


def docx_to_text(path):
    try:
        z = zipfile.ZipFile(path)
        xml = z.read("word/document.xml")
    except zipfile.BadZipFile:
        fail(f"not a valid .docx (legacy .doc? bad zip): {path}")
    except KeyError:
        fail(f"no document body in .docx: {path}")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        fail(f"unreadable .docx body: {path}")
    # Document order covers table cells too: each cell holds its own paragraphs.
    lines = []
    for p in root.iter(f"{W}p"):
        frags = []
        for el in p.iter():  # descendant order keeps tabs/breaks in place
            if el.tag == f"{W}t" and el.text:
                frags.append(el.text)
            elif el.tag == f"{W}tab":
                frags.append(" ")
            elif el.tag == f"{W}br":
                frags.append("\n")
        for piece in "".join(frags).split("\n"):
            if piece.strip():
                lines.append(piece.strip())
    if not lines:
        fail(f"no text in .docx: {path}")
    return "\n".join(lines), path.name, None


def epub_to_text(path):
    try:
        z = zipfile.ZipFile(path)
        names = set(z.namelist())
    except zipfile.BadZipFile:
        fail(f"not a readable EPUB (bad zip, maybe DRM): {path}")
    if "META-INF/encryption.xml" in names:
        fail(f"DRM-protected EPUB, cannot read: {path}")
    opf_name = None
    if "META-INF/container.xml" in names:
        try:
            croot = ET.fromstring(z.read("META-INF/container.xml"))
            for el in croot.iter():
                if el.tag.endswith("rootfile"):
                    opf_name = el.get("full-path")
                    break
        except ET.ParseError:
            pass
    if not opf_name:
        cands = [n for n in names if n.lower().endswith(".opf")]
        if not cands:
            fail(f"no OPF package found in EPUB: {path}")
        opf_name = cands[0]
    try:
        oroot = ET.fromstring(z.read(opf_name))
    except ET.ParseError:
        fail(f"unreadable OPF in EPUB: {path}")
    base = opf_name.rpartition("/")[0]
    manifest, order, title = {}, [], path.stem
    for el in oroot.iter():
        tag = el.tag
        if tag.endswith("item") and el.get("id"):
            href = f"{base}/{el.get('href')}" if base else el.get("href")
            manifest[el.get("id")] = href
        elif tag.endswith("itemref") and el.get("idref") in manifest:
            order.append(manifest[el.get("idref")])
        elif tag.endswith("title") and el.text and el.text.strip() and title == path.stem:
            title = el.text.strip()
    texts = []
    for href in order:  # spine order = chapter order
        try:
            raw = z.read(href).decode("utf-8", errors="replace")
        except KeyError:
            continue
        p = BodyText()
        p.feed(raw)
        if p.lines():
            texts.append("\n".join(p.lines()))
    text = "\n\n".join(texts).strip()
    if not text:
        fail(f"no readable chapters in EPUB: {path}")
    return text, title, None


def pub_to_pdf(path):
    if not shutil.which("soffice"):
        fail(f"export to PDF first (soffice not found): {path}")
    tmp = Path(tempfile.mkdtemp(prefix="ingest_pub_"))
    try:
        r = subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
                            "--outdir", str(tmp), str(path)],
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        fail(f"soffice timed out: {path}")
    outs = list(tmp.glob("*.pdf"))
    if r.returncode != 0 or not outs:
        fail(f"soffice conversion failed: {path}")
    return outs[0], tmp


UA = "flowcheck/0.1 (hackathon research tool)"


def fetch_url(url):
    if not url.startswith(("http://", "https://")):
        fail(f"only http/https URLs allowed: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read(MAX_URL_BYTES + 1)
            ctype = r.headers.get_content_type()
    except Exception as e:
        fail(f"fetch failed for {url}: {e}")
    if len(raw) > MAX_URL_BYTES:
        fail(f"response over 5 MB cap: {url}")
    return raw, ctype


def normalize(text):
    # Join line-end hyphens only between letters, next line starting lowercase.
    text = re.sub(r"([A-Za-z])-\n([a-z])", r"\1\2", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file_or_url")
    ap.add_argument("--id", required=True, dest="source_id")
    args = ap.parse_args()

    src = args.file_or_url
    url_or_null, pages, tmpdir, oldid = None, None, None, None
    try:
        if src.startswith(("http://", "https://", "www.")):
            url = src if "://" in src else "https://" + src
            raw, ctype = fetch_url(url)
            if ctype == "application/pdf" or url.lower().endswith(".pdf"):
                tmp = Path(tempfile.mkdtemp(prefix="ingest_dl_"))
                name = Path(url.split("?")[0]).name or "download.pdf"
                (tmp / name).write_bytes(raw)
                tmpdir = tmp
                text, title, pages = pdf_to_text(tmp / name)
                url_or_null = url
            else:
                html = raw.decode("utf-8", errors="replace")
                text, title, url_or_null = html_to_text(html), title_of(html), url
                pages = 1  # one fetched page; local txt/html keep pages=None
                rev = re.search(r'"wg(?:Cur)?RevisionId":(\d+)', html)
                if rev:
                    oldid = rev.group(1)
                    if "wikipedia.org" in url:
                        url_or_null = f"https://en.wikipedia.org/w/index.php?oldid={oldid}"
        else:
            path = Path(src)
            if not path.exists():
                fail(f"file not found: {src}")
            if path.stat().st_size > MAX_FILE_BYTES:
                fail(f"file over 30 MB cap: {src}")
            sfx = path.suffix.lower()
            if sfx == ".pdf":
                text, title, pages = pdf_to_text(path)
            elif sfx in (".html", ".htm"):
                raw = path.read_text(encoding="utf-8", errors="replace")
                text, title = html_to_text(raw), title_of(raw)
            elif sfx == ".docx":
                text, title, pages = docx_to_text(path)
            elif sfx == ".epub":
                text, title, pages = epub_to_text(path)
            elif sfx == ".pub":
                pdf_path, tmpdir = pub_to_pdf(path)
                text, title, pages = pdf_to_text(pdf_path)
            else:
                text, title = path.read_text(encoding="utf-8", errors="replace"), path.name
    finally:
        # No leaked temp dirs even when a later step fails.
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

    text = normalize(text)
    out = Path("workspace")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.source_id}_source.md").write_text(text + "\n", encoding="utf-8")
    prov = {"source": src, "url_or_null": url_or_null, "title": title,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "chars": len(text), "pages": pages, "oldid": oldid}
    (out / f"{args.source_id}_source.json").write_text(json.dumps(prov, indent=2))

    print(f"pages: {pages if pages else 'n/a'}, chars: {len(text)}")
    print("Check the source's license before using it in a demo.")


if __name__ == "__main__":
    main()
