import json
import os
from typing import Any, Literal, Optional

from fastapi import FastAPI, Header, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field


app = FastAPI(
    title="Sophia Verify API",
    description="Verify whether AI-generated output satisfies the requested requirements.",
    version="0.1.0",
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

RAPIDAPI_PROXY_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET")


class Violation(BaseModel):
    requirement: str
    observed: str
    reason: str
    severity: Literal["low", "medium", "high"]


class VerifyRequest(BaseModel):
    spec: str = Field(
        ...,
        description="The requirements that the AI-generated output must satisfy.",
    )
    output: Any = Field(
        ...,
        description="The AI-generated output to verify.",
    )
    evidence: Optional[Any] = Field(
        default=None,
        description="Optional evidence used to verify factual or external claims.",
    )


class VerifyResponse(BaseModel):
    verified: bool
    score: float = Field(ge=0.0, le=1.0)
    violations: list[Violation]
    explanation: str


SYSTEM = """
You are Sophia Verify, a strict machine-work verifier.

Your only task is to determine whether OUTPUT satisfies SPEC.

Rules:
- Use EVIDENCE when it is supplied.
- Do not rewrite or improve the output.
- Do not invent requirements that are not in SPEC.
- Explicit numeric, count, location, timing, format, inclusion, and exclusion
  constraints are binding.
- If EVIDENCE is supplied, unsupported material claims are violations.
- If a requirement cannot be verified from OUTPUT and supplied EVIDENCE,
  treat that requirement as a violation.
- verified must be true only when all material requirements are satisfied.
- score measures compliance with SPEC, not writing quality.

Return the structured verification result only.
""".strip()


def verify_rapidapi_proxy_secret(
    x_rapidapi_proxy_secret: Optional[str],
) -> None:
    """
    Allow requests only when they came through the configured RapidAPI proxy.
    """
    if not RAPIDAPI_PROXY_SECRET:
        raise HTTPException(
            status_code=503,
            detail="RapidAPI proxy authentication is not configured.",
        )

    if x_rapidapi_proxy_secret != RAPIDAPI_PROXY_SECRET:
        raise HTTPException(
            status_code=403,
            detail="Forbidden.",
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/verify", response_model=VerifyResponse)
def verify(
    request: VerifyRequest,
    x_rapidapi_proxy_secret: Optional[str] = Header(
        default=None,
        alias="X-RapidAPI-Proxy-Secret",
    ),
):
    verify_rapidapi_proxy_secret(x_rapidapi_proxy_secret)

    payload = json.dumps(
        {
            "spec": request.spec,
            "output": request.output,
            "evidence": request.evidence,
        },
        ensure_ascii=False,
        default=str,
    )

    try:
        response = client.responses.parse(
            model=os.getenv("SOPHIA_VERIFY_MODEL", "gpt-5.6"),
            input=[
                {
                    "role": "system",
                    "content": SYSTEM,
                },
                {
                    "role": "user",
                    "content": payload,
                },
            ],
            text_format=VerifyResponse,
        )

        result = response.output_parsed

        if result is None:
            raise HTTPException(
                status_code=502,
                detail="Verifier returned no structured result.",
            )

        return result

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Verification failed: {exc}",
        ) from exc
