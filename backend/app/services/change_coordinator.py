"""Change coordinator service managing a bounded queue and background processing of filesystem change events."""

from datetime import datetime, timezone
from pathlib import Path
import queue
from threading import Event, Lock, Thread
import time
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.services.indexer import IndexingService
from app.watcher.events import FileChangeEvent, FileChangeType

logger = get_logger(__name__)


class ChangeCoordinator:
    """Consumes debounced filesystem events from a bounded queue and routes to discrete indexing actions."""

    def __init__(
        self,
        indexing_service: IndexingService,
        max_queue_size: int = 1000,
    ) -> None:
        self.indexing_service = indexing_service
        self.max_queue_size = max_queue_size
        self._queue: queue.Queue[Optional[FileChangeEvent]] = queue.Queue(maxsize=max_queue_size)
        self._stop_event = Event()
        self._worker_thread: Optional[Thread] = None
        self._lock = Lock()

        # Metrics & status tracking
        self._is_running = False
        self._processed_count = 0
        self._error_count = 0
        self._current_file: Optional[str] = None
        self._last_event_time: Optional[float] = None
        self._last_error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def processed_count(self) -> int:
        with self._lock:
            return self._processed_count

    @property
    def error_count(self) -> int:
        with self._lock:
            return self._error_count

    @property
    def current_file(self) -> Optional[str]:
        with self._lock:
            return self._current_file

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of current coordinator status and activity metrics."""
        with self._lock:
            last_event_iso = (
                datetime.fromtimestamp(self._last_event_time, tz=timezone.utc).isoformat()
                if self._last_event_time
                else None
            )
            return {
                "is_running": self._is_running,
                "queue_size": self._queue.qsize(),
                "processed_count": self._processed_count,
                "error_count": self._error_count,
                "current_file": self._current_file,
                "last_event_time": last_event_iso,
                "last_error": self._last_error,
            }

    def start(self) -> None:
        """Start the background consumer worker thread."""
        with self._lock:
            if self._is_running:
                return
            self._stop_event.clear()
            self._is_running = True
            self._worker_thread = Thread(
                target=self._worker_loop,
                daemon=True,
                name="ChangeCoordinatorWorker",
            )
            self._worker_thread.start()
            logger.info("Change coordinator worker started")

    def stop(self, timeout: float = 3.0) -> None:
        """Signal worker to stop and wait for completion."""
        with self._lock:
            if not self._is_running:
                return
            self._is_running = False
            self._stop_event.set()

        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
            logger.info("Change coordinator worker stopped cleanly")

    def enqueue(self, event: FileChangeEvent) -> bool:
        """Enqueue an event for processing. Returns True if enqueued, False if dropped or full."""
        if not self._is_running:
            logger.warning("Change coordinator is not running; dropping event: %s", event)
            return False

        try:
            self._queue.put_nowait(event)
            return True
        except queue.Full:
            logger.error("Change coordinator queue full (capacity=%d); dropping event: %s", self.max_queue_size, event)
            with self._lock:
                self._error_count += 1
                self._last_error = f"Queue overflow (dropped event on {event.path})"
            return False

    def _worker_loop(self) -> None:
        """Dedicated background worker loop dispatching events to IndexingService with coalesced batching."""
        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if event is None or self._stop_event.is_set():
                break

            # Collect a batch of immediately pending events from the queue (up to 16)
            batch = [event]
            while len(batch) < 16:
                try:
                    next_ev = self._queue.get_nowait()
                    if next_ev is None:
                        self._stop_event.set()
                        break
                    batch.append(next_ev)
                except queue.Empty:
                    break

            any_embeddings_needed = False
            for current_ev in batch:
                filename = current_ev.path.name
                with self._lock:
                    self._current_file = filename
                    self._last_event_time = time.time()

                try:
                    needs_sync = self._process_event(current_ev, generate_embeddings=False)
                    if needs_sync:
                        any_embeddings_needed = True
                    with self._lock:
                        self._processed_count += 1
                except Exception as exc:
                    logger.error(
                        "Unexpected error processing change event on '%s': %s",
                        current_ev.path,
                        exc,
                        exc_info=True,
                    )
                    with self._lock:
                        self._error_count += 1
                        self._last_error = str(exc)
                finally:
                    with self._lock:
                        self._current_file = None
                    self._queue.task_done()

            # Coalesced embedding generation across all files processed in this batch
            if any_embeddings_needed and getattr(self.indexing_service, "semantic_pipeline", None):
                try:
                    self.indexing_service.semantic_pipeline.sync_embeddings()
                except Exception as exc:
                    logger.error("Error generating coalesced embeddings in coordinator: %s", exc)

    def _process_event(self, event: FileChangeEvent, generate_embeddings: bool = True) -> bool:
        """Route an event to the appropriate single-file indexing operation. Returns True if embeddings may be needed."""
        path = event.path
        change_type = event.change_type

        logger.info("Processing change event [%s]: %s", change_type.name, path)

        if change_type in (FileChangeType.CREATED, FileChangeType.MODIFIED):
            # If the file was deleted before we got around to processing it, delete instead
            if not path.exists():
                logger.debug("File '%s' does not exist at processing time; treating as DELETED", path.name)
                self.indexing_service.delete_single_file(path)
                return False

            rec = self.indexing_service.index_single_file(
                file_path=path,
                force_reindex=False,
                generate_embeddings=generate_embeddings,
            )
            return rec is not None

        elif change_type == FileChangeType.DELETED:
            self.indexing_service.delete_single_file(path)
            return False

        elif change_type == FileChangeType.MOVED:
            if event.dest_path is not None:
                self.indexing_service.move_single_file(old_path=path, new_path=event.dest_path)
            else:
                self.indexing_service.delete_single_file(path)
            return False
        return False

