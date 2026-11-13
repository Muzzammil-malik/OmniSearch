"""System diagnostics and application status endpoints."""

from pathlib import Path
from typing import Optional
import mimetypes
import os
import platform
import subprocess
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.v1.endpoints.folders import get_indexing_service
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.database.connection import DatabaseConnectionManager
from app.schemas.indexing import IndexingStatsResponse
from app.schemas.system import (
    ContextMenuStatusResponse,
    ContextMenuToggleRequest,
    ContextMenuToggleResponse,
    FileActionRequest,
    FileActionResponse,
    NativeFolderPickerResponse,
    SystemStatusResponse,
)
from app.services.indexer import IndexingService
from app.services.system_service import SystemService

logger = get_logger(__name__)
router = APIRouter()


def get_system_service(settings: Settings = Depends(get_settings)) -> SystemService:
    """Dependency providing configured SystemService instance."""
    db = DatabaseConnectionManager()
    return SystemService(db=db, settings=settings)


@router.get(
    "/system/status",
    response_model=SystemStatusResponse,
    summary="System Diagnostic Status",
    description="Retrieve operational telemetry across database, vector store, and local embedding models.",
)
async def get_system_status(
    service: SystemService = Depends(get_system_service),
) -> SystemStatusResponse:
    """Retrieve detailed system and subsystem diagnostics."""
    return service.get_system_status()


@router.get(
    "/system/stats",
    response_model=IndexingStatsResponse,
    summary="System Content Statistics",
    description="Retrieve aggregated statistics on indexed files, chunks, and vector embeddings.",
)
async def get_system_stats(
    indexing_service: IndexingService = Depends(get_indexing_service),
) -> IndexingStatsResponse:
    """Retrieve aggregated indexing statistics."""
    return indexing_service.get_indexing_stats()


@router.post(
    "/system/pick-folder",
    response_model=NativeFolderPickerResponse,
    summary="Native OS Folder Picker",
    description="Invoke the native operating-system folder selection dialog and return the chosen path.",
)
def pick_folder_native() -> NativeFolderPickerResponse:
    """Invoke the host OS native folder selection dialog."""
    import platform
    system = platform.system().lower()

    # 1. Tkinter (cross-platform, native dialog on Windows, macOS, Linux)
    try:
        import tkinter
        import tkinter.filedialog
        root = tkinter.Tk()
        root.withdraw()
        root.lift()
        root.attributes("-topmost", True)
        root.focus_force()
        selected = tkinter.filedialog.askdirectory(parent=root, title="Select Folder for OmniSearch Library")
        root.destroy()
        if selected:
            from pathlib import Path
            return NativeFolderPickerResponse(path=str(Path(selected).resolve()), canceled=False)
        return NativeFolderPickerResponse(path=None, canceled=True)
    except Exception as exc:
        logger.warning("Tkinter folder picker failed: %s; trying platform fallback", exc)

    # 2. Windows PowerShell FolderBrowserDialog fallback
    if system == "windows":
        import subprocess
        try:
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "$f.Description = 'Select Folder for OmniSearch Library'; "
                "$f.ShowNewFolderButton = $true; "
                "$top = New-Object System.Windows.Forms.Form; "
                "$top.TopMost = $true; "
                "if ($f.ShowDialog($top) -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Sta", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = res.stdout.strip()
            if out:
                from pathlib import Path
                return NativeFolderPickerResponse(path=str(Path(out).resolve()), canceled=False)
            return NativeFolderPickerResponse(path=None, canceled=True)
        except Exception as exc:
            logger.error("PowerShell native folder dialog failed: %s", exc)
            return NativeFolderPickerResponse(path=None, canceled=False, error=str(exc))

    return NativeFolderPickerResponse(path=None, canceled=False, error="Native folder picker not supported on host platform")


# Comprehensive MIME mapping covering modern media and documents
MEDIA_MIME_TYPES = {
    # Images
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".ico": "image/x-icon",
    # Audio
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/opus",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".wma": "audio/x-ms-wma",
    ".weba": "audio/webm",
    # Video
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".ogv": "video/ogg",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".wmv": "video/x-ms-wmv",
    ".m4v": "video/mp4",
    # Documents
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".json": "application/json",
    ".csv": "text/csv; charset=utf-8",
}


def guess_media_type(file_path: Path) -> str:
    """Determine accurate MIME type for media playback and embedded preview."""
    ext = file_path.suffix.lower()
    if ext in MEDIA_MIME_TYPES:
        return MEDIA_MIME_TYPES[ext]
    media_type, _ = mimetypes.guess_type(str(file_path))
    return media_type or "application/octet-stream"


def validate_file_scope(
    db: DatabaseConnectionManager,
    resolved_path: Path,
    file_id: Optional[int],
) -> bool:
    """Validate that the requested file path belongs to an indexed file or active library folder."""
    clean_id = file_id if isinstance(file_id, int) else None
    try:
        with db.connection() as conn:
            cursor = conn.cursor()

            # 1. If file_id is provided, verify it directly
            if clean_id is not None:
                cursor.execute("SELECT id, path FROM files WHERE id = ?;", (clean_id,))
                row = cursor.fetchone()
                if row:
                    db_path = Path(row["path"]).resolve()
                    if db_path == resolved_path:
                        cursor.close()
                        return True

            # 2. Check if path matches an indexed file in files table
            cursor.execute("SELECT id FROM files WHERE path = ? LIMIT 1;", (str(resolved_path),))
            if cursor.fetchone():
                cursor.close()
                return True

            # 3. Check if path is inside any active library folder
            cursor.execute("SELECT path FROM folders WHERE enabled = 1;")
            folders = cursor.fetchall()
            cursor.close()
            for fld in folders:
                try:
                    folder_path = Path(fld["path"]).resolve()
                    if resolved_path.is_relative_to(folder_path):
                        return True
                except (ValueError, TypeError):
                    continue
    except Exception as exc:
        logger.error("Error during file scope validation for %s: %s", resolved_path, exc)
        return False

    return False


@router.get(
    "/system/file-content",
    summary="Serve Local File for Preview",
    description="Stream raw file content (images, audio, video, PDF) with range request support for media previews.",
)
def get_file_content(
    file_id: Optional[int] = Query(default=None, description="Indexed file database ID"),
    path: Optional[str] = Query(default=None, description="Absolute file path on host"),
    db: DatabaseConnectionManager = Depends(DatabaseConnectionManager),
) -> FileResponse:
    """Safely stream local file content for frontend preview."""
    # Handle direct function call where default is Query object
    clean_file_id: Optional[int] = file_id if isinstance(file_id, int) else None
    clean_path: Optional[str] = path if isinstance(path, str) and path else None

    if clean_file_id is None and not clean_path:
        raise HTTPException(status_code=400, detail="Either 'file_id' or 'path' must be provided.")

    resolved: Optional[Path] = None

    if clean_file_id is not None and not clean_path:
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT path FROM files WHERE id = ?;", (clean_file_id,))
            row = cursor.fetchone()
            cursor.close()
            if not row:
                raise HTTPException(status_code=404, detail="File ID not found in library.")
            resolved = Path(row["path"]).resolve()
    else:
        try:
            resolved = Path(clean_path).resolve()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid file path: {exc}")

    # Security check: must belong to indexed files or an active library folder
    if not validate_file_scope(db, resolved, clean_file_id):
        raise HTTPException(
            status_code=403,
            detail="Access denied: requested file is not part of an indexed library folder.",
        )

    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="File no longer exists at this location.")

    media_type = guess_media_type(resolved)

    return FileResponse(
        path=str(resolved),
        media_type=media_type,
        filename=resolved.name,
        content_disposition_type="inline",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get(
    "/files/{file_id}/content",
    summary="Serve Indexed File by ID",
    description="Stream raw file content for a specific indexed file ID.",
)
def get_file_content_by_id(
    file_id: int,
    db: DatabaseConnectionManager = Depends(DatabaseConnectionManager),
) -> FileResponse:
    """Stream raw file content for a specific indexed file ID."""
    return get_file_content(file_id=file_id, path=None, db=db)


@router.post(
    "/system/open-file",
    response_model=FileActionResponse,
    summary="Open File in OS Default Application",
    description="Launch the selected file using the operating system's default file association.",
)
def open_file_endpoint(req: FileActionRequest) -> FileActionResponse:
    """Open file using host operating system default application."""
    try:
        resolved = Path(req.path).resolve()
    except Exception as exc:
        return FileActionResponse(success=False, error=f"Invalid file path: {exc}")

    if not resolved.is_file():
        return FileActionResponse(success=False, error="File no longer exists at this location.")

    sys_name = platform.system().lower()
    try:
        if sys_name == "windows":
            os.startfile(str(resolved))
        elif sys_name == "darwin":
            subprocess.run(["open", str(resolved)], check=True)
        else:
            subprocess.run(["xdg-open", str(resolved)], check=True)
        return FileActionResponse(success=True)
    except Exception as exc:
        logger.error("Failed to open file %s: %s", resolved, exc)
        return FileActionResponse(success=False, error=str(exc))


@router.post(
    "/system/reveal-file",
    response_model=FileActionResponse,
    summary="Reveal File in OS File Explorer",
    description="Open the host file explorer with the selected file highlighted.",
)
def reveal_file_endpoint(req: FileActionRequest) -> FileActionResponse:
    """Reveal file in host operating system file manager."""
    try:
        resolved = Path(req.path).resolve()
    except Exception as exc:
        return FileActionResponse(success=False, error=f"Invalid file path: {exc}")

    if not resolved.is_file():
        return FileActionResponse(success=False, error="File no longer exists at this location.")

    sys_name = platform.system().lower()
    try:
        if sys_name == "windows":
            subprocess.run(["explorer.exe", f"/select,{str(resolved)}"])
        elif sys_name == "darwin":
            subprocess.run(["open", "-R", str(resolved)], check=True)
        else:
            subprocess.run(["xdg-open", str(resolved.parent)], check=True)
        return FileActionResponse(success=True)
    except Exception as exc:
        logger.error("Failed to reveal file %s: %s", resolved, exc)
        return FileActionResponse(success=False, error=str(exc))


CONTEXT_MENU_KEYS = [
    r"Software\Classes\Directory\shell\OmniSearch",
    r"Software\Classes\Directory\Background\shell\OmniSearch",
    r"Software\Classes\Folder\shell\OmniSearch",
]


def is_context_menu_registered_windows() -> bool:
    """Check if OmniSearch context menu keys exist in Windows Registry."""
    if platform.system().lower() != "windows":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CONTEXT_MENU_KEYS[0], 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, "")
            return val == "Search with OmniSearch"
    except Exception:
        return False


def set_context_menu_windows(enable: bool) -> tuple[bool, Optional[str]]:
    """Register or unregister OmniSearch in Windows Explorer context menu."""
    if platform.system().lower() != "windows":
        return False, "Windows Explorer context menu integration is only supported on Windows."
    try:
        import ctypes
        import winreg

        if enable:
            # Root directory: 6 levels up: app/api/v1/endpoints/system.py -> backend -> OmniSearch
            root_dir = Path(__file__).resolve().parents[5]
            frontend_dir = root_dir / "frontend"
            electron_exe = frontend_dir / "node_modules" / "electron" / "dist" / "electron.exe"
            main_js = frontend_dir / "electron" / "main.js"

            if not electron_exe.exists():
                return False, f"Electron binary not found at {electron_exe}"

            cmd_str = f'"{electron_exe}" "{main_js}" --open-folder "%V"'
            icon_str = str(electron_exe)

            for k in CONTEXT_MENU_KEYS:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, k) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Search with OmniSearch")
                    winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_str)
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{k}\\command") as cmd_key:
                    winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd_str)

        else:
            for k in CONTEXT_MENU_KEYS:
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{k}\\command")
                except Exception:
                    pass
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, k)
                except Exception:
                    pass

        # Invalidate Explorer shell cache immediately
        try:
            SHCNE_ASSOCCHANGED = 0x08000000
            SHCNF_IDLIST = 0x0000
            ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
        except Exception as notify_err:
            logger.debug("SHChangeNotify notice: %s", notify_err)

        return True, None
    except Exception as exc:
        logger.error("Error setting Windows context menu: %s", exc)
        return False, str(exc)


@router.get(
    "/system/context-menu",
    response_model=ContextMenuStatusResponse,
    summary="Get Windows Explorer Context Menu Status",
    description="Query current Windows Registry registration status of the Explorer context menu.",
)
def get_context_menu_status_endpoint() -> ContextMenuStatusResponse:
    """Query current context menu registration status."""
    enabled = is_context_menu_registered_windows()
    return ContextMenuStatusResponse(enabled=enabled)


@router.post(
    "/system/context-menu",
    response_model=ContextMenuToggleResponse,
    summary="Enable/Disable Windows Explorer Context Menu",
    description="Register or unregister OmniSearch in the Windows Explorer folder context menu.",
)
def toggle_context_menu_endpoint(req: ContextMenuToggleRequest) -> ContextMenuToggleResponse:
    """Register or unregister Explorer context menu entries."""
    success, error = set_context_menu_windows(req.enabled)
    return ContextMenuToggleResponse(success=success, error=error)




