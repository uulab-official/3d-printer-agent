# 필라멘트 프리셋 가져오기와 상속 검토

작성일: 2026-11-13 (Asia/Seoul).

관련 JSON 파일을 함께 가져와 선택한 필라멘트 프리셋에 명시된 설정을 연결하고, 각 값이 어느 파일에서 왔는지 확인하는 기능입니다. 부모에서 받은 값과 자식이 바꾼 값을 구분한 뒤, 기존 프로필 검토기로 현재 장비·재료 조건을 검토합니다.

**상속 해석 완료는 Studio의 전체 설정 완성이나 출력 검증을 의미하지 않습니다.** 업로드하지 않은 기본값을 만들어 넣지 않으며, 결과 보고서를 Bambu Studio에 바로 가져올 수 있는 완전한 프리셋으로 취급하지 않습니다. 이 기능은 온도·유량·속도를 자동 추천하거나 프린터에 적용하지 않습니다.

## 화면에서 사용하는 순서

1. 왼쪽 메뉴의 **재료 설정**을 엽니다.
2. **JSON 파일 추가**에서 사용할 프리셋과 부모 프리셋들을 선택합니다. 여러 파일을 한 번에 선택하거나, 나중에 파일을 추가할 수 있습니다. Studio 내보내기 `.bbsflmt`·`.bbscfg`·`.zip`은 **Studio 내보내기 가져오기**를 사용합니다. 형식과 범위는 [묶음 가져오기 안내](FILAMENT_ARCHIVES.md)를 참고하세요.
3. **검토할 프로필** 선택 상자(`profile-target`)에서 최종 검토 대상을 고릅니다. 목록에는 JSON의 이름과 파일명이 함께 표시됩니다.
4. 아래 JSON 편집창에서 선택한 문서의 편집본을 확인합니다. 다른 문서로 선택을 바꾸어도 각 문서의 편집본은 유지됩니다. 가져온 원래 JSON은 별도로 보존합니다.
5. **내 프린터와 재료**에 실제 장비 조건과 정확한 재료 식별 정보를 입력하고 **프로필 검토하기**를 누릅니다. 모르는 정보는 비워 두면 추가 확인 대상으로 표시됩니다.
6. **설정이 어디에서 왔나요?**에서 부모부터 대상까지의 연결, 각 설정의 최종값·출처, 덮어쓰기 기록을 확인합니다. 그 아래에는 같은 입력 조건에 대한 프로필 검토 결과가 표시됩니다.
7. 필요한 경우 **검토 보고서 다운로드**로 `filament-review.json`을 저장합니다. 보고서에는 검토에 제출한 편집본, 처음 가져온 JSON, 설정 출처와 당시 장비 조건이 들어 있습니다.

부모 파일이 빠졌다면 결과에 필요한 정확한 프리셋 이름이 표시됩니다. 해당 이름을 가진 JSON을 **JSON 파일 추가**로 가져온 뒤 다시 검토하세요. 파일명을 비슷하게 바꾸거나 다른 프리셋의 이름을 부모 이름처럼 수정하는 것으로 부족한 근거를 대신하지 않습니다.

파일 추가는 기존 모음에 덧붙이는 동작입니다. 원본 JSON 내용이 같은 파일은 건너뛰고 기존 편집본을 유지합니다. 같은 이름의 다른 내용은 이번 추가 전체를 중단하고 충돌한 이름을 안내합니다. 잘못 추가한 문서는 **선택 파일 제거**로 하나만 제거하고, 편집본은 **원본으로 되돌리기**로 복원할 수 있습니다. 전체 모음을 교체하려면 **파일 모음 비우기**를 사용하세요. 모음을 비워도 현재 편집창의 JSON은 남아 단일 프로필로 검토할 수 있습니다.

파일 모음 없이 JSON만 붙여 넣으면 기존 단일 프로필 검토 경로를 사용합니다. 현재 JSON을 파일 모음에 추가하면 그 입력을 비교 원본으로 보존하고 주요 설정 편집과 상속 보고서를 사용할 수 있습니다. 작업 이름을 붙여 **이 PC에 저장**하면 원본·편집본·선택 대상·사용 조건을 다시 열 수 있습니다. 자세한 흐름과 편집·충돌 규칙은 [필라멘트 작업 안내](FILAMENT_WORKSPACES.md)를 따릅니다.

## 결과가 오래된 입력을 보여 주지 않도록 하는 처리

다음 변경은 기존 검토 결과와 보고서 다운로드 링크를 즉시 무효화합니다.

- JSON 편집 또는 검토 대상 변경
- 파일 추가·제거·원본 복원 또는 파일 모음 비우기
- 주요 설정 편집과 저장한 작업 다시 열기
- 프린터·프리셋·노즐·플레이트·압출기·공급 방식·재료·제품 식별 상태 변경

파일 읽기나 API 응답을 기다리는 사이에 입력이 바뀌어도 이전 요청의 결과가 다시 나타나지 않도록 revision과 작업 전환을 확인합니다. 파일 추가가 실패하면 기존 입력과 그 입력에 대한 이전 검토를 그대로 유지합니다. 실제 입력 변경이나 새 검토 실패는 이전 결과를 해제합니다. 다운로드가 사라졌다면 현재 입력으로 다시 검토해야 합니다.

## 지원 범위와 차단 조건

| 입력 또는 상황 | 현재 처리 |
|---|---|
| 원시 필라멘트 JSON | 지원. 명시된 `name`이 필요하고, `type`이 있으면 `filament`여야 함 |
| `settings`, `scope`, `source`, `validation` envelope | 지원. 설정 이름은 `settings.name`으로 확인 |
| 단일 문자열 `inherits` | 정확한 이름으로 부모를 찾아 연결 |
| 없거나 빈 문자열인 `inherits` | 제공된 파일에서 더 연결할 부모가 없는 끝점으로 처리 |
| 일반 설정의 자식 값 | 부모 값을 해당 값 전체로 교체. 지원되는 배열·객체도 전체 교체하며 요소별 추정 병합은 하지 않음 |
| 누락된 대상 또는 부모 | `needs_input`. 필요한 이름을 표시하고 해석 결과는 제공하지 않음 |
| 중복 이름, 순환 참조, 깊이 초과 | `blocked` |
| 문자열이 아닌 `inherits` | `blocked`. 다중 부모를 임의로 처리하지 않음 |
| 비어 있지 않은 `include` | `blocked`. Bambu Studio에는 있는 기능이지만 현재 해석기의 지원 범위 밖임 |
| 압출기 variant 관련 설정 | `blocked`. 변형 이름에 따라 달라지는 배열을 일반 덮어쓰기로 처리하지 않음 |
| 설정 값의 `"nil"` 또는 `null` | `blocked`. 부모값 유지·기본값 적용 등의 의미를 추정하지 않음 |
| `Inherits`, `INCLUDE` 등 예약 메타데이터의 비정규 대소문자 표기 | `blocked`. 상속 지시를 일반 설정으로 잘못 넘기지 않음 |
| 없는 필수 수치·적용 범위 | 값을 채우지 않음. 별도 프로필 검토에서 필요한 근거로 표시 |

이름은 대소문자와 공백을 포함해 정확히 일치해야 합니다. 파일명, `alias`, `filament_settings_id`, `setting_id`나 유사한 이름으로 부모를 추정하지 않습니다. 이력에 쓰는 파일명은 표시용 라벨이며 서버가 여는 파일 경로가 아닙니다.

입력은 **1–64개 문서**, 상속 깊이 **최대 32개**, JSON 값의 중첩 **최대 64단계**로 제한합니다. 현재 문서·대상 이름·사용 조건은 합계 **2 MiB** 이하이며 비교 원본에도 같은 제한을 독립적으로 적용합니다. 원본과 편집본을 함께 전송하는 `/api/profiles/resolve`의 HTTP 요청 전체 제한은 **8 MiB**입니다. JSON 편집으로 문서가 커진 경우에도 제한을 다시 적용합니다. 지나치게 깊은 설정이나 사용 조건은 입력 오류로 안내합니다.

필라멘트의 `filament_extruder_variant`, 프로세스의 `print_extruder_variant`·`print_extruder_id`, 프린터의 `printer_extruder_variant`·`printer_extruder_id`는 일반 설정 배열과 의미가 다릅니다. 특히 최신 공식 `fdm_filament_common`과 관련 템플릿에도 variant와 `"nil"`이 있으므로 **최신 공식 프리셋 중 상당수는 이번 지원 범위에서 해석이 차단됩니다.** 해당 필드를 지워 통과시키는 방식은 올바른 변환이 아닙니다.

## 메타데이터와 근거의 경계

`scope`, `source`, `validation`은 **선택한 대상 문서의 envelope에서만** 사용합니다. 부모가 특정 장비에 맞는다고 적혀 있거나 제조사 출처·측정 성공을 주장해도, 그 주장을 자식의 적용 범위나 검증 결과로 승격시키지 않습니다. 대상의 장비 조건은 사용자가 제출한 `setup`과 별도로 비교합니다.

다음 identity·관리 메타데이터 역시 대상 문서의 값만 유지하는 정책입니다.

```text
name, type, from, version, setting_id, instantiation, url,
filament_settings_id, user_id, base_id, updated_time,
is_custom_defined, alias, renamed_from
```

`description`과 `filament_id` 등 지원되는 다른 명시값은 부모에서 이어받고 자식이 덮어쓸 수 있습니다. `inherits`와 `include` 같은 연결 지시는 지원되는 연결을 모두 해석한 후 결과 설정에서만 제외하며, 원본 문서에는 그대로 남깁니다. 연결이 실패하면 부분적으로 합친 설정을 완성된 결과로 내놓지 않습니다.

사용자 파일의 `from: "system"`, `source.authority: "manufacturer"`, 원문 URL이나 검증 기록은 입력된 정보입니다. 해시를 계산하거나 상속을 해석했다는 사실만으로 발행처의 진위 또는 실물 출력 성공이 확인되는 것은 아닙니다.

원본 비교가 있는 요청은 해석된 설정의 변경을 따로 표시합니다. 상위 프리셋을 수정해 대상에 적용되는 값이 달라져도 기존의 긍정적인 검증 주장을 `stale`로 처리하며, 실제 측정을 다시 했다고 표시하지 않습니다. 원본 체인을 해석할 수 없을 때도 기존 검증의 적용 가능성을 보류합니다. 원래의 `source`·`validation` 메타데이터는 증거에 그대로 남고, 수정된 값이 원래 발행처의 권고로 보이지 않도록 변경 필드를 표시합니다.

## API 입력 예시

`POST /api/profiles/resolve`는 `documents`, `target_name`, `setup`과 선택적인 `baseline`을 받습니다. 기존 로컬 API의 세션·요청 출처 검사를 동일하게 적용합니다. 아래는 파일 연결 형식을 설명하는 예시이며, 출력 온도나 완전한 프리셋을 제공하는 예시가 아닙니다.

```json
{
  "documents": [
    {
      "filename": "example-base.json",
      "profile": {
        "name": "Example Base",
        "type": "filament",
        "description": "부모 문서에 명시한 설명"
      }
    },
    {
      "filename": "example-custom.json",
      "profile": {
        "settings": {
          "name": "Example Custom",
          "type": "filament",
          "inherits": "Example Base",
          "description": "선택한 대상 문서가 바꾼 설명"
        },
        "scope": {},
        "source": { "authority": "user" },
        "validation": { "status": "unverified" }
      }
    }
  ],
  "target_name": "Example Custom",
  "setup": {}
}
```

이 예시는 설명 값의 상속·덮어쓰기와 원본 출처를 확인하기 위한 것입니다. 장비 조건과 필수 출력 수치가 없으므로 프로필 준비 가능을 뜻하지 않습니다.

편집 전후를 비교하려면 `baseline: {"documents": [...], "target_name": "원래 대상 이름"}`을 함께 보냅니다. `documents`에는 처음 제공한 문서들을 같은 `{filename, profile}` 구조로 넣습니다. 대상 이름을 편집했다면 바뀌기 전 이름을 사용합니다. UI는 파일 모음을 검토할 때 이 원본 비교 정보를 함께 전송합니다. 호출자가 임의로 제공한 baseline은 변경 이력 인증이나 실물 측정의 증거가 아닙니다.

## 보고서의 필드와 상태

| 필드 | 의미 |
|---|---|
| `schema_version` | 보고서 스키마 버전. 현재 `1` |
| `status` | 상속 해석의 `resolved`, `needs_input`, `blocked` |
| `target_name` | 요청한 정확한 대상 프리셋 이름 |
| `setup` | 검토 당시 제출한 장비·재료 조건의 복사본. 이후 호출자 입력을 바꾸어도 보고서의 조건이 바뀌지 않도록 deep copy함 |
| `documents` | 검토에 제출한 `filename`·`profile`과 각 profile 객체의 canonical JSON `sha256`. UI에서 편집했다면 편집본임. 묶음 가져오기는 별도 `origin`도 보존 |
| `imported_documents` | baseline으로 제공한 원본 문서, canonical JSON 해시와 선택적인 `origin`. baseline이 없으면 빈 목록 |
| `chain` | 성공했을 때의 루트부터 대상까지 이름·파일명·해시. 실패하면 빈 목록 |
| `field_sources` | 필드별 최종 출처 이름·파일명·해시, 상속 여부, 각 명시값의 `history`, 비교 가능한 경우 원본 대비 `edited` 여부 |
| `resolved_profile` | 해석된 설정과 대상 envelope. 실패하면 `null` |
| `review` | 해석 결과에 기존 `evaluate_profile`을 적용한 별도 검토. 해석 실패 시 `null` |
| `edit_review` | 원본 비교 상태, 원본 해석 상태·문제, 변경 필드, 기존 검증 주장 무효화 여부 |
| `issues`, `warnings` | 추가 파일 요청, 해석 차단 이유, 검토 범위 안내 |
| `full_config` | 항상 `false`. Studio 내부 기본값과 전체 스키마를 재현했다는 의미가 아님 |
| `native_verified` | 항상 `false`. 설치된 Studio로 동일 결과를 검증한 상태가 아님 |

UI에서 내려받는 보고서에는 `edited_filenames`도 추가됩니다. 현재 검토에 제출한 JSON이 처음 가져온 JSON과 달라진 문서의 파일명 목록입니다. 이는 대상에 적용되는 설정 변경과 구분합니다. 사용하지 않는 문서를 수정해도 파일 편집은 존재하지만 대상의 적용값은 같을 수 있습니다.

`edit_review.status`는 `untracked`(비교하지 못함), `unchanged`, `changed`, `baseline_unresolved` 중 하나입니다. 현재 체인이 해석되지 않으면 적용값 비교는 `untracked`이며, 원본 체인의 상태는 별도로 남습니다. 해석된 두 설정을 비교할 때 JSON 키 순서는 무시하고 값과 표현 형태는 보존합니다. 제거한 필드도 `changed_fields`에 들어갑니다. 비교할 수 없는 필드의 `edited`는 `false`로 단정하지 않고 `null`입니다.

여기서 원본 보존은 파싱된 JSON 값과 구조의 보존입니다. 보고서에 파일의 들여쓰기·줄바꿈·원래 바이트열을 그대로 보관한다는 뜻은 아닙니다. 묶음에서 가져온 문서는 `origin`에 묶음과 원본 멤버의 바이트 해시를 별도로 기록합니다. 이 정보는 설정이나 제조사·측정 근거로 병합하지 않습니다. 보고서 다운로드는 파일 모음 검토 결과에 제공되며, 검토 실패 보고서에도 어떤 문서를 제출했는지 확인할 수 있습니다.

`resolved`는 **제공된 문서의 지원되는 연결과 명시값을 해석했다**는 의미입니다. 별도 `review.decision`은 입력 부족이나 근거 부족을 계속 표시할 수 있습니다. `ready_to_prepare` 역시 기존 검토기의 제한된 필드·조건 검사를 통과했다는 뜻이며 전체 슬라이서 설정, 실제 Studio 실행, 실물 출력 성공을 증명하지 않습니다.

### canonical JSON 해시 정의

문서의 `sha256`은 **`profile` 객체 전체**를 아래 방식으로 직렬화한 UTF-8 바이트의 SHA-256입니다. `filename`은 포함하지 않으며, envelope를 사용하면 `settings`뿐 아니라 그 객체에 들어 있는 `scope`, `source`, `validation` 등도 포함합니다.

```python
import hashlib
import json

serialized = json.dumps(
    profile,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
).encode("utf-8")
sha256 = hashlib.sha256(serialized).hexdigest()
```

객체 키 순서와 JSON 공백의 차이는 제거하지만 배열 순서는 유지합니다. 원본 파일 바이트의 해시나 제조사 전자서명은 아닙니다. 같은 내용의 파일을 다른 이름으로 가져오면 같은 해시를 얻고, 실제 JSON 값 또는 envelope 근거가 바뀌면 해시도 달라집니다. `field_sources`와 `chain`의 해시는 해당 값을 제공한 **검토 제출 문서**를 가리킵니다.

## 참고한 공식 소스

다음 링크는 Bambu Studio 커밋 `930fe93851afbc76b1c64dd37d8728b6a9afc89c`로 고정되어 있습니다. 이 커밋의 [버전 문자열](https://github.com/bambulab/BambuStudio/blob/930fe93851afbc76b1c64dd37d8728b6a9afc89c/version.inc)은 `02.09.01.70`입니다. 소스의 동작을 확인한 기준이며, 사용자 PC에 설치된 버전의 동작을 검증한 것은 아닙니다.

- [단일 문자열 상속과 정확한 이름 조회](https://github.com/bambulab/BambuStudio/blob/930fe93851afbc76b1c64dd37d8728b6a9afc89c/src/libslic3r/Preset.hpp): `inherits`와 `find_preset_internal`.
- [메타데이터 파싱](https://github.com/bambulab/BambuStudio/blob/930fe93851afbc76b1c64dd37d8728b6a9afc89c/src/libslic3r/Config.cpp): `load_from_json`은 주요 메타데이터를 일반 설정과 분리하고 대소문자를 무시해 확인합니다.
- [부모·include·자식의 적용 및 내부 기본값](https://github.com/bambulab/BambuStudio/blob/930fe93851afbc76b1c64dd37d8728b6a9afc89c/src/libslic3r/PresetBundle.cpp): `load_vendor_configs_from_json`은 include를 Studio 기본 설정과의 차이로 적용합니다. 업로드한 JSON만 덮어쓰는 방식과 같지 않습니다.
- [사용자 프리셋의 차이값 저장과 variant 처리](https://github.com/bambulab/BambuStudio/blob/930fe93851afbc76b1c64dd37d8728b6a9afc89c/src/libslic3r/Preset.cpp): `save`, `get_extruder_names_and_keysets`, `extend_default_config_length` 및 사용자 프리셋 로딩 경로.
- [variant별 병합](https://github.com/bambulab/BambuStudio/blob/930fe93851afbc76b1c64dd37d8728b6a9afc89c/src/libslic3r/PrintConfig.cpp)과 [nil 요소 처리](https://github.com/bambulab/BambuStudio/blob/930fe93851afbc76b1c64dd37d8728b6a9afc89c/src/libslic3r/Config.hpp): `update_diff_values_to_child_config`, `set_only_diff`.
- [공식 공통 필라멘트](https://github.com/bambulab/BambuStudio/blob/930fe93851afbc76b1c64dd37d8728b6a9afc89c/resources/profiles/BBL/filament/fdm_filament_common.json)와 [표준·고유량 변형 템플릿](https://github.com/bambulab/BambuStudio/blob/930fe93851afbc76b1c64dd37d8728b6a9afc89c/resources/profiles/BBL/filament/fdm_filament_template_direct_dual.json): 실제 variant·nil 사용 사례.

현재 기능의 검증 결과는 [개발 상태](STATUS.md)와 [검증 기록](VERIFICATION.md)을 따릅니다. 이 문서의 형식 예시와 공식 소스 조사는 실제 필라멘트 추천값 또는 실물 출력 결과로 사용하지 않습니다.
