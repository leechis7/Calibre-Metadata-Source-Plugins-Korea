# 개발·빌드 안내

## 요구 사항

- Git과 Python. 일반 ZIP 빌드의 최소 버전은 Python 3.8이며, 개발에는 CI와 같은 Python 3.11을 권장합니다.
- 회귀 테스트에는 `requirements-dev.txt`의 lxml·mechanize·Pillow가 필요합니다.
- 실제 플러그인 검사는 설치된 Calibre의 `calibre-debug`로 실행합니다. 일반 Python과 별도 런타임입니다.

Calibre 플러그인은 Python 패키지를 pip로 배포하는 대신 ZIP으로 설치합니다. 빌드한 ZIP에는 서점별 코드와 공통 코드가 함께 들어가며, 설치 후 런타임 의존성은 Calibre가 제공합니다.

## 환경 준비

저장소를 복제한 뒤 루트에서 명령을 실행합니다.

```sh
git clone https://github.com/leechis7/Calibre-Metadata-Source-Plugins-Korea.git
cd Calibre-Metadata-Source-Plugins-Korea
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/build.py
```

Linux·macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/build.py
```

가상환경을 활성화한 뒤에는 아래 예제의 `python` 명령을 그대로 사용해도 됩니다. 활성화하지 않았다면 해당 가상환경의 Python 경로로 바꿔 실행하세요.

### Ubuntu ARM에서 이어서 개발하기

유지보수 개발환경은 Ubuntu ARM으로 이전합니다. 위 Linux 명령으로 가상환경을 만들고 회귀 테스트와 ZIP 빌드를 실행합니다. ZIP에는 Python 소스와 리소스를 포함하므로 ARM 전용 설치 파일을 따로 만들지 않습니다.

mise로 Python을 관리한다면 사용할 버전을 선택한 뒤 `mise exec -- python -m venv .venv`로 가상환경을 만들 수 있습니다. CI는 Python 3.11을 사용하며, 로컬 Python 버전이 다르면 함께 기록하세요.

Ubuntu ARM에서의 실행 검증은 아직 수행하지 않았습니다. 새 환경에서 테스트·빌드를 다시 실행하고, 실제 Calibre 검사는 해당 환경에서 동작하는 Calibre의 `calibre-debug`를 사용하세요. Windows Portable Calibre 실행 파일은 Linux 검사에 사용하지 않습니다.

## 저장소와 ZIP 구조

```text
plugins/aladin/          알라딘 코드·설정·번역
plugins/yes24/           YES24 코드·설정
plugins/kyobo/           교보 코드·설정
shared/                 각 ZIP에 포함되는 공통 모듈
scripts/                빌드·릴리즈·실시간 검사 도구
tests/fixtures/         축약한 서점 응답 자료
docs/                   개발·릴리즈 안내
.github/                CI와 이슈·PR 양식
```

`scripts/build.py`가 `shared/*.py`를 각 ZIP 루트로 복사하고 서점 코드, 고유한 `plugin-import-name-*.txt`, 라이선스를 포함합니다. 플러그인마다 서로 다른 `calibre_plugins` 네임스페이스를 사용합니다.

```sh
python scripts/build.py                     # 세 서점 일괄 빌드
python scripts/build.py yes24               # YES24만 빌드
python scripts/build.py --output-dir dist   # 출력 폴더 지정
```

현재 버전이 1.2.4라면 `dist/`에 다음 파일이 생성됩니다.

```text
Calibre-Metadata-Plugin-Aladin-v1.2.4.zip
Calibre-Metadata-Plugin-YES24-v1.2.4.zip
Calibre-Metadata-Plugin-Kyobo-v1.2.4.zip
SHA256SUMS.txt
```

빌드는 Python 문법, 필수 마커, 파일 이름 충돌과 일괄 빌드 시 버전 일치를 확인합니다. ZIP은 파일 순서·타임스탬프를 고정해 같은 환경과 소스로 재현할 수 있게 만듭니다. ZIP과 가상환경은 Git에 포함하지 않습니다.

한 서점만 빌드하면 `SHA256SUMS.txt`도 그 실행에서 만든 ZIP만 포함하도록 덮어씁니다. 릴리즈 직전에는 반드시 세 서점을 일괄 빌드하세요.

## 검증 단계

회귀 테스트는 네트워크 없이 응답 자료와 작은 Calibre API 대역으로 실행합니다. 실제 mechanize 응답 객체도 사용하지만, Calibre 앱 설치 검사를 대신하지는 않습니다.

```sh
python -m unittest discover -s tests -v
```

Calibre가 설치된 환경에서는 빌드한 세 ZIP을 실제 로더·Metadata로 검사하는 오프라인 회귀 검사도 실행할 수 있습니다. 이 검사는 합성 HTTP 응답을 사용하며 서점에는 접속하지 않습니다. 별도 설정 폴더에 테스트용 플러그인을 설치합니다.

```sh
python scripts/build.py
CALIBRE_CONFIG_DIRECTORY="$PWD/.dev-deps/calibre-offline-settings" calibre-debug -e scripts/regression_calibre.py
```

검사 사례와 최근 실행 결과는 [검증 기록](validation.md)을 참고하세요.

실시간 HTTP 검사에는 인터넷 연결이 필요합니다. 상품 정보·사이트 상태에 따라 실패할 수 있어 CI에서는 자동 실행하지 않습니다.

```sh
python scripts/smoke.py --store kyobo
python scripts/smoke_mechanize.py --store yes24
```

실제 Calibre 검사는 먼저 ZIP을 빌드한 뒤 별도 설정 폴더로 실행합니다. 이 도구는 설정 폴더가 저장소 내부인지 확인하고 그곳에 플러그인을 설치합니다. 사용 중인 서재와 Portable 설정을 지정하지 마세요.

Windows PowerShell 예제:

```powershell
$previousCalibreConfig = $env:CALIBRE_CONFIG_DIRECTORY
$env:CALIBRE_CONFIG_DIRECTORY = Join-Path (Get-Location) '.dev-deps\calibre-smoke-settings'
try {
    & 'C:\tools\Calibre Portable\Calibre\calibre-debug.exe' -e scripts/smoke_calibre.py
    & 'C:\tools\Calibre Portable\Calibre\calibre-debug.exe' -e scripts/smoke_calibre.py -- --store yes24 --title 'The Book of Debugging' --isbn 9781718504066 --author 'Johannes Kuhlmann' --allow-missing-toc
    & 'C:\tools\Calibre Portable\Calibre\calibre-debug.exe' -e scripts/smoke_calibre.py -- --store kyobo --title 'AI Governance in Practice' --isbn 9781807300814 --author 'Hemang Doshi' --allow-missing-toc
} finally {
    if ($null -eq $previousCalibreConfig) {
        Remove-Item Env:CALIBRE_CONFIG_DIRECTORY
    } else {
        $env:CALIBRE_CONFIG_DIRECTORY = $previousCalibreConfig
    }
}
```

Calibre 실행 파일 경로는 자신의 설치 위치에 맞게 바꾸세요. 위 예제는 테스트가 끝나면 기존 설정 환경변수를 복원합니다.

Linux·macOS에서 `calibre-debug`가 PATH에 있으면 다음처럼 실행합니다.

```sh
CALIBRE_CONFIG_DIRECTORY="$PWD/.dev-deps/calibre-smoke-settings" calibre-debug -e scripts/smoke_calibre.py
```

`--store`는 `all`·`aladin`·`yes24`·`kyobo`, `--title`·`--isbn`은 시험할 책, `--author`는 제목 검색에 포함할 저자를 지정합니다. 목차를 제공하지 않는 상품에는 `--allow-missing-toc`을 지정합니다. 이 검사는 실제 Calibre 로더·브라우저·메타데이터를 사용하며 GUI 조작 확인은 별도로 진행합니다.

## 자주 발생하는 문제

- lxml·mechanize를 찾을 수 없음: 테스트에 쓰는 Python으로 의존성을 설치했는지 확인합니다.
- 서점에 책이 없음: 해당 서점의 상품 페이지를 확인합니다. 다른 서점에서 찾았더라도 같은 책이 등록돼 있다고 단정할 수 없습니다.
- 로그의 플러그인 버전이 오래됨: 사용하는 Calibre 설정에 ZIP을 설치하고 앱을 완전히 종료했다가 재시작합니다.
- 빈 응답·사이트 구조 변경: 서점 URL, ISBN, 발생 시점과 로그를 첨부해 버그를 신고합니다.

## 수동 서점 진단과 호환성 검사

`python scripts/smoke.py --report .dev-deps/live-report.json`은 빌드한 ZIP을 실제 Calibre로 설치해 세 서점의 제목·ISBN 검색과 표지를 검사합니다. 교보 API 복구도 실제 플러그인과 같은 경로로 실행합니다. 첫 실패 후에도 나머지 검사를 계속하고 JSON에 서점·단계·관찰된 실패 분류·누락 필드·로그를 남깁니다. `partial_metadata`는 서점이 제공하지 않는 소개·목차 등의 경고이며, 장애나 파서 오류로 단정하지 않습니다. `unknown_failure`와 `mixed_failure`는 추가 확인이 필요한 상태입니다. 이 검사는 수동 실행이며 자동 일정은 만들지 않습니다.

`calibre-debug -e scripts/compat_calibre.py`는 임시 설정과 빈 임시 서재에서 세 ZIP의 설치·설정 UI 생성·옵션 변경·저장·새 프로세스에서 설정 유지를 확인합니다. 사용자 서재는 열지 않습니다. GitHub Actions는 최소 Calibre 5.0.0 및 실행 시점의 최신 공식 Calibre에서 이 검사와 오프라인 검색·표지 회귀 검사를 수행하며, 두 버전의 성공을 릴리스 조건으로 사용합니다.
