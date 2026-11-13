# Studio 내보내기 파일 가져오기

작성일: 2026-11-13 (Asia/Seoul).

Bambu Studio에서 내보낸 묶음을 **재료 설정** 화면에 바로 추가할 수 있습니다.
파일을 직접 풀어서 필라멘트 JSON을 하나씩 고르는 과정을 줄입니다. 가져온
필라멘트는 기존 주요 설정 편집, 상속 검토, 작업 저장 기능으로 이어집니다.

## 사용 순서

1. Bambu Studio에서 필요한 사용자 프리셋을 내보냅니다. 아래 표의 필라멘트
   묶음, 프린터 묶음 또는 일반 프리셋 ZIP을 사용할 수 있습니다.
2. 이 앱의 **재료 설정 → Studio 내보내기 가져오기**에서 파일 하나를 선택합니다.
3. 추가한 필라멘트 수와 제외한 프린터·출력 공정 파일을 확인합니다.
4. **검토할 프로필**에서 사용할 문서를 선택합니다. 가져오기 정보에서 묶음
   이름과 내부 파일 경로를 확인할 수 있습니다.
5. 장비·재료 조건을 입력하고 **프로필 검토하기**를 누릅니다. 부모 프리셋이
   없으면 필요한 이름을 확인해 JSON이나 다른 묶음을 추가합니다.
6. 편집을 이어 가려면 이름을 붙여 **이 PC에 저장**합니다. 원본, 정확한 편집
   문자열, 선택 대상, 사용 조건과 가져오기 정보가 함께 복원됩니다.

| 파일 | 지원하는 구조 | 가져오는 내용 |
|---|---|---|
| `.bbsflmt` | `bundle_structure.json`과 공급자별 필라멘트 JSON | 목록에 선언된 필라멘트 |
| `.bbscfg` | `bundle_structure.json`, printer/filament/process 범주의 JSON | 필라멘트만 추가; 프린터·출력 공정은 제외 목록에 표시 |
| `.zip` | 일반 프리셋 JSON 파일 모음; 지원하는 manifest가 있으면 함께 검사 | 필라멘트로 식별되는 JSON; 다른 종류는 제외 목록에 표시 |

확장자만 바꾼 임의 ZIP은 형식을 만족하지 않을 수 있습니다. 실제 GUI 내보내기는
`type`을 생략할 수 있으므로 `filament_settings_id` 같은 종류 식별 정보도
확인합니다. 선언한 종류와 내용이 충돌하면 파일 전체를 추가하지 않습니다.
원본에 없는 `type`을 추가하거나 `from`, `inherits`를 바꾸지 않습니다.

## 현재 입력을 보호하는 규칙

- 파일 선택은 기존 모음에 추가합니다. 이미 선택한 대상과 사용 조건을 유지합니다.
- 첫 파일을 추가하기 전에 붙여 넣은 JSON이 있으면 함께 보존합니다. 단독 초안이
  아직 올바른 JSON이 아니면 내용을 그대로 두고 먼저 문법을 완성하도록 안내합니다.
- 파일 모음의 기존 초안이 미완성인 경우에도 다른 부모 파일을 추가할 수 있습니다.
  상속 검토를 실행할 때는 제출하는 각 JSON이 올바른 형식이어야 합니다.
- 처음 가져온 JSON 내용이 같은 파일은 중복 추가하지 않습니다. 이미 편집한
  초안과 처음 기록한 가져오기 정보도 덮어쓰지 않습니다.
- 같은 프리셋 이름의 다른 내용은 어느 쪽을 선택할지 추정하지 않습니다. 이번
  추가 전체를 중단하므로, 원치 않는 문서를 제거하거나 별도 작업으로 가져오세요.
- 파일이 잘못됐거나 제한을 넘으면 일부만 추가하지 않습니다. 현재 입력과 이전
  검토는 유지합니다. 성공적으로 추가하거나 입력을 수정하면 이전 검토가 해제됩니다.
- 읽기나 서버 응답을 기다리는 사이에 편집하거나 작업을 바꾸면 늦은 응답을 버립니다.

## 원본과 가져오기 정보

프로필의 파싱된 JSON을 `profile`로 보존하고 편집 문자열을 별도로 관리합니다.
묶음에서 읽은 원래 UTF-8 텍스트가 최초 편집 문자열이 됩니다. 원본으로 되돌리기는
원래 JSON 값으로 복원하며 최초 들여쓰기까지 복원하는 기능은 아닙니다.

`origin`은 프로필 바깥의 가져오기 기록입니다.

| 필드 | 의미 |
|---|---|
| `type` | `bambu_preset_archive` |
| `archive_name` | 사용자가 선택한 묶음 파일명 |
| `archive_sha256` | 처음 받은 묶음 파일 전체 바이트의 SHA-256 |
| `member_path` | 묶음 내부의 JSON 경로. 서버에서 여는 파일 경로가 아님 |
| `member_sha256` | 묶음에서 읽은 원본 JSON 바이트의 SHA-256 |

이 기록은 작업 저장과 검토 보고서의 현재·원본 문서에 함께 남습니다. 기존
보고서의 `sha256`은 정렬해 직렬화한 **profile 객체**의 해시로, 원본 바이트
해시와 다릅니다. 편집해도 `origin`은 처음 가져온 파일을 가리킵니다.

파일명, 공급자 폴더와 해시는 제조사 인증이나 측정 증거가 아닙니다. API를 통해
다시 제출되는 `origin`도 사용자가 제공한 정보로 취급합니다. 묶음 manifest의
계정 식별자와 네트워크 라이브러리 버전을 출처 인증·Studio 설치 버전으로
사용하지 않으며, 응답·저장 기록에 복사하지 않습니다.

## 제한과 검토 범위

묶음 하나는 압축 상태 **4 MiB**, 모든 내부 파일의 압축 해제 크기 합계 **4 MiB**,
내부 항목 **256개**까지 지원합니다. JSON 파일 하나는 **2 MiB**까지이며,
선택한 필라멘트 문서는 **64개**, 해당 문서 JSON 합계 **2 MiB**까지입니다.
기존 모음과 합친 결과에도 문서 수와 원본·편집본 각각의 **2 MiB** 제한을
적용합니다. 추가할 때 편집본 크기는 미완성 초안을 파싱하지 않고 정확한 편집
문자열과 문서 정보를 기준으로 계산하므로 공백도 크기에 포함됩니다.

파일을 디스크에 추출하지 않습니다. 잘못된 경로·중복 항목·심볼릭 링크·암호화·
지원하지 않는 압축·CRC 오류·잘못된 UTF-8/JSON·과도한 중첩을 거절합니다.
다른 종류라서 제외하는 파일도 전체 크기와 ZIP 무결성 검사에 포함됩니다.

**가져오기 성공은 설정 완성이나 슬라이싱 성공이 아닙니다.** Studio의 사용자
프리셋 묶음에는 시스템 부모가 빠지고 변경값만 들어 있을 수 있습니다. 기존
해석기는 제공된 단일 부모 관계만 다루며, 기본값·include·variant·`nil`은
[기존 지원 범위](FILAMENT_PRESETS.md)를 따릅니다. 가져온 필라멘트를 native
machine/process/filament 전체 구성으로 자동 변환하지 않습니다.

## API

`POST /api/profiles/import-archive`에 다음 JSON을 보냅니다. 로컬 세션 토큰과
같은 출처 검사가 필요하며 요청 전체는 base64 오버헤드를 포함해 **8 MiB**입니다.

```json
{
  "filename": "my-material.bbsflmt",
  "content_base64": "선택한 파일 바이트의 base64 문자열"
}
```

응답에는 `schema_version`, `archive`, `documents`, `ignored_members`, `warnings`가
있습니다. 각 문서는 `filename`, 변경하지 않은 `profile`, 원문 `draft_text`,
위의 `origin`을 포함합니다. 이 API는 입력 후보만 반환하고 작업을 저장하거나
Studio를 실행하지 않습니다. 올바르지 않은 묶음은 HTTP 422, 요청 전체 크기
초과는 413입니다. 검토 API에는 `draft_text`를 제외한 문서를 사용합니다.

## 형식 근거와 확인 범위

형식은 Bambu Studio `v02.09.01.70`, 커밋
`56a57d00a591360cf41bf21383915ee5bf357be5`의 아래 구현에서 확인했습니다.

- [묶음과 일반 ZIP 내보내기](https://github.com/bambulab/BambuStudio/blob/56a57d00a591360cf41bf21383915ee5bf357be5/src/slic3r/GUI/CreatePresetsDialog.cpp): `archive_preset_bundle_to_file`, `archive_filament_bundle_to_file`, `save_presets_to_zip`.
- [JSON 종류 식별과 native 부모 처리](https://github.com/bambulab/BambuStudio/blob/56a57d00a591360cf41bf21383915ee5bf357be5/src/libslic3r/PresetBundle.cpp): `import_presets`, `import_json_presets`.
- [사용자 프리셋의 변경값 저장](https://github.com/bambulab/BambuStudio/blob/56a57d00a591360cf41bf21383915ee5bf357be5/src/libslic3r/Preset.cpp): `Preset::save`.
- [저장 JSON의 메타데이터](https://github.com/bambulab/BambuStudio/blob/56a57d00a591360cf41bf21383915ee5bf357be5/src/libslic3r/Config.cpp): `ConfigBase::save_to_json`.
- [네트워크 버전 함수](https://github.com/bambulab/BambuStudio/blob/56a57d00a591360cf41bf21383915ee5bf357be5/src/slic3r/Utils/NetworkAgent.cpp): `NetworkAgent::get_version`.

테스트는 이 구조를 따라 직접 만든 합성 입력을 사용합니다. 제조사 프리셋
데이터를 저장소에 복사하지 않았습니다. 파서·브라우저 검사, 기존 native
슬라이싱 검사와 실제 GUI 내보내기/실물 출력 검증은 구분합니다. 실행한 결과는
[검증 기록](VERIFICATION.md)에서 확인하세요.
