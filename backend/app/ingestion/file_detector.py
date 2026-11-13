"""File type and signature validation to prevent extension spoofing and misclassification."""

from pathlib import Path
from typing import Optional, Set, Tuple
import zipfile

from app.core.logging import get_logger

logger = get_logger(__name__)

# Common code and text extensions
CODE_EXTENSIONS: Set[str] = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h", ".cs",
    ".go", ".rs", ".php", ".css", ".json", ".xml", ".yaml", ".yml",
    ".sql", ".sh", ".bat", ".ps1",
}

TEXT_EXTENSIONS: Set[str] = {".txt", ".text", ".log", ".ini", ".cfg", ".conf"}
MARKDOWN_EXTENSIONS: Set[str] = {".md", ".markdown"}
HTML_EXTENSIONS: Set[str] = {".html", ".htm", ".xhtml"}
CSV_EXTENSIONS: Set[str] = {".csv", ".tsv"}
DOCUMENT_EXTENSIONS: Set[str] = {".pdf", ".docx", ".pptx", ".xlsx"}
IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}
AUDIO_EXTENSIONS: Set[str] = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wma"}
VIDEO_EXTENSIONS: Set[str] = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".wmv", ".m4v", ".mpeg", ".mpg"}

ALL_SUPPORTED_EXTENSIONS: Set[str] = (
    CODE_EXTENSIONS
    | TEXT_EXTENSIONS
    | MARKDOWN_EXTENSIONS
    | HTML_EXTENSIONS
    | CSV_EXTENSIONS
    | DOCUMENT_EXTENSIONS
    | IMAGE_EXTENSIONS
    | AUDIO_EXTENSIONS
    | VIDEO_EXTENSIONS
)

# Known binary executable signatures to block/reject
EXECUTABLE_SIGNATURES: Tuple[bytes, ...] = (
    b"MZ",              # Windows PE Executable/DLL
    b"\x7fELF",         # Linux Executable
    b"\xca\xfe\xba\xbe", # Mach-O or Java bytecode
    b"\xfe\xed\xfa\xce", # Mach-O 32-bit
    b"\xfe\xed\xfa\xcf", # Mach-O 64-bit
    b"\xcf\xfa\xed\xfe", # Mach-O 64-bit little endian
)

PDF_SIGNATURE = b"%PDF-"
ZIP_SIGNATURE = b"PK\x03\x04"


class FileTypeDetector:
    """Detects and validates file types by combining extension with header signature inspection."""

    @staticmethod
    def is_supported_extension(extension: str) -> bool:
        """Check if an extension is supported by OmniSearch."""
        return extension.lower() in ALL_SUPPORTED_EXTENSIONS

    @staticmethod
    def get_format_category(extension: str) -> str:
        """Map extension to normalized category string."""
        ext = extension.lower()
        if ext == ".pdf":
            return "pdf"
        if ext == ".docx":
            return "docx"
        if ext == ".pptx":
            return "pptx"
        if ext == ".xlsx":
            return "xlsx"
        if ext in IMAGE_EXTENSIONS:
            return "image"
        if ext in AUDIO_EXTENSIONS:
            return "audio"
        if ext in VIDEO_EXTENSIONS:
            return "video"
        if ext in HTML_EXTENSIONS:
            return "html"
        if ext in CSV_EXTENSIONS:
            return "csv"
        if ext in MARKDOWN_EXTENSIONS:
            return "markdown"
        if ext in CODE_EXTENSIONS:
            return "code"
        if ext in TEXT_EXTENSIONS:
            return "text"
        return "unsupported"

    @classmethod
    def validate_file(cls, file_path: Path) -> Tuple[bool, str, Optional[str]]:
        """Inspect file header and extension to validate authenticity.

        Returns:
            Tuple of:
            - is_valid: bool (True if valid and supported)
            - format_category: str (e.g. 'pdf', 'docx', 'code', 'unsupported')
            - error_reason: Optional[str] (error description if invalid)
        """
        path = Path(file_path)
        if not path.is_file():
            return False, "unsupported", f"Path does not exist or is not a regular file: {path}"

        ext = path.suffix.lower()
        if not cls.is_supported_extension(ext):
            return False, "unsupported", f"Unsupported file extension '{ext}'"

        try:
            file_size = path.stat().st_size
        except (OSError, PermissionError) as exc:
            return False, "unsupported", f"Cannot access file metadata: {exc}"

        # Handle empty files: supported as empty documents
        if file_size == 0:
            return True, cls.get_format_category(ext), None

        # Read only the first 2 KB for signature inspection (no large memory loading)
        try:
            with open(path, "rb") as f:
                header = f.read(2048)
        except (OSError, PermissionError) as exc:
            return False, "unsupported", f"Unreadable file header: {exc}"

        # 1. Reject disguised executables immediately
        for sig in EXECUTABLE_SIGNATURES:
            if header.startswith(sig):
                return False, "rejected_executable", f"File contains executable binary header signature: {sig!r}"

        category = cls.get_format_category(ext)

        # 2. PDF validation
        if category == "pdf":
            if PDF_SIGNATURE not in header[:1024]:
                return False, "invalid_pdf", "File has .pdf extension but lacks '%PDF-' signature"
            return True, "pdf", None

        # 3. Office OpenXML validation (DOCX, PPTX, XLSX)
        if category in {"docx", "pptx", "xlsx"}:
            if not header.startswith(ZIP_SIGNATURE):
                return False, f"invalid_{category}", f"File has .{category} extension but lacks valid ZIP header"
            # Verify internal structure without extracting contents
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    namelist = zf.namelist()
                    if "[Content_Types].xml" not in namelist:
                        return False, f"invalid_{category}", "Missing [Content_Types].xml in Office document"
                    if category == "docx" and not any(name.startswith("word/") for name in namelist):
                        return False, "invalid_docx", "Missing word/ structure in DOCX archive"
                    if category == "pptx" and not any(name.startswith("ppt/") for name in namelist):
                        return False, "invalid_pptx", "Missing ppt/ structure in PPTX archive"
                    if category == "xlsx" and not any(name.startswith("xl/") for name in namelist):
                        return False, "invalid_xlsx", "Missing xl/ structure in XLSX archive"
            except zipfile.BadZipFile as exc:
                return False, f"invalid_{category}", f"Corrupted or invalid Office ZIP container: {exc}"
            except Exception as exc:
                return False, f"invalid_{category}", f"Office container inspection failed: {exc}"
            return True, category, None

        # 4. Image validation
        if category == "image":
            # Signatures for JPEG, PNG, GIF, BMP, WEBP, TIFF
            is_valid_image = (
                header.startswith(b"\xff\xd8\xff")  # JPEG
                or header.startswith(b"\x89PNG\r\n\x1a\n")  # PNG
                or header.startswith(b"GIF87a") or header.startswith(b"GIF89a")  # GIF
                or header.startswith(b"BM")  # BMP
                or (header.startswith(b"RIFF") and b"WEBP" in header[8:16])  # WEBP
                or header.startswith(b"II*\x00") or header.startswith(b"MM\x00*")  # TIFF
            )
            if not is_valid_image:
                return False, "invalid_image", f"File has image extension '{ext}' but header signature does not match image formats"
            return True, "image", None

        # 5. Audio and Video validation (binary multimedia)
        if category in {"audio", "video"}:
            return True, category, None

        # 6. Text-based files (TXT, Code, Markdown, CSV, HTML)
        # Check for binary null-byte contamination (heuristic for non-text binary files)
        if category in {"text", "code", "markdown", "csv", "html"}:
            if b"\x00" in header:
                return False, "binary_mismatch", f"File extension '{ext}' expects text, but null bytes were detected"

        return True, category, None

