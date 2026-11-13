"""System diagnostics and application status endpoints."""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints.folders import get_indexing_service
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.database.connection import DatabaseConnectionManager
from app.schemas.indexing import IndexingStatsResponse
from app.schemas.system import NativeFolderPickerResponse, SystemStatusResponse
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


