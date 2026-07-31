"""CLI: ingesta de la bóveda Obsidian al corpus RAG.

Recorre el directorio del vault (montado en /vault dentro del container),
limpia el frontmatter YAML y los wikilinks `[[X]]` para dejar texto puro,
y llama a `RagService.ingest_text()` con `source_type="vault"` y
`source_uri=<ruta relativa>`.

Skips:
- Archivos en _Templates, _Attachments, _Daily
- Contenido idéntico (mismo content_hash) — para soportar re-ejecuciones
  idempotentes después de un sync.

Uso:
    docker compose exec rag python -m services.rag.cli_ingest_vault \\
        --tenant-id 1 --vault-dir /vault
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import sys
from pathlib import Path

from sqlalchemy import select

from shared.database import _get_session_factory
from services.rag.models import Document
from services.rag.repository import RagRepository
from services.rag.service import RagService


SKIP_DIRS = {"_Templates", "_Attachments", "_Daily", ".obsidian"}
FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def clean_markdown(raw: str) -> str:
    """Strip frontmatter and unwrap wikilinks to plain text."""
    # Strip frontmatter
    cleaned = FRONTMATTER_RE.sub("", raw, count=1).lstrip()
    # Convert [[X|alias]] → alias; [[X]] → X
    cleaned = WIKILINK_RE.sub(lambda m: m.group(2) or m.group(1), cleaned)
    return cleaned


def derive_title(rel_path: Path, content: str) -> str:
    """Use first H1 if present, otherwise filename stem."""
    for line in content.splitlines()[:20]:
        if line.startswith("# "):
            return line[2:].strip()
    return rel_path.stem


async def find_existing(db, tenant_id: int, source_uri: str) -> Document | None:
    """Locate a previously ingested vault document by source_uri."""
    res = await db.execute(
        select(Document).where(
            Document.tenant_id == tenant_id,
            Document.source_type == "vault",
            Document.source_uri == source_uri,
        )
    )
    return res.scalar_one_or_none()


async def ingest_one(svc: RagService, db, tenant_id: int, path: Path, rel_path: Path) -> str:
    """Ingest a single markdown file. Returns 'created' | 'updated' | 'skipped'."""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    content = clean_markdown(raw)
    if not content.strip():
        return "skipped"

    source_uri = str(rel_path).replace("\\", "/")
    title = derive_title(rel_path, content)
    new_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    existing = await find_existing(db, tenant_id, source_uri)
    if existing and existing.content_hash == new_hash:
        return "skipped"

    if existing:
        # Delete old chunks+doc, then re-ingest
        await svc.delete_document(tenant_id, existing.id)

    await svc.ingest_text(
        tenant_id=tenant_id,
        title=title,
        content=content,
        source_type="vault",
        source_uri=source_uri,
        mime_type="text/markdown",
        language="es",
        meta={"vault_path": source_uri},
    )
    return "updated" if existing else "created"


async def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Obsidian vault into RAG corpus")
    ap.add_argument("--tenant-id", type=int, default=2)
    ap.add_argument("--vault-dir", type=str, default="/vault")
    args = ap.parse_args()

    vault = Path(args.vault_dir)
    if not vault.exists():
        print(f"❌ Vault directory not found: {vault}", file=sys.stderr)
        sys.exit(1)

    files: list[Path] = []
    for md in vault.rglob("*.md"):
        if any(part in SKIP_DIRS for part in md.relative_to(vault).parts):
            continue
        files.append(md)

    print(f"📚 Found {len(files)} markdown files in {vault}")

    factory = _get_session_factory("rag")
    async with factory() as db:
        repo = RagRepository(db)
        svc = RagService(repo)

        stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        for i, md in enumerate(files, 1):
            rel = md.relative_to(vault)
            try:
                result = await ingest_one(svc, db, args.tenant_id, md, rel)
                stats[result] += 1
                marker = {"created": "✨", "updated": "🔄", "skipped": "·"}[result]
                print(f"  [{i:3d}/{len(files)}] {marker} {rel}")
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                stats["failed"] += 1
                print(f"  [{i:3d}/{len(files)}] ❌ {rel} — {exc}", file=sys.stderr)

    print(
        f"\n✅ Done. created={stats['created']} updated={stats['updated']} "
        f"skipped={stats['skipped']} failed={stats['failed']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
