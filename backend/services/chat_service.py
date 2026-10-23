"""CrisisCore AI assistant — Google Gemini (free tier) with an offline safety fallback.

The chat must always answer, even with no API key, a Gemini outage, or an
exhausted free-tier quota. Every reply says where it came from (`source`).
"""
import threading
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

import httpx

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TIMEOUT_SECONDS,
    CHAT_RATE_LIMIT_PER_MINUTE,
)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

MAX_MESSAGE_CHARS = 1000
MAX_HISTORY_TURNS = 6
MAX_CONTEXT_CHARS = 6000
MAX_CONTEXT_LIST_ITEMS = 10

SYSTEM_PROMPT = """You are the CrisisCore AI Assistant, part of an India disaster-preparedness dashboard.
Help people stay safe before, during and after floods, earthquakes, cyclones, fires, heatwaves and droughts.

Rules:
- Be concise and practical: at most 6 short bullet points ("• ") or 2 short paragraphs, plain text, no markdown.
- Put life-safety steps first. Mention India's emergency number 112 once, only when the question is about an emergency or a hazard in progress.
- Use the live dashboard context only when the question is about current conditions; never invent alerts, readings or locations that are not in it.
- If data is unavailable, say so and point to official sources: IMD (mausam.imd.gov.in), NDMA (ndma.gov.in), and local authorities.
- Politely decline topics unrelated to safety, disasters, weather or emergency resources. Do not add this as a disclaimer to on-topic answers.

Accuracy rules for the dashboard context:
- Earthquakes: an earthquake is in India ONLY if the context lists it as inside India. Events in China, Tibet (Xizang), Nepal, Myanmar or other countries are outside India, even if they may be felt in India. Use the exact counts given; never contradict them.
- Official warnings (NDMA SACHET / IMD / CWC / SDMA, GDACS) are authoritative. "Automated indicators" and "AI estimates" are CrisisCore calculations, not official forecasts; say so when you mention them.
- A source listed as unavailable, loading or disabled means the data is missing, NOT that there is no danger. Never claim something is safe because data is missing.
- Hospitals/shelters: say whether the information is live or from a saved snapshot, exactly as given. Never invent names, distances or phone numbers.
- If the context does not contain the answer, say you do not have that information and point to official sources."""

# ---------------------------------------------------------------------------
# Offline fallback answers (NDMA-style guidance)
# ---------------------------------------------------------------------------

EMERGENCY_FOOTER = (
    "In an emergency in India call 112. Follow official updates from IMD and NDMA."
)

FALLBACK_TOPICS: List[Dict[str, Any]] = [
    {
        "topic": "earthquake",
        "keywords": ["earthquake", "quake", "tremor", "seismic", "aftershock"],
        "answer": (
            "During an earthquake:\n"
            "• DROP to your hands and knees, take COVER under a sturdy table or desk, and HOLD ON until the shaking stops.\n"
            "• Stay away from windows, glass, heavy furniture and anything that can fall.\n"
            "• If indoors, stay inside — do not run out during shaking. Do not use lifts.\n"
            "• If outdoors, move to an open area away from buildings, trees, poles and power lines.\n"
            "• If driving, stop safely away from bridges and flyovers and stay in the vehicle.\n"
            "After shaking stops: expect aftershocks, check for injuries, gas leaks and damage, and evacuate damaged buildings carefully."
        ),
    },
    {
        "topic": "flood",
        "keywords": [
            "flood", "inundat", "waterlogg", "heavy rain", "rising", "water level",
            "submerged", "monsoon", "dam ", "river",
        ],
        "answer": (
            "For floods:\n"
            "• Move to higher ground immediately if water is rising; follow evacuation orders.\n"
            "• Never walk or drive through flood water — 15 cm of moving water can knock you down, 60 cm can sweep away a car.\n"
            "• Switch off electricity and gas at the mains if water may enter your home; stay away from fallen power lines.\n"
            "• Keep an emergency kit ready: drinking water, dry food, medicines, torch, power bank, documents in a waterproof bag.\n"
            "• Drink only boiled or treated water afterwards, and avoid contact with flood water (infection risk)."
        ),
    },
    {
        "topic": "cyclone",
        "keywords": ["cyclone", "hurricane", "typhoon", "storm surge", "storm", "strong wind", "gale"],
        "answer": (
            "For cyclones:\n"
            "• Track IMD cyclone warnings and evacuate early if you live in a coastal or low-lying area.\n"
            "• Stay indoors in the strongest part of the building, away from windows; move to a cyclone shelter if advised.\n"
            "• Secure or bring in loose objects, and keep doors and windows shut.\n"
            "• Keep an emergency kit, charged phone and battery radio ready; store drinking water.\n"
            "• The calm 'eye' is not the end — stay inside until authorities say it is safe. Avoid fallen lines and damaged structures afterwards."
        ),
    },
    {
        "topic": "fire",
        "keywords": ["fire", "smoke", "burn", "blaze", "wildfire", "forest fire", "gas leak"],
        "answer": (
            "For fire:\n"
            "• Get out immediately and call 101 (Fire) or 112. Do not stop to collect belongings.\n"
            "• Stay low under smoke — crawl to the exit; cover your nose and mouth with a cloth.\n"
            "• Feel doors before opening: if hot, use another way out. Never use lifts.\n"
            "• If your clothes catch fire: STOP, DROP and ROLL.\n"
            "• If trapped, close doors, block gaps with wet cloth, and signal from a window.\n"
            "• For a gas leak: don't switch electrical items on or off, open windows, shut the regulator and leave."
        ),
    },
    {
        "topic": "heatwave",
        "keywords": ["heatwave", "heat wave", "heat stroke", "heatstroke", "sunstroke", "hot", "heat", "temperature"],
        "answer": (
            "For heatwaves:\n"
            "• Stay indoors in the hottest hours (about 12 pm–4 pm); keep rooms shaded and ventilated.\n"
            "• Drink water often even if not thirsty; use ORS, lassi, lemon water or buttermilk. Avoid alcohol and very sugary drinks.\n"
            "• Wear light, loose cotton clothes and cover your head outdoors.\n"
            "• Check on elderly people, children, outdoor workers and pets.\n"
            "• Heat stroke signs: confusion, very high body temperature, hot dry skin, fainting — move the person to shade, cool them with water, and call 108/112."
        ),
    },
    {
        "topic": "drought",
        "keywords": ["drought", "water shortage", "water scarcity", "dry spell", "no rain", "save water"],
        "answer": (
            "For drought and water shortage:\n"
            "• Store safe drinking water and prioritise it for drinking, cooking and hygiene.\n"
            "• Fix leaks, reuse water where safe (e.g. for plants or flushing), and use buckets instead of hoses.\n"
            "• Harvest rainwater when it does rain.\n"
            "• Follow local water-supply schedules and advisories.\n"
            "• Watch for heat illness and dehydration, especially in children and the elderly."
        ),
    },
]

GENERAL_FALLBACK = (
    "I can help with safety steps for earthquakes, floods, cyclones, fires, heatwaves and droughts. "
    "Try asking, for example, \"What should I do during an earthquake?\" or \"How do I prepare for a flood?\"\n\n"
    "General preparedness: keep an emergency kit (water, food, medicines, torch, power bank, copies of documents), "
    "know your nearest hospital and shelter (shown on the map), and agree on a family meeting point."
)

FALLBACK_NOTES = {
    "no_api_key": "Offline safety guide (AI not configured).",
    "timeout": "The AI service took too long, so here is the offline safety guide.",
    "quota": "The AI service is busy right now (free-tier limit reached), so here is the offline safety guide.",
    "api_error": "The AI service is unavailable right now, so here is the offline safety guide.",
    "blocked": "The AI could not answer this, so here is the offline safety guide.",
}


def fallback_answer(message: str) -> str:
    text = message.lower()
    matches = [t for t in FALLBACK_TOPICS if any(k in text for k in t["keywords"])]
    if not matches:
        return f"{GENERAL_FALLBACK}\n\n{EMERGENCY_FOOTER}"
    body = "\n\n".join(t["answer"] for t in matches[:2])
    return f"{body}\n\n{EMERGENCY_FOOTER}"


# ---------------------------------------------------------------------------
# Per-IP rate limit (in-memory sliding window)
# ---------------------------------------------------------------------------

_rate_lock = threading.Lock()
_requests_by_ip: Dict[str, deque] = defaultdict(deque)


def check_rate_limit(ip: str) -> Optional[int]:
    """Return None if allowed, else seconds until the next request is allowed."""
    now = time.monotonic()
    window = 60.0
    with _rate_lock:
        q = _requests_by_ip[ip]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= CHAT_RATE_LIMIT_PER_MINUTE:
            return max(1, int(window - (now - q[0])) + 1)
        q.append(now)
        # Drop idle IPs so the table can't grow without bound
        if len(_requests_by_ip) > 1000:
            for key in [k for k, v in _requests_by_ip.items() if not v]:
                del _requests_by_ip[key]
        return None


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------

def _format_context(context: Optional[Dict[str, Any]]) -> str:
    if not context:
        return ""
    lines = []
    for key, value in context.items():
        if value is None or value == "" or value == []:
            continue
        if isinstance(value, list):
            items = [str(v) for v in value[:MAX_CONTEXT_LIST_ITEMS]]
            lines.append(f"- {key}:" + "".join(f"\n    * {item}" for item in items))
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)[:MAX_CONTEXT_CHARS]


def _build_contents(message: str, history: List[Dict[str, str]], context_text: str) -> List[Dict[str, Any]]:
    contents = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        role = "model" if turn.get("role") == "assistant" else "user"
        text = str(turn.get("text", ""))[:MAX_MESSAGE_CHARS]
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    prompt = message
    if context_text:
        prompt = f"Live dashboard context:\n{context_text}\n\nUser question: {message}"
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    return contents


class GeminiError(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(detail or reason)
        self.reason = reason


def _call_gemini(message: str, history: List[Dict[str, str]], context_text: str) -> str:
    try:
        resp = httpx.post(
            GEMINI_URL.format(model=GEMINI_MODEL),
            headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": _build_contents(message, history, context_text),
                "generationConfig": {"maxOutputTokens": 700},
            },
            timeout=GEMINI_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as e:
        raise GeminiError("timeout", str(e))
    except httpx.HTTPError as e:
        raise GeminiError("api_error", f"{type(e).__name__}: {e}")

    if resp.status_code == 429:
        raise GeminiError("quota", resp.text[:300])
    if resp.status_code != 200:
        raise GeminiError("api_error", f"HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise GeminiError("blocked", str(data.get("promptFeedback", "no candidates")))
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    except ValueError as e:
        raise GeminiError("api_error", f"invalid JSON: {e}")
    if not text:
        raise GeminiError("blocked", f"empty reply (finishReason={candidates[0].get('finishReason')})")
    return text


def answer_chat(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    message = message.strip()[:MAX_MESSAGE_CHARS]
    history = history or []

    if not GEMINI_API_KEY:
        reason = "no_api_key"
    else:
        try:
            reply = _call_gemini(message, history, _format_context(context))
            return {"reply": reply, "source": "gemini", "model": GEMINI_MODEL}
        except GeminiError as e:
            print(f"[Chat] Gemini failed ({e.reason}): {e}")
            reason = e.reason
        except Exception as e:  # never let the chat crash the request
            print(f"[Chat] Unexpected error: {type(e).__name__}: {e}")
            reason = "api_error"

    return {
        "reply": fallback_answer(message),
        "source": "fallback",
        "fallback_reason": reason,
        "notice": FALLBACK_NOTES.get(reason, FALLBACK_NOTES["api_error"]),
    }
