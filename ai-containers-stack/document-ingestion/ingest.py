#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from fastembed import TextEmbedding

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
NAMESPACE = uuid.UUID("4d4f834a-018d-4f8b-858c-e8cf4ecf231a")
TARGET_CHARS = 1800
OVERLAP_CHARS = 250


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean(text: str) -> str:
    text = text.replace("\x00", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def pdf_pages(path: Path) -> list[str]:
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True, capture_output=True, text=True, errors="replace"
    )
    return [clean(page) for page in result.stdout.split("\f") if clean(page)]


def docx_pages(path: Path) -> list[str]:
    result = subprocess.run(
        ["textutil", "-convert", "txt", "-stdout", str(path)],
        check=True, capture_output=True, text=True, errors="replace"
    )
    return [clean(result.stdout)]


def xlsx_pages(path: Path) -> list[str]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", ns):
                shared.append("".join(node.text or "" for node in item.findall(".//m:t", ns)))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in relationships.findall("r:Relationship", rel_ns)}
        sheets: list[str] = []
        for sheet in workbook.findall("m:sheets/m:sheet", ns):
            rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = targets[rid].lstrip("/")
            member = target if target.startswith("xl/") else f"xl/{target}"
            root = ET.fromstring(archive.read(member))
            lines = [f"Worksheet: {sheet.attrib['name']}"]
            for row in root.findall(".//m:sheetData/m:row", ns):
                values: list[str] = []
                for cell in row.findall("m:c", ns):
                    ref = cell.attrib.get("r", "")
                    value = cell.findtext("m:v", default="", namespaces=ns)
                    if cell.attrib.get("t") == "s" and value.isdigit():
                        value = shared[int(value)]
                    elif cell.attrib.get("t") == "inlineStr":
                        value = "".join(node.text or "" for node in cell.findall(".//m:t", ns))
                    if value:
                        values.append(f"{ref}={value}")
                if values:
                    lines.append(" | ".join(values))
            sheets.append(clean("\n".join(lines)))
        return sheets


def extract(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return pdf_pages(path)
    if suffix == ".docx":
        return docx_pages(path)
    if suffix == ".xlsx":
        return xlsx_pages(path)
    raise ValueError(f"Unsupported file: {path}")


def split_page(text: str) -> list[str]:
    if len(text) <= TARGET_CHARS:
        return [text]
    paragraphs = re.split(r"\n\s*\n|(?<=\.)\s+(?=[A-Z0-9])", text)
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        paragraph = clean(paragraph)
        if not paragraph:
            continue
        if len(current) + len(paragraph) + 2 <= TARGET_CHARS:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
            current = f"{current[-OVERLAP_CHARS:]}\n\n{paragraph}".strip()
        else:
            for start in range(0, len(paragraph), TARGET_CHARS - OVERLAP_CHARS):
                chunks.append(paragraph[start:start + TARGET_CHARS])
            current = ""
    if current:
        chunks.append(current)
    return chunks


def env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: ingest.py FILE...", file=sys.stderr)
        return 2

    supplied = [Path(item).resolve() for item in sys.argv[1:]]
    for path in supplied:
        if not path.is_file():
            raise FileNotFoundError(path)

    groups: dict[str, list[Path]] = {}
    for path in supplied:
        groups.setdefault(sha256(path), []).append(path)

    documents: list[dict] = []
    chunks: list[dict] = []
    for digest, paths in groups.items():
        path = paths[0]
        pages = extract(path)
        document_id = str(uuid.uuid5(NAMESPACE, digest))
        documents.append({
            "id": document_id,
            "filename": path.name,
            "source_path": str(path),
            "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "sha256": digest,
            "title": path.stem,
            "page_count": len(pages),
            "byte_size": path.stat().st_size,
            "language": "en/ro",
            "metadata": json.dumps({"aliases": [str(p) for p in paths[1:]], "extractor": "codex-local-v1"}),
        })
        index = 0
        for page_number, page in enumerate(pages, 1):
            for content in split_page(page):
                if len(content) < 40:
                    continue
                chunks.append({
                    "id": str(uuid.uuid5(NAMESPACE, f"{digest}:{index}")),
                    "document_id": document_id,
                    "chunk_index": index,
                    "page_from": page_number,
                    "page_to": page_number,
                    "heading": content.splitlines()[0][:240],
                    "content": content,
                    "token_estimate": max(1, len(content) // 4),
                    "metadata": json.dumps({"source_sha256": digest}),
                })
                index += 1

    print(f"Unique documents: {len(documents)}; chunks: {len(chunks)}")
    embedder = TextEmbedding(model_name=MODEL)
    vectors = list(embedder.embed([row["content"] for row in chunks], batch_size=32))
    if len(vectors) != len(chunks):
        raise RuntimeError("Embedding count mismatch")
    for row, vector in zip(chunks, vectors):
        row["embedding"] = "{" + ",".join(f"{float(value):.8g}" for value in vector) + "}"
        row["embedding_model"] = MODEL

    root = Path(__file__).resolve().parents[1]
    settings = env_file(root / ".env")
    with tempfile.TemporaryDirectory(prefix="cargo-ingest-") as temp_name:
        temp = Path(temp_name)
        docs_csv = temp / "documents.csv"
        chunks_csv = temp / "chunks.csv"
        with docs_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(documents[0]), quoting=csv.QUOTE_ALL)
            writer.writeheader(); writer.writerows(documents)
        with chunks_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(chunks[0]), quoting=csv.QUOTE_ALL)
            writer.writeheader(); writer.writerows(chunks)

        sql = temp / "load.sql"
        sql.write_text(f"""
\\set ON_ERROR_STOP on
begin;
create temp table stage_documents (like public.knowledge_documents including defaults);
create temp table stage_chunks (like public.knowledge_chunks including defaults);
\\copy stage_documents(id,filename,source_path,media_type,sha256,title,page_count,byte_size,language,metadata) from '{docs_csv}' csv header;
\\copy stage_chunks(id,document_id,chunk_index,page_from,page_to,heading,content,token_estimate,metadata,embedding,embedding_model) from '{chunks_csv}' csv header;
delete from public.knowledge_documents d using stage_documents s where d.sha256 = s.sha256;
insert into public.knowledge_documents(id,filename,source_path,media_type,sha256,title,page_count,byte_size,language,metadata)
select id,filename,source_path,media_type,sha256,title,page_count,byte_size,language,metadata from stage_documents;
insert into public.knowledge_chunks(id,document_id,chunk_index,page_from,page_to,heading,content,token_estimate,metadata,embedding,embedding_model)
select id,document_id,chunk_index,page_from,page_to,heading,content,token_estimate,metadata,embedding,embedding_model from stage_chunks;
commit;
""", encoding="utf-8")
        process_env = os.environ.copy()
        process_env["PGPASSWORD"] = settings["SUPABASE_DB_PASSWORD"]
        subprocess.run([
            "/usr/local/opt/postgresql@15/bin/psql", "-X", "-v", "ON_ERROR_STOP=1",
            "-h", "127.0.0.1", "-p", settings.get("SUPABASE_DB_PORT", "54322"),
            "-U", settings["SUPABASE_DB_USER"], "-d", settings["SUPABASE_DB_NAME"],
            "-f", str(sql),
        ], check=True, env=process_env)

    print(f"Imported {len(documents)} documents and {len(chunks)} chunks with {len(vectors[0])}-dimensional embeddings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
