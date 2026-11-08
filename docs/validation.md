# 메타데이터 품질·복구 검증

## v1.2.5 배포 검증 — 2026-11-09

- 권수 비교: `삼국지: 1권`과 `삼국지: 2권`, 하이픈 뒤 권수 및 상·중·하권을 구분합니다. 잘못된 ISBN은 제목 검색으로 우회하지 않습니다.
- 요청 안정성: 세 소스의 메타데이터·표지 GET은 일시적 오류만 한 번 재시도하고 공통 제한 시간을 사용합니다. 알라딘 작업 스레드는 취소와 제한 시간을 공유하며, 상세 응답 수신 중 또는 파싱 후 취소되면 결과·캐시를 저장하지 않습니다.
- 일반 테스트: 92개 중 91개 통과, 실제 Calibre 전용 AJAX 사례 1개는 일반 Python에서 제외됩니다.
- 실제 Calibre 9.13.0 / Ubuntu ARM: 오프라인 회귀 15개 통과. 세 ZIP 설치, 설정 UI 생성·옵션 변경·저장, 새 프로세스에서 플러그인 버전과 설정 유지 확인. 임시 설정과 빈 임시 서재만 사용했습니다.
- GitHub Actions / Ubuntu 22.04 x86_64: Calibre 5.0.0 및 최신 9.18.0에 설치·검색·표지·설정 저장·재시작 검사를 추가했습니다. 태그 배포에서도 두 버전을 다시 검사하고 성공해야 공개합니다.
- 수동 실시간 진단: `트렌드 코리아 2027` / `9791124073483`의 세 서점 제목·ISBN 검색과 표지 다운로드가 여섯 경우 모두 성공했습니다. JSON 보고서는 서점·검색 방식·단계·누락 필드와 관찰된 실패 분류를 담습니다. 실패 시에도 다음 서점 검사를 계속하며, 책소개·목차 미제공은 장애로 단정하지 않습니다.
- Calibre 5.0.0의 최초 검사는 HTTP 오류를 흉내 낸 테스트 응답에 스트림이 없어 실패했습니다. 실제 HTTP 응답처럼 `BytesIO` 스트림을 넣어 테스트를 수정했습니다. 알라딘 설정창에서는 Qt6의 표 항목 타입 및 Qt5 위젯 임포트 문제를 수정했습니다.

아래는 이전 개발 단계의 검증 기록입니다.

## 2026-11-02 개발 단계

2026-11-02, Ubuntu ARM 환경에서 CAL-3·CAL-4·CAL-5·CAL-6·CAL-9·CAL-13에 해당하는 로컬 변경을 검증했습니다. 공개된 v1.2.4와 구분하기 위해 변경 이력은 Unreleased에 기록하며 플러그인 버전은 올리지 않았습니다.

## 검사 범위

- 세 서점의 국내서·외국서·절판 상태 도서: 제목+저자 및 ISBN 검색.
- ISBN-10/13의 동일 판본 허용, 체크섬 오류 및 다른 ISBN의 판본 제외.
- ISBN 검색 실패 또는 상품 ID 재검색 시 ISBN 제약 유지, 다른 판본의 캐시 오염 방지.
- 제목 일부만 같은 책, 다른 권수, 다른 저자, 원서/번역서 제목, 전자책·오디오북·개정판·세트 표시 비교.
- 검색 결과 없음, 상품 404, 접속 실패, 페이지 구조 변경, 후보 제외 이유의 진단 로그.
- 교보 HTML이 계속 빈 상태에서 같은 상품 ID의 info·top API 복구, 잘못된 상품 ID·ISBN·API 오류 및 복구 중 취소.
- JPEG·PNG·GIF·WebP 디코딩, 손상·HTML·과도한 크기·64px 미만 표지 거부 및 다운로드 후 취소.
- 소개문의 숨김 문구·버튼·중복 섹션·깨진 글자·미정의 값과 다른 상품의 설명 거부.
- 기존 취소·제한 시간·세션 리다이렉트·교보 빈 응답 복구·표지 캐시·독립 ZIP 빌드 검사.

추가 카탈로그 응답은 합성 자료입니다. 절판 여부나 현재 서점 재고를 확인한 자료가 아닙니다. 원서·번역서가 같은 제목을 쓰거나 서점이 판본 표시를 생략한 경우 ISBN 없이 완전하게 구분할 수 없습니다.

## 실행 결과

| 검사 | 결과 |
| --- | --- |
| 가상환경 Python 3.14.7의 일반 회귀 테스트 | 80개 통과 |
| 세 서점 독립 ZIP 및 SHA-256 빌드 | 성공 |
| 실제 Calibre 9.13.0 오프라인 카탈로그 회귀 검사 | 세 서점에 걸친 11개 테스트 메서드 통과 |
| YES24 실시간 제목·ISBN 검색 및 표지 | 트렌드 코리아 2027, ISBN 9791124073483 통과 |
| 알라딘 실시간 제목·ISBN 검색 및 표지 | 같은 책 통과 |
| 교보 실시간 제목·ISBN 검색 및 표지 | 같은 책을 info·top API로 복구해 통과. 표지 140,214바이트 |
| 교보 외국도서 실시간 제목+저자·ISBN 검색 및 표지 | AI Governance in Practice, ISBN 9781807300814 통과. 표지 98,655바이트 |

일반 회귀 테스트에서 합성 카탈로그는 YES24·교보 경로를 실행하고, 실제 Calibre 실행에서는 알라딘을 포함한 세 서점을 실행합니다. Calibre는 저장소의 `.dev-deps` 아래 별도 설정 폴더를 사용했습니다. 사용 중인 서재에는 접근하지 않았습니다. 두 Calibre 검사 도구는 매번 임시 설정 폴더와 새 프로세스로 실행해 이전 ZIP 모듈이 재사용되지 않도록 합니다.

## 실행 명령

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/build.py
CALIBRE_CONFIG_DIRECTORY="$PWD/.dev-deps/calibre-offline-settings" calibre-debug -e scripts/regression_calibre.py
CALIBRE_CONFIG_DIRECTORY="$PWD/.dev-deps/calibre-live-yes24" calibre-debug -e scripts/smoke_calibre.py -- --store yes24
CALIBRE_CONFIG_DIRECTORY="$PWD/.dev-deps/calibre-live-aladin" calibre-debug -e scripts/smoke_calibre.py -- --store aladin
CALIBRE_CONFIG_DIRECTORY="$PWD/.dev-deps/calibre-live-kyobo" calibre-debug -e scripts/smoke_calibre.py -- --store kyobo
```

## 교보 복구 동작

변경 전에는 상세 HTML이 세 번 모두 비어 실시간 검사에 실패했고, 원래 HEAD 코드에서도 같은 현상을 재현했습니다. 지금은 info API의 상품 ID와 ISBN, top API의 연결 상품 ID를 대조해 동일 상품의 정보를 복구합니다. API에서 제공되지 않은 책소개는 생략하며 다른 책의 소개로 채우지 않습니다. 목차·저자소개·서평은 같은 상품의 middle API가 제공하는 항목만 사용합니다.

## 남은 제한

교보 API가 제공하지 않는 책소개·언어 등은 비어 있을 수 있습니다. Calibre 최소 지원 버전 및 최신 버전의 설치·설정 UI 검증은 이 결과로 완료 처리하지 않습니다. 2026-11-02 Jira에서 CAL-3·CAL-4·CAL-6에 이어 CAL-5·CAL-9·CAL-13도 완료 상태로 갱신했습니다. 원격 push·릴리스 공개는 수행하지 않았습니다.
