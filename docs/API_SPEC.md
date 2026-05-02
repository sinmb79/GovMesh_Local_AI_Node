# API Spec Draft

## Control Plane

| Method | Path | Purpose |
|---|---|---|
| POST | `/nodes/register` | 노드 등록 |
| POST | `/nodes/{node_id}/heartbeat` | 노드 상태 보고 |
| GET | `/nodes` | 노드 목록 |
| POST | `/tasks` | 작업 생성 |
| GET | `/tasks/next` | 다음 작업 조회 |
| POST | `/tasks/{task_id}/result` | 작업 결과 보고 |
| POST | `/audit/events` | 감사 이벤트 기록 |
| GET | `/benchmarks` | 벤치마크 결과 목록 |

## Quarantine Gateway

| Method | Path | Purpose |
|---|---|---|
| POST | `/imports/upload` | 반입 파일 업로드 |
| GET | `/imports/{id}` | 반입 상태 조회 |
| POST | `/imports/{id}/scan` | 해시와 위험 패턴 검사 |
| POST | `/imports/{id}/approve` | 승인 |
| POST | `/imports/{id}/reject` | 반려 |
| GET | `/imports/approved` | 승인된 반입물 목록 |

## Skill Registry

| Method | Path | Purpose |
|---|---|---|
| POST | `/skills/drafts` | skill 초안 등록 |
| POST | `/skills/{id}/review` | 검토 요청 |
| POST | `/skills/{id}/approve` | 승인 |
| POST | `/skills/{id}/reject` | 거부 |
| POST | `/skills/{id}/deploy` | 배포 |

## Response Rules

- 정책 차단 응답은 `block_reason`, `risk_level`, `user_message`를 포함해야 합니다.
- 감사 가능한 변경 응답은 `audit_event_id`를 포함해야 합니다.
- PII 원문은 응답 또는 로그에 남기지 않습니다.
