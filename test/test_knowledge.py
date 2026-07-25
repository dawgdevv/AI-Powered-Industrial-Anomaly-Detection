import json
import tempfile
import unittest
from pathlib import Path

from iot_stream.knowledge.chroma_store import CORPUS_PATH, ChromaIncidentStore
from iot_stream.knowledge.models import RetrievalQuery
from iot_stream.knowledge.retriever import IncidentRetriever


class FixedEmbeddings:
    def embed_documents(self, texts):
        return [[float(index + 1), 0.5, 0.25] for index, _ in enumerate(texts)]

    def embed_query(self, _text):
        return [1.0, 0.5, 0.25]


class RecordingCollection:
    def __init__(self):
        self.where = None

    def query(self, **kwargs):
        self.where = kwargs["where"]
        return {
            "ids": [["KB-INC-0001:vibration"]],
            "documents": [["source-backed pump incident"]],
            "metadatas": [[{"incident_id": "KB-INC-0001", "verified": True}]],
            "distances": [[0.2]],
        }

    def get(self, **_kwargs):
        return {"ids": [], "documents": [], "metadatas": []}


class KnowledgeBaseTests(unittest.TestCase):
    def test_corpus_has_twenty_source_backed_records(self):
        records = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(records), 20)
        self.assertTrue(all(record["verified"] and record["source"]["url"] for record in records))
        self.assertIn("DATA_QUALITY", {record["incident_category"] for record in records})

    def test_indexer_persists_sensor_specific_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ChromaIncidentStore(Path(directory))
            indexed = store.index_corpus(FixedEmbeddings())
            self.assertEqual(indexed, store.count())
            self.assertGreater(indexed, 20)

    def test_retriever_enforces_metadata_filters(self):
        collection = RecordingCollection()
        matches = IncidentRetriever(collection, FixedEmbeddings()).search(
            RetrievalQuery(
                "rising vibration on a pump",
                "centrifugal_pump",
                "vibration",
                "EQUIPMENT_CONDITION",
            )
        )
        self.assertEqual(matches[0].incident_id, "KB-INC-0001")
        self.assertEqual(
            collection.where["$and"],
            [
                {"equipment_type": "centrifugal_pump"},
                {"sensor_type": "vibration"},
                {"incident_category": "EQUIPMENT_CONDITION"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
