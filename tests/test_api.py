import os
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from fastapi.testclient import TestClient
import app.main as main

client = TestClient(main.app)

class FakeResponses:
    def parse(self, **kwargs):
        class R:
            output_parsed = main.VerifyResponse(
                verified=False,
                score=0.67,
                violations=[
                    main.Violation(
                        requirement="Hotel must cost no more than $200",
                        observed="$235",
                        reason="Price exceeds the specified maximum.",
                        severity="high",
                    )
                ],
                explanation="One binding requirement was violated.",
            )
        return R()

class FakeClient:
    responses = FakeResponses()

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_verify(monkeypatch):
    monkeypatch.setattr(main, "client", FakeClient())
    r = client.post("/verify", json={
        "spec": "Return exactly 3 hotels under $200.",
        "output": ["Hotel A $180", "Hotel B $235", "Hotel C $190"],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["verified"] is False
    assert body["violations"][0]["severity"] == "high"
