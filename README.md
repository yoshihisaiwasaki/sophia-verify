# Sophia Verify v0.1

**One API. One job. Check whether AI-generated work actually satisfies the request.**

Sophia Verify is intentionally not an observability platform, prompt manager, payment engine, escrow service, or agent framework.

## Endpoint

`POST /verify`

### Request

```json
{
  "spec": "Return exactly 3 hotels in Shinjuku, each under $200 and non-smoking.",
  "output": [
    {"name": "A", "price": 180, "non_smoking": true},
    {"name": "B", "price": 235, "non_smoking": true},
    {"name": "C", "price": 190, "non_smoking": true}
  ],
  "evidence": null
}
```

### Response

```json
{
  "verified": false,
  "score": 0.67,
  "violations": [
    {
      "requirement": "Each hotel must cost no more than $200",
      "observed": "Hotel B costs $235",
      "reason": "Price exceeds the specified maximum.",
      "severity": "high"
    }
  ],
  "explanation": "One binding requirement was violated."
}
```

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows, then edit it
# cp .env.example .env   # macOS/Linux

set OPENAI_API_KEY=YOUR_KEY   # Windows CMD
# $env:OPENAI_API_KEY="YOUR_KEY"  # PowerShell
# export OPENAI_API_KEY=YOUR_KEY   # macOS/Linux

uvicorn app.main:app --reload
```

Open `/docs` for the interactive FastAPI API console.

## Test

```bash
pytest -q
```

## v0.1 scope

Included:
- requirement compliance
- numeric/count constraints
- required/excluded conditions
- optional evidence consistency
- machine-readable PASS/FAIL + violations

Explicitly excluded:
- payments
- PAY/HOLD/BLOCK
- escrow
- legal adjudication
- outcome guarantees
- agent orchestration
- tracing/observability dashboards

## Launch hypothesis

Developers will pay for a tiny verification checkpoint if it is materially easier than building and maintaining bespoke evaluators.

Kill criterion: if third-party developers test it but nobody pays after the initial launch/fix cycle, do not expand the platform. Change the offer or kill it.
