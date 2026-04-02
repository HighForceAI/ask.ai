"""
ask.ai — one prompt in, one expert answer out.

Run: uvicorn api.main:app --reload
"""

import os
import time
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Request
from typing import Optional

from .models import AskRequest, AskResponse
from .classifier import classify
from .executor import execute
from skills.registry import REGISTRY

load_dotenv()

# Rich logging format so you can follow the thought process
logging.basicConfig(
    level=logging.INFO,
    format="\033[90m%(asctime)s\033[0m \033[1m%(name)s\033[0m %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("askai.main")

app = FastAPI(title="ask.ai", version="0.1.0")

VALID_KEYS = set(os.environ.get("API_KEYS", "dev-key-123").split(","))


@app.post("/v1/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    x_api_key: Optional[str] = Header(None),
):
    start = time.time()

    # Auth
    key = x_api_key or request.api_key
    if key not in VALID_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")

    log.info("NEW REQUEST: %s", request.prompt[:100] + ("..." if len(request.prompt) > 100 else ""))

    # 1. Classify — picks skill + model + metadata
    classifier = await classify(request.prompt)

    # 2. Execute — runs skill agent, optional reviewer
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


@app.get("/v1/skills")
def list_skills():
    """List all available skills."""
    return {
        key: {
            "name": s["name"],
            "tags": s["tags"],
            "reviewer": s["reviewer"],
        }
        for key, s in REGISTRY.items()
    }


@app.get("/health")
def health():
    return {"status": "ok"}
