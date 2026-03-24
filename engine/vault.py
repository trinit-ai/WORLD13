"""
Vault: Unified file surface for TMOS13.

Three tiers:
  - output: System-generated files (deliverables, exports). Immutable.
  - upload: Direct user uploads. Mutable.
  - synced: Cloud-pulled files (Google Drive, etc). Mutable.

Every file gets RAG-indexed for pack accessibility.

Singleton: init_vault_service(supabase, storage, rag, file_processor, manifest) → get_vault_service()
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import hashlib
import logging

logger = logging.getLogger("tmos13.vault")


VALID_TIERS = {"output", "upload", "synced"}
VALID_SOURCES = {
    "deliverable", "transcript_export", "note_export",
    "direct_upload", "google_drive", "dropbox", "onedrive",
}
VALID_SYNC_STATUSES = {"current", "stale", "error", "pending"}


@dataclass
class VaultItem:
    id: str = ""
    owner_id: str = ""
    filename: str = ""
    mime_type: Optional[str] = None
    size_bytes: int = 0
    checksum: Optional[str] = None
    tier: str = "upload"
    source: str = "direct_upload"
    source_id: Optional[str] = None
    source_path: Optional[str] = None
    department: Optional[str] = None
    pack_id: Optional[str] = None
    session_id: Optional[str] = None
    contact_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    rag_indexed: bool = False
    rag_chunks: int = 0
    storage_path: str = ""
    sync_source_modified_at: Optional[str] = None
    sync_last_pulled_at: Optional[str] = None
    sync_status: Optional[str] = None
    dimensions: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict) -> "VaultItem":
        return cls(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            filename=row["filename"],
            mime_type=row.get("mime_type"),
            size_bytes=row.get("size_bytes", 0),
            checksum=row.get("checksum"),
            tier=row.get("tier", "upload"),
            source=row.get("source", "direct_upload"),
            source_id=row.get("source_id"),
            source_path=row.get("source_path"),
            department=row.get("department"),
            pack_id=row.get("pack_id"),
            session_id=row.get("session_id"),
            contact_id=str(row["contact_id"]) if row.get("contact_id") else None,
            tags=row.get("tags") or [],
            rag_indexed=row.get("rag_indexed", False),
            rag_chunks=row.get("rag_chunks", 0),
            storage_path=row.get("storage_path", ""),
            sync_source_modified_at=row.get("sync_source_modified_at"),
            sync_last_pulled_at=row.get("sync_last_pulled_at"),
            sync_status=row.get("sync_status"),
            dimensions=row.get("dimensions"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


class VaultService:
    """
    Unified file surface. Aggregates outputs, uploads, and synced files.
    Every file gets RAG-indexed for pack accessibility.
    """

    def __init__(self, supabase_client, storage=None, rag_engine=None,
                 file_processor=None, manifest_service=None):
        self._db = supabase_client
        self._storage = storage
        self._rag = rag_engine
        self._files = file_processor
        self._manifest = manifest_service
        self._table = "vault_items"
        logger.info("VaultService initialized")

    # ── Tier 1: Outputs (called by other services) ──────

    async def register_output(
        self,
        owner_id: str,
        filename: str,
        storage_path: str,
        source: str,
        source_id: str,
        size_bytes: int = 0,
        mime_type: str | None = None,
        department: str | None = None,
        pack_id: str | None = None,
        session_id: str | None = None,
        contact_id: str | None = None,
        dimensions: dict | None = None,
        file_data: bytes | None = None,
    ) -> VaultItem:
        """Register a system-generated output. Outputs are IMMUTABLE."""
        if source not in VALID_SOURCES:
            raise ValueError(f"Invalid source: {source}")

        # If file_data provided and no storage_path, upload to exports bucket
        if file_data and not storage_path:
            storage_path = f"vault/{source}/{source_id}.md"
            if self._storage:
                try:
                    await self._storage.upload_asset(
                        storage_path, file_data, mime_type or "text/markdown",
                    )
                except Exception as e:
                    logger.warning(f"Vault output upload failed: {e}")

        row = {
            "owner_id": owner_id,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "tier": "output",
            "source": source,
            "source_id": source_id,
            "storage_path": storage_path,
            "department": department,
            "pack_id": pack_id,
            "session_id": session_id,
            "contact_id": contact_id,
            "dimensions": dimensions,
        }

        result = self._db.table(self._table).insert(row).execute()
        item = VaultItem.from_row(result.data[0])

        # RAG index (best effort)
        await self._safe_rag_index(item, storage_path, file_data=file_data)

        logger.info(f"Vault output registered: {item.id} ({filename})")
        return item

    # ── Tier 2: Uploads ─────────────────────────────────

    async def upload(
        self,
        owner_id: str,
        file_data: bytes,
        filename: str,
        mime_type: str | None = None,
        department: str | None = None,
        tags: list[str] | None = None,
        pack_id: str | None = None,
    ) -> VaultItem:
        """Direct user upload with dedup, storage, RAG indexing, and Manifest logging."""
        checksum = hashlib.sha256(file_data).hexdigest()

        # Dedup: check if same file already exists for this owner
        existing = await self._find_by_checksum(owner_id, checksum)
        if existing:
            logger.info(f"Vault upload deduped: {filename} → existing {existing.id}")
            return existing

        # Detect mime type if not provided
        if not mime_type:
            from files import detect_file_type
            detected_mime, _, _ = detect_file_type(filename, file_data)
            mime_type = detected_mime

        # Store file via storage layer
        storage_path = f"vault/{owner_id}/{checksum[:16]}/{filename}"
        if self._storage:
            try:
                await self._storage.upload_asset(storage_path, file_data, mime_type)
            except Exception as e:
                logger.error(f"Vault storage upload failed: {e}")
                raise ValueError(f"Storage upload failed: {e}")

        row = {
            "owner_id": owner_id,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": len(file_data),
            "checksum": checksum,
            "tier": "upload",
            "source": "direct_upload",
            "storage_path": storage_path,
            "department": department,
            "tags": tags or [],
            "pack_id": pack_id,
        }

        result = self._db.table(self._table).insert(row).execute()
        item = VaultItem.from_row(result.data[0])

        # RAG index
        await self._safe_rag_index(item, storage_path, file_data=file_data)

        # Log to Manifest (sync)
        if self._manifest:
            try:
                self._manifest.log(
                    owner_id=owner_id,
                    event_type="file_uploaded",
                    category="vault",
                    summary=f"Uploaded: {filename} ({len(file_data)} bytes)",
                    detail={
                        "vault_item_id": item.id,
                        "filename": filename,
                        "mime_type": mime_type,
                        "size_bytes": len(file_data),
                        "tier": "upload",
                    },
                    department=department,
                    pack_id=pack_id,
                    importance="low",
                )
            except Exception as e:
                logger.warning(f"Failed to log upload to manifest: {e}")

        logger.info(f"Vault upload complete: {item.id} ({filename}, {len(file_data)} bytes)")
        return item

    # ── Tier 3: Synced ──────────────────────────────────

    async def register_synced(
        self,
        owner_id: str,
        filename: str,
        storage_path: str,
        source: str,
        source_id: str,
        source_path: str,
        size_bytes: int = 0,
        mime_type: str | None = None,
        sync_source_modified_at: str | None = None,
        file_data: bytes | None = None,
    ) -> VaultItem:
        """Register a cloud-synced file. Updates existing if same source+source_id."""
        # Check for existing synced item
        existing = await self._find_by_source(owner_id, source, source_id)
        if existing:
            updates = {
                "sync_last_pulled_at": datetime.now(timezone.utc).isoformat(),
                "sync_status": "current",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if sync_source_modified_at:
                updates["sync_source_modified_at"] = sync_source_modified_at
            if size_bytes:
                updates["size_bytes"] = size_bytes

            result = (
                self._db.table(self._table)
                .update(updates)
                .eq("id", existing.id)
                .execute()
            )
            return VaultItem.from_row(result.data[0])

        # Create new
        checksum = hashlib.sha256(file_data).hexdigest() if file_data else None

        row = {
            "owner_id": owner_id,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "checksum": checksum,
            "tier": "synced",
            "source": source,
            "source_id": source_id,
            "source_path": source_path,
            "storage_path": storage_path,
            "sync_source_modified_at": sync_source_modified_at,
            "sync_last_pulled_at": datetime.now(timezone.utc).isoformat(),
            "sync_status": "current",
        }

        result = self._db.table(self._table).insert(row).execute()
        item = VaultItem.from_row(result.data[0])

        # RAG index
        if file_data:
            await self._safe_rag_index(item, storage_path, file_data=file_data)

        # Log to Manifest (sync)
        if self._manifest:
            try:
                self._manifest.log(
                    owner_id=owner_id,
                    event_type="file_synced",
                    category="vault",
                    summary=f"Synced: {filename} from {source}",
                    detail={
                        "vault_item_id": item.id,
                        "filename": filename,
                        "source": source,
                        "source_id": source_id,
                        "source_path": source_path,
                    },
                    importance="low",
                )
            except Exception as e:
                logger.warning(f"Failed to log sync to manifest: {e}")

        return item

    # ── Common CRUD ─────────────────────────────────────

    async def get(self, item_id: str) -> VaultItem | None:
        result = (
            self._db.table(self._table)
            .select("*")
            .eq("id", item_id)
            .execute()
        )
        if not result.data:
            return None
        return VaultItem.from_row(result.data[0])

    async def list(
        self,
        owner_id: str,
        tier: str | None = None,
        source: str | None = None,
        department: str | None = None,
        search: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[VaultItem], int]:
        """List vault items with filters. Newest first."""
        query = self._db.table(self._table).select("*", count="exact")
        query = query.eq("owner_id", owner_id)

        if tier:
            query = query.eq("tier", tier)
        if source:
            query = query.eq("source", source)
        if department:
            query = query.eq("department", department)
        if tags:
            query = query.contains("tags", tags)
        if search:
            query = query.ilike("filename", f"%{search}%")

        query = query.order("created_at", desc=True)
        query = query.range(offset, offset + limit - 1)

        result = query.execute()
        items = [VaultItem.from_row(row) for row in result.data]
        total = result.count or 0
        return items, total

    async def delete(self, item_id: str) -> bool:
        """Delete a vault item. Only tier=upload and tier=synced."""
        item = await self.get(item_id)
        if not item:
            raise ValueError(f"Vault item not found: {item_id}")
        if item.tier == "output":
            raise ValueError("Output files are immutable and cannot be deleted")

        self._db.table(self._table).delete().eq("id", item_id).execute()
        logger.info(f"Vault item deleted: {item_id} ({item.filename})")
        return True

    async def refile(self, item_id: str, department: str) -> bool:
        """Update the department on a vault item."""
        item = await self.get(item_id)
        if not item:
            return False
        self._db.table(self._table).update({"department": department, "updated_at": "now()"}).eq("id", item_id).execute()
        logger.info(f"Vault item refiled: {item_id} -> {department}")
        return True

    async def download(self, item_id: str) -> tuple[bytes, str, str]:
        """Download a vault file. Returns (file_data, mime_type, filename)."""
        item = await self.get(item_id)
        if not item:
            raise ValueError(f"Vault item not found: {item_id}")

        # Read from storage via signed URL (or direct for local)
        if self._storage:
            url = await self._storage.get_signed_url("assets", item.storage_path)
            return b"", item.mime_type or "application/octet-stream", item.filename

        return b"", item.mime_type or "application/octet-stream", item.filename

    async def stats(self, owner_id: str) -> dict:
        """Aggregate vault stats for dashboard."""
        result = (
            self._db.table(self._table)
            .select("tier, size_bytes, department, rag_indexed")
            .eq("owner_id", owner_id)
            .execute()
        )

        rows = result.data
        by_tier: dict[str, dict] = {}
        by_department: dict[str, int] = {}
        total_size = 0
        rag_count = 0

        for row in rows:
            t = row["tier"]
            if t not in by_tier:
                by_tier[t] = {"tier": t, "count": 0, "bytes": 0}
            by_tier[t]["count"] += 1
            by_tier[t]["bytes"] += row.get("size_bytes", 0)

            d = row.get("department") or "unassigned"
            by_department[d] = by_department.get(d, 0) + 1

            total_size += row.get("size_bytes", 0)
            if row.get("rag_indexed"):
                rag_count += 1

        # Count sync connections
        sync_count = 0
        try:
            sync_result = (
                self._db.table("vault_sync_connections")
                .select("id", count="exact")
                .eq("owner_id", owner_id)
                .execute()
            )
            sync_count = sync_result.count or 0
        except Exception:
            pass

        return {
            "total_items": len(rows),
            "storage_used_bytes": total_size,
            "by_tier": list(by_tier.values()),
            "by_department": [{"department": k, "count": v} for k, v in by_department.items()],
            "rag_indexed": rag_count,
            "sync_connections": sync_count,
        }

    async def search(self, owner_id: str, query: str) -> list[VaultItem]:
        """Search by filename. Returns up to 20."""
        items, _ = await self.list(owner_id, search=query, limit=20)
        return items

    # ── Internal ────────────────────────────────────────

    async def _find_by_checksum(self, owner_id: str, checksum: str) -> VaultItem | None:
        result = (
            self._db.table(self._table)
            .select("*")
            .eq("owner_id", owner_id)
            .eq("checksum", checksum)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return VaultItem.from_row(result.data[0])

    async def _find_by_source(self, owner_id: str, source: str, source_id: str) -> VaultItem | None:
        result = (
            self._db.table(self._table)
            .select("*")
            .eq("owner_id", owner_id)
            .eq("source", source)
            .eq("source_id", source_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return VaultItem.from_row(result.data[0])

    async def _safe_rag_index(self, item: VaultItem, storage_path: str,
                               file_data: bytes | None = None):
        """RAG index a vault item. Best-effort — never fails the parent operation."""
        if not self._rag:
            return
        try:
            from files import is_text_file, extract_text
            from pathlib import Path
            ext = Path(item.filename).suffix.lstrip(".").lower()
            mime = item.mime_type or "application/octet-stream"

            if not file_data:
                return

            if is_text_file(mime, ext):
                text = file_data.decode("utf-8", errors="replace")
            else:
                # Try binary document extraction (PDF, DOCX)
                text = extract_text(file_data, item.filename, mime)
                if not text:
                    return
            if not text.strip():
                return

            self._rag.add_uploaded_document(
                f"vault:{item.id}", item.filename, text,
            )

            chunk_count = len(text) // 2000 + 1
            self._db.table(self._table).update({
                "rag_indexed": True,
                "rag_chunks": chunk_count,
            }).eq("id", item.id).execute()

            logger.info(f"Vault RAG indexed: {item.id} ({item.filename}, ~{chunk_count} chunks)")
        except Exception as e:
            logger.warning(f"RAG indexing failed for vault item {item.id}: {e}")


# ── Singleton ───────────────────────────────────────────

_vault_service: VaultService | None = None


def init_vault_service(supabase_client, storage=None, rag_engine=None,
                       file_processor=None, manifest_service=None) -> VaultService:
    global _vault_service
    _vault_service = VaultService(
        supabase_client, storage=storage, rag_engine=rag_engine,
        file_processor=file_processor, manifest_service=manifest_service,
    )
    return _vault_service


def get_vault_service() -> VaultService:
    if _vault_service is None:
        raise RuntimeError("VaultService not initialized. Call init_vault_service() first.")
    return _vault_service
