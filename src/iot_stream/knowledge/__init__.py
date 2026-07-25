"""Source-backed incident knowledge base and retrieval contracts."""

from iot_stream.knowledge.chroma_store import ChromaIncidentStore
from iot_stream.knowledge.litellm_embeddings import LiteLLMEmbeddingClient
from iot_stream.knowledge.models import RetrievalMatch, RetrievalQuery
from iot_stream.knowledge.retriever import IncidentRetriever
from iot_stream.knowledge.service import build_incident_retriever, build_knowledge_store

__all__ = [
    "ChromaIncidentStore",
    "IncidentRetriever",
    "LiteLLMEmbeddingClient",
    "RetrievalMatch",
    "RetrievalQuery",
    "build_incident_retriever",
    "build_knowledge_store",
]
