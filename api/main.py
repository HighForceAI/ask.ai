"""
ask.ai — one prompt in, one expert answer out.

Run: uvicorn api.main:app --reload
"""

import os
import time
import secrets
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Optional
import json
import asyncio

from .models import AskRequest, AskResponse
from .classifier import classify
from .executor import execute
from skills.registry import REGISTRY

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="\033[90m%(asctime)s\033[0m \033[1m%(name)s\033[0m %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("askai.main")

app = FastAPI(title="ask.ai", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Key management ────────────────────────────────────────────────
# Seed from env, new keys added at runtime via /v1/keys/create
VALID_KEYS = set(os.environ.get("API_KEYS", "dev-key-123").split(","))
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "admin-secret-change-me")


def _check_key(x_api_key: Optional[str], body_key: Optional[str]):
    key = x_api_key or body_key
    if key not in VALID_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key


# ── Key endpoints ─────────────────────────────────────────────────────

@app.post("/v1/keys/create")
async def create_key(x_admin_secret: Optional[str] = Header(None)):
    """Generate a new ask- prefixed API key. Requires admin secret."""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    key = f"ask-{secrets.token_hex(24)}"
    VALID_KEYS.add(key)
    log.info("NEW KEY CREATED: %s...%s", key[:8], key[-4:])
    return {"api_key": key}


@app.post("/v1/keys/revoke")
async def revoke_key(
    api_key: str,
    x_admin_secret: Optional[str] = Header(None),
):
    """Revoke an API key. Requires admin secret."""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    VALID_KEYS.discard(api_key)
    log.info("KEY REVOKED: %s...%s", api_key[:8], api_key[-4:])
    return {"revoked": True}


@app.get("/v1/keys/list")
async def list_keys(x_admin_secret: Optional[str] = Header(None)):
    """List all active keys (masked). Requires admin secret."""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    return {
        "keys": [f"{k[:8]}...{k[-4:]}" for k in VALID_KEYS],
        "count": len(VALID_KEYS),
    }


# ── Main endpoints ────────────────────────────────────────────────────

@app.post("/v1/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    x_api_key: Optional[str] = Header(None),
):
    start = time.time()
    _check_key(x_api_key, request.api_key)

    log.info("NEW REQUEST: %s", request.prompt[:100] + ("..." if len(request.prompt) > 100 else ""))

    classifier = await classify(request.prompt)
    result = await execute(prompt=request.prompt, classifier=classifier)

    elapsed = time.time() - start
    log.info("REQUEST COMPLETE in %.1fs | skill=%s model=%s cost=$%.6f reviewed=%s",
             elapsed, classifier.skill, result["model_used"], result["cost_usd"], result["reviewed"])

    return AskResponse(
        answer=result["answer"],
        skill_used=REGISTRY[classifier.skill]["name"],
        model_used=result["model_used"],
        reviewed=result["reviewed"],
        cost_usd=result["cost_usd"],
        classifier=classifier,
    )


@app.post("/v1/ask/stream")
async def ask_stream(
    request: AskRequest,
    x_api_key: Optional[str] = Header(None),
):
    """SSE streaming endpoint — sends classifier step, then streams answer text."""
    _check_key(x_api_key, request.api_key)

    log.info("NEW STREAM REQUEST: %s", request.prompt[:100] + ("..." if len(request.prompt) > 100 else ""))

    async def event_stream():
        start = time.time()

        classifier = await classify(request.prompt)
        yield f"data: {json.dumps({'type': 'classifier', 'data': classifier.model_dump()})}\n\n"

        skill = REGISTRY[classifier.skill]
        yield f"data: {json.dumps({'type': 'skill', 'data': {'name': skill['name'], 'key': classifier.skill}})}\n\n"

        result = await execute(prompt=request.prompt, classifier=classifier)

        answer = result["answer"]
        chunk_size = 12
        for i in range(0, len(answer), chunk_size):
            yield f"data: {json.dumps({'type': 'chunk', 'data': answer[i:i + chunk_size]})}\n\n"
            await asyncio.sleep(0.02)

        elapsed = time.time() - start
        yield f"data: {json.dumps({'type': 'done', 'data': {'model_used': result['model_used'], 'reviewed': result['reviewed'], 'cost_usd': result['cost_usd'], 'elapsed': round(elapsed, 1)}})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/v1/skills")
def list_skills():
    return {
        key: {"name": s["name"], "tags": s["tags"], "reviewer": s["reviewer"]}
        for key, s in REGISTRY.items()
    }


@app.get("/health")
def health():
    return {"status": "ok"}
