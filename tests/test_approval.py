import pytest

from approval import execute


@pytest.mark.parametrize(
    ("decision", "text", "expected"),
    [("approve", None, "Original"), ("edit", "Revised", "Revised"), ("reject", None, None)],
)
def test_review_across_database_reopens(tmp_path, decision, text, expected):
    db = tmp_path / "test.sqlite"
    started = execute(db, "start", text="Original")
    request_id = started["id"]
    assert started["status"] == "pending"
    assert "approved_reply" not in started
    assert execute(db, "status", request_id=request_id) == started
    result = execute(db, "review", request_id=request_id, decision=decision, text=text)
    assert result["status"] == "completed"
    assert result["draft"] == "Original"
    assert result["decision"] == decision
    assert result["approved_reply"] == expected
    assert execute(db, "status", request_id=request_id) == result
    with pytest.raises(ValueError, match="already"):
        execute(db, "review", request_id=request_id, decision="approve")


def test_invalid_edit_keeps_review_pending(tmp_path):
    db = tmp_path / "test.sqlite"
    request_id = execute(db, "start", text="Original")["id"]
    with pytest.raises(ValueError, match="edited reply"):
        execute(db, "review", request_id=request_id, decision="edit", text=" ")
    assert execute(db, "status", request_id=request_id)["status"] == "pending"


def test_unknown_request(tmp_path):
    with pytest.raises(ValueError, match="Unknown"):
        execute(tmp_path / "test.sqlite", "status", request_id="missing")
