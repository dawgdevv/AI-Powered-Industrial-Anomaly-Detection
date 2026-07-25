# Incident Knowledge Base

This directory contains a 20-record, source-backed retrieval corpus for the industrial diagnosis agent.

## Provenance rules

- Every record is based on a publicly accessible source and carries its source URL.
- `source_kind` distinguishes field incidents, public maintenance cases, and experimental run-to-failure records.
- `verified` means the source is a government, public-sector, peer-reviewed, or named industrial case source—not that the project independently validated the event.
- Numeric readings are omitted unless the source states them. The agent must not invent measurements, thresholds, or maintenance history.
- `derived_operational_next_step` is a conservative project interpretation for the demo; it is not presented as a source-authorized maintenance procedure.

## Data shape

`incidents.json` is an array of records with:

- identity and provenance: `incident_id`, `source_kind`, `verified`, `source`;
- retrieval filters: `equipment_type`, `sensor_types`, `incident_category`, `pattern_type`;
- evidence: `observed_indicators`, `confirmed_or_reported_cause`, `outcome_or_resolution`;
- agent-safe retrieval text: `retrieval_text` and `derived_operational_next_step`.

## Retrieval constraints

Filter by `equipment_type`, `sensor_types`, and `incident_category` before semantic search. Do not use experimental records as a direct basis for a field recommendation without an explicit `source_kind` warning.

## Inference boundary

`retriever.py` is intentionally dependency-free. It expects:

1. a configured Chroma collection whose document ID is `incident_id`;
2. scalar metadata fields named `equipment_type`, `sensor_type`, and `incident_category`;
3. one indexed document per applicable sensor type (duplicate a multi-sensor incident at indexing time);
4. an embedding client that implements `embed_query(text) -> list[float]`.

The inference layer returns Chroma's raw distance. Confidence calibration belongs in the application policy because distance values are specific to the selected embedding model and collection configuration.

## Runbook

1. Copy `.env.example` to `.env` and configure the LiteLLM gateway values.
2. Install the gateway with `uv tool install 'litellm[proxy]'`. Copy `litellm-config.yaml.example` to `litellm-config.yaml`, export `MISTRAL_API_KEY` and `LITELLM_MASTER_KEY`, then start LiteLLM with a Mistral embedding-model route matching `LITELLM_EMBEDDING_MODEL`.
3. Build or rebuild the local index:

   ```bash
   PYTHONPATH=src uv run python -m iot_stream.knowledge.indexer --reset
   ```

4. Verify the local collection without calling a model:

   ```bash
   uv run uvicorn --app-dir src iot_stream.api.main:app --reload
   curl http://127.0.0.1:8000/api/knowledge/health
   ```

5. Call `POST /api/knowledge/search` with `text`, `equipment_type`, `sensor_type`, and `incident_category` to run a filter-first semantic search.
