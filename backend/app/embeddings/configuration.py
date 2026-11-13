"""Configuration settings for local embedding generation."""

from pathlib import Path
from typing import Optional, Set
from pydantic import BaseModel, Field


class EmbeddingConfig(BaseModel):
    """Runtime configuration for local EmbeddingGemma 2 inference."""

    model_id: str = Field(
        default="google/embeddinggemma-2",
        description="HuggingFace model repository identifier for Google EmbeddingGemma 2.",
    )
    dimension: int = Field(
        default=768,
        description="Embedding vector dimension. EmbeddingGemma 2 natively outputs 768 dimensions and supports MRL truncation.",
    )
    batch_size: int = Field(
        default=16,
        ge=1,
        le=128,
        description="Batch size for generating document chunk embeddings on CPU.",
    )
    fetch_pool_size: int = Field(
        default=128,
        ge=16,
        le=1024,
        description="Number of candidate chunks fetched from SQLite per cycle before length-aware grouping and batch slicing.",
    )
    device: str = Field(
        default="cpu",
        description="Inference device ('cpu' or 'cuda' if hardware acceleration is available).",
    )
    precision: str = Field(
        default="float32",
        description="Float precision for inference ('float32' or 'bfloat16').",
    )
    cache_dir: Optional[Path] = Field(
        default=None,
        description="Local directory for caching downloaded model weights.",
    )
    local_files_only: bool = Field(
        default=False,
        description="Whether to only load from local cache without contacting external repository.",
    )
    max_sequence_length: int = Field(
        default=512,
        ge=64,
        le=2048,
        description="Maximum sequence token length for chunk truncation.",
    )

    VALID_DIMENSIONS: Set[int] = {768, 512, 256, 128}

    def validate_dimension(self) -> None:
        """Validate that the configured dimension is a recognized Matryoshka dimension."""
        if self.dimension not in self.VALID_DIMENSIONS:
            raise ValueError(
                f"Invalid embedding dimension {self.dimension}. "
                f"EmbeddingGemma 2 supports MRL dimensions: {sorted(self.VALID_DIMENSIONS)}"
            )

