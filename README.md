# Calibre Metadata Source Plugins Korea

Calibre에서 **알라딘·YES24·교보문고**의 도서 메타데이터와 표지를 가져옵니다. 하나의 저장소에서 개발하고 서점별 독립 ZIP 세 개로 배포합니다. 원하는 서점만 설치하거나 모두 설치해 Calibre에서 소스별 사용 여부와 우선순위를 설정할 수 있습니다.

## 설치

| 서점 | Calibre 표시 이름 | v1.2.4 설치 파일 |
| --- | --- | --- |
| 알라딘 | `Aladin.co.kr` | [Aladin ZIP](https://github.com/leechis7/Calibre-Metadata-Source-Plugins-Korea/releases/download/v1.2.4/Calibre-Metadata-Plugin-Aladin-v1.2.4.zip) |
| YES24 | `YES24.com` | [YES24 ZIP](https://github.com/leechis7/Calibre-Metadata-Source-Plugins-Korea/releases/download/v1.2.4/Calibre-Metadata-Plugin-YES24-v1.2.4.zip) |
| 교보문고 | `Kyobobook.co.kr` | [Kyobo ZIP](https://github.com/leechis7/Calibre-Metadata-Source-Plugins-Korea/releases/download/v1.2.4/Calibre-Metadata-Plugin-Kyobo-v1.2.4.zip) |

다른 버전과 변경 내용은 [Releases](https://github.com/leechis7/Calibre-Metadata-Source-Plugins-Korea/releases)와 [CHANGELOG.md](CHANGELOG.md)에서 확인하세요.

1. 원하는 ZIP을 다운로드합니다. 압축을 풀지 않습니다.
2. Calibre `환경설정 → 고급 → 플러그인 → 파일에서 플러그인 불러오기`에서 설치합니다.
3. Calibre를 완전히 종료했다가 다시 실행합니다.
4. `환경설정 → 메타데이터 다운로드`에서 사용할 소스와 옵션을 설정합니다.
5. 도서의 `메타데이터 편집 → 메타데이터 다운로드`를 실행합니다.

최소 Calibre 버전은 5.0.0이며 실제 런타임 검증은 Portable Calibre 9.15.0에서 수행했습니다. YES24·교보 설정은 Calibre 기본 UI를 사용합니다. 알라딘의 표시 이름, `aladin.co.kr` 식별자와 `plugins/Aladin` 설정 저장소는 유지해 업데이트할 수 있습니다.

## 지원 기능

| 기능 | 알라딘 | YES24 | 교보문고 |
| --- | --- | --- | --- |
| 제목·저자·ISBN·출판사·출간일 | 지원 | 지원 | 지원 |
| 책소개·저자소개·출판사 리뷰·목차 | 제공 시 지원 | 제공 시 지원 | 제공 시 지원 |
| 표지 | cover500 / 작은 표지 옵션 | XL | 최대 1000px 요청 |
| 평점·분류 태그·언어 | 지원 | 제공 시 지원 | 제공 시 지원 |
| 시리즈 | 지원 | 제공 시 지원 | 미지원 |

YES24는 국내·외국도서 통합 검색을 사용합니다. YES24·교보는 최대 결과 수, 목차 포함과 분류 태그 사용 여부를 설정할 수 있습니다. ISBN-10/13의 같은 판본을 확인하며, ISBN 없이 검색할 때는 제목·저자를 비교합니다.

개발 중인 변경에서는 세 서점의 판본 비교를 통일합니다. ISBN을 지정하면 체크섬과 ISBN-10/13 변환으로 같은 판본인지 확인하며, 결과가 없더라도 ISBN 조건을 버리지 않습니다. ISBN 없이 검색하면 제목·저자와 명시된 전자책·오디오북·개정판·세트 표기를 비교합니다. 서점이 판본 정보를 생략하면 완전한 구분은 어려우므로 정확한 판본에는 ISBN 검색을 권장합니다. 로그에는 후보 제외 이유와 책 없음·접속 실패·페이지 구조 변경을 구분해 표시합니다.

개발 버전은 교보 상세 페이지가 빈 응답을 반환하면 같은 상품의 API로 정보를 복구합니다. API가 책소개를 제공하지 않으면 해당 섹션은 생략합니다. 소개문의 숨김 문구·중복 섹션·깨진 글자를 걸러내며, 표지는 JPEG·PNG·GIF·WebP의 실제 디코딩과 크기를 검사합니다. 가로·세로 각각 64px 이상, 4천만 화소 이하, 20 MiB 이하의 정상 이미지만 반환합니다.

서점에 등록되지 않은 도서와 제공하지 않는 항목은 가져올 수 없습니다. 저자소개의 한국어·영어 혼합 문구 등 서점 원문의 내용이 그대로 포함될 수 있습니다. 교보의 추가 정보 API가 실패하더라도 기본 도서정보는 반환합니다.

## 개발·빌드·릴리즈

- [개발·빌드 안내](docs/development.md): Windows·Linux 환경 준비, 일괄·개별 ZIP 빌드, 회귀 테스트와 실제 Calibre 검사
- [릴리즈 안내](docs/releasing.md): 버전 변경, 로컬 검증, 승인 후 태그 push와 GitHub Release, 수동·초안 배포 및 실패 대응
- [기여 안내](CONTRIBUTING.md): 버그 신고, 파서 수정과 Pull request 제출

환경을 준비한 뒤 저장소 루트에서 실행하는 기본 명령입니다.

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python scripts/build.py
python scripts/release.py  # 로컬 빌드와 업로드 계획만 표시
```

`dist/`에 독립 ZIP 세 개와 `SHA256SUMS.txt`가 생성됩니다. 각 ZIP에는 해당 서점 코드·공통 모듈·라이선스가 포함됩니다. 실행 의존성은 Calibre가 제공합니다.

GitHub Actions는 `main` push·PR에서 테스트와 빌드를 실행합니다. **`v*` 태그를 push하면 검사 후 공개 Release가 자동 생성됩니다.** 에이전트가 작업할 때 push·태그 push·릴리즈 배포는 저장소 소유자의 사전 승인을 받습니다.

## 문제 신고

[Issues](https://github.com/leechis7/Calibre-Metadata-Source-Plugins-Korea/issues)에서 버그 신고 양식을 사용하세요. 운영체제·Calibre 버전·플러그인 버전, 책 제목·저자·ISBN·상품 URL과 다운로드 로그를 포함하면 재현에 도움이 됩니다. 로그의 개인정보·쿠키·인증 정보는 제거하세요.

## 출처와 라이선스

알라딘 플러그인은 YongSeok Choi(`sseeookk`)의 [원본 GPL-3.0 플러그인](https://github.com/sseeookk/Calibre-Aladin.co.kr-Metadata-Source-Plugin)을 기반으로 한 유지보수 포크입니다. 원본은 Grant Drake의 Goodreads/Barnes 플러그인과 공통 GUI 코드에 기반합니다. 원 저작권 고지와 [GPL-3.0 라이선스](LICENSE)를 유지하고 각 ZIP에도 라이선스를 포함합니다.

`leechis7`는 2026-06-02부터 유지보수했으며 v1.2.0에서 YES24·교보와 모노레포 빌드를 추가했습니다.

[알라딘 MobileRead 포럼](https://www.mobileread.com/forums/showthread.php?t=236797)
