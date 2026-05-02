# Runbook

## Verify

```powershell
python -m pytest
```

운영 준비 상태:

```powershell
python scripts/govmesh_doctor.py
```

로컬 토큰 생성:

```powershell
python scripts/generate_local_tokens.py --powershell
```

## Run Benchmark

```powershell
python -m packages.govmesh_benchmark run --sample samples/documents --out reports/benchmarks
```

출력:

- JSON report
- Markdown report

## Node Agent

성능 진단:

```powershell
python -m apps.node_agent performance-doctor
```

문서 폴더 정책 스캔:

```powershell
python -m apps.node_agent scan-folder --path samples/documents
```

샘플 RAG 질의:

```powershell
python -m apps.node_agent query --sample samples/documents --question "근거 문서 기준으로 요약해줘"
```

장기 worker loop:

```powershell
python -m apps.node_agent run-worker --control-plane http://127.0.0.1:8787 --node-id <node_id> --interval 5
```

## Control Plane

로컬 서버:

```powershell
python -m apps.control_plane
```

기본 bind:

```text
127.0.0.1:8787
```

주요 API:

- `POST /nodes/register`
- `POST /nodes/{node_id}/heartbeat`
- `POST /tasks`
- `GET /tasks/next`
- `POST /tasks/{task_id}/result`
- `GET /audit/verify`
- `POST /skills/drafts`
- `POST /skills/{skill_id}/approve`
- `POST /skills/{skill_id}/deploy`

## Quarantine Gateway

로컬 서버:

```powershell
python -m apps.quarantine_gateway
```

기본 bind:

```text
127.0.0.1:8790
```

반입 흐름:

```text
upload -> scan -> approve/reject -> approved registry
```

승인 전에는 registry에 들어가지 않습니다. 위험 확장자나 위험 문자열이 있으면 approve가 차단됩니다.

## Admin Status

```powershell
python -m apps.admin_ui --control-plane http://127.0.0.1:8787
```

## Release Gate

```powershell
python scripts/release_gate.py
```

Portable bundle:

```powershell
.\scripts\build_portable.ps1
```

Evidence package:

```powershell
python scripts/build_evidence_package.py
```

Current-user worker task:

```powershell
.\scripts\install_windows_service.ps1 -ControlPlaneUrl http://127.0.0.1:8787 -NodeId <node_id>
```

## Safety Checks

- 감사로그 검증: `GET /audit/verify`
- raw PII 로그 누출 금지: 테스트에서 fake 주민번호가 audit log에 저장되지 않는지 확인
- provider 호출 전 policy decision 확인
- local API 기본 bind는 `127.0.0.1`
