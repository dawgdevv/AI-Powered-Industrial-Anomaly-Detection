"""CLI for building the local Chroma incident index."""

from __future__ import annotations

import argparse

from iot_stream.knowledge.litellm_embeddings import (
    LiteLLMEmbeddingClient,
    LiteLLMEmbeddingSettings,
)
from iot_stream.knowledge.service import build_knowledge_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Index source-backed industrial incidents in Chroma")
    parser.add_argument("--reset", action="store_true", help="Rebuild the collection from the JSON corpus")
    args = parser.parse_args()

    store = build_knowledge_store()
    if args.reset:
        store.reset()
    embeddings = LiteLLMEmbeddingClient(LiteLLMEmbeddingSettings.from_env())
    indexed = store.index_corpus(embeddings)
    print(f"Indexed {indexed} sensor-specific incident documents; collection now has {store.count()} documents.")


if __name__ == "__main__":
    main()
