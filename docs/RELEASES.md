# 검증된 패키지의 릴리스 배포

**[v0.3.0 공개 릴리스](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.3.0)**가
2026-11-14 12:38:19 UTC에 게시됐습니다. 소스와 tag는
[`18e0af01a92e6204116836fc9cb8e09089340211`](https://github.com/uulab-official/3d-printer-agent/commit/18e0af01a92e6204116836fc9cb8e09089340211)이며,
아래 세 검증을 통과한 원본 wheel과 검증 보고서 등 7개 자산을 포함합니다.
[실제 승격 실행](https://github.com/uulab-official/3d-printer-agent/actions/runs/43595774058)과
[검증 기록](VERIFICATION.md)에서 결과와 범위를 확인할 수 있습니다.
릴리스 파일은 Actions의 단기 보관 산출물과 구분합니다.

배포 wheel은 `3d_printer_agent_local-0.3.0-py3-none-any.whl`, **153,564바이트**이며
SHA-256은 `c19f456dea74dfa47dedeeb4726c67c2556ce6655c1a1aed72ff8a2e3bbcb35d`입니다.
이 값은 릴리스 내부 wheel의 해시이며 Actions가 묶은 외부 ZIP의 해시와 다릅니다.

## 게시 조건

같은 저장소의 현재 `main` push 커밋에서 다음 세 workflow의 최신 실행이 모두
성공해야 합니다.

- `CI`: Python·컨트롤러·실제 브라우저와 기본 패키지 검사.
- `Installed desktop package qualification`: 공통 wheel 하나의 Linux·macOS·Windows 실제 설치·CAD·HTTP·백업·복원.
- `Native Bambu CLI qualification`: 고정한 Studio 버전의 Linux native 회귀.

각 workflow 완료가 승격 검사를 시작하지만 아직 다른 검사가 끝나지 않았다면
게시하지 않습니다. 다른 브랜치, PR/fork, 이전 main 커밋이나 서로 다른 소스의
보고서를 조합해 게시하지 않습니다. 소스 버전은 `pyproject.toml`의 명시적인 버전이며,
이미 게시한 같은 버전의 tag·파일은 이동하거나 덮어쓰지 않습니다.

실패한 job을 재실행해 같은 이름의 이전 산출물이 남으면 가장 최근 artifact ID의
자료를 검사합니다. 최신 자료가 잘못되었다고 이전 성공 자료로 되돌아가지는 않습니다.
재실행하지 않은 성공 job의 산출물은 그대로 사용할 수 있습니다. tag 생성과 최종
공개 직전에도 workflow ID·실행 차수·최신 성공 여부를 다시 확인하며, 검사가 다시
시작되거나 main이 바뀌면 draft를 보존하고 공개하지 않습니다.

## 재빌드하지 않는 배포물

승격 작업은 설치 검사에서 사용한 원본 wheel·영수증·SHA256SUMS와 세 운영체제의
보고서를 내려받습니다. GitHub 아카이브 해시, ZIP 목록·경로, wheel·설치 보고서의
버전·소스·파일 해시, 실제 소스와의 일치를 확인합니다. 이 단계에서 앱을 다시 빌드하거나
내려받은 코드를 실행하지 않습니다.

공개 자산은 wheel, `SHA256SUMS`, `wheel-receipt.json`, `release-evidence.json`과
운영체제별 qualification 보고서입니다. 먼저 draft release에 완전한 자산을 올리고
검사한 뒤 공개합니다. 중간 실패는 draft 상태로 남으며, 재실행은 정확히 일치하는
원본·기존 자산만 이어갈 수 있습니다. 다른 바이트가 이미 있으면 자동 교체하지 않습니다.

## 설치와 파일 확인

릴리스의 설명에서 지원 환경과 해당 소스 커밋을 확인합니다. 같은 릴리스의 wheel,
SHA256SUMS 또는 영수증을 함께 받고 실제 wheel의 SHA-256을 비교하세요.
Python 3.12 가상환경에서 다음과 같이 설치할 수 있습니다.

```bash
python -m pip install ./3d_printer_agent_local-0.3.0-py3-none-any.whl
printer-agent --version
printer-agent doctor
printer-agent
```

시스템 라이브러리 준비는 [로컬 운영 안내](LOCAL_OPERATION.md)를 따릅니다.
원본 저장소를 받은 폴더에서 테스트한 것과, 설치된 패키지를 그 폴더 밖에서 실행한
결과를 구분합니다. 업데이트 전 자료 보존은 [백업·복원](BACKUP_RESTORE.md)에 있습니다.

## 권한과 검증 의미

승격 job은 GitHub의 작업 토큰에서 `actions: read`, `contents: write`만 요청합니다.
토큰이나 다운로드용 임시 서명 URL을 로그·보고서·릴리스에 남기지 않습니다.
워크플로우 이벤트와 자산은 검증 대상 데이터이며 임의 셸 명령으로 실행하지 않습니다.
조직 권한이나 GitHub API가 발행을 거절하면 실패를 기록하고 이미 공개된 자산을
변경하지 않습니다.

출처는 [GitHub workflow_run 이벤트](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run),
[workflow 권한](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions),
[Release API](https://docs.github.com/en/rest/releases/releases)입니다.

해시는 내려받은 바이트의 일치를 확인합니다. 별도의 코드 서명·공증·제조사 인증이나
실제 출력 품질 보증으로 표시하지 않습니다. 이 릴리스는 Python 패키지이며 서명된
DMG/MSI, 자동 업데이트 프로그램, 공개 다중 사용자 서버 또는 물리 프린터 제어를
제공하는 설치 프로그램은 아닙니다. 사용자가 릴리스를 삭제하거나 저장소 운영 조건이
바뀔 수 있으므로 무기한 보관을 보증한다는 의미도 아닙니다.
