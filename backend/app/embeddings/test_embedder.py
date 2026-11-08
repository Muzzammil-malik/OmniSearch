"""Deterministic test embedder for reproducible, fast, and offline testing."""

import hashlib
import math
from pathlib import Path
from typing import List, Optional
from app.embeddings.base import BaseEmbedder
from app.embeddings.prompts import format_document_prompt, format_query_prompt


class DeterministicTestEmbedder(BaseEmbedder):
    """Generates deterministic, L2-normalized pseudo-embeddings for automated testing without downloading large model weights."""

    def __init__(
        self,
        dimension: int = 768,
        model_id: str = "google/embeddinggemma-2-test",
    ) -> None:
        self._dimension = dimension
        self._model_id = model_id
        self._is_loaded = True

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def unload(self) -> None:
        self._is_loaded = False

    def embed_query(self, query: str) -> List[float]:
        formatted = format_query_prompt(query)
        return self._generate_vector(formatted)

    def embed_documents(
        self,
        documents: List[str],
        titles: Optional[List[Optional[str]]] = None,
    ) -> List[List[float]]:
        if not documents:
            return []
        titles_list = titles or [None] * len(documents)
        embeddings: List[List[float]] = []
        for doc, title in zip(documents, titles_list):
            formatted = format_document_prompt(doc, title=title)
            embeddings.append(self._generate_vector(formatted))
        return embeddings

    def embed_image(self, image_path: str) -> List[float]:
        p = Path(image_path)
        tag = f"image: {p.stem} {p.suffix.lower()}"
        return self._generate_vector(tag)

    def embed_audio(self, audio_path: str) -> List[float]:
        p = Path(audio_path)
        tag = f"audio: {p.stem} {p.suffix.lower()}"
        return self._generate_vector(tag)

    def embed_video(self, video_path: str) -> List[float]:
        p = Path(video_path)
        tag = f"video: {p.stem} {p.suffix.lower()}"
        return self._generate_vector(tag)

    def _generate_vector(self, text: str) -> List[float]:
        """Generate a deterministic pseudo-semantic vector using word hash seeds and L2 normalization."""
        words = text.lower().split()
        vector = [0.0] * self._dimension

        # Combine word hashes so semantically overlapping texts share vector components
        for word in words:
            seed = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
            for d in range(self._dimension):
                # Pseudo-random float in [-1, 1] derived from word hash and dimension index
                h = (seed ^ (d * 0x9E3779B9)) & 0xFFFFFFFF
                val = (h / 0xFFFFFFFF) * 2.0 - 1.0
                vector[d] += val

        # If empty text or zero vector, generate constant non-zero seed
        norm_sq = sum(v * v for v in vector)
        if norm_sq < 1e-9:
            vector = [1.0 / math.sqrt(self._dimension)] * self._dimension
            return vector

        # L2-normalize vector to unit length
        norm = math.sqrt(norm_sq)
        return [v / norm for v in vector]

