# Release Checklist

## Required Gates

- `python -m pytest`
- `python scripts/release_gate.py`
- `python scripts/build_evidence_package.py`
- `python scripts/build_release_bundle.py`
- `python -m packages.govmesh_benchmark run --sample samples/documents --out reports/benchmarks`
- `python -m apps.node_agent performance-doctor`
- `python -m apps.node_agent scan-folder --path samples/documents`
- `python -m apps.node_agent query --sample samples/documents --question "근거 문서 기준으로 요약해줘"`

## Security Gates

- 실제 정부 데이터 없음
- 실제 개인정보 없음
- fake PII는 tests 또는 sample corpus에만 존재
- 외부 네트워크 호출 없음
- API 기본 bind는 `127.0.0.1`
- raw PII audit log 저장 없음
- 승인되지 않은 skill 실행 차단
- llama.cpp provider는 `approved=True`와 local path 검증 없이는 실행 불가

## Packaging

Windows portable bundle:

```powershell
.\scripts\build_portable.ps1
python scripts/build_release_bundle.py
```

Output:

```text
dist\govmesh-portable
dist\govmesh-local-ai-node-v0.3.1.zip
```

Smoke test:

```powershell
.\scripts\smoke_test.ps1
```

Evidence package:

```powershell
python scripts/build_evidence_package.py
```

Current-user worker install:

```powershell
.\scripts\install_windows_service.ps1 -ControlPlaneUrl http://127.0.0.1:8787 -NodeId <node_id>
```
