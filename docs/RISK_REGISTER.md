# Risk Register

| ID | 위험 | 영향 | MVP 대응 | 검증 |
|---|---|---|---|---|
| R-001 | 구형 PC에서 추론이 느림 | 사용자 반발, 도입 실패 | safe mode, context 제한, RAG/스캔 우선 | G0/G1 profile benchmark |
| R-002 | 분산 추론 네트워크 병목 | 성능 저하 | 대형 모델 샤딩 제외, batch 작업 우선 | slow node simulation |
| R-003 | Windows/WSL 호환성 | 설치 실패 | Windows native Python, no-admin local mode | Windows path tests |
| R-004 | local LLM API 외부 노출 | 데이터 유출, 자원 남용 | `127.0.0.1` 기본 bind, gateway 승인 | public bind detection test |
| R-005 | 개인정보 로그 유출 | 법적/신뢰 문제 | raw prompt 저장 금지, mask/hash | log leakage grep |
| R-006 | RAG prompt injection | 정책 우회, 잘못된 응답 | injection scanner, quoted evidence | malicious sample tests |
| R-007 | 모델 환각 | 행정 오류 | context 기반 답변, confidence, 사람 검토 | no-citation answer fail |
| R-008 | 자동 skill 실행 위험 | 감사/책임 불명확 | draft-review-approve-deploy workflow | unapproved skill denial |
| R-009 | 모델 라이선스 충돌 | 배포/조달 문제 | model registry license 필수 | missing license reject |
| R-010 | 사용자 불신 | 도입 저항 | 수집 항목 표시, pause/resume, CPU 제한 | notice and pause tests |
| R-011 | API 토큰 누락 또는 과권한 토큰 | 내부 API 오남용 | 역할별 bearer token, 운영 진입점 토큰 필수 | auth-enabled API tests |
| R-012 | 감사로그 사후 조작 | 사고 조사 신뢰도 하락 | hash chain + optional HMAC signature | signed audit tests |
| R-013 | 압축파일 기반 반입 우회 | 악성 파일 반입 | zip traversal/size/nested archive checks | quarantine zip tests |
| R-014 | 민감 chunk의 RAG 근거 사용 | 개인정보가 답변 근거로 재노출 | sensitive chunk default exclusion | RAG exclusion tests |
| R-015 | 승인 flag만으로 로컬 실행파일 실행 | 악성 wrapper/model 실행 | executable/model SHA-256 pinning | runtime integrity tests |
