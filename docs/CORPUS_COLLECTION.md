# Corpus Collection Procedure

GovMesh 평가 corpus는 실제 개인정보와 실제 정부 내부문서를 저장소에 넣지 않는다는 원칙을 지킵니다.

## Collection Flow

1. 기관 보안 담당자가 수집 범위를 승인합니다.
2. 원본 문서는 기관 내부 격리 위치에서만 보관합니다.
3. 평가용 문장은 개인정보와 내부 식별자를 제거하거나 합성 데이터로 대체합니다.
4. 각 항목은 `should_block`, `expected_kinds`, `source_class`, `reviewer`를 기록합니다.
5. corpus 반입은 Quarantine Gateway를 거칩니다.
6. release gate 전에는 fake PII 범위 검사를 실행합니다.

## JSONL Format

```json
{"id":"case-001","text":"합성 샘플 문장","should_block":false,"expected_kinds":[],"source_class":"synthetic","reviewer":"security"}
```

## Review Rules

- 실제 주민등록번호 금지
- 실제 전화번호 금지
- 실제 이메일 금지
- 실제 내부 문서명 금지
- 민감 패턴은 합성값만 사용
- reviewer 없는 항목은 benchmark에 넣지 않음

## Local Command

```powershell
python scripts/create_corpus_template.py --out samples/policy_corpus_template.jsonl
```
