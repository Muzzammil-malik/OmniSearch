"""Thread-safe event debouncer and coalescer for filesystem change events."""

from collections import OrderedDict
from pathlib import Path
from threading import Event, Lock, Thread
import time
from typing import Callable, Dict, Optional, Tuple, Union

from app.core.logging import get_logger
from app.watcher.events import FileChangeEvent, FileChangeType

logger = get_logger(__name__)


class ChangeDebouncer:
    """Coalesces rapid bursts of filesystem events for the same file into a single action."""

    def __init__(
        self,
        on_event: Callable[[FileChangeEvent], None],
        debounce_ms: int = 800,
    ) -> None:
        self.on_event = on_event
        self.debounce_seconds = max(0.05, debounce_ms / 1000.0)
        self._lock = Lock()
        # Map: normalized_path_str -> (change_type, path_obj, dest_path_obj, last_event_timestamp)
        self._pending: Dict[str, Tuple[FileChangeType, Path, Optional[Path], float]] = OrderedDict()
        self._stop_event = Event()
        self._flusher_thread = Thread(target=self._flusher_loop, daemon=True, name="DebouncerFlusher")
        self._flusher_thread.start()

    def record_event(
        self,
        change_type: FileChangeType,
        path: Union[str, Path],
        dest_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """Record an incoming event, coalescing with any pending event for the same file path."""
        path_obj = Path(path).resolve()
        dest_obj = Path(dest_path).resolve() if dest_path else None
        norm_key = str(path_obj).lower()
        now = time.time()

        with self._lock:
            if norm_key in self._pending:
                existing_type, _, existing_dest, _ = self._pending[norm_key]

                if existing_type == FileChangeType.CREATED:
                    if change_type == FileChangeType.DELETED:
                        # Created and deleted within the debounce window: transient file -> drop
                        del self._pending[norm_key]
                        return
                    if change_type == FileChangeType.MOVED and dest_obj:
                        del self._pending[norm_key]
                        new_key = str(dest_obj).lower()
                        self._pending[new_key] = (FileChangeType.CREATED, dest_obj, None, now)
                        return
                    # Create + modify -> keep as CREATED
                    self._pending[norm_key] = (FileChangeType.CREATED, path_obj, None, now)
                    return

                elif existing_type == FileChangeType.MODIFIED:
                    if change_type == FileChangeType.DELETED:
                        self._pending[norm_key] = (FileChangeType.DELETED, path_obj, None, now)
                        return
                    if change_type == FileChangeType.MOVED:
                        self._pending[norm_key] = (FileChangeType.MOVED, path_obj, dest_obj, now)
                        return
                    # Modify + modify -> keep as MODIFIED with updated timestamp
                    self._pending[norm_key] = (FileChangeType.MODIFIED, path_obj, None, now)
                    return

                elif existing_type == FileChangeType.DELETED:
                    if change_type == FileChangeType.CREATED:
                        # Re-created
                        self._pending[norm_key] = (FileChangeType.MODIFIED, path_obj, None, now)
                        return

            self._pending[norm_key] = (change_type, path_obj, dest_obj, now)

    def _flusher_loop(self) -> None:
        """Background thread continually checking for settled events."""
        interval = min(0.1, self.debounce_seconds / 2.0)
        while not self._stop_event.is_set():
            self._flush_settled()
            self._stop_event.wait(timeout=interval)

    def _flush_settled(self) -> None:
        """Dispatch events that have had no new changes within the debounce window."""
        now = time.time()
        to_dispatch = []

        with self._lock:
            settled_keys = [
                key
                for key, (_, _, _, last_time) in self._pending.items()
                if (now - last_time) >= self.debounce_seconds
            ]
            for key in settled_keys:
                to_dispatch.append(self._pending.pop(key))

        for change_type, path_obj, dest_obj, ts in to_dispatch:
            try:
                self.on_event(
                    FileChangeEvent(
                        change_type=change_type,
                        path=path_obj,
                        dest_path=dest_obj,
                        timestamp=ts,
                    )
                )
            except Exception as exc:
                logger.error("Error dispatching debounced event for %s: %s", path_obj, exc, exc_info=True)

    def flush_all(self) -> None:
        """Immediately dispatch all pending events without waiting for debounce timeout."""
        with self._lock:
            all_items = list(self._pending.values())
            self._pending.clear()

        for change_type, path_obj, dest_obj, ts in all_items:
            try:
                self.on_event(
                    FileChangeEvent(
                        change_type=change_type,
                        path=path_obj,
                        dest_path=dest_obj,
                        timestamp=ts,
                    )
                )
            except Exception as exc:
                logger.error("Error during debouncer flush_all for %s: %s", path_obj, exc, exc_info=True)

    def stop(self) -> None:
        """Stop the background flusher thread."""
        self._stop_event.set()
        self.flush_all()
        if self._flusher_thread.is_alive():
            self._flusher_thread.join(timeout=2.0)

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

