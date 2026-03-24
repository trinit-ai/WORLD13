"""
TMOS13 File Processing Service

Handles file type detection, metadata extraction, chunking for large files,
thumbnail generation, and presentation formatting.

Integrates with the storage layer for persistence and the RAG engine for
indexing uploaded document content.

Usage:
    processor = FileProcessor(storage, max_upload_bytes=50_000_000)
    meta = await processor.process(file_bytes, "report.pdf", "application/pdf", user_id="u1")
    chunks = processor.chunk_text(long_text, max_chunk_size=4000)
"""
import base64
import hashlib
import logging
import mimetypes
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

from io import BytesIO

logger = logging.getLogger("tmos13.files")

# ─── Constants ───────────────────────────────────────────

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB default
MAX_CHUNK_SIZE = 4000                 # characters per chunk
CHUNK_OVERLAP = 200                   # overlap between consecutive chunks

ALLOWED_EXTENSIONS = {
    # Documents
    "txt", "md", "csv", "json", "xml", "yaml", "yml", "toml",
    "pdf", "doc", "docx", "rtf", "odt",
    # Code
    "py", "js", "ts", "jsx", "tsx", "html", "css", "scss",
    "java", "go", "rs", "rb", "php", "sh", "sql", "swift", "kt",
    # Images
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp",
    # Audio
    "mp3", "wav", "ogg", "webm", "flac", "m4a",
    # Data
    "sqlite", "db", "parquet",
    # Archives
    "zip", "tar", "gz",
}

BLOCKED_EXTENSIONS = {"exe", "dll", "bat", "cmd", "msi", "scr", "com", "pif"}


# ─── Enums ───────────────────────────────────────────────

class FileCategory(str, Enum):
    """High-level file category for display logic."""
    DOCUMENT = "document"
    IMAGE = "image"
    AUDIO = "audio"
    CODE = "code"
    DATA = "data"
    ARCHIVE = "archive"
    OTHER = "other"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


# ─── Data Models ─────────────────────────────────────────

@dataclass
class FileMetadata:
    """Complete metadata for an uploaded file."""
    file_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    filename: str = ""
    original_name: str = ""
    mime_type: str = "application/octet-stream"
    size_bytes: int = 0
    category: str = "other"
    extension: str = ""
    checksum_sha256: str = ""

    # Owner
    user_id: str = "anonymous"
    session_id: str = ""

    # Processing
    status: str = "pending"
    chunks_count: int = 0
    preview_text: str = ""
    thumbnail_url: str = ""
    download_url: str = ""

    # Timestamps
    uploaded_at: float = field(default_factory=time.time)
    processed_at: float = 0.0

    # Dimensions (images/audio)
    width: int = 0
    height: int = 0
    duration_seconds: float = 0.0
    page_count: int = 0

    # Display
    display_name: str = ""
    icon: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def size_display(self) -> str:
        """Human-readable file size."""
        if self.size_bytes < 1024:
            return f"{self.size_bytes} B"
        elif self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        else:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"


@dataclass
class FileChunk:
    """A chunk of file content for processing or display."""
    chunk_id: str = ""
    file_id: str = ""
    index: int = 0
    total: int = 0
    content: str = ""
    start_offset: int = 0
    end_offset: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ─── File Type Detection ─────────────────────────────────

# Extension → category mapping
_EXT_CATEGORY = {
    # Documents
    "txt": FileCategory.DOCUMENT, "md": FileCategory.DOCUMENT,
    "csv": FileCategory.DATA, "json": FileCategory.DATA,
    "xml": FileCategory.DATA, "yaml": FileCategory.DATA,
    "yml": FileCategory.DATA, "toml": FileCategory.DATA,
    "pdf": FileCategory.DOCUMENT, "doc": FileCategory.DOCUMENT,
    "docx": FileCategory.DOCUMENT, "rtf": FileCategory.DOCUMENT,
    "odt": FileCategory.DOCUMENT,
    # Code
    "py": FileCategory.CODE, "js": FileCategory.CODE,
    "ts": FileCategory.CODE, "jsx": FileCategory.CODE,
    "tsx": FileCategory.CODE, "html": FileCategory.CODE,
    "css": FileCategory.CODE, "scss": FileCategory.CODE,
    "java": FileCategory.CODE, "go": FileCategory.CODE,
    "rs": FileCategory.CODE, "rb": FileCategory.CODE,
    "php": FileCategory.CODE, "sh": FileCategory.CODE,
    "sql": FileCategory.CODE, "swift": FileCategory.CODE,
    "kt": FileCategory.CODE,
    # Images
    "png": FileCategory.IMAGE, "jpg": FileCategory.IMAGE,
    "jpeg": FileCategory.IMAGE, "gif": FileCategory.IMAGE,
    "svg": FileCategory.IMAGE, "webp": FileCategory.IMAGE,
    "ico": FileCategory.IMAGE, "bmp": FileCategory.IMAGE,
    # Audio
    "mp3": FileCategory.AUDIO, "wav": FileCategory.AUDIO,
    "ogg": FileCategory.AUDIO, "webm": FileCategory.AUDIO,
    "flac": FileCategory.AUDIO, "m4a": FileCategory.AUDIO,
    # Data
    "sqlite": FileCategory.DATA, "db": FileCategory.DATA,
    "parquet": FileCategory.DATA,
    # Archives
    "zip": FileCategory.ARCHIVE, "tar": FileCategory.ARCHIVE,
    "gz": FileCategory.ARCHIVE,
}

# Category → icon mapping
_CATEGORY_ICONS = {
    FileCategory.DOCUMENT: "file-text",
    FileCategory.IMAGE: "image",
    FileCategory.AUDIO: "music",
    FileCategory.CODE: "code",
    FileCategory.DATA: "database",
    FileCategory.ARCHIVE: "archive",
    FileCategory.OTHER: "file",
}


def detect_file_type(filename: str, data: bytes = b"") -> tuple[str, FileCategory, str]:
    """
    Detect MIME type, category, and icon from filename and optional magic bytes.

    Returns (mime_type, category, icon).
    """
    ext = Path(filename).suffix.lstrip(".").lower()

    # MIME from extension
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        # Fallback magic-byte detection for common formats
        if data[:4] == b"%PDF":
            mime_type = "application/pdf"
            ext = "pdf"
        elif data[:4] == b"\x89PNG":
            mime_type = "image/png"
            ext = "png"
        elif data[:3] == b"\xff\xd8\xff":
            mime_type = "image/jpeg"
            ext = "jpg"
        elif data[:4] == b"GIF8":
            mime_type = "image/gif"
            ext = "gif"
        elif data[:4] == b"PK\x03\x04":
            mime_type = "application/zip"
            ext = "zip"
        elif data[:4] == b"RIFF" and len(data) > 8 and data[8:12] == b"WAVE":
            mime_type = "audio/wav"
            ext = "wav"
        else:
            mime_type = "application/octet-stream"

    category = _EXT_CATEGORY.get(ext, FileCategory.OTHER)
    icon = _CATEGORY_ICONS.get(category, "file")

    return mime_type, category, icon


def is_text_file(mime_type: str, ext: str) -> bool:
    """Check if a file is a readable text file."""
    if mime_type.startswith("text/"):
        return True
    text_mimes = {
        "application/json", "application/xml", "application/yaml",
        "application/javascript", "application/typescript",
        "application/x-yaml", "application/toml",
    }
    if mime_type in text_mimes:
        return True
    text_exts = {
        "py", "js", "ts", "jsx", "tsx", "html", "css", "scss",
        "java", "go", "rs", "rb", "php", "sh", "sql", "swift", "kt",
        "md", "txt", "csv", "json", "xml", "yaml", "yml", "toml",
    }
    return ext.lower() in text_exts


# ─── Text Chunking ───────────────────────────────────────

def chunk_text(
    text: str,
    max_chunk_size: int = MAX_CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    file_id: str = "",
) -> list[FileChunk]:
    """
    Split text into overlapping chunks for display and processing.

    Tries to break at paragraph or sentence boundaries when possible.
    """
    if not text or len(text) <= max_chunk_size:
        return [FileChunk(
            chunk_id=f"{file_id}:0" if file_id else "0",
            file_id=file_id,
            index=0,
            total=1,
            content=text,
            start_offset=0,
            end_offset=len(text),
        )]

    chunks = []
    pos = 0
    idx = 0

    while pos < len(text):
        end = min(pos + max_chunk_size, len(text))

        # Try to break at paragraph boundary
        if end < len(text):
            # Look for double newline within last 20% of chunk
            search_start = pos + int(max_chunk_size * 0.8)
            para_break = text.rfind("\n\n", search_start, end)
            if para_break > search_start:
                end = para_break + 2  # include the newlines

            # Fallback: look for single newline
            elif text.rfind("\n", search_start, end) > search_start:
                end = text.rfind("\n", search_start, end) + 1

            # Fallback: look for sentence end
            elif text.rfind(". ", search_start, end) > search_start:
                end = text.rfind(". ", search_start, end) + 2

        chunk_content = text[pos:end]
        chunks.append(FileChunk(
            chunk_id=f"{file_id}:{idx}" if file_id else str(idx),
            file_id=file_id,
            index=idx,
            total=0,  # set after loop
            content=chunk_content,
            start_offset=pos,
            end_offset=end,
        ))

        # Advance with overlap
        pos = max(end - overlap, pos + 1) if end < len(text) else end
        idx += 1

    # Set total on all chunks
    for c in chunks:
        c.total = len(chunks)

    return chunks


# ─── Binary Document Text Extraction ─────────────────────

def extract_text(data: bytes, filename: str, mime_type: str) -> str | None:
    """
    Extract text content from binary document formats (PDF, DOCX).

    Returns the extracted text string, or None if extraction fails
    or the format is not supported.
    """
    ext = Path(filename).suffix.lstrip(".").lower()

    # PDF extraction
    if mime_type == "application/pdf" or ext == "pdf":
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(BytesIO(data))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            if pages:
                return "\n\n".join(pages)
            logger.warning(f"PDF text extraction returned empty for {filename}")
            return None
        except Exception as e:
            logger.warning(f"PDF text extraction failed for {filename}: {e}")
            return None

    # DOCX extraction
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or ext == "docx":
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(BytesIO(data))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            if paragraphs:
                return "\n\n".join(paragraphs)
            logger.warning(f"DOCX text extraction returned empty for {filename}")
            return None
        except Exception as e:
            logger.warning(f"DOCX text extraction failed for {filename}: {e}")
            return None

    return None


# ─── Preview Extraction ──────────────────────────────────

def extract_preview(data: bytes, mime_type: str, ext: str, max_length: int = 500) -> str:
    """Extract a text preview from file data for display cards."""
    if is_text_file(mime_type, ext):
        try:
            text = data.decode("utf-8", errors="replace")
            if len(text) <= max_length:
                return text
            return text[:max_length] + "..."
        except Exception:
            return ""

    # Try binary document extraction for PDF/DOCX
    if mime_type == "application/pdf" or ext == "pdf" or ext == "docx" or \
       mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = extract_text(data, f"file.{ext}", mime_type)
        if text:
            if len(text) <= max_length:
                return text
            return text[:max_length] + "..."
        if ext == "pdf":
            return "[PDF document — text extraction unavailable]"
        return "[DOCX document — text extraction unavailable]"

    if mime_type.startswith("image/"):
        return f"[Image: {ext.upper()}]"

    if mime_type.startswith("audio/"):
        return f"[Audio: {ext.upper()}]"

    return ""


# ─── Checksum ────────────────────────────────────────────

def compute_checksum(data: bytes) -> str:
    """Compute SHA-256 checksum of file data."""
    return hashlib.sha256(data).hexdigest()


# ─── Validation ──────────────────────────────────────────

def validate_upload(
    filename: str,
    size_bytes: int,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> tuple[bool, str]:
    """
    Validate a file upload. Returns (ok, error_message).
    """
    if not filename:
        return False, "Filename is required"

    ext = Path(filename).suffix.lstrip(".").lower()

    if ext in BLOCKED_EXTENSIONS:
        return False, f"File type .{ext} is not allowed"

    if ext and ext not in ALLOWED_EXTENSIONS and ext not in BLOCKED_EXTENSIONS:
        # Allow unknown extensions but log
        logger.warning(f"Upload with unknown extension: .{ext}")

    if size_bytes > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        return False, f"File exceeds maximum size of {max_mb:.0f} MB"

    if size_bytes == 0:
        return False, "File is empty"

    # Check for path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return False, "Invalid filename"

    return True, ""


# ─── File Processor (main entry point) ───────────────────

class FileProcessor:
    """
    Orchestrates file upload processing: validation, type detection,
    metadata extraction, chunking, and storage.
    """

    def __init__(self, storage=None, max_upload_bytes: int = MAX_UPLOAD_BYTES):
        self.storage = storage
        self.max_upload_bytes = max_upload_bytes
        self._files: dict[str, FileMetadata] = {}  # in-memory index
        self._file_content: dict[str, bytes] = {}  # raw content cache for citations
        logger.info("FileProcessor initialized")

    async def process(
        self,
        data: bytes,
        filename: str,
        content_type: str = "",
        user_id: str = "anonymous",
        session_id: str = "",
    ) -> FileMetadata:
        """
        Process an uploaded file: validate, detect type, extract metadata,
        store, and return metadata.
        """
        # Validate
        ok, err = validate_upload(filename, len(data), self.max_upload_bytes)
        if not ok:
            raise ValueError(err)

        # Detect type
        mime_type, category, icon = detect_file_type(filename, data)
        if content_type and content_type != "application/octet-stream":
            mime_type = content_type  # trust client's content-type if specific

        ext = Path(filename).suffix.lstrip(".").lower()

        # Build metadata
        meta = FileMetadata(
            filename=f"{uuid.uuid4().hex[:8]}_{filename}",
            original_name=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            category=category.value if isinstance(category, FileCategory) else category,
            extension=ext,
            checksum_sha256=compute_checksum(data),
            user_id=user_id,
            session_id=session_id,
            status=ProcessingStatus.PROCESSING.value,
            display_name=filename,
            icon=icon,
            uploaded_at=time.time(),
        )

        # Extract preview
        meta.preview_text = extract_preview(data, mime_type, ext)

        # Chunk text content
        if is_text_file(mime_type, ext):
            try:
                text = data.decode("utf-8", errors="replace")
                chunks = chunk_text(text, file_id=meta.file_id)
                meta.chunks_count = len(chunks)
            except Exception as e:
                logger.warning(f"Failed to chunk {filename}: {e}")

        # Store file
        if self.storage:
            try:
                url = await self.storage.upload_asset(meta.filename, data, mime_type)
                meta.download_url = url
            except Exception as e:
                logger.error(f"Storage upload failed for {filename}: {e}")
                meta.status = ProcessingStatus.FAILED.value
                self._files[meta.file_id] = meta
                return meta

        meta.status = ProcessingStatus.READY.value
        meta.processed_at = time.time()
        self._files[meta.file_id] = meta

        # Cache content for citation-enabled document retrieval
        self._file_content[meta.file_id] = data

        logger.info(
            f"Processed file: {filename} ({meta.size_display}, {meta.category})"
        )
        return meta

    def get(self, file_id: str) -> Optional[FileMetadata]:
        """Get file metadata by ID."""
        return self._files.get(file_id)

    def get_content(self, file_id: str) -> Optional[bytes]:
        """Get raw file content by ID. Returns None if not cached."""
        return self._file_content.get(file_id)

    def list_files(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[FileMetadata]:
        """List files with optional filters."""
        files = list(self._files.values())
        if user_id:
            files = [f for f in files if f.user_id == user_id]
        if session_id:
            files = [f for f in files if f.session_id == session_id]
        if category:
            files = [f for f in files if f.category == category]
        files.sort(key=lambda f: f.uploaded_at, reverse=True)
        return files

    def delete(self, file_id: str) -> bool:
        """Remove file from index. Returns True if found."""
        if file_id in self._files:
            del self._files[file_id]
            self._file_content.pop(file_id, None)
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._files)

    def get_chunks(self, file_id: str, data: bytes) -> list[FileChunk]:
        """Chunk file data and return chunks list."""
        meta = self.get(file_id)
        if not meta:
            return []
        if not is_text_file(meta.mime_type, meta.extension):
            return []
        try:
            text = data.decode("utf-8", errors="replace")
            return chunk_text(text, file_id=file_id)
        except Exception:
            return []
