import json
import tempfile
import unittest
from pathlib import Path

from iot_stream.knowledge.chroma_store import CORPUS_PATH, ChromaIncidentStore
from iot_stream.knowledge.models import RetrievalQuery
from iot_stream.knowledge.retriever import IncidentRetriever
from iot_stream.incidents.models import Incident, IncidentCategory, IncidentState


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
            "ids": [["WT-INC-001:vibration"]],
            "documents": [["water-treatment intake pump scenario"]],
            "metadatas": [[{"incident_id": "WT-INC-001", "verified": True}]],
            "distances": [[0.2]],
        }

    def get(self, **_kwargs):
        return {"ids": [], "documents": [], "metadatas": []}


class KnowledgeBaseTests(unittest.TestCase):
    def test_corpus_has_one_scenario_for_each_water_treatment_asset(self):
        records = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(records), 6)
        self.assertTrue(all(record["source_kind"] == "water_treatment_simulation" for record in records))
        self.assertEqual(
            {record["equipment_type"] for record in records},
            {"centrifugal_pump", "aeration_blower", "flash_mixer", "decanter_centrifuge", "metering_pump", "screw_conveyor"},
        )

    def test_indexer_persists_sensor_specific_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ChromaIncidentStore(Path(directory))
            indexed = store.index_corpus(FixedEmbeddings())
            self.assertEqual(indexed, store.count())
            self.assertEqual(indexed, 11)

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
        self.assertEqual(matches[0].incident_id, "WT-INC-001")
        self.assertEqual(
            collection.where["$and"],
            [
                {"equipment_type": "centrifugal_pump"},
                {"sensor_type": "vibration"},
                {"incident_category": "EQUIPMENT_CONDITION"},
            ],
        )

    def test_confirmed_operator_report_becomes_labelled_local_knowledge(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ChromaIncidentStore(Path(directory))
            incident = Incident(
                incident_id="INC-000001", device_id="sensor-1",
                category=IncidentCategory.EQUIPMENT_CONDITION,
                state=IncidentState.RESOLVED, first_seen=1, last_seen=2,
                detectors={"spike"},
            )
            store.upsert_operator_report(
                incident, "Replaced the worn bearing and vibration returned to normal.",
                "centrifugal_pump", "vibration", FixedEmbeddings(),
            )
            report = store.collection.get(ids=["operator-report:INC-000001"], include=["metadatas"])
            self.assertEqual(report["metadatas"][0]["source_kind"], "operator_report")
            self.assertFalse(report["metadatas"][0]["verified"])

if __name__ == "__main__":
    unittest.main()
