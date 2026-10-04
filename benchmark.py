import json
import os
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Any, Optional


class Violation(BaseModel):
    requirement: str
    observed: str
    reason: str
    severity: str


class VerifyResponse(BaseModel):
    verified: bool
    score: float = Field(ge=0, le=1)
    violations: list[Violation]
    explanation: str


SYSTEM = """
You are a strict machine-work verifier.

Your only task is to determine whether OUTPUT satisfies SPEC.

Use EVIDENCE if supplied.

Rules:
- Do not rewrite or improve the output.
- Do not invent requirements.
- Explicit numeric, count, location, timing, format, inclusion,
  and exclusion constraints are binding.
- If evidence is required to support a material claim and the claim
  cannot be verified from the supplied evidence, treat it as a violation.
- Requirements that cannot be verified from the supplied information
  are violations.
- verified is true only if all material requirements are satisfied.
- score measures compliance with the specification, not writing quality.
"""


TESTS = [
    {
        "name": "01 PASS - numeric limit",
        "spec": "Return exactly 3 hotels, each under $200.",
        "output": [
            {"name": "Hotel A", "price": 180},
            {"name": "Hotel B", "price": 195},
            {"name": "Hotel C", "price": 190},
        ],
        "evidence": None,
        "expected": True,
    },
    {
        "name": "02 FAIL - numeric limit",
        "spec": "Return exactly 3 hotels, each under $200.",
        "output": [
            {"name": "Hotel A", "price": 180},
            {"name": "Hotel B", "price": 235},
            {"name": "Hotel C", "price": 190},
        ],
        "evidence": None,
        "expected": False,
    },
    {
        "name": "03 FAIL - exact count",
        "spec": "Return exactly 3 product names.",
        "output": ["Alpha", "Beta", "Gamma", "Delta"],
        "evidence": None,
        "expected": False,
    },
    {
        "name": "04 PASS - required fields",
        "spec": "Return a customer record containing name, email, and country.",
        "output": {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "country": "Japan",
        },
        "evidence": None,
        "expected": True,
    },
    {
        "name": "05 FAIL - missing required field",
        "spec": "Return a customer record containing name, email, and country.",
        "output": {
            "name": "Jane Smith",
            "country": "Japan",
        },
        "evidence": None,
        "expected": False,
    },
    {
        "name": "06 PASS - exclusion",
        "spec": "Write a short summary without mentioning price.",
        "output": "The product is compact, lightweight, and designed for travel.",
        "evidence": None,
        "expected": True,
    },
    {
        "name": "07 FAIL - exclusion",
        "spec": "Write a short summary without mentioning price.",
        "output": "The product is compact and costs $49.",
        "evidence": None,
        "expected": False,
    },
    {
        "name": "08 PASS - multiple constraints",
        "spec": "Return exactly 2 Japanese cities. Each city must have a population value above 1,000,000.",
        "output": [
            {"city": "Tokyo", "population": 14000000},
            {"city": "Yokohama", "population": 3700000},
        ],
        "evidence": None,
        "expected": True,
    },
    {
        "name": "09 FAIL - one of multiple constraints",
        "spec": "Return exactly 2 Japanese cities. Each city must have a population value above 1,000,000.",
        "output": [
            {"city": "Tokyo", "population": 14000000},
            {"city": "Nara", "population": 350000},
        ],
        "evidence": None,
        "expected": False,
    },
    {
        "name": "10 FAIL - unsupported evidence claim",
        "spec": "Using the supplied evidence, state whether Acme Corp had 2025 revenue above $10 million.",
        "output": {
            "answer": "Yes",
            "revenue": "$15 million",
        },
        "evidence": {
            "text": "Acme Corp reported 2025 revenue of $8 million."
        },
        "expected": False,
    },
    {
        "name": "11 PASS - evidence supported",
        "spec": "Using the supplied evidence, state whether Acme Corp had 2025 revenue above $10 million.",
        "output": {
            "answer": "No",
            "revenue": "$8 million",
        },
        "evidence": {
            "text": "Acme Corp reported 2025 revenue of $8 million."
        },
        "expected": True,
    },
    {
        "name": "12 FAIL - unverifiable requirement",
        "spec": "Confirm that this package was physically delivered to the customer today.",
        "output": {
            "delivered": True
        },
        "evidence": None,
        "expected": False,
    },
    {
        "name": "13 PASS - boundary below",
        "spec": "Return a value strictly less than 100.",
        "output": {
            "value": 99
        },
        "evidence": None,
        "expected": True,
    },
    {
        "name": "14 FAIL - boundary equal",
        "spec": "Return a value strictly less than 100.",
        "output": {
            "value": 100
        },
        "evidence": None,
        "expected": False,
    },
    {
        "name": "15 FAIL - wrong location",
        "spec": "Recommend exactly one restaurant located in Tokyo.",
        "output": {
            "name": "Example Restaurant",
            "location": "Osaka"
        },
        "evidence": None,
        "expected": False,
    },
]


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

passed = 0
failed = 0
results = []

print("\nSophia Verify Benchmark")
print("=" * 60)

for test in TESTS:
    payload = json.dumps(
        {
            "spec": test["spec"],
            "output": test["output"],
            "evidence": test["evidence"],
        },
        ensure_ascii=False,
    )

    try:
        response = client.responses.parse(
            model=os.getenv("SOPHIA_VERIFY_MODEL", "gpt-5.6"),
            input=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": payload},
            ],
            text_format=VerifyResponse,
        )

        result = response.output_parsed
        actual = result.verified
        correct = actual == test["expected"]

        if correct:
            passed += 1
            mark = "PASS"
        else:
            failed += 1
            mark = "FAIL"

        print(
            f'{mark:4} | {test["name"]} | '
            f'expected={test["expected"]} actual={actual} '
            f'score={result.score}'
        )

        results.append(
            {
                "name": test["name"],
                "expected": test["expected"],
                "actual": actual,
                "correct": correct,
                "score": result.score,
                "violations": [
                    v.model_dump() for v in result.violations
                ],
                "explanation": result.explanation,
            }
        )

    except Exception as exc:
        failed += 1
        print(f'ERROR | {test["name"]} | {exc}')
        results.append(
            {
                "name": test["name"],
                "expected": test["expected"],
                "error": str(exc),
            }
        )


total = len(TESTS)
accuracy = passed / total if total else 0

print("=" * 60)
print(f"RESULT: {passed}/{total} correct ({accuracy:.1%})")
print(f"Incorrect/errors: {failed}")

with open(
    "benchmark_results.json",
    "w",
    encoding="utf-8",
) as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("Detailed results saved to benchmark_results.json")