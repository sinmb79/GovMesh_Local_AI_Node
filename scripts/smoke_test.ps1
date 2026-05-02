$ErrorActionPreference = "Stop"

python -m pytest
python -m packages.govmesh_benchmark run --sample samples/documents --out reports/benchmarks
python -m apps.node_agent performance-doctor
python -m apps.node_agent scan-folder --path samples/documents
python -m apps.node_agent query --sample samples/documents --question "근거 문서 기준으로 요약해줘"
python scripts/release_gate.py --skip-pytest

Write-Host "GovMesh smoke test passed."
