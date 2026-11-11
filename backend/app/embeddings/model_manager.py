"""Model manager for loading, caching, and releasing embedding models."""

import gc
import logging
import threading
from typing import Optional, Tuple, Any

from app.core.dependencies import TorchDependencyManager, NativeDependencyError
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.exceptions import ModelLoadError, ModelNotFoundError

logger = logging.getLogger(__name__)


class EmbeddingModelManager:
    """Singleton/managed model cache for local embedding models."""

    _instance: Optional["EmbeddingModelManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._tokenizer: Optional[Any] = None
        self._model: Optional[Any] = None
        self._st_model: Optional[Any] = None
        self._st_model_id: Optional[str] = None
        self._loaded_model_id: Optional[str] = None
        self._loaded_device: Optional[str] = None
        self._op_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "EmbeddingModelManager":
        """Get or create the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @property
    def is_loaded(self) -> bool:
        """Check if model and tokenizer are currently resident in memory."""
        return (self._model is not None and self._tokenizer is not None) or self._st_model is not None

    def get_sentence_transformer(self, config: EmbeddingConfig) -> Any:
        """Lazy-load and return a SentenceTransformer multimodal model instance."""
        with self._op_lock:
            if self._st_model is not None and self._st_model_id == config.model_id:
                return self._st_model

            try:
                torch = TorchDependencyManager.get_instance().ensure_torch()
                from sentence_transformers import SentenceTransformer
            except NativeDependencyError as e:
                raise ModelLoadError(f"PyTorch native dependency failed ({e.category}): {e.original_exception}") from e
            except ImportError as e:
                raise ModelLoadError(f"Required library sentence_transformers is not installed: {e}") from e

            config.validate_dimension()
            torch_dtype = torch.bfloat16 if config.precision == "bfloat16" else torch.float32
            logger.info("Loading SentenceTransformer model %s (device=%s, dtype=%s)...", config.model_id, config.device, torch_dtype)
            try:
                st_model = SentenceTransformer(
                    config.model_id,
                    device=config.device,
                    model_kwargs={"dtype": torch_dtype},
                    local_files_only=getattr(config, "local_files_only", False),
                    truncate_dim=config.dimension if config.dimension < 768 else None,
                )
                self._st_model = st_model
                self._st_model_id = config.model_id
                logger.info("Successfully loaded SentenceTransformer model %s.", config.model_id)
                return self._st_model
            except Exception as e:
                err_msg = str(e).lower()
                if (
                    "not found" in err_msg
                    or "repository" in err_msg
                    or "cannot find" in err_msg
                    or "couldn't find" in err_msg
                    or "local_files_only" in err_msg
                ):
                    raise ModelNotFoundError(f"Embedding model not found for '{config.model_id}': {e}") from e
                raise ModelLoadError(f"Failed loading SentenceTransformer model '{config.model_id}': {e}") from e

    def get_model_and_tokenizer(
        self, config: EmbeddingConfig
    ) -> Tuple[Any, Any]:
        """Lazy-load and return (tokenizer, model) based on config.

        Raises:
            ModelNotFoundError: If local files or repository cannot be found.
            ModelLoadError: If loading model weights fails.
        """
        with self._op_lock:
            if (
                self.is_loaded
                and self._loaded_model_id == config.model_id
                and self._loaded_device == config.device
            ):
                return self._tokenizer, self._model

            # Need to load or reload model
            try:
                torch = TorchDependencyManager.get_instance().ensure_torch()
                from transformers import AutoModel, AutoTokenizer
            except NativeDependencyError as e:
                raise ModelLoadError(f"PyTorch native dependency failed ({e.category}): {e.original_exception}") from e
            except ImportError as e:
                raise ModelLoadError(
                    f"Required libraries (torch, transformers) are not installed: {e}"
                ) from e

            config.validate_dimension()

            logger.info("Loading embedding model %s on %s...", config.model_id, config.device)
            local_only = getattr(config, "local_files_only", False)
            try:
                tokenizer = AutoTokenizer.from_pretrained(
                    config.model_id,
                    cache_dir=str(config.cache_dir) if config.cache_dir else None,
                    local_files_only=local_only,
                )
            except Exception as e:
                err_msg = str(e).lower()
                if (
                    "not found" in err_msg
                    or "repository" in err_msg
                    or "entry not found" in err_msg
                    or "cannot find" in err_msg
                    or "couldn't find" in err_msg
                    or "local_files_only" in err_msg
                ):
                    raise ModelNotFoundError(
                        f"Embedding model repository or weights not found for '{config.model_id}': {e}"
                    ) from e
                raise ModelLoadError(
                    f"Failed to load tokenizer for '{config.model_id}': {e}"
                ) from e

            try:
                torch_dtype = torch.bfloat16 if config.precision == "bfloat16" else torch.float32
                model = AutoModel.from_pretrained(
                    config.model_id,
                    torch_dtype=torch_dtype,
                    cache_dir=str(config.cache_dir) if config.cache_dir else None,
                    local_files_only=local_only,
                )
                device = torch.device(config.device)
                model.to(device)
                model.eval()
            except Exception as e:
                err_msg = str(e).lower()
                if (
                    "not found" in err_msg
                    or "repository" in err_msg
                    or "cannot find" in err_msg
                    or "couldn't find" in err_msg
                    or "local_files_only" in err_msg
                ):
                    raise ModelNotFoundError(
                        f"Embedding model weights not found for '{config.model_id}': {e}"
                    ) from e
                raise ModelLoadError(
                    f"Failed to load model weights for '{config.model_id}': {e}"
                ) from e

            self._tokenizer = tokenizer
            self._model = model
            self._loaded_model_id = config.model_id
            self._loaded_device = config.device
            logger.info("Successfully loaded embedding model %s.", config.model_id)

            return self._tokenizer, self._model

    def unload(self) -> None:
        """Unload model and tokenizer from memory and trigger garbage collection."""
        with self._op_lock:
            if self._model is not None or self._tokenizer is not None or self._st_model is not None:
                logger.info("Unloading embedding model from memory.")
                self._model = None
                self._tokenizer = None
                self._st_model = None
                self._st_model_id = None
                self._loaded_model_id = None
                self._loaded_device = None
                gc.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
