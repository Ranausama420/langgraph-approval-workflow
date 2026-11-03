from fastapi.testclient import TestClient


def test_review_api_persists_and_rejects_duplicate(tmp_path, monkeypatch):
    import api
    monkeypatch.setattr(api, "DB", tmp_path / "api.sqlite")
    with TestClient(api.app) as client:
        reviewer = {"X-User-Id": "reviewer-demo"}
        created = client.post("/reviews", json={"draft": "Original", "ticket_id": "SUP-7"}, headers=reviewer)
        assert created.status_code == 201
        review_id = created.json()["id"]
        assert client.get("/reviews?status=pending", headers=reviewer).json()["items"][0]["ticket_id"] == "SUP-7"
        assert client.post(f"/reviews/{review_id}/decision", json={"decision": "edit", "text": "Revised"}, headers=reviewer).status_code == 200
        duplicate = client.post(f"/reviews/{review_id}/decision", json={"decision": "approve"}, headers=reviewer)
        assert duplicate.status_code == 409
        assert client.get(f"/reviews/{review_id}", headers=reviewer).json()["approved_reply"] == "Revised"


def test_api_requires_role_and_supports_manager_assignment(tmp_path, monkeypatch):
    import api
    monkeypatch.setattr(api, "DB", tmp_path / "api.sqlite")
    with TestClient(api.app) as client:
        created = client.post("/reviews", json={"draft": "Please check login", "ticket_id": "SUP-8"}, headers={"X-User-Id": "customer-demo"})
        review_id = created.json()["id"]
        assert client.post(f"/reviews/{review_id}/decision", json={"decision": "approve"}, headers={"X-User-Id": "customer-demo"}).status_code == 403
        assigned = client.post(f"/reviews/{review_id}/assign", json={"reviewer_id": "reviewer-demo"}, headers={"X-User-Id": "manager-demo"})
        assert assigned.status_code == 200
