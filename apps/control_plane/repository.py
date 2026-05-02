"""SQLite repository for the control plane MVP."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Literal

from packages.govmesh_common import BenchmarkRun, Node, Task


class SQLiteRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute("create table if not exists schema_migrations (version integer primary key, applied_at text not null)")
            conn.execute("create table if not exists nodes (node_id text primary key, payload text not null)")
            conn.execute("create table if not exists tasks (task_id text primary key, status text not null, priority integer not null, payload text not null)")
            conn.execute("create table if not exists benchmarks (run_id text primary key, payload text not null)")
            conn.execute(
                "insert or ignore into schema_migrations (version, applied_at) values (1, datetime('now'))"
            )
            conn.commit()
        finally:
            conn.close()

    def schema_version(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("select max(version) as version from schema_migrations").fetchone()
        finally:
            conn.close()
        return int(row["version"] or 0)

    def save_node(self, node: Node) -> Node:
        conn = self._connect()
        try:
            conn.execute(
                "insert or replace into nodes (node_id, payload) values (?, ?)",
                (node.node_id, node.model_dump_json()),
            )
            conn.commit()
        finally:
            conn.close()
        return node

    def get_node(self, node_id: str) -> Node:
        conn = self._connect()
        try:
            row = conn.execute("select payload from nodes where node_id = ?", (node_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            raise KeyError(node_id)
        return Node.model_validate(json.loads(row["payload"]))

    def list_nodes(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Node]:
        conn = self._connect()
        try:
            rows = conn.execute("select payload from nodes order by node_id").fetchall()
        finally:
            conn.close()
        nodes = [Node.model_validate(json.loads(row["payload"])) for row in rows]
        if status is not None:
            nodes = [node for node in nodes if node.status == status]
        return nodes[offset : offset + limit]

    def save_task(self, task: Task) -> Task:
        conn = self._connect()
        try:
            conn.execute(
                "insert or replace into tasks (task_id, status, priority, payload) values (?, ?, ?, ?)",
                (task.task_id, task.status, task.priority, task.model_dump_json()),
            )
            conn.commit()
        finally:
            conn.close()
        return task

    def get_task(self, task_id: str) -> Task:
        conn = self._connect()
        try:
            row = conn.execute("select payload from tasks where task_id = ?", (task_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            raise KeyError(task_id)
        return Task.model_validate(json.loads(row["payload"]))

    def list_tasks(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        conn = self._connect()
        try:
            rows = conn.execute("select payload from tasks order by priority asc, task_id asc").fetchall()
        finally:
            conn.close()
        tasks = [Task.model_validate(json.loads(row["payload"])) for row in rows]
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        return tasks[offset : offset + limit]

    def next_task(self) -> Task | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "select payload from tasks where status in ('queued', 'failed') order by priority asc, task_id asc limit 1"
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        task = Task.model_validate(json.loads(row["payload"]))
        if task.status == "failed" and task.retry_count >= task.max_retries:
            return None
        return task

    def retry_task(self, task_id: str, *, error: str | None = None) -> Task:
        task = self.get_task(task_id)
        retried = task.model_copy(
            update={
                "status": "queued" if task.retry_count + 1 <= task.max_retries else "failed",
                "retry_count": task.retry_count + 1,
                "error": error,
            }
        )
        return self.save_task(retried)

    def save_benchmark(self, run: BenchmarkRun) -> BenchmarkRun:
        conn = self._connect()
        try:
            conn.execute(
                "insert or replace into benchmarks (run_id, payload) values (?, ?)",
                (run.run_id, run.model_dump_json()),
            )
            conn.commit()
        finally:
            conn.close()
        return run

    def list_benchmarks(self) -> list[BenchmarkRun]:
        conn = self._connect()
        try:
            rows = conn.execute("select payload from benchmarks order by run_id").fetchall()
        finally:
            conn.close()
        return [BenchmarkRun.model_validate(json.loads(row["payload"])) for row in rows]
