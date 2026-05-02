import json

import pytest
from pydantic import ValidationError

from packages.govmesh_common import (
    AuditChain,
    AuditEvent,
    BenchmarkRun,
    CheckpointStore,
    FileRegistryEntry,
    Node,
    PolicyDecision,
    Task,
    canonical_json,
    sha256_file,
    sha256_text,
)


def test_canonical_json_and_hashing_are_stable(tmp_path) -> None:
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert sha256_text("GovMesh") == sha256_text("GovMesh")

    sample = tmp_path / "sample.txt"
    sample.write_text("GovMesh Local AI Node", encoding="utf-8")

    assert sha256_file(sample) == sha256_text("GovMesh Local AI Node")


def test_phase_one_schemas_validate_core_fields() -> None:
    node = Node(
        hostname="sample-pc",
        os="Windows",
        agent_version="0.2.0",
        cpu_count=8,
        memory_total_mb=16_384,
        disk_free_mb=100_000,
    )
    task = Task(task_type="scan_pii", payload={"file_id": "file_sample"})
    file_entry = FileRegistryEntry(
        path="samples/documents/sample_policy_notice.md",
        sha256="a" * 64,
        size_bytes=123,
        source="sample",
    )
    benchmark = BenchmarkRun(benchmark_type="pc_profile", metrics={"cpu_count": 8})
    decision = PolicyDecision(
        allow=False,
        risk_level="blocked",
        block_reason="pii_detected",
        masked_text="홍길동 ******",
        user_message="개인정보 후보가 있어 차단했습니다.",
        findings=[{"kind": "rrn", "start": 4, "end": 18}],
    )

    assert node.node_id.startswith("node_")
    assert task.task_id.startswith("task_")
    assert file_entry.file_id.startswith("file_")
    assert benchmark.run_id.startswith("bench_")
    assert decision.allow is False


def test_schema_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        Node(
            hostname="bad-pc",
            os="Windows",
            agent_version="0.2.0",
            cpu_count=0,
            memory_total_mb=0,
            disk_free_mb=0,
        )

    with pytest.raises(ValidationError):
        Task(task_type="external_network_scan")


def test_audit_chain_appends_lists_and_verifies(tmp_path) -> None:
    chain = AuditChain(tmp_path / "audit.jsonl")

    first = chain.append(
        event_type="node.registered",
        actor="test-suite",
        target_id="node_sample",
        payload={"hostname": "sample-pc"},
    )
    second = chain.append(
        AuditEvent(
            event_type="task.completed",
            actor="test-suite",
            target_id="task_sample",
            payload={"status": "ok"},
        )
    )

    events = chain.list()

    assert len(events) == 2
    assert events[0].event_hash == first.event_hash
    assert events[1].previous_hash == first.event_hash
    assert second.event_hash is not None
    assert chain.verify() is True


def test_audit_chain_verify_fails_after_payload_tamper(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    chain = AuditChain(path)
    chain.append(event_type="task.completed", actor="test-suite", payload={"status": "ok"})

    tampered = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    tampered["payload"]["status"] = "changed"
    path.write_text(json.dumps(tampered, ensure_ascii=False) + "\n", encoding="utf-8")

    assert chain.verify() is False


def test_audit_chain_verify_fails_after_previous_hash_tamper(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    chain = AuditChain(path)
    chain.append(event_type="node.registered", actor="test-suite", payload={"node": "one"})
    chain.append(event_type="node.heartbeat", actor="test-suite", payload={"node": "one"})

    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    events[1]["previous_hash"] = "f" * 64
    path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
    )

    assert chain.verify() is False


def test_signed_audit_chain_fails_with_wrong_key(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    chain = AuditChain(path, signing_key="correct-key")
    event = chain.append(event_type="node.registered", actor="test-suite", payload={"node": "one"})

    assert event.signature is not None
    assert chain.head()["signature"] is not None
    assert chain.verify() is True
    assert AuditChain(path, signing_key="wrong-key").verify() is False


def test_audit_chain_exports_and_verifies_checkpoint(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    checkpoint = tmp_path / "checkpoints" / "audit-head.json"
    chain = AuditChain(path, signing_key="checkpoint-key")
    chain.append(event_type="node.registered", actor="test-suite", payload={"node": "one"})

    exported = chain.export_checkpoint(checkpoint, label="unit-test")

    assert exported["label"] == "unit-test"
    assert chain.verify_checkpoint(checkpoint) is True

    chain.append(event_type="node.heartbeat", actor="test-suite", payload={"node": "one"})

    assert chain.verify_checkpoint(checkpoint) is False


def test_checkpoint_store_appends_and_returns_latest(tmp_path) -> None:
    chain = AuditChain(tmp_path / "audit.jsonl", signing_key="checkpoint-key")
    store = CheckpointStore(tmp_path / "checkpoints.jsonl")
    chain.append(event_type="node.registered", actor="test-suite", payload={"node": "one"})

    first = chain.export_checkpoint(tmp_path / "first.json", label="first")
    store.append(first)
    chain.append(event_type="node.heartbeat", actor="test-suite", payload={"node": "one"})
    second = chain.export_checkpoint(tmp_path / "second.json", label="second")
    store.append(second)

    assert len(store.list()) == 2
    assert store.latest_for_source(str(tmp_path / "audit.jsonl"))["label"] == "second"
    assert store.verify() is True

    lines = (tmp_path / "checkpoints.jsonl").read_text(encoding="utf-8").splitlines()
    tampered = lines[0].replace('"label":"first"', '"label":"changed"')
    (tmp_path / "checkpoints.jsonl").write_text(tampered + "\n" + "\n".join(lines[1:]) + "\n", encoding="utf-8")
    assert store.verify() is False
