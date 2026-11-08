"""Production local embedder implementation using Google EmbeddingGemma 2."""

import logging
from typing import List, Optional

from app.embeddings.base import BaseEmbedder
from app.embeddings.configuration import EmbeddingConfig
from app.embeddings.exceptions import (
    DimensionMismatchError,
    InferenceError,
)
from app.embeddings.model_manager import EmbeddingModelManager
from app.embeddings.prompts import format_document_prompt, format_query_prompt

logger = logging.getLogger(__name__)


class EmbeddingGemmaEmbedder(BaseEmbedder):
    """Local embedding generator using EmbeddingGemma 2 and PyTorch/Transformers."""

    def __init__(
        self,
        config: Optional[EmbeddingConfig] = None,
        model_manager: Optional[EmbeddingModelManager] = None,
    ) -> None:
        self.config = config or EmbeddingConfig()
        self.config.validate_dimension()
        self.manager = model_manager or EmbeddingModelManager.get_instance()

    @property
    def dimension(self) -> int:
        return self.config.dimension

    @property
    def model_id(self) -> str:
        return self.config.model_id

    @property
    def is_loaded(self) -> bool:
        return self.manager.is_loaded

    def unload(self) -> None:
        self.manager.unload()

    def embed_query(self, query: str) -> List[float]:
        """Generate a normalized embedding vector for a user search query."""
        formatted_prompt = format_query_prompt(query)
        embeddings = self._generate_embeddings([formatted_prompt])
        return embeddings[0]

    def embed_documents(
        self,
        documents: List[str],
        titles: Optional[List[Optional[str]]] = None,
    ) -> List[List[float]]:
        """Generate normalized embedding vectors for a batch of document chunks."""
        if not documents:
            return []

        formatted_prompts: List[str] = []
        for i, text in enumerate(documents):
            title = titles[i] if titles and i < len(titles) else None
            formatted_prompts.append(format_document_prompt(text, title))

        return self._generate_embeddings(formatted_prompts)

    def _to_normalized_vector(self, raw_embedding: Any) -> List[float]:
        """Convert raw numpy or tensor model output to normalized 1D float list."""
        import numpy as np
        arr = np.asarray(raw_embedding, dtype=np.float32)
        if arr.ndim == 2:
            arr = arr[0]
        elif arr.ndim > 2:
            arr = arr.reshape(-1)

        # MRL truncation
        if self.config.dimension < arr.shape[0]:
            arr = arr[: self.config.dimension]

        norm = float(np.linalg.norm(arr))
        if norm > 1e-9:
            arr = arr / norm
        return arr.tolist()

    def embed_image(self, image_path: str) -> List[float]:
        """Generate a 768-D normalized embedding vector for an image file."""
        from pathlib import Path
        from PIL import Image
        path = Path(image_path).resolve()
        if not path.is_file():
            raise InferenceError(f"Image file does not exist: {path}")

        try:
            model = self.manager.get_sentence_transformer(self.config)
            with Image.open(path) as img:
                img_rgb = img.convert("RGB")
                if max(img_rgb.size) > 768:
                    img_rgb.thumbnail((768, 768), Image.Resampling.LANCZOS)
                embeddings = model.encode({"image": [img_rgb]}, normalize_embeddings=True)
                return self._to_normalized_vector(embeddings)
        except Exception as e:
            raise InferenceError(f"Image embedding inference failed for {path.name}: {e}") from e

    def embed_audio(self, audio_path: str) -> List[float]:
        """Generate a 768-D normalized embedding vector for an audio file."""
        from pathlib import Path
        path = Path(audio_path).resolve()
        if not path.is_file():
            raise InferenceError(f"Audio file does not exist: {path}")

        try:
            model = self.manager.get_sentence_transformer(self.config)
            embeddings = model.encode({"audio": [str(path)]}, normalize_embeddings=True)
            return self._to_normalized_vector(embeddings)
        except Exception as e:
            raise InferenceError(f"Audio embedding inference failed for {path.name}: {e}") from e

    def embed_video(self, video_path: str) -> List[float]:
        """Generate a 768-D normalized embedding vector for a video file."""
        from pathlib import Path
        from app.ingestion.extractors.video import sample_video_frames
        path = Path(video_path).resolve()
        if not path.is_file():
            raise InferenceError(f"Video file does not exist: {path}")

        try:
            frames = sample_video_frames(path, max_frames=16)
            if not frames:
                raise InferenceError(f"No decodable frames in video file: {path.name}")

            model = self.manager.get_sentence_transformer(self.config)
            embeddings = model.encode({"video": [frames]}, normalize_embeddings=True)
            return self._to_normalized_vector(embeddings)
        except Exception as e:
            raise InferenceError(f"Video embedding inference failed for {path.name}: {e}") from e

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Batch-process formatted text prompts through the model and mean pool."""
        if not texts:
            return []

        try:
            import torch
        except ImportError as e:
            raise InferenceError(f"PyTorch is required for embedding inference: {e}") from e

        tokenizer, model = self.manager.get_model_and_tokenizer(self.config)
        device = torch.device(self.config.device)
        batch_size = self.config.batch_size
        results: List[List[float]] = []

        try:
            for start_idx in range(0, len(texts), batch_size):
                batch_texts = texts[start_idx : start_idx + batch_size]

                encoded = tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=self.config.max_sequence_length,
                    return_tensors="pt",
                )
                encoded = {k: v.to(device) for k, v in encoded.items()}

                with torch.no_grad():
                    outputs = model(**encoded)
                    # Last hidden state: (batch_size, seq_len, hidden_dim)
                    last_hidden = outputs.last_hidden_state
                    attention_mask = encoded["attention_mask"].unsqueeze(-1)  # (batch_size, seq_len, 1)

                    # Attention-weighted mean pooling
                    sum_embeddings = torch.sum(last_hidden * attention_mask, dim=1)
                    sum_mask = torch.clamp(attention_mask.sum(dim=1), min=1e-9)
                    pooled = sum_embeddings / sum_mask

                    # Matryoshka dimension truncation if configured dimension < native dimension
                    if self.config.dimension < pooled.shape[-1]:
                        pooled = pooled[:, : self.config.dimension]
                    elif self.config.dimension > pooled.shape[-1]:
                        raise DimensionMismatchError(
                            f"Model output dimension ({pooled.shape[-1]}) is smaller than "
                            f"configured target dimension ({self.config.dimension})."
                        )

                    # L2 Normalization
                    normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
                    batch_results = normalized.cpu().tolist()
                    results.extend(batch_results)

            return results
        except Exception as e:
            if isinstance(e, DimensionMismatchError):
                raise
            raise InferenceError(f"Inference computation failed: {e}") from e

