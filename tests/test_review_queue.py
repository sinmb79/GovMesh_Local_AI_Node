from packages.govmesh_review import ReviewDecision, ReviewQueue


def test_review_queue_stores_hash_not_raw_content(tmp_path) -> None:
    queue = ReviewQueue(tmp_path / "reviews.jsonl")

    item = queue.create(
        target_type="rag_answer",
        target_id="answer-1",
        reason="grounding_required",
        summary="Needs review",
        content="secret raw answer",
        evidence_ids=["doc#1"],
        created_by="tester",
    )

    stored = (tmp_path / "reviews.jsonl").read_text(encoding="utf-8")
    assert item.status == "open"
    assert item.content_hash
    assert "secret raw answer" not in stored
    assert queue.list(status="open")[0].review_id == item.review_id


def test_review_queue_decision_updates_latest_state(tmp_path) -> None:
    queue = ReviewQueue(tmp_path / "reviews.jsonl")
    item = queue.create(
        target_type="import",
        target_id="import-1",
        reason="manual_review_required",
        summary="Unsupported file type",
    )

    decided = queue.decide(item.review_id, ReviewDecision(decision="rejected", reviewer="operator", reason="unsafe"))

    assert decided.status == "rejected"
    assert queue.get(item.review_id).status == "rejected"
    assert queue.list(status="open") == []
