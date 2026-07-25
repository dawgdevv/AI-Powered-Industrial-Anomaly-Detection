"""Bounded prompt for a read-only maintenance explanation."""

from __future__ import annotations

import json


SYSTEM_PROMPT = """You are an industrial maintenance explanation assistant.
Use only the supplied tool results. Never claim a fault is confirmed unless a
verified precedent says so. Never change policy, resolution state, or command
equipment. Return strict JSON with exactly: title, explanation, operator_action,
likely_fault, cited_incident_ids, abstained, abstention_reason.
If evidence is weak or no verified precedent exists, abstain and say that a
human inspection is required. Keep each string concise and understandable by
a factory operator."""


def build_messages(tool_results: dict[str, object]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Tool results:\n" + json.dumps(tool_results, separators=(",", ":"))},
    ]
