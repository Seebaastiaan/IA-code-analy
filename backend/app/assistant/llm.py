"""
Cliente de la API de IA por REST (httpx, sin SDK). Gemini responde en JSON con un esquema
(`responseSchema`), así la salida siempre se puede parsear.

La clave viaja en la cabecera `x-goog-api-key`, nunca en la URL.
"""

import json
from dataclasses import dataclass

import httpx

from app.config import Settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT_S = 60


def model_label(model: str) -> str:
    """"gemini-3.8-flash" → "Gemini 3.8 Flash" (lo que muestra el frontend)."""
    return " ".join(part.capitalize() for part in model.split("-"))


class LlmError(Exception):
    """Fallo del proveedor. `kind`: "quota" (429) o "busy" (503)."""

    def __init__(self, message: str, kind: str | None = None):
        super().__init__(message)
        self.kind = kind


@dataclass
class Turn:
    role: str  # "user" | "model"
    text: str


@dataclass
class Answer:
    data: dict
    model: str  # etiqueta para mostrar ("Gemini 3.8 Flash")


def _check(res: httpx.Response, provider: str) -> None:
    if res.status_code == 429:
        raise LlmError(f"{provider} alcanzó su límite de solicitudes", kind="quota")
    if res.status_code == 503:
        raise LlmError(f"{provider} tiene demasiada demanda en este momento", kind="busy")
    if res.status_code in (401, 403):
        raise LlmError(f"La clave de {provider} no es válida o no tiene permiso")
    if res.status_code >= 400:
        try:
            detail = res.json().get("error", {}).get("message", "")
        except ValueError:
            detail = res.text[:200]
        raise LlmError(f"{provider} respondió {res.status_code}: {detail}")


class LLM:
    def __init__(self, settings: Settings, http: httpx.Client | None = None):
        self.settings = settings
        self.http = http or httpx.Client(timeout=TIMEOUT_S)

    def answer(self, system: str, turns: list[Turn], schema: dict) -> Answer:
        """Respuesta JSON del modelo configurado (GEMINI_MODEL)."""
        model = self.settings.gemini_model
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": t.role, "parts": [{"text": t.text}]} for t in turns],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        try:
            res = self.http.post(f"{GEMINI_URL}/models/{model}:generateContent", headers={"x-goog-api-key": self.settings.gemini_api_key}, json=body)
        except httpx.HTTPError as exc:
            raise LlmError(f"No se pudo contactar a Gemini: {type(exc).__name__}") from exc
        _check(res, "Gemini")
        data = res.json()
        candidates = data.get("candidates") or []
        if not candidates:
            reason = data.get("promptFeedback", {}).get("blockReason", "sin respuesta")
            raise LlmError(f"Gemini no respondió ({reason})")
        text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if not p.get("thought"))
        return Answer(_parse(text, "Gemini"), model_label(model))


def _parse(text: str, provider: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlmError(f"{provider} devolvió una respuesta que no es JSON") from exc
    if not isinstance(data, dict):
        raise LlmError(f"{provider} devolvió una respuesta inesperada")
    return data
