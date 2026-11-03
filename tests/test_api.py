from fastapi.testclient import TestClient


def test_review_api_persists_and_rejects_duplicate(tmp_path, monkeypatch):
    import api
    monkeypatch.setattr(api, "DB", tmp_path / "api.sqlite")
    with TestClient(api.app) as client:
        created = client.post("/reviews", json={"draft": "Original", "ticket_id": "SUP-7"})
        assert created.status_code == 201
        review_id = created.json()["id"]
        assert client.get("/reviews?status=pending").json()["items"][0]["ticket_id"] == "SUP-7"
        assert client.post(f"/reviews/{review_id}/decision", json={"decision": "edit", "text": "Revised"}).status_code == 200
        duplicate = client.post(f"/reviews/{review_id}/decision", json={"decision": "approve"})
        assert duplicate.status_code == 409
        assert client.get(f"/reviews/{review_id}").json()["approved_reply"] == "Revised"
