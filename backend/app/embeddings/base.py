"""Abstract base class interface for embedding generators."""

from abc import ABC, abstractmethod
from typing import List, Optional


class BaseEmbedder(ABC):
    """Abstract interface for local text and document embedding inference."""

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """Generate a normalized embedding vector for a user search query.

        Args:
            query: User search query text.

        Returns:
            L2-normalized float vector of length `dimension`.
        """

    @abstractmethod
    def embed_documents(
        self,
        documents: List[str],
        titles: Optional[List[Optional[str]]] = None,
    ) -> List[List[float]]:
        """Generate normalized embedding vectors for a batch of document chunks.

        Args:
            documents: List of chunk text contents.
            titles: Optional parallel list of document titles for structured task prompting.

        Returns:
            List of L2-normalized float vectors, each of length `dimension`.
        """

    def embed_image(self, image_path: str) -> List[float]:
        """Generate a normalized embedding vector for an image file.

        Args:
            image_path: Absolute path to the source image file.

        Returns:
            L2-normalized float vector of length `dimension`.
        """
        raise NotImplementedError

    def embed_audio(self, audio_path: str) -> List[float]:
        """Generate a normalized embedding vector for an audio file.

        Args:
            audio_path: Absolute path to the source audio file.

        Returns:
            L2-normalized float vector of length `dimension`.
        """
        raise NotImplementedError

    def embed_video(self, video_path: str) -> List[float]:
        """Generate a normalized embedding vector for a video file.

        Args:
            video_path: Absolute path to the source video file.

        Returns:
            L2-normalized float vector of length `dimension`.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector embedding dimension."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Return the model identifier."""

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Return True if model weights are currently resident in memory."""

    @abstractmethod
    def unload(self) -> None:
        """Unload model from memory and release resources."""

