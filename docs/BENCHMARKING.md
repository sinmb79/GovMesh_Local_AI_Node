# Benchmarking

이 문서는 GovMesh Local AI Node가 무엇을 따라 하고 무엇을 피해야 하는지 판단하기 위한 벤치마킹 기준입니다. 기준일은 2026-05-02입니다.

## Benchmark Targets

| 대상 | 참고점 | GovMesh 적용 방향 |
|---|---|---|
| Petals | BitTorrent-style collaborative inference | 대형 모델 샤딩은 MVP 제외, 분산 색인/임베딩/스캔부터 시작 |
| llama.cpp | GGUF, CPU/GPU local inference | `LocalRuntimeAdapter` 후보, RPC는 실험 기능으로 격리 |
| exo | local device discovery and distributed inference | 자동 발견보다 수동 등록과 정책 승인 우선 |
| Ollama | 쉬운 local model API UX | 쉬운 UX는 참고하되 기본 bind와 gateway 정책 강화 |
| GPT4All | desktop local document UX | 비개발자 UX와 LocalDocs 방향 참고 |
| LocalAI | OpenAI-compatible local API | provider interface 참고, MVP는 범용성 축소 |
| Hermes Agent | persistent memory and skills | skill 철학 참고, 자동 실행은 승인제로 제한 |
| AMD GAIA | local PC AI agent | PC agent UX와 air-gapped 메시지 참고 |
| GovOn | Korean civil-service response adapter | 행정 tone과 human-in-the-loop 구조 참고 |

## Metrics

### Local Runtime

- TTFT
- tokens/sec
- cold start and warm start
- peak RAM
- CPU usage
- context length sensitivity

### RAG

- chunking throughput
- embedding docs/min
- search latency p50/p95
- top-k retrieval quality
- missing citation rate

### Policy

- PII precision/recall
- prompt injection detection
- policy block latency
- raw PII log leakage count, 목표값 0

### Node Operations

- heartbeat success rate
- task assignment latency
- failed task retry rate
- slow node exclusion accuracy
- network usage

## Source Notes

- llama.cpp RPC 문서는 RPC backend가 proof-of-concept이며 fragile/insecure라고 경고하므로, GovMesh MVP에서는 RPC를 끕니다.
- SentinelLABS/Censys의 2026-01-29 Ollama 노출 연구는 local LLM API의 public bind 금지와 gateway 승인 원칙을 뒷받침합니다.

## References

- Petals: https://petals.dev/
- Petals paper: https://arxiv.org/abs/2209.01188
- llama.cpp RPC: https://github.com/ggml-org/llama.cpp/blob/master/tools/rpc/README.md
- exo: https://github.com/exo-explore/exo
- Ollama docs: https://docs.ollama.com/
- GPT4All docs: https://docs.gpt4all.io/
- LocalAI: https://localai.io/
- Hermes Agent: https://hermes-agent.org/
- AMD GAIA: https://github.com/amd/gaia
- SentinelLABS/Censys Ollama exposure research: https://www.sentinelone.com/labs/silent-brothers-ollama-hosts-form-anonymous-ai-network-beyond-platform-guardrails/
