import json
import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from openai import OpenAI

app = FastAPI(
    title="Sophia Verify API",
    version="0.1.0",
    description="One job: check whether AI-generated work satisfies a specification."
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class VerifyRequest(BaseModel):
    spec: str = Field(..., min_length=1, description="The requirements the output must satisfy.")
    output: Any = Field(..., description="The AI-generated work to verify.")
    evidence: Optional[Any] = Field(default=None, description="Optional source/evidence used to verify factual constraints.")

class Violation(BaseModel):
    requirement: str
    observed: str
    reason: str
    severity: str = Field(description="low, medium, or high")

class VerifyResponse(BaseModel):
    verified: bool
    score: float = Field(ge=0, le=1)
    violations: list[Violation]
    explanation: str

SYSTEM = """You are Sophia Verify, a strict machine-work verifier.
Your ONLY job is to determine whether OUTPUT satisfies SPEC, using EVIDENCE when supplied.

Rules:
1. Do not improve, rewrite, or continue the output.
2. Do not invent requirements not present in SPEC.
3. Treat explicit numeric, count, location, timing, format, inclusion and exclusion constraints as binding.
4. If evidence is supplied, factual claims that materially affect compliance must be supported by it.
5. If a requirement cannot be verified from the supplied material, identify that as a violation rather than assuming success.
6. verified=true only when all material requirements are satisfied.
7. score is compliance from 0.0 to 1.0, not writing quality.
8. Return concise machine-usable results.
"""

def _serialize(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)

@app.get("/health")
def health():
    return {"status": "ok", "service": "sophia-verify", "version": "0.1.0"}

@app.post("/verify", response_model=VerifyResponse)
def verify(req: VerifyRequest):
    payload = f"""SPEC:
{req.spec}

OUTPUT:
{_serialize(req.output)}

EVIDENCE:
{_serialize(req.evidence) if req.evidence is not None else "NONE"}
"""
    try:
        response = client.responses.parse(
            model=os.getenv("SOPHIA_VERIFY_MODEL", "gpt-5.6"),
            input=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": payload},
            ],
            text_format=VerifyResponse,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("No parsed verification result returned.")
        return parsed
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Verification engine error: {exc}") from exc
