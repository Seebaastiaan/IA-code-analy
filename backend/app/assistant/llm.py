"""
Clientes de los modelos por REST (httpx, sin SDK):
- Gemini: respuestas en JSON con esquema y embeddings (`gemini-embedding-001`). Con `on_delta`, la respuesta
  llega por streaming (`streamGenerateContent`, SSE) y se va entregando el texto del campo `answer`.
- Respaldo cuando Gemini responde 429 o 503 (alta demanda): los modelos de GEMINI_FALLBACK_MODELS y
  después Groq (Llama 3.3), si hay GROQ_API_KEY. Groq no tiene embeddings.

Las claves viajan en cabeceras (`x-goog-api-key`, `Authorization`), nunca en la URL.
"""

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import numpy as np

from app.config import Settings

log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
EMBED_DIM = 768
EMBED_BATCH = 100
TIMEOUT_S = 60
# Un 503 (alta demanda) suele pasar en segundos: se reintenta una vez el mismo modelo
BUSY_RETRY_WAIT_S = 1.5

GROQ_LABEL = "Groq · Llama 3.3"


def model_label(model: str) -> str:
    """"gemini-3.8-flash" → "Gemini 3.8 Flash" (lo que muestra el frontend)."""
    return " ".join(part.capitalize() for part in model.split("-"))


class LlmError(Exception):
    """Fallo del proveedor. `kind`: "quota" (429) o "busy" (503); en ambos vale la pena usar el respaldo."""

    def __init__(self, message: str, kind: str | None = None):
        super().__init__(message)
        self.kind = kind

    @property
    def rate_limited(self) -> bool:
        return self.kind in ("quota", "busy")


@dataclass
class Turn:
    role: str  # "user" | "model"
    text: str


@dataclass
class Answer:
    data: dict
    model: str  # etiqueta para mostrar ("Gemini 3.8 Flash")


ANSWER_START = re.compile(r'"answer"\s*:\s*"')
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "/": "/", "\\": "\\", '"': '"'}


def partial_answer(text: str) -> str:
    """Texto (ya decodificado) del campo "answer" de un JSON que todavía está llegando."""
    m = ANSWER_START.search(text)
    if not m:
        return ""
    out: list[str] = []
    i, n = m.end(), len(text)
    while i < n:
        c = text[i]
        if c == '"':
            break
        if c != "\\":
            out.append(c)
            i += 1
            continue
        if i + 1 >= n:
            break  # escape incompleto: se espera al siguiente fragmento
        esc = text[i + 1]
        if esc != "u":
            out.append(ESCAPES.get(esc, esc))
            i += 2
            continue
        if i + 6 > n:
            break
        code = int(text[i + 2 : i + 6], 16)
        if 0xD800 <= code < 0xDC00:  # par sustituto (emoji): necesita la segunda mitad
            if i + 12 > n:
                break
            low = int(text[i + 8 : i + 12], 16)
            out.append(chr(0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)))
            i += 12
            continue
        out.append(chr(code))
        i += 6
    return "".join(out)


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

    def chain(self) -> list[tuple[str, str]]:
        """Modelos en orden de preferencia: (proveedor, modelo)."""
        s = self.settings
        gemini = [s.gemini_model] + [m.strip() for m in s.gemini_fallback_models.split(",") if m.strip()]
        models = [("gemini", m) for m in dict.fromkeys(gemini)]
        if s.groq_api_key:
            models.append(("groq", s.groq_model))
        return models

    def _post(self, url: str, headers: dict, body: dict, provider: str) -> httpx.Response:
        """POST con un reintento si el modelo está saturado (503)."""
        for attempt in (1, 2):
            try:
                res = self.http.post(url, headers=headers, json=body)
            except httpx.HTTPError as exc:
                raise LlmError(f"No se pudo contactar a {provider}: {type(exc).__name__}") from exc
            if res.status_code == 503 and attempt == 1:
                time.sleep(BUSY_RETRY_WAIT_S)
                continue
            _check(res, provider)
            return res
        raise AssertionError("inalcanzable")

    # ─── Embeddings ───

    def embed(self, texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
        """Matriz (n, 768) float32 con filas normalizadas (con dimensión < 3072 Gemini no las normaliza)."""
        model = f"models/{self.settings.gemini_embedding_model}"
        rows: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH):
            batch = texts[i : i + EMBED_BATCH]
            body = {"requests": [{"model": model, "content": {"parts": [{"text": t}]}, "taskType": task, "outputDimensionality": EMBED_DIM} for t in batch]}
            res = self._post(f"{GEMINI_URL}/{model}:batchEmbedContents", {"x-goog-api-key": self.settings.gemini_api_key}, body, "Gemini")
            rows += [e["values"] for e in res.json()["embeddings"]]
        if not rows:
            return np.zeros((0, EMBED_DIM), dtype=np.float32)
        m = np.asarray(rows, dtype=np.float32)
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        return m / np.where(norms == 0, 1, norms)

    # ─── Respuestas ───

    def answer(self, system: str, turns: list[Turn], schema: dict, on_delta: Callable[[str], None] | None = None) -> Answer:
        """
        Respuesta JSON del primer modelo de `chain()` que responda; solo se pasa al siguiente ante 429/503.
        Con `on_delta`, Gemini responde por streaming y cada trozo nuevo del campo "answer" se entrega al llegar
        (Groq no: entrega la respuesta completa de una vez).
        """
        chain = self.chain()
        sent = [0]  # caracteres de "answer" ya entregados

        def emit(answer: str) -> None:
            if on_delta and len(answer) > sent[0]:
                on_delta(answer[sent[0] :])
                sent[0] = len(answer)

        for i, (provider, model) in enumerate(chain):
            try:
                if provider == "groq":
                    data = self._groq(system, turns, schema)
                    emit(str(data.get("answer") or ""))
                    return Answer(data, GROQ_LABEL)
                if on_delta:
                    return Answer(self._gemini_stream(model, system, turns, schema, emit), model_label(model))
                return Answer(self._gemini(model, system, turns, schema), model_label(model))
            except LlmError as exc:
                # Si ya se mostró parte de una respuesta, cambiar de modelo la mezclaría con otra
                if not exc.rate_limited or i == len(chain) - 1 or sent[0]:
                    raise
                log.warning("%s no disponible (%s); se usa el respaldo", model, exc)
        raise LlmError("No hay modelos configurados")

    def _gemini_body(self, system: str, turns: list[Turn], schema: dict) -> dict:
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": t.role, "parts": [{"text": t.text}]} for t in turns],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }

    def _gemini(self, model: str, system: str, turns: list[Turn], schema: dict) -> dict:
        body = self._gemini_body(system, turns, schema)
        data = self._post(f"{GEMINI_URL}/models/{model}:generateContent", {"x-goog-api-key": self.settings.gemini_api_key}, body, "Gemini").json()
        candidates = data.get("candidates") or []
        if not candidates:
            reason = data.get("promptFeedback", {}).get("blockReason", "sin respuesta")
            raise LlmError(f"Gemini no respondió ({reason})")
        text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if not p.get("thought"))
        return _parse(text, "Gemini")

    def _gemini_stream(self, model: str, system: str, turns: list[Turn], schema: dict, emit: Callable[[str], None]) -> dict:
        url = f"{GEMINI_URL}/models/{model}:streamGenerateContent?alt=sse"
        headers = {"x-goog-api-key": self.settings.gemini_api_key}
        body = self._gemini_body(system, turns, schema)
        for attempt in (1, 2):
            text, blocked = "", None
            try:
                with self.http.stream("POST", url, headers=headers, json=body) as res:
                    if res.status_code == 503 and attempt == 1:
                        time.sleep(BUSY_RETRY_WAIT_S)
                        continue
                    if res.status_code >= 400:
                        res.read()
                        _check(res, "Gemini")
                    for line in res.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            chunk = json.loads(line[5:])
                        except json.JSONDecodeError:
                            continue
                        candidates = chunk.get("candidates") or []
                        if not candidates:
                            blocked = chunk.get("promptFeedback", {}).get("blockReason") or blocked
                            continue
                        text += "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if not p.get("thought"))
                        emit(partial_answer(text))
            except httpx.HTTPError as exc:
                raise LlmError(f"No se pudo contactar a Gemini: {type(exc).__name__}") from exc
            if not text:
                raise LlmError(f"Gemini no respondió ({blocked or 'sin respuesta'})")
            return _parse(text, "Gemini")
        raise AssertionError("inalcanzable")

    def _groq(self, system: str, turns: list[Turn], schema: dict) -> dict:
        # Groq no acepta esquema: el modo JSON + la descripción del esquema en el sistema
        messages = [{"role": "system", "content": f"{system}\n\nResponde SOLO con un objeto JSON con este esquema:\n{json.dumps(schema)}"}]
        messages += [{"role": "assistant" if t.role == "model" else "user", "content": t.text} for t in turns]
        body = {"model": self.settings.groq_model, "messages": messages, "temperature": 0.2, "response_format": {"type": "json_object"}}
        res = self._post(GROQ_URL, {"Authorization": f"Bearer {self.settings.groq_api_key}"}, body, "Groq")
        return _parse(res.json()["choices"][0]["message"]["content"], "Groq")


def _parse(text: str, provider: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlmError(f"{provider} devolvió una respuesta que no es JSON") from exc
    if not isinstance(data, dict):
        raise LlmError(f"{provider} devolvió una respuesta inesperada")
    return data
