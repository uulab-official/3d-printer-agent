# 3D Printer Agent

[![CI](https://github.com/uulab-official/3d-printer-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/uulab-official/3d-printer-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**An open-source local workspace for parameterized CAD, filament profile review, and Bambu Studio preparation.**

한국어 요청으로 치수가 있는 모델을 만들고, 필라멘트 설정의 근거를 확인하며, Bambu Studio 슬라이싱을 준비하는 **개발 초기 버전 v0.1**입니다. [uulab-official/3d-printer-agent](https://github.com/uulab-official/3d-printer-agent)에서 개발합니다. API 키 없이 로컬 CAD 생성과 설정 검토를 사용할 수 있습니다.

이 버전은 `수납함`, `열린 케이블 받침`, `원형 인셋 프레임` 세 가지 파라메트릭 모델을 실제 CAD로 생성합니다. 일반적인 자유형 모델링, MakerWorld 검색·리믹스, 실시간 쇼핑 수집, 프린터 직접 제어는 후속 개발 범위입니다. [현재 개발 상태](docs/STATUS.md), [로컬 검증 기록](docs/VERIFICATION.md), [기여 안내](CONTRIBUTING.md)를 함께 확인하세요.

![실제 생성한 세 CAD 모델](examples/model-preview.png)

위 이미지는 생성한 STEP 형상과 앱의 Canvas 렌더 코드를 사용한 결과입니다. 실제 브라우저 화면이나 실물 출력 사진은 아닙니다.

## 시작하기

검증 환경은 Linux와 Python 3.12.14입니다. 새 PC에서는 Python 3.12 가상환경을 권장합니다. Windows·macOS의 설치와 native Bambu 실행은 아직 별도로 검증하지 않았습니다.

저장소를 받은 다음 프로젝트 폴더로 이동합니다.

```bash
git clone https://github.com/uulab-official/3d-printer-agent.git
cd 3d-printer-agent
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m print_agent
```

Windows PowerShell에서는 가상환경 활성화 대신 다음처럼 실행할 수도 있습니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m print_agent
```

브라우저에서 `http://127.0.0.1:8765`를 엽니다. 서버는 자신의 PC에서만 접속할 수 있는 주소에 바인딩합니다. 종료는 `Ctrl+C`입니다. CadQuery를 처음 설치할 때는 CAD 엔진 의존성을 다운로드하므로 시간이 걸릴 수 있습니다.

```bash
python -m print_agent doctor
python -m print_agent --port 8766 --data-dir ./my-print-data
python -m unittest discover -v
```

UI 상태 회귀 검사는 개발용 Node.js가 있을 때 `node tests/test_ui_state.cjs`로 실행할 수 있습니다. DOM 대역을 사용하는 검사이며 실제 브라우저 테스트와 구분합니다.

CI는 Python 검사와 패키지 설치, UI 상태 검사, 실제 Chromium에서의 브라우저 검사를 실행하도록 구성했습니다. 실행 결과는 [GitHub Actions](https://github.com/uulab-official/3d-printer-agent/actions)에서 커밋별로 확인합니다. 브라우저 검사에는 개발용 Node.js가 필요하며 실행 방법은 [기여 안내](CONTRIBUTING.md)를 따릅니다.

개발 소스에서 실행하는 방법이며 `pip install .` 후 `printer-agent` 진입점도 제공합니다. 패키지 설치는 별도 PC에서 아직 검증하지 않았습니다. API 키 없이 템플릿 모드와 실제 CAD 생성이 동작합니다.

## 사용할 수 있는 작업

| 기능 | 현재 동작 | 확인 범위 |
|---|---|---|
| 처음 만들 물건 | 세 가지 기본 템플릿과 용도 소개 | 개인 맞춤 추천 엔진은 후속 범위 |
| 한국어 요청 | mm/cm, 가로·세로·높이, 칸 수 등을 해석 | 규칙 기반 템플릿 모드. 자유로운 대화 이해를 보장하지 않음 |
| 모델 만들기 | CadQuery의 실제 솔리드와 미리보기 메시 생성 | 유효 형상, 연결된 솔리드 하나, 체적, 요청 치수, 닫힌 미리보기 메시 |
| 내보내기 | STL·STEP·3MF·재생산용 Python·SHA-256 manifest | 실제 파일 생성 및 STEP 재읽기 검사 |
| 재료 설정 | JSON·적용 범위·제품 식별·미해결 상속·필수 수치 검토 | 제조사 진위와 전체 슬라이서 스키마 검증은 미구현 |
| 교정 변경 검토 | K, flow ratio, MVS 기록의 재검토 필요성 판정 | API 제공. 측정이나 프린터 저장은 하지 않음 |
| Bambu Studio | 실행 파일 탐지, full config 준비, CLI 어댑터 | 현재 개발 환경에 미설치. 테스트용 실행 대역으로 계약 검증 |
| 구매 비교 | 직접 입력한 가격·중량·배송비로 kg당 단가 계산 | 실시간 가격·재고·쿠폰은 수집하지 않음 |
| 작업 기록 | 생성 파라미터·파일·이벤트·사용자 출력 결과 | 사용자 결과는 `user_reported`로 구분 |
| LLM 연결 | OpenAI-compatible Chat Completions 어댑터 | 합성 서버 응답으로 계약 검증. 실제 모델 연결은 미검증 |

### 첫 요청 예시

```text
가로 12cm 세로 8cm 높이 3.5cm 수납함을 3칸으로 만들어줘
14cm x 9cm x 4cm 수납함
가로 80mm 세로 18mm 높이 12mm 케이블 받침, 홈 5개
52mm 포토마그넷 프레임 만들어줘
```

제작안에 입력하지 않은 치수의 기본값을 표시합니다. 생성 전 편집할 수 있습니다. `칸 3개`는 칸막이 2개라는 뜻입니다. 원형 인셋의 `fit_clearance=0.3`은 지름 전체에 0.3mm를 더하며, 한쪽당 0.3mm라는 뜻이 아닙니다. 케이블 받침은 위가 열린 홈이며 스냅 고정장치가 아닙니다. 프레임은 원판용 포켓이며 자석·접착·실물 끼워맞춤을 검증하지 않습니다.

모델 3MF에는 형상만 들어 있습니다. 출력 준비가 끝난 G-code 프로젝트가 아닙니다. 인필·서포트·출력 시간·필라멘트 무게는 실제 슬라이싱 후에만 확정할 수 있으며, 이번 버전은 그 통계의 버전별 파서를 구현하지 않아 `null`을 반환합니다.

`examples/`에는 실제 생성한 세 모델과 재생산 소스가 포함됩니다. 앱에서 내려받은 `model.py`는 다음과 같이 새로운 폴더에 같은 형상을 다시 만듭니다.

```bash
python model.py ./reproduced
```

## 필라멘트 설정 검토

숫자를 자동 추정하지 않습니다. 먼저 제품 라벨·정확한 SKU와 현재 프린터 조건을 입력합니다.

`setup`에 필요한 값:

```json
{
  "printer_model": "현재 프린터의 정확한 모델명",
  "printer_preset": "Bambu Studio의 정확한 프린터 프리셋 이름",
  "nozzle_diameter": 0.4,
  "plate_type": "Textured PEI Plate",
  "extruder": "사용 중인 압출기 식별자",
  "feed_mode": "사용 중인 외부 스풀 또는 정확한 AMS 구성 식별자",
  "material_id": "제조사·제품·재료·색상 등을 구분하는 정확한 제품 ID",
  "material_identity_status": "exact"
}
```

위의 0.4와 플레이트는 입력 형식을 보여주는 예시입니다. 사용 중인 장비값으로 바꾸어야 합니다. 단순히 PLA라고만 입력하면 정확한 제품이 확인된 것으로 취급하지 않습니다.

raw Bambu 필라멘트 JSON 또는 다음 envelope를 받습니다.

```json
{
  "id": "프로필 식별자",
  "settings": {},
  "scope": {},
  "source": {
    "authority": "manufacturer",
    "url": "원문 URL",
    "publisher": "발행처",
    "retrieved_at": "확인 시각"
  },
  "validation": {
    "status": "unverified",
    "setup_fingerprint": {}
  }
}
```

빈 `settings`·`scope`는 설명용 구조이며 준비 가능한 설정이 아닙니다. `scope`에는 현재 설정과 대응하는 일곱 장비·재료 조건이 필요합니다. `compatible_printers`의 정확한 프리셋 일치는 `scope.printer_preset` 근거를 대신할 수 있습니다. 다른 모델과 비슷한 이름이라는 이유로 호환 판정을 내리지 않습니다.

준비 가능 판정에는 다음 값이 필요합니다.

- `nozzle_temperature`, `nozzle_temperature_initial_layer`
- `filament_flow_ratio`, `filament_max_volumetric_speed`
- 선택한 플레이트에 대응하는 온도와 첫 레이어 온도
- 해소된 `inherits`·`include`, 명확한 프로필 ID와 적용 범위

현재 플레이트 필드 대응은 Textured PEI, Smooth PEI/High Temp, Engineering, Cool Plate, Bambu Cool Plate SuperTack입니다. 미지원 플레이트나 압출기별 배열 대응이 불분명하면 추가 근거를 요청합니다. 원본 필드를 보존하고, 해석하지 못한 실행 관련 값은 자동 준비를 막습니다.

`ready_to_prepare`는 제한된 설정 검토를 통과했다는 뜻입니다. 공급자 인증·전체 스키마 검증·실물 출력 성공의 증거가 아닙니다. 사용자가 출처를 `manufacturer`라고 입력해도 외부 확인이 완료됐다고 표시하지 않습니다. 같은 장비에서 검증했다는 입력은 `reported_validated`로 표시합니다.

## Bambu Studio 연결

Bambu Studio의 공식 CLI 사용 문서는 [Command-Line-Usage](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage)입니다. 어댑터는 해당 방식으로 전체 machine/process/filament 구성을 준비합니다. 실제 설치 버전의 `--help`에서 필요한 옵션을 확인한 뒤 실행합니다.

OS의 알려진 설치 경로와 PATH를 탐지합니다. 찾지 못하면 **자신이 설치한 실행 파일**의 절대 경로를 지정하고 앱을 다시 시작합니다.

```bash
export PPA_BAMBU_PATH="/absolute/path/to/bambu-studio"
python -m print_agent
```

```powershell
$env:PPA_BAMBU_PATH = "C:\Program Files\Bambu Studio\bambu-studio.exe"
.\.venv\Scripts\python.exe -m print_agent
```

위 경로는 예시입니다. 앱이 실행 파일을 찾았다는 것과 해당 버전의 CLI가 검증됐다는 것을 구분합니다. Linux AppImage는 시스템 실행에 필요한 환경이 별도로 필요할 수 있습니다. Mac/Windows 경로 발견 코드는 있지만 해당 OS의 native 실행은 아직 시험하지 않았습니다.

슬라이싱 입력 묶음은 다음 구조입니다.

```json
{
  "source": "user_export",
  "machine": {},
  "process": {},
  "filaments": [{}]
}
```

빈 객체는 형식 예시이며 실행할 수 없습니다. 사용자 장비의 **상속을 해소한 전체 설정**을 넣어야 합니다. Bambu의 개별 사용자 프리셋 내보내기는 상속된 차이값만 포함할 수 있어 그대로 사용할 수 없습니다. 이 버전은 자동 상속 해석기를 포함하지 않습니다. 설정 파일을 조작해 상속 필드만 지우는 방법은 전체 설정을 만드는 방법이 아닙니다.

어댑터의 지원 검사 범위는 식별자, FFF 장비·노즐·출력 영역, 시작/종료 G-code, 레이어·벽·인필·일부 속도, 재료·지름·밀도·flow·MVS·노즐·베드 온도입니다. 전체 Bambu 스키마를 검증하지 않습니다. 호스트 후처리 프로그램과 임의 CLI 옵션은 허용하지 않습니다.

실행 결과는 종료 코드만으로 성공 처리하지 않습니다. 새로운 3MF의 ZIP 무결성, 비어 있지 않은 G-code, 핵심 설정 read-back을 검사합니다. 설정을 확인하지 못하거나 요청값과 다르면 `needs_review`입니다. 이 파일을 실제 프린터에 보내는 동작은 구현하지 않았습니다.

## 로컬 또는 웹 LLM

이 버전의 LLM 모드는 **OpenAI-compatible `/chat/completions` 프로토콜**을 받는 서버를 대상으로 합니다. 특정 서비스의 현재 모델명·주소는 해당 서버 문서를 확인하고 지정하세요.

```bash
export PPA_LLM_BASE_URL="http://127.0.0.1:1234/v1"
export PPA_LLM_MODEL="your-served-model-id"
# 인증을 요구하는 서버인 경우에만:
export PPA_LLM_API_KEY="your-key"
python -m print_agent
```

PowerShell에서는 `$env:PPA_LLM_BASE_URL`, `$env:PPA_LLM_MODEL`, `$env:PPA_LLM_API_KEY`를 사용합니다. 원격 서버는 HTTPS만 허용하고, HTTP는 loopback 주소에 한정합니다. 환경변수는 앱을 시작한 프로세스에서 읽습니다. `.env` 파일 자동 로딩은 제공하지 않습니다.

LLM 모드를 선택하면 입력한 요청과 파라미터 스키마를 지정한 서버에 보냅니다. API 키를 브라우저에 보내거나 작업 파일에 저장하지 않습니다. 템플릿 모드는 외부 LLM 요청을 보내지 않습니다. 이 연결은 ChatGPT/다른 웹사이트의 로그인 세션을 자동 조작하는 기능이 아닙니다.

LLM은 허용된 템플릿의 숫자와 설명만 제안합니다. 실행 코드·shell 명령·임의 도구 이름은 스키마에서 거부합니다. CAD 생성은 로컬의 고정된 모델 함수가 수행합니다. 서버 응답 계약을 테스트했으며 실제 LLM의 한국어 이해 성능은 별도 평가가 필요합니다.

## 구매 비교와 기록

상품명, 통화, 가격, 중량(g), 배송비를 직접 입력합니다. 배송비를 비우면 `미확인`이며 무료 배송으로 계산하지 않습니다. 배송비를 확인해 0을 넣은 경우만 무료로 계산합니다. 통화가 다르면 별도로 정렬합니다. 최소 중량은 0.001g이며 배송비 포함 kg당 단가는 소수 두 자리까지 반올림합니다. 세금·쿠폰·재고·제품 동일성 확인은 후속 작업입니다.

작업 데이터는 기본 `./data/` 아래에 저장됩니다. `PPA_DATA_DIR` 또는 `--data-dir`로 바꿀 수 있습니다. 작업별 폴더에는 모델 파일, 파라미터, SHA-256 manifest, 이벤트가 있고 SQLite는 기록 목록의 인덱스입니다. `manifest.json`은 생성 시점의 형상 증거이고, 후속 슬라이싱·사용자 결과는 `job.json`의 별도 기록입니다.

사용자가 성공이라고 입력해도 프로그램이 실제 프린터를 관찰한 것으로 바꾸지 않습니다. 향후에는 장비·제품·습도·교정·출력 사진과 결과를 연결하여 설정 개선에 사용할 계획입니다.

## 코드 구조와 다음 개발

```text
print_agent/
  app.py          로컬 API·요청 경계
  planner.py      규칙 파서·선택적 LLM 어댑터
  geometry.py     세 가지 CadQuery 템플릿·실제 파일 내보내기
  profiles.py     재료 근거·호환성·교정 유효성 검토
  slicer.py       Bambu CLI 준비·실행·결과 read-back
  offers.py       입력된 상품의 배송비 포함 단가
  storage.py      작업 폴더·manifest·SQLite 기록
  static/         한국어 반응형 UI·실제 메시 뷰어
tests/            CAD·설정·어댑터·API 테스트
examples/         실제 생성 모델과 소스
docs/             구현 계약·검증 결과·제품 로드맵·평가 기준
```

공식 문서의 최신 내용을 검색하고 출처를 남기는 지식 계층, 사용자 프리셋 상속 해석, 실제 장비 통합 테스트, 모델 권리·원본 형태를 확인하는 커스텀 기능이 다음 핵심 작업입니다. [제품 로드맵](docs/PRODUCT_ROADMAP.md)과 [벤치마크 제안](docs/BENCHMARKS.md)에 후속 범위와 평가 조건을 정리했습니다.

상용 웹사이트 운영에 필요한 계정·결제·원격 기기 인증·백업·팀 권한·업데이트 배포는 포함하지 않습니다. 이 앱을 공용 인터넷에 그대로 공개하는 배포 형태도 제공하지 않습니다. 웹사이트와 로컬 실행기를 분리하는 다음 단계의 기반으로 사용합니다.
