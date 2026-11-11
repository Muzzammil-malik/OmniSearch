"""CLI diagnostic utility to inspect native dependencies and runtime environment for OmniSearch."""

import argparse
import json
import os
from pathlib import Path
import sys

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.core.dependencies import (
    ChromaDependencyManager,
    TorchDependencyManager,
    get_environment_diagnostics,
)
from app.vector_store.chroma import ChromaVectorStore


def run_diagnostics(as_json: bool = False) -> None:
    settings = get_settings()
    diag = get_environment_diagnostics()

    # Model file availability
    local_model_path = Path(os.path.expandvars(r"%LOCALAPPDATA%\OmniSearch\models\embeddinggemma-2"))
    weights_file = local_model_path / "model.safetensors"
    model_exists = local_model_path.exists() and weights_file.exists()

    diag["embedding_model"] = {
        "model_id": settings.resolved_embedding_model,
        "local_path": str(local_model_path),
        "weights_present": model_exists,
    }

    # Vector store status
    vs = ChromaVectorStore(persist_dir=settings.vectors_dir)
    diag["vector_store"] = {
        "persist_dir": str(settings.vectors_dir),
        "is_available": vs.is_available(),
    }
    if vs.is_available():
        try:
            diag["vector_store"]["total_vectors"] = vs.count()
        except Exception as exc:
            diag["vector_store"]["total_vectors"] = None
            diag["vector_store"]["count_error"] = str(exc)

    if as_json:
        print(json.dumps(diag, indent=2, default=str))
        return

    print("=" * 70)
    print(" OmniSearch — System & Native Dependency Diagnostic Report")
    print("=" * 70)
    print(f" Python Version : {sys.version.split()[0]} ({diag['architecture']})")
    print(f" Platform       : {diag['platform']}")
    print(f" OS System      : {diag['system']} {diag['release']}")
    print("-" * 70)

    # PyTorch
    torch_info = diag["pytorch"]
    print(f" PyTorch Available       : {torch_info['available']}")
    if torch_info["available"]:
        print(f" PyTorch Version         : {torch_info['version']}")
    else:
        print(f" PyTorch Failure Category: {torch_info['error_category']}")
        print(f" PyTorch Error           : {torch_info['error_message']}")

    print("-" * 70)

    # ChromaDB
    chroma_info = diag["chromadb"]
    vs_info = diag["vector_store"]
    print(f" ChromaDB Available       : {chroma_info['available']}")
    if chroma_info["available"]:
        print(f" ChromaDB Version         : {chroma_info['version']}")
        print(f" Vectors Directory        : {vs_info.get('persist_dir')}")
        print(f" Total Vectors Indexed    : {vs_info.get('total_vectors')}")
    else:
        print(f" ChromaDB Failure Category: {chroma_info['error_category']}")
        print(f" ChromaDB Error           : {chroma_info['error_message']}")

    print("-" * 70)

    # Embedding Model
    model_info = diag["embedding_model"]
    print(f" EmbeddingGemma Model ID : {model_info['model_id']}")
    print(f" Local Weights Present   : {model_info['weights_present']}")
    print(f" Local Weights Path      : {model_info['local_path']}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="OmniSearch Native Dependency Diagnostics")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()
    run_diagnostics(as_json=args.json)


if __name__ == "__main__":
    main()

