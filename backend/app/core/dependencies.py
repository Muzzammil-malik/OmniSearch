"""Robust native dependency management and diagnostic detection."""

import logging
import platform
import sys
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def classify_native_error(exc: Exception) -> str:
    """Classify native dependency loading exception, detecting Windows Application Control / DLL failures.

    Returns one of:
        - 'application_control_policy_blocked': WinError 4551 / Code Integrity / Smart App Control block
        - 'native_dll_load_failed': WinError 126/127 or missing/broken shared library
        - 'not_installed': ModuleNotFoundError / ImportError
        - 'initialization_failed': generic initialization error
    """
    if hasattr(exc, "category") and getattr(exc, "category", None):
        return getattr(exc, "category")

    err_str = str(exc).lower()
    win_error = getattr(exc, "winerror", None)

    # WinError 4551: ERROR_APPLICATION_CONTROL_POLICY_BLOCK
    if (
        win_error == 4551
        or "4551" in err_str
        or "application control policy" in err_str
        or "error_application_control_policy_block" in err_str
        or "smart app control" in err_str
    ):
        return "application_control_policy_blocked"

    if (
        "shm.dll" in err_str
        or "cygrpc" in err_str
        or "dll load failed" in err_str
        or win_error in {126, 127}
    ):
        return "native_dll_load_failed"

    if isinstance(exc, (ModuleNotFoundError, ImportError)) and (
        "no module named" in err_str or "cannot import" in err_str
    ):
        return "not_installed"

    return "initialization_failed"


class NativeDependencyError(Exception):
    """Base exception for native library initialization failures."""

    def __init__(
        self,
        message: str,
        category: str = "initialization_failed",
        original_exception: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.original_exception = original_exception


class PyTorchDependencyError(NativeDependencyError):
    """Raised when native PyTorch dependency fails to initialize."""


class ChromaDependencyError(NativeDependencyError):
    """Raised when native ChromaDB / grpc dependency fails to initialize."""


class TorchDependencyManager:
    """Thread-safe singleton managing PyTorch import lifecycle, caching failures, and preserving root cause."""

    _instance: Optional["TorchDependencyManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._initialized = False
        self._is_available = False
        self._module: Optional[Any] = None
        self._original_exception: Optional[Exception] = None
        self._error_category: Optional[str] = None
        self._op_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> "TorchDependencyManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton for testing."""
        with cls._lock:
            cls._instance = None

    def is_available(self) -> bool:
        """Return True if PyTorch is confirmed available."""
        if not self._initialized:
            try:
                self.ensure_torch()
            except Exception:
                pass
        return self._is_available

    def get_original_exception(self) -> Optional[Exception]:
        return self._original_exception

    def get_error_category(self) -> Optional[str]:
        return self._error_category

    def get_version(self) -> Optional[str]:
        if self._is_available and self._module:
            return getattr(self._module, "__version__", None)
        return None

    def _import_torch(self) -> Any:
        import torch
        return torch

    def configure_threads(self, num_threads: int = 6) -> None:
        """Centralized PyTorch CPU thread configuration applied safely."""
        with self._op_lock:
            if not self._is_available or self._module is None:
                return
            try:
                self._module.set_num_threads(num_threads)
                logger.info("Configured PyTorch CPU intra-op threads: %d", num_threads)
            except Exception as exc:
                logger.warning("Could not set PyTorch thread count to %d: %s", num_threads, exc)

    def ensure_torch(self) -> Any:
        """Attempt native PyTorch initialization safely or re-raise cached original exception."""
        with self._op_lock:
            if self._initialized:
                if self._is_available and self._module is not None:
                    return self._module
                # Report cached root cause rather than secondary PyTorch initialization error
                raise PyTorchDependencyError(
                    f"PyTorch is unavailable ({self._error_category}): {self._original_exception}",
                    category=self._error_category or "initialization_failed",
                    original_exception=self._original_exception,
                ) from self._original_exception

            try:
                mod = self._import_torch()
                self._module = mod
                self._is_available = True
                self._initialized = True
                # Centralized thread tuning (6 threads benchmarked as optimal on 8-core CPU)
                try:
                    mod.set_num_threads(6)
                except Exception:
                    pass
                # Check and isolate SciPy capability if native binaries are blocked
                ScipyDependencyManager.get_instance().check_capability()
                return mod
            except Exception as exc:
                self._initialized = True
                self._is_available = False
                self._original_exception = exc
                self._error_category = classify_native_error(exc)
                logger.error(
                    "Native PyTorch dependency failed to load (category: %s): %s",
                    self._error_category,
                    exc,
                    exc_info=True,
                )
                raise PyTorchDependencyError(
                    f"PyTorch is unavailable ({self._error_category}): {exc}",
                    category=self._error_category,
                    original_exception=exc,
                ) from exc


class ScipyDependencyManager:
    """Thread-safe singleton managing optional SciPy import lifecycle and Windows Application Control compatibility."""

    _instance: Optional["ScipyDependencyManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._initialized = False
        self._is_available = False
        self._is_blocked = False
        self._original_exception: Optional[Exception] = None
        self._error_category: Optional[str] = None
        self._op_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> "ScipyDependencyManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    def is_available(self) -> bool:
        if not self._initialized:
            self.check_capability()
        return self._is_available

    def is_blocked(self) -> bool:
        if not self._initialized:
            self.check_capability()
        return self._is_blocked

    def get_error_category(self) -> Optional[str]:
        return self._error_category

    def get_original_exception(self) -> Optional[Exception]:
        return self._original_exception

    def _probe_scipy(self) -> Any:
        import scipy
        return scipy

    def check_capability(self) -> bool:
        """Probe SciPy availability and isolate native Windows Application Control blocks from transformers."""
        with self._op_lock:
            if self._initialized:
                return self._is_available

            try:
                import importlib.util
                spec = importlib.util.find_spec("scipy")
                if spec is None:
                    # Case B: SciPy not installed
                    self._initialized = True
                    self._is_available = False
                    self._is_blocked = False
                    return False

                # Package exists on disk: probe actual native import
                mod = self._probe_scipy()
                self._initialized = True
                self._is_available = True
                self._is_blocked = False
                return True
            except Exception as exc:
                # Case C: package directory exists on disk but native import failed/blocked
                self._initialized = True
                self._is_available = False
                self._original_exception = exc
                self._error_category = classify_native_error(exc)
                self._is_blocked = (self._error_category in ("application_control_policy_blocked", "native_dll_load_failed"))

                logger.info(
                    "SciPy package found but native loading failed (category: %s); isolating from transformers: %s",
                    self._error_category,
                    exc,
                )
                # Safely mask unimportable package from transformers
                sys.modules["scipy"] = None
                return False


class ChromaDependencyManager:
    """Thread-safe singleton managing ChromaDB / gRPC import lifecycle, caching failures, and preserving root cause."""

    _instance: Optional["ChromaDependencyManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._initialized = False
        self._is_available = False
        self._module: Optional[Any] = None
        self._original_exception: Optional[Exception] = None
        self._error_category: Optional[str] = None
        self._op_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> "ChromaDependencyManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton for testing."""
        with cls._lock:
            cls._instance = None

    def is_available(self) -> bool:
        """Return True if ChromaDB is confirmed available."""
        if not self._initialized:
            try:
                self.ensure_chromadb()
            except Exception:
                pass
        return self._is_available

    def get_original_exception(self) -> Optional[Exception]:
        return self._original_exception

    def get_error_category(self) -> Optional[str]:
        return self._error_category

    def get_version(self) -> Optional[str]:
        if self._is_available and self._module:
            return getattr(self._module, "__version__", None)
        return None

    def _import_chromadb(self) -> Any:
        import chromadb
        return chromadb

    def ensure_chromadb(self) -> Any:
        """Attempt native ChromaDB initialization safely or re-raise cached original exception."""
        with self._op_lock:
            if self._initialized:
                if self._is_available and self._module is not None:
                    return self._module
                raise ChromaDependencyError(
                    f"ChromaDB is unavailable ({self._error_category}): {self._original_exception}",
                    category=self._error_category or "initialization_failed",
                    original_exception=self._original_exception,
                ) from self._original_exception

            try:
                mod = self._import_chromadb()
                self._module = mod
                self._is_available = True
                self._initialized = True
                return mod
            except Exception as exc:
                self._initialized = True
                self._is_available = False
                self._original_exception = exc
                self._error_category = classify_native_error(exc)
                logger.error(
                    "Native ChromaDB dependency failed to load (category: %s): %s",
                    self._error_category,
                    exc,
                    exc_info=True,
                )
                raise ChromaDependencyError(
                    f"ChromaDB is unavailable ({self._error_category}): {exc}",
                    category=self._error_category,
                    original_exception=exc,
                ) from exc


def get_environment_diagnostics() -> Dict[str, Any]:
    """Gather read-only environment and native dependency diagnostic report."""
    torch_mgr = TorchDependencyManager.get_instance()
    chroma_mgr = ChromaDependencyManager.get_instance()

    torch_avail = torch_mgr.is_available()
    chroma_avail = chroma_mgr.is_available()

    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
        "system": platform.system(),
        "release": platform.release(),
        "pytorch": {
            "available": torch_avail,
            "version": torch_mgr.get_version(),
            "error_category": torch_mgr.get_error_category(),
            "error_message": str(torch_mgr.get_original_exception()) if torch_mgr.get_original_exception() else None,
        },
        "chromadb": {
            "available": chroma_avail,
            "version": chroma_mgr.get_version(),
            "error_category": chroma_mgr.get_error_category(),
            "error_message": str(chroma_mgr.get_original_exception()) if chroma_mgr.get_original_exception() else None,
        },
    }

