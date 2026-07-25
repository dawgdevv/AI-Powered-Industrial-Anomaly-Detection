"""One bounded Mistral explanation call with a deterministic fallback."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from iot_stream.agent.prompt import build_messages
from iot_stream.agent.state import AgentAssessment


class MistralExplanationClient:
    def __init__(self, api_base: str, api_key: str, model: str, timeout_seconds: float = 8):
        self.api_base, self.api_key, self.model, self.timeout_seconds = api_base.rstrip("/"), api_key, model, timeout_seconds

    @classmethod
    def from_env(cls) -> "MistralExplanationClient | None":
        model = os.getenv("LITELLM_CHAT_MODEL")
        key = os.getenv("LITELLM_API_KEY")
        if not model or not key:
            return None
        return cls(
            os.getenv("LITELLM_API_BASE", "http://127.0.0.1:4000/v1"),
            key,
            model,
            float(os.getenv("LITELLM_AGENT_TIMEOUT_SECONDS", "8")),
        )

    def explain(self, incident_id: str, tool_results: dict[str, object]) -> AgentAssessment:
        response = httpx.post(
            f"{self.api_base}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": build_messages(tool_results),
                "temperature": 0,
                "max_tokens": 220,
                "response_format": {"type": "json_object"},
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        try:
            content = response.json()["choices"][0]["message"]["content"]
            value: dict[str, Any] = json.loads(content)
            cited = value.get("cited_incident_ids", [])
            if not isinstance(cited, list) or not all(isinstance(item, str) for item in cited):
                raise ValueError("invalid cited incident IDs")
            precedents = tool_results["get_retrieved_precedents"]["precedents"]
            allowed_ids = {str(item.get("incident_id")) for item in precedents}
            verified_ids = {str(item.get("incident_id")) for item in precedents if item.get("verified") is True}
            if not set(cited).issubset(allowed_ids):
                raise ValueError("model cited an incident it was not given")
            if not verified_ids and not bool(value.get("abstained")):
                raise ValueError("model attempted a diagnosis without verified evidence")
            return AgentAssessment(
                incident_id=incident_id,
                title=str(value["title"]), explanation=str(value["explanation"]), operator_action=str(value["operator_action"]),
                likely_fault=str(value["likely_fault"]) if value.get("likely_fault") else None,
                cited_incident_ids=cited, abstained=bool(value["abstained"]),
                abstention_reason=str(value["abstention_reason"]) if value.get("abstention_reason") else None,
                model=self.model, model_fallback=False,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError("Mistral returned an invalid structured assessment") from error


def deterministic_assessment(incident_id: str, tool_results: dict[str, object]) -> AgentAssessment:
    incident = tool_results["get_incident_context"]
    precedents = tool_results["get_retrieved_precedents"]["precedents"]
    verified = next((item for item in precedents if item.get("verified") is True), None)
    if verified:
        fault = str(verified.get("fault_family") or "equipment condition").replace("_", " ")
        return AgentAssessment(incident_id, f"Likely {fault}", "The sensor pattern matches detector evidence and a verified historical precedent.", "Inspect the equipment at the next safe opportunity; use the cited case as investigation context.", fault, [str(verified["incident_id"])], False, None, None, True)
    return AgentAssessment(incident_id, "Unusual equipment pattern needs inspection", "The agent found an abnormal reading pattern but no verified precedent strong enough to name a fault safely.", "Keep monitoring and have maintenance inspect the equipment if the condition persists.", None, [], True, "no_verified_precedent", None, True)
