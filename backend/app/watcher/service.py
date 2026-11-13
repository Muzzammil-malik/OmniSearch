"""Local filesystem watcher service using watchdog."""

from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Set, Union
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.core.logging import get_logger
from app.watcher.debouncer import ChangeDebouncer
from app.watcher.events import FileChangeType
from app.watcher.filters import is_supported_file, should_ignore_path

logger = get_logger(__name__)


class OmniSearchEventHandler(FileSystemEventHandler):
    """Event handler filtering and routing watchdog events to the debouncer."""

    def __init__(self, debouncer: ChangeDebouncer) -> None:
        super().__init__()
        self.debouncer = debouncer

    def on_created(self, event: FileSystemEvent) -> None:
        if should_ignore_path(event.src_path, event.is_directory):
            return
        if not is_supported_file(event.src_path):
            return
        self.debouncer.record_event(FileChangeType.CREATED, event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if should_ignore_path(event.src_path, event.is_directory):
            return
        if not is_supported_file(event.src_path):
            return
        self.debouncer.record_event(FileChangeType.MODIFIED, event.src_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if should_ignore_path(event.src_path, event.is_directory):
            return
        # Deleted files might no longer exist to check extension, but filter standard temp files
        self.debouncer.record_event(FileChangeType.DELETED, event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        dest = getattr(event, "dest_path", None)
        if should_ignore_path(event.src_path, event.is_directory) and (
            not dest or should_ignore_path(dest, event.is_directory)
        ):
            return

        self.debouncer.record_event(
            FileChangeType.MOVED,
            path=event.src_path,
            dest_path=dest,
        )


class FileSystemWatcher:
    """Manages watchdog observer instances for registered active folders with deduplication."""

    def __init__(self, debouncer: ChangeDebouncer) -> None:
        self.debouncer = debouncer
        self.handler = OmniSearchEventHandler(debouncer)
        self._observer: Optional[Observer] = None
        self._lock = Lock()
        # folder_id -> watchdog watch object
        self._watches: Dict[int, Any] = {}
        # folder_id -> normalized Path
        self._watched_paths: Dict[int, Path] = {}
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def watched_folders(self) -> List[str]:
        with self._lock:
            return [str(p) for p in self._watched_paths.values()]

    def start(self) -> None:
        """Start the filesystem observer."""
        with self._lock:
            if self._is_running:
                return
            try:
                self._observer = Observer()
                self._observer.daemon = True
                self._observer.start()
                self._is_running = True
                logger.info("Filesystem observer started successfully")
            except Exception as exc:
                logger.error("Failed to start watchdog filesystem observer: %s", exc)
                self._is_running = False
                raise

    def stop(self) -> None:
        """Stop the filesystem observer cleanly."""
        with self._lock:
            if not self._is_running or not self._observer:
                return
            try:
                self._observer.stop()
                self._observer.join(timeout=3.0)
                self._watches.clear()
                self._watched_paths.clear()
                self._is_running = False
                logger.info("Filesystem observer stopped cleanly")
            except Exception as exc:
                logger.warning("Error stopping watchdog observer: %s", exc)

    def add_folder(self, folder_id: int, path: Union[str, Path]) -> bool:
        """Add a folder to be watched recursively. Avoids duplicate watchers for nested paths."""
        resolved = Path(path).resolve()
        if not resolved.exists() or not resolved.is_dir():
            logger.warning("Cannot watch non-existent folder: %s", resolved)
            return False

        with self._lock:
            if folder_id in self._watches:
                return True

            # Deduplication: check if already covered by an existing parent watch
            for existing_id, existing_path in self._watched_paths.items():
                if resolved == existing_path or resolved.is_relative_to(existing_path):
                    logger.debug("Folder %s already covered by watcher on %s", resolved, existing_path)
                    self._watched_paths[folder_id] = resolved
                    return True

            if not self._is_running or not self._observer:
                self._watched_paths[folder_id] = resolved
                return True

            try:
                watch = self._observer.schedule(self.handler, str(resolved), recursive=True)
                self._watches[folder_id] = watch
                self._watched_paths[folder_id] = resolved
                logger.info("Scheduled recursive filesystem watch for folder #%d: %s", folder_id, resolved)
                return True
            except Exception as exc:
                logger.error("Failed to schedule watch for folder '%s': %s", resolved, exc)
                return False

    def remove_folder(self, folder_id: int) -> bool:
        """Remove watch on a folder."""
        with self._lock:
            watch = self._watches.pop(folder_id, None)
            self._watched_paths.pop(folder_id, None)

            if watch and self._observer and self._is_running:
                try:
                    self._observer.unschedule(watch)
                    logger.info("Unscheduled filesystem watch for folder #%d", folder_id)
                    return True
                except Exception as exc:
                    logger.warning("Failed to unschedule watch for folder #%d: %s", folder_id, exc)
                    return False
            return True

    def sync_folders(self, active_folders: List[Any]) -> None:
        """Synchronize active watched directories with a list of active folder records."""
        active_map = {f.id: Path(f.path) for f in active_folders if getattr(f, "enabled", True)}

        with self._lock:
            current_ids = set(self._watched_paths.keys())
            target_ids = set(active_map.keys())

        # Remove deleted / disabled folders
        for fid in current_ids - target_ids:
            self.remove_folder(fid)

        # Add new enabled folders
        for fid in target_ids - current_ids:
            self.add_folder(fid, active_map[fid])

