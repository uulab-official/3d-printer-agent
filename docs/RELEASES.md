# 검증된 패키지의 릴리스 배포

**[v0.34.0 공개 릴리스](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.34.0)**가
2026-11-21 **03:44:14 UTC**에 게시됐습니다. 소스와 tag는
[`1ce91b1b81e9f10c95079dc88e5c2f36c0b0334e`](https://github.com/uulab-official/3d-printer-agent/commit/1ce91b1b81e9f10c95079dc88e5c2f36c0b0334e)이며,
아래 세 검증을 통과한 원본 wheel과 검증 보고서 등 **7개 자산**을 포함합니다.
[실제 승격 실행](https://github.com/uulab-official/3d-printer-agent/actions/runs/44862598604)과 [검증 기록](VERIFICATION.md)에서 결과와 범위를 확인할 수 있습니다.
릴리스 파일은 Actions의 단기 보관 산출물과 구분합니다.

배포 wheel은 `3d_printer_agent_local-0.34.0-py3-none-any.whl`, **351,623바이트**이며
SHA-256은 `b28402093bb7095f94af530aaa24b5e1a83c9101b63908e06d1e7b58250556c1`입니다.
이 값은 릴리스 내부 wheel의 해시이며 Actions가 묶은 외부 ZIP의 해시와 다릅니다.

| 같은 main 소스의 검증 | 관측 결과 |
|---|---|
| [앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44861993160) | 성공(실행 차수 1). 로그는 권한 문제로 다시 읽지 못했고, 같은 코드의 PR 실행에서 Python **828개**·컨트롤러 **222개**·Chromium **118개** 통과 |
| [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44861993176) | 같은 wheel을 설치한 Ubuntu 24.04·macOS 15·Windows 2025에서 각각 **397개** 통과(공개 보고서로 확인) |
| [Native Bambu](https://github.com/uulab-official/3d-printer-agent/actions/runs/44861993202) | Linux Studio `02.09.01.70`의 기존 네 경로와 새 품질별 비교 단계 통과 |

v0.34.0은 같은 모델을 지금 설정·곱게·빠르게·튼튼하게로 네 번 슬라이스해 예상 시간·재료·레이어·서포트를 비교합니다(PR #31). 프린터·필라멘트·플레이트·
모델은 그대로 두고 정해진 공정 값만 바꾸며, 현재 슬라이스 결과는 바꾸지 않습니다. 고른 설정은 설정 JSON에 넣어 평소처럼 검토·슬라이스합니다. 세 workflow와
승격 모두 실행 차수 1로 통과했습니다(먼저 끝난 게이트가 부른 두 번의 승격 실행은 나머지 게이트를 기다리며 게시 없이 끝났습니다). 공개 자산 7개를 인증 없이
다시 내려받아 wheel·`SHA256SUMS`·영수증의 해시와 바이트 수가 일치하고, 근거 JSON의 보고서 해시가 내려받은 세 보고서와 같으며, 근거·영수증·보고서의 소스
커밋이 tag 커밋과 같고 보고서가 모두 통과 상태임을 확인했습니다. 이후 문서 갱신은 릴리스 tag와 파일을 바꾸지 않습니다.

### 이전 릴리스 v0.33.0

[v0.33.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.33.0)은 2026-11-21 **03:09:09 UTC**에 [`4b5bcea`](https://github.com/uulab-official/3d-printer-agent/commit/4b5bceaf13ad0c5b15f2bdb743fcb1a579ac65f4)에서
게시됐습니다. wheel **347,213바이트**, SHA-256 `18a142bdcb890bf840529d7896cfa454b308c1b9fbc92dea7e317a19e138aa20`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44858957287)(Python 821·컨트롤러 221·Chromium 116), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44858957303)(세 OS 각 396개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44858957292)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.32.0

[v0.32.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.32.0)은 2026-11-20 **07:37:02 UTC**에 [`ae6688b`](https://github.com/uulab-official/3d-printer-agent/commit/ae6688b46aba407735840c38f799cc2a25a4e592)에서
게시됐습니다. wheel **344,800바이트**, SHA-256 `4cf6402754392b2d45a53521b3a62b1655d52554e14e92c9aba3dd9b11d96600`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44695085771)(Python 819·컨트롤러 221·Chromium 114), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44695085682)(세 OS 각 393개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44695085677)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.31.0

[v0.31.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.31.0)은 2026-11-20 **06:52:36 UTC**에 [`703e69e`](https://github.com/uulab-official/3d-printer-agent/commit/703e69ebf223922da5e85b10220e39f1feda62c2)에서
게시됐습니다. wheel **330,111바이트**, SHA-256 `724d2a1fbc0cda2856bf96755e6d7c77aa3810f194d7ed55b00ac6c9cc753e61`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44689753988)(Python 809·컨트롤러 220·Chromium 110), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44689754006)(세 OS 각 389개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44689753969)가 같은 커밋에서 통과했습니다(승격은 실행 차수 2).

### 이전 릴리스 v0.30.0

[v0.30.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.30.0)은 2026-11-20 **06:01:39 UTC**에 [`ebdc45e`](https://github.com/uulab-official/3d-printer-agent/commit/ebdc45e255943064cfe136d539482ef4463ce43b)에서
게시됐습니다. wheel **327,471바이트**, SHA-256 `42f105acdb0e403e5ab201b1a7368eb6250b723197fe558a218bd3821f64cacb`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44683833313)(Python 800·컨트롤러 220·Chromium 108), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44683833172)(세 OS 각 373개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44683833197)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.29.1

[v0.29.1](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.29.1)은 2026-11-20 **01:14:07 UTC**에 [`f9bacff`](https://github.com/uulab-official/3d-printer-agent/commit/f9bacffb83be4cf79e8bf49bcaa5cfc4a6104cfb)에서
게시됐습니다. wheel **326,042바이트**, SHA-256 `25866d08cb3b95204e640a493b18ee6ee36df8354c2f5803c7a72efec070c2f1`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44644109003)(Python 798·컨트롤러 219·Chromium 108, 실행 차수 3), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44644108891)(세 OS 각 373개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44644108924)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.29.0

[v0.29.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.29.0)은 2026-11-19 **13:27:25 UTC**에 [`6164466`](https://github.com/uulab-official/3d-printer-agent/commit/6164466d50ad8fe6e1614b606d6ee54d58457d9b)에서
게시됐습니다. wheel **326,041바이트**, SHA-256 `562d946e7809a7bf27f711072fafd2931edb333fc680b38b52d3b33e5354ad75`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44531710101)(Python 798·컨트롤러 219·Chromium 106), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44531709361)(세 OS 각 373개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44531709367)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.28.0

[v0.28.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.28.0)은 2026-11-19 **12:42:11 UTC**에 [`1c15c7b`](https://github.com/uulab-official/3d-printer-agent/commit/1c15c7bbdfe635014720d11c19762d6688917431)에서
게시됐습니다. wheel **324,467바이트**, SHA-256 `2af94928d2b8bbe610b921177fa951ae6ef27521ac7d7b8963eb4e605b57646d`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44523839462)(Python 793·컨트롤러 219·Chromium 106), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44523839402)(세 OS 각 373개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44523839971)(실행 차수 2)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.27.0

[v0.27.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.27.0)은 2026-11-19 **08:19:19 UTC**에 [`8374323`](https://github.com/uulab-official/3d-printer-agent/commit/837432390941c3b93e8c42cbd7b29cff9b79aa04)에서
게시됐습니다. wheel **322,919바이트**, SHA-256 `23e1f6e64400d986771d62e2be2129b6d53daadd1c5cb7b3b84e15c6c3be367b`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44484865695)(Python 791·컨트롤러 219·Chromium 104), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44484865785)(세 OS 각 373개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44484865569)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.26.0

[v0.26.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.26.0)은 2026-11-19 **04:58:33 UTC**에 [`21ac9e1`](https://github.com/uulab-official/3d-printer-agent/commit/21ac9e1bf5086cf9e2a98f9c36fec81fe7efe3e2)에서
게시됐습니다. wheel **320,898바이트**, SHA-256 `7f1624dc52fc27f4f0941caa08ff5cda12b28c22d99536f68d4ddc2e20ee7952`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44460842266)(Python 789·컨트롤러 218·Chromium 104), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44460842294)(세 OS 각 373개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44460842221)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.25.0

[v0.25.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.25.0)은 2026-11-18 **00:07:15 UTC**에 [`bf7c186`](https://github.com/uulab-official/3d-printer-agent/commit/bf7c1865c8148a0dcec185b247c2255e25d039c1)에서
게시됐습니다. wheel **317,618바이트**, SHA-256 `30e4585867878fc5c70e90d9dd3ca4bf2bd53d26f26ea1ade3380feec650aabb`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44202886373)(Python 784·컨트롤러 217·Chromium 102), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44202886379)(세 OS 각 372개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44202886330)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.24.0

[v0.24.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.24.0)은 2026-11-17 **08:13:15 UTC**에 [`c800064`](https://github.com/uulab-official/3d-printer-agent/commit/c800064da75d1dee368597defb46507184de738f)에서
게시됐습니다. wheel **311,861바이트**, SHA-256 `a45aa89b004ba0a9bc7a865f009162dc70558775e8809e487064b0ad8f99fcbb`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44043739144)(Python 772·컨트롤러 216·Chromium 100), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44043739272)(세 OS 각 355개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44043739125)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.23.0

[v0.23.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.23.0)은 2026-11-17 **07:32:38 UTC**에 [`95cfcf0`](https://github.com/uulab-official/3d-printer-agent/commit/95cfcf04118e3c3f456434b5e7b843673b86aaa5)에서
게시됐습니다. wheel **308,072바이트**, SHA-256 `9b3cac3ff54777b5a91906540a5f60f1d3875acc9f9fbbe4add8c51bfe3088ae`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44038597238)(Python 769·컨트롤러 216·Chromium 98), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44038597293)(세 OS 각 354개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44038597309)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.20.0

[v0.20.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.20.0)은 2026-11-17 **06:35:19 UTC**에 [`0e3645b`](https://github.com/uulab-official/3d-printer-agent/commit/0e3645ba20d5312ac88a27fd4e0518ca64267f3a)에서
게시됐습니다. wheel **304,612바이트**, SHA-256 `0f5342fde630425cd54c8ebf0c1cd64020abb0436460477f4f41b33189b36c2f`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44031399678)(Python 762·컨트롤러 214·Chromium 94), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44031399682)(세 OS 각 337개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44031399774)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.19.0

[v0.19.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.19.0)은 2026-11-17 **06:03:05 UTC**에 [`554e120`](https://github.com/uulab-official/3d-printer-agent/commit/554e1202081047f54f25e9b3a0321cb233f0637f)에서
게시됐습니다(PR #13·#14·#15). wheel **302,880바이트**, SHA-256 `42bf000649ff12bbb0def6b3094b8a06367eda51649c7d2b0f72caf424d7e0aa`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44027511632)(Python 754·컨트롤러 214·Chromium 92), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44027511573)(세 OS 각 337개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44027511657)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.16.0

[v0.16.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.16.0)은 2026-11-17 **04:47:16 UTC**에 [`c45a33e`](https://github.com/uulab-official/3d-printer-agent/commit/c45a33e33727b05e62fd340f0beb02cdeba091ba)에서
게시됐습니다. wheel **292,769바이트**, SHA-256 `cdef32c3860b2a0067c9bc5b7a7a7767ef9fc8140d5ffa7343b01268af935ed6`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44018819257)(Python 743·컨트롤러 210·Chromium 88), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44018819259)(세 OS 각 336개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44018819228)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.15.0

[v0.15.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.15.0)은 2026-11-17 **03:33:51 UTC**에 [`35416f7`](https://github.com/uulab-official/3d-printer-agent/commit/35416f7fad9644110e21b28c49580ba0cbcda5ce)에서
게시됐습니다(PR #8·#9·#10). wheel **284,700바이트**, SHA-256 `919ef2f3edd5178bd9013892a40b3da8601e36202a6873e2c5a1d85421b86b33`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/44010260872)(Python 738·컨트롤러 209·Chromium 86), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/44010260911)(세 OS 각 327개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/44010260897)가 같은 커밋에서 통과했습니다. 버전을 올리지 않은 PR #11 병합 뒤의 승격 실행은
“기존 버전 tag가 다른 커밋을 가리킨다”며 tag를 옮기지 않고 중단했고, v0.15.0 tag와 파일은 바뀌지 않았습니다.

### 이전 릴리스 v0.12.1

[v0.12.1](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.12.1)은 2026-11-17 **01:23:23 UTC**에 [`1ea9a0c`](https://github.com/uulab-official/3d-printer-agent/commit/1ea9a0ce3a32a0d3d97ea1bb05041e3049599464)에서
게시됐습니다. wheel **262,422바이트**, SHA-256 `cc87d1c849e0a70a42f985bca0b552cbcac7fef62aaab077cb45c9708e502eee`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/43994307197)(Python 703·컨트롤러 207·Chromium 84), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/43994307046)(세 OS 각 326개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/43994306976)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.12.0

[v0.12.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.12.0)은 2026-11-16 **23:57:38 UTC**에 [`b96e657`](https://github.com/uulab-official/3d-printer-agent/commit/b96e657e5fc2ce8ca5b5900e68d0a26e28be7c90)에서
게시됐습니다. wheel **262,041바이트**, SHA-256 `03090a4137df859f215593e8a8082329b13166cd0089d626f86dc51c85ecc203`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/43982877129)(Python 702·컨트롤러 206·Chromium 84), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/43982877138)(세 OS 각 326개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/43982877304)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.11.0

[v0.11.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.11.0)은 2026-11-16 **13:46:36 UTC**에 [`1882063`](https://github.com/uulab-official/3d-printer-agent/commit/1882063972a5fec923c8684659fd6ea919e24d8c)에서
게시됐습니다. wheel **257,616바이트**, SHA-256 `c7f20f810b512f16fba0fcfa46c8fcfbeb79e7750f40d44efea27ae9da6c7c56`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/43877881237)(Python 694·컨트롤러 205·Chromium 82), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/43877881160)(세 OS 각 309개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/43877881380)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.10.0

[v0.10.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.10.0)은 2026-11-16 **13:01:27 UTC**에 [`a74a477`](https://github.com/uulab-official/3d-printer-agent/commit/a74a477aad2d3aa6d7147c2df6079a828346582b)에서
게시됐습니다. wheel **254,450바이트**, SHA-256 `cd7404ad820aca59536cee1633fd53f51f4f5a67f0cc0c5a7f74230d93c41133`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/43870761890)(Python 694·컨트롤러 203·Chromium 80), [설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/43870762021)(세 OS 각 309개),
[Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/43870761873)가 같은 커밋에서 통과했습니다.

### 이전 릴리스 v0.9.0

[v0.9.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.9.0)은 2026-11-16 **06:10:06 UTC**에 PR #3 병합 커밋
[`b48e5406d122cda3b892aac1938131a2276b14ba`](https://github.com/uulab-official/3d-printer-agent/commit/b48e5406d122cda3b892aac1938131a2276b14ba)에서 자동 승격으로 게시됐습니다.
wheel **232,858바이트**, SHA-256 `ae880f8b6d6840cfdd0c1ac30b8fcbaf012af0faa0a5b543f915d44f15a7c8e3`.
[앱 CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/43814155368)(Python 666·컨트롤러 195·Chromium 58),
[설치 패키지](https://github.com/uulab-official/3d-printer-agent/actions/runs/43814155417)(세 OS 각 **290개**), [Native](https://github.com/uulab-official/3d-printer-agent/actions/runs/43814155586)가 같은 커밋에서 통과했습니다.
게시 당시에는 이 기록을 남기지 못했고, 2026-11-16에 공개 자산을 인증 없이 내려받아 같은 방식으로 대조했습니다.

## 게시 조건

같은 저장소의 현재 `main` push 커밋에서 다음 세 workflow의 최신 실행이 모두
성공해야 합니다.

- `CI`: Python·컨트롤러·실제 브라우저와 기본 패키지 검사.
- `Installed desktop package qualification`: 공통 wheel 하나의 Linux·macOS·Windows 실제 설치·CAD·HTTP·백업·복원.
- `Native Bambu CLI qualification`: 고정한 Studio 버전의 Linux native 회귀.

세 workflow는 모두 `main` push를 검사합니다. 브라우저 검사만 고친 커밋도 native
검증에서 빠지지 않으며, PR의 native 경로 필터는 별도로 유지합니다.
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
python -m pip install ./3d_printer_agent_local-0.24.0-py3-none-any.whl
printer-agent --version
printer-agent doctor
printer-agent
```

앱 실행에는 Node.js가 필요하지 않습니다. 소스의 전체 개발 테스트에는
Python 3.12와 Node.js 22 이상을 함께 준비하고 [기여 안내](../CONTRIBUTING.md)를 따릅니다.
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
