# GUI Design

## 1. 문서 범위

이 문서는 ROPI 관제 시스템의 PyQt6 GUI 설계를 정의한다.

현재 작성 범위는 관리자/관제 운영자 UI와 방문자 키오스크 UI이다. 두 UI는 같은 PyQt6 기반이지만 제품 기준으로 별도 앱으로 설계한다.

관리자/관제 운영자 UI의 목적은 다음과 같다.

- 교육받은 관제 운영자 또는 관리자가 로봇 작업을 요청하고 진행 상태를 빠르게 확인한다.
- 관제 담당자가 로봇, 작업, 이벤트, 재고, 어르신 정보를 한 화면 흐름 안에서 추적한다.
- 운반, 순찰, 안내, 추종 시나리오를 공통 `task` 관점에서 일관되게 표시한다.
- 시나리오별 세부 정보는 각 detail panel에서 분리해 보여준다.
- 장애 발생 시 `task_id`, `assigned_robot_id`, `reason_code`, 이벤트 로그를 기준으로 원인 추적이 가능해야 한다.

제품에 노출되는 Admin UI 문구는 이 앱을 요양보호사용 콘솔로 설명하지 않는다. 실제 요양보호사용 화면은 쉬운 한국어와 낮은 정보 밀도를 가진 별도 workflow로 둔다. 구현상 `caregiver` 패키지명과 `caregiver_id` payload 필드는 현재 Control Service/DB 계약 호환을 위해 유지할 수 있지만, 화면에 보이는 Admin UI 라벨은 `관리자`, `관제 운영자`, 운영 관점 문구를 사용한다.

방문자 키오스크 UI의 목적은 다음과 같다.

- 방문자가 로비에서 방문 등록, 어르신 찾기, 로봇 안내 요청, 직원 호출을 수행한다.
- 관리자용 운영 정보나 내부 enum을 노출하지 않고 방문자용 문구로 상태를 안내한다.
- 터치스크린 환경에서 큰 버튼, 짧은 단계, 명확한 오류 복구 흐름을 제공한다.

이 문서는 프롬프트 문서가 아니라 설계서이다. 와이어프레임 제작 시에는 각 페이지 섹션을 페이지별 요구사항으로 복사해 사용할 수 있다.

---

## 2. 현재 구현 기준

### 2-1. 현재 UI 구조

이전 코드에는 `LoginRoleWindow`가 있었지만, 제품 설계 기준에서는 관리자 앱과 방문자 키오스크 앱을 분리하므로 역할 선택 창을 제거한다.

관리자 앱의 제품 진입 흐름은 다음과 같다.

```text
Admin App
-> CaregiverLoginWindow
-> CaregiverMainWindow
```

방문자 키오스크는 별도 앱으로 시작한다.

```text
Kiosk App
-> KioskHomeWindow
```

`LoginRoleWindow`는 제품 IA에 포함하지 않으며 제품 코드에 남기지 않는다.
관리자 앱에서 로그아웃하더라도 역할 선택 화면으로 돌아가지 않고 관리자 로그인 화면으로 복귀한다.
방문자 키오스크는 방문자용 홈 화면에서 시작하며 관리자 앱의 로그인 화면이나 역할 선택 화면을 재사용하지 않는다.
방문자 키오스크에서 세션 종료 또는 초기화가 필요할 때는 키오스크 홈 화면으로 복귀하며 `LoginRoleWindow`를 띄우지 않는다.

현재 `CaregiverMainWindow`의 주요 화면은 다음과 같다.

| 화면 | 현재 코드 위치 | 현재 상태 |
| --- | --- | --- |
| 홈 대시보드 | `ui/admin_ui/main_window.py` | 서버 dashboard bundle 조회 구조 존재 |
| 작업 요청 | `ui/utils/pages/caregiver/task_request_page.py` | 운반/순찰 요청은 서버 연동 구조 존재, 안내는 관리자 작업 요청 탭에서 제외, 추종은 비활성 탭 |
| 작업 모니터 | `ui/utils/pages/caregiver/task_monitor_page.py` | task snapshot/push 반영, 순찰 낙상 알림/증거사진/재개 UI 존재 |
| 좌표/구역 설정 | 구현 예정 | DB 기반 구역/정밀 주차 좌표 설정 페이지 |
| 재고 관리 | `ui/utils/pages/caregiver/inventory_management_page.py` | 서버 조회/추가 연동 존재 |
| 어르신 정보 | `ui/utils/pages/caregiver/patient_info_page.py` | 서버 조회 연동 존재 |
| 알림/오류 | `ui/utils/pages/caregiver/alert_log_page.py` | 현재 mock 데이터 중심 |
| 로봇 상태 | `ui/utils/pages/caregiver/robot_status_page.py` | 메인 사이드바 진입 구조 존재, 상세 데이터 연동은 보강 대상 |

### 2-2. 현재 와이어프레임 검토 기준

현재 `wireframes/stitch_carebot_operations_dashboard/`에는 관리자 콘솔용 HTML/Tailwind 와이어프레임과 PNG 화면이 있다.

와이어프레임은 색상, 카드 배치, 페이지별 정보 밀도 참고 자료로 사용한다. 단, HTML의 app shell을 그대로 PyQt로 옮기지는 않는다.

검토 결과 반영해야 할 정규화 항목은 다음과 같다.

| 항목 | 와이어프레임 현재 상태 | 설계 반영 기준 |
| --- | --- | --- |
| 브랜드 | `RoboCare OS`, `Admin Console`, `Operational Console` 혼재 | 제품 브랜드는 `ROPI`로 통일 |
| Top nav bar | 페이지마다 `CONTROL SERVICE`, `DATABASE`, `ROS2`, `AI SERVER` nav가 반복 | global top nav 제거, 상태 chip으로만 표시 |
| Sidebar width | `280px`과 `260px` 혼재 | 관리자 콘솔은 `260px` 고정 기준 |
| Sidebar menu | 페이지마다 메뉴명/순서가 일부 다름 | 정보 구조의 공통 sidebar 메뉴로 통일 |
| Header | fixed/sticky topbar가 페이지마다 다름 | 공통 `PageHeader` 안에 title, subtitle, status strip 배치 |
| Font | 와이어프레임 일부가 Manrope/Inter 사용 | PyQt 앱은 Pretendard/Noto Sans KR 기준 |
| Dark mode | 일부 HTML에 dark class 포함 | phase 1 관리자 UI는 light theme만 설계 |
| Duplicate pages | `task_request`와 `task_request_ui_sync` 중복 | `task_request_ui_sync`를 작업 요청 기준안으로 사용 |
| Unsafe action | `Manual Override`가 실제 기능 없이 노출 | backend 안전 기능 전에는 제거 또는 disabled |

### 2-3. 현재 시나리오 연동 상태

GUI 설계는 모든 시나리오를 공통 task 모델로 다룬다. 다만 현재 구현 완료 수준은 시나리오마다 다르므로, 와이어프레임과 구현 우선순위는 이를 구분해야 한다.

| 시나리오 | 대상 로봇 | 현재 연동 수준 | UI 설계 기준 |
| --- | --- | --- | --- |
| 운반 | `pinky2`, `jetcobot1`, `jetcobot2` | 관제 서버 연동 성공 | 실제 요청/상태/취소/결과를 상세 표시 |
| 순찰 | `pinky3` | phase 1 서버 연동 및 관련 UI 구현 진행 | task 생성, 상태 추적, 낙상 대응 UI를 작업 모니터와 연결 |
| 안내 | `pinky1` | 키오스크 안내 흐름 일부 구현, 서버 연동 보강 대상 | 방문자 키오스크와 연결될 task 구조를 완성. 관리자 작업 요청 탭에는 노출하지 않음 |
| 추종 | 미정 또는 확장 | 관리자 작업 요청 화면에 비활성 탭으로만 표시 | phase 1 완성 범위에서 제외 |

현재 phase 1에서 실제 연동 기준으로 다루는 흐름은 운반과 순찰이다.

관리자 작업 요청 화면은 phase 1에서 안내 탭을 노출하지 않는다. 안내는 방문자 키오스크 흐름에서 별도로 다룬다. 추종은 향후 확장 가능성을 보여주는 비활성 탭으로만 남기고, 탭 라벨에는 `준비 중` 문구를 붙이지 않는다.

- 운반 작업 생성은 `DeliveryRequestRemoteService.create_delivery_task()`를 통해 서버로 전송한다.
- 서버 응답에는 `result_code`, `result_message`, `reason_code`, `task_id`, `task_status`, `assigned_robot_id`가 포함되어야 한다.
- 현재 phase 1에서는 운반 작업이 `pinky2`에 즉시 배정되는 구조이다.
- 작업 생성 이후 실제 로봇 workflow는 Control Service의 background task로 진행된다.
- 작업 완료, 실패, 취소 결과는 서버와 DB의 critical write 대상이다.
- 순찰 작업 생성은 `DeliveryRequestRemoteService.create_patrol_task()`를 통해 서버로 전송한다.
- 작업 모니터는 task snapshot과 task event push를 반영하고, 순찰 낙상 알림, 증거사진 조회, 현장 조치 후 재개 UI를 포함한다.
- 순찰의 실제 ROS/DB/AI 연동 검증은 Control Service, ROS adapter, DB connectivity를 소유한 server-side runtime environment에서 수행한다.

이 문서의 전체 화면 구조는 운반 전용으로 설계하지 않는다. 운반 전용 필드는 작업 요청의 `Delivery` form과 작업 상세의 `Delivery detail` 영역에만 둔다.

### 2-4. UI/API 필드명 기준

새 UI 설계에서 사용하는 표준 필드명은 다음을 따른다.

| 개념 | UI/API 표준명 | 비고 |
| --- | --- | --- |
| 작업 ID | `task_id` | 숫자형 `u64`, 화면에는 정수로 표시 |
| 요청자 ID | `caregiver_id` | 숫자형. 현재 DB/API 호환 필드명이며 화면에는 운영자/요청자 식별자로 표시 |
| 어르신 ID | `member_id` | 숫자형 |
| 방문자 ID | `visitor_id` | 숫자형 |
| 물품 ID | `item_id` | 숫자형 |
| 주 실행 로봇 | `assigned_robot_id` | 예: `pinky2` |
| 작업 상태 | `task_status` | 예: `WAITING_DISPATCH`, `RUNNING`, `COMPLETED` |
| 작업 단계 | `phase` | 시나리오 내부 단계 |
| 실패/거절 사유 | `reason_code` | 사람이 읽는 메시지와 함께 표시 |

새 UI에서는 `assigned_pinky_id`를 사용하지 않는다. 로봇 로컬 또는 ROS adapter 내부에서만 `pinky_id` 같은 명칭이 등장할 수 있다.

---

## 3. 사용자와 운영 상황

### 3-1. 주요 사용자

관리자/관제 운영자 UI의 1차 사용자는 일반 요양보호사가 아니라 교육받은 관제 운영자 또는 시설 관리자이다.

운영자는 로봇 엔지니어는 아니지만, 요양보호사용 간단 요청 화면보다 높은 정보 밀도의 운영 정보를 다룰 수 있어야 한다. 다음 정보를 빠르게 이해할 수 있어야 한다.

- 지금 어떤 로봇이 사용 가능한가
- 내 요청이 접수되었는가
- 작업이 어디까지 진행되었는가
- 실패했다면 왜 실패했는가
- 취소할 수 있는가
- 로봇 또는 서버 연결에 문제가 있는가

실제 요양보호사용 UI는 이 Admin UI와 분리하고, 물품, 목적지, 현재 진행 상태, 긴급 알림, 직원 조치처럼 쉬운 요청/상태 문구만 노출한다.

관제 담당자는 Admin UI에서 진단 정보를 본다.

- 로봇별 상태와 최근 heartbeat
- task workflow 상태
- 이벤트 로그와 `reason_code`
- DB, Control Service, ROS2, AI Server 연결 상태

### 3-2. 운영 환경

관리자 UI는 데스크톱 또는 노트북에서 실행되는 PyQt6 앱을 기준으로 한다.

- 기준 해상도: 1280x800
- 권장 해상도: 1440x900 이상
- 넓은 화면에서는 대시보드 정보 밀도를 높인다.
- 좁은 화면에서는 좌측 사이드바와 주요 카드가 겹치지 않도록 scroll area를 사용한다.

---

## 4. 정보 구조

관리자/관제 운영자 UI의 권장 사이드바 구조는 다음과 같다.

| 메뉴 | 목적 | phase 1 우선순위 |
| --- | --- | --- |
| 홈 | 전체 운영 현황과 최근 작업 확인 | 높음 |
| 작업 요청 | 운반, 순찰 task 생성, 추종 비활성 탭 표시 | 높음 |
| 작업 모니터 | 진행 중/대기/완료/실패 작업 추적과 취소 | 높음 |
| 좌표/구역 설정 | DB 기반 구역, 정밀 주차 좌표, 목적지 좌표 설정 | 높음 |
| 로봇 상태 | 로봇별 연결, 배터리, 위치, 현재 작업 확인 | 중간 |
| 재고 관리 | 운반 가능한 물품과 수량 관리 | 높음 |
| 어르신 정보 | 어르신 검색, 선호/비선호, 최근 이벤트 확인 | 중간 |
| 알림/로그 | 운영 이벤트, 오류, 실패 사유 추적 | 중간 |

현재 구현은 홈, 작업 요청, 재고 관리, 어르신 정보, 알림/오류 중심이다. 설계상으로는 `작업 모니터`와 `로봇 상태`가 분리되는 것이 좋다. 이유는 홈 대시보드는 빠른 요약용이고, 장애 분석이나 취소 처리는 더 자세한 작업/로봇 단위 화면이 필요하기 때문이다.

phase 1 구현 부담을 줄이고 싶다면 `작업 모니터`는 홈 대시보드의 상세 버전으로 시작해도 된다. 단, 와이어프레임과 설계에서는 별도 페이지로 잡아두는 편이 이후 확장에 유리하다.

독립 시스템 상태 페이지는 phase 1 sidebar에 포함하지 않는다. 서비스 health는 홈에서 요약하고, 로봇 연결 상태는 로봇 상태 페이지에서 확인하며, 장애 원인 추적은 알림/로그에서 처리한다.

---

## 5. 디자인 시스템

### 5-1. 시각 방향

관리자 UI는 "따뜻한 요양 서비스"보다 "침착한 운영 관제 콘솔"에 가깝게 설계한다.

단, 의료/요양시설에서 사용하므로 지나치게 어둡거나 공격적인 관제 화면은 피한다. 배경은 밝고 안정적으로 유지하되, 상태 칩과 작업 카드에서 운영 우선순위가 즉시 보이도록 대비를 준다.

### 5-2. 색상 토큰

| 토큰 | 색상 | 사용처 |
| --- | --- | --- |
| `color-bg` | `#F5F7FA` | 앱 전체 배경 |
| `color-surface` | `#FFFFFF` | 카드, 폼, 테이블 영역 |
| `color-surface-soft` | `#EEF4F7` | 사이드바, 보조 패널 |
| `color-text-primary` | `#16202A` | 주요 텍스트 |
| `color-text-secondary` | `#5B6775` | 설명, 보조 텍스트 |
| `color-border` | `#D8E0E8` | 카드/테이블 경계 |
| `color-primary` | `#005C55` | 주요 액션, 현재 선택 메뉴 |
| `color-primary-strong` | `#004C46` | 주요 버튼 hover/pressed |
| `color-primary-accent` | `#0F766E` | 상태 강조, 보조 teal accent |
| `color-action-blue` | `#2563EB` | 진행 중, 정보성 액션 |
| `color-warning` | `#F59E0B` | 지연, 주의 |
| `color-danger` | `#DC2626` | 실패, 취소, 긴급 |
| `color-success` | `#16A34A` | 완료, 정상 |
| `color-muted` | `#94A3B8` | 비활성, 대기 |

### 5-3. 폰트

권장 폰트는 다음과 같다.

| 용도 | 폰트 |
| --- | --- |
| 기본 한글 UI | Pretendard |
| 대체 한글 UI | Noto Sans KR |
| 숫자/KPI | Pretendard SemiBold 또는 같은 계열 굵은 weight |

PyQt6 환경에서는 폰트 설치 여부가 로컬 머신마다 달라질 수 있다. 따라서 QSS에는 `"Pretendard", "Noto Sans KR", sans-serif` 순서로 지정한다.

PyQt6는 브라우저가 아니므로 웹 CSS처럼 CDN 기반 웹폰트나 `@font-face`에 의존하지 않는다. 권장 방식은 앱에 `.ttf` 또는 `.otf` 폰트 파일을 포함하고, 앱 시작 시 `QFontDatabase.addApplicationFont()`로 로드하는 것이다.

권장 정책:

| 항목 | 기준 |
| --- | --- |
| 기본 방식 | 앱 assets에 Pretendard 폰트 파일 포함 |
| 로딩 방식 | `QFontDatabase.addApplicationFont()` |
| fallback | 시스템에 설치된 `Noto Sans KR`, 이후 Qt 기본 sans-serif |
| 배포 가정 | 대상 머신에 폰트가 반드시 설치되어 있다고 가정하지 않음 |

### 5-4. 공통 컴포넌트

| 컴포넌트 | 목적 |
| --- | --- |
| `SidebarButton` | 좌측 메뉴 이동 |
| `PageHeader` | 페이지 제목, 설명, 주요 액션 표시. 시스템 상태 strip은 명시적으로 요청한 화면에서만 표시 |
| `PageTimeCard` | header 영역에 현재 시각/날짜와 선택적 마지막 갱신, 상태, 액션 표시 |
| `SystemStatusStrip` | Control Service, DB, ROS2, AI Server 상태 chip 표시 |
| `KeyValueRow` | 상세 데이터를 raw `key: value` 문자열이 아니라 작은 key 배지와 분리된 value로 표시 |
| `KpiCard` | 숫자 중심 운영 지표 표시 |
| `StatusChip` | 상태를 색상과 텍스트로 표시 |
| `RobotCard` | 로봇별 현재 상태 요약 |
| `TaskCard` | 작업 ID, 상태, 로봇, 목적지, 취소 가능 여부 표시 |
| `FlowColumn` | 작업 상태별 칸반 컬럼 |
| `DataTable` | 재고, 로그, 로봇, 작업 목록 표시 |
| `FormCard` | 입력 폼 그룹 |
| `ResultPanel` | 요청 결과, 실패 사유, 다음 행동 표시 |
| `EmptyState` | 데이터 없음 안내 |
| `LoadingState` | 서버 요청 중 표시 |
| `ErrorState` | 네트워크/서버/검증 실패 표시 |

### 5-5. 상태 칩 기준

| 상태 | 색상 | 표시 예 |
| --- | --- | --- |
| 정상 | Green | `정상`, `연결됨`, `완료` |
| 진행 | Blue | `진행 중`, `이동 중`, `요청 처리 중` |
| 대기 | Slate/Gray | `대기`, `미배정`, `준비 중` |
| 주의 | Amber | `지연`, `재고 부족`, `응답 대기` |
| 실패 | Red | `실패`, `연결 끊김`, `취소 실패` |
| 비활성 | Muted | `미지원`, `준비 중` |

색상만으로 상태를 구분하지 않는다. 칩 텍스트와 아이콘 또는 짧은 설명을 함께 사용한다.

---

## 6. 공통 레이아웃

### 6-1. 앱 프레임

관리자 앱은 다음 구조를 기본으로 한다.

global top navigation bar는 사용하지 않는다. 좌측 sidebar가 페이지 이동을 담당한다. 서비스 연결 상태는 모든 페이지에 기본 노출하지 않고, 홈 대시보드 health block처럼 실제 상태 맥락이 있는 화면에서만 `SystemStatusStrip`으로 표시한다.

```text
+---------------------------------------------------------------+
| Sidebar | PageHeader: title / subtitle / optional status      |
|         |-----------------------------------------------------|
|         | Main Content                                        |
|         |                                                     |
|         |                                                     |
+---------------------------------------------------------------+
```

권장 크기:

| 영역 | 기준 |
| --- | --- |
| Sidebar width | 240px 고정 기준 |
| PageHeader height | 72-96px, 페이지별 주요 액션 포함 가능 |
| Page horizontal margin | 24px |
| Card radius | 16-20px |
| Card padding | 18-24px |
| Primary button height | 44-48px |
| Table row height | 40-48px |

### 6-2. PageHeader와 SystemStatusStrip

`PageHeader`는 모든 관리자 화면에 유지한다. 다만 독립적인 top nav bar가 아니라 페이지 콘텐츠 영역의 첫 번째 공통 컴포넌트로 둔다.

시각적으로 `PageHeader`는 모든 관리자 페이지에서 가벼운 hero/card 처리를 사용한다. 옅은 배경, 좌측 accent, 제목, 설명으로 구성하고, 제목 위 eyebrow label은 넣지 않는다. 이렇게 해야 페이지 제목이 raw text처럼 보이지 않으면서 shell 컴포넌트를 하나로 유지할 수 있다.

표시 요소:

- 페이지 제목
- 페이지 설명
- 공통 `PageTimeCard`: 모든 관리자 페이지의 현재 시각/날짜, 선택적 마지막 갱신 시각, 상태 문구, 페이지 액션
- 페이지별 주요 액션, 예: 새로고침, 내보내기, 필터 초기화
- 선택적 `SystemStatusStrip`: Control Service, DB, ROS2, AI Server 상태 chip
- 현재 로그인 사용자 이름과 `caregiver_id`, 필요 시 우측 보조 영역에 표시
- 마지막 갱신 시각

`PageTimeCard`는 관리자 페이지 전반에서 안정적인 가로/세로 크기를 사용한다. 새로고침, 저장, 변경 취소, 스트림 재연결 같은 페이지별 action은 카드 안의 예약된 action row에 배치하며 세로로 쌓지 않는다. 상태 문구와 마지막 갱신 시각은 비어 있을 때도 slot을 예약해 다른 페이지로 이동하거나 action 구성이 달라져도 header 높이가 변하지 않게 한다. Header action button은 공통 버튼 padding을 수용할 수 있는 세로 높이를 유지해 한글 라벨이 위아래로 잘리지 않게 한다. 카드 하단 rounded corner가 잘리지 않도록 action row 아래의 세로 여유도 확보하며, 코드에서 고정한 버튼 높이와 충돌하는 QSS min/max height 규칙을 함께 적용하지 않는다.

`SystemStatusStrip`은 `PageHeader`의 기본 표시 요소가 아니다. 실제 상태 조회가 연결되지 않은 화면에서 `확인 중` 상태를 반복 노출하면 운영자가 장애 또는 지연으로 오해할 수 있으므로, 홈 대시보드는 기본 `확인 중` chip을 그대로 두지 않고 Control Service heartbeat 결과로 strip을 갱신해야 한다.

서비스 상태 chip은 nav item이 아니다. 클릭 이동이 필요하면 알림/로그 페이지로 이동하는 보조 액션으로만 사용한다.

상태가 비정상일 때는 해당 chip을 amber/red로 표시하고, 필요한 경우 알림/로그 페이지로 이동할 수 있게 한다.

### 6-2-1. 금지되는 관리자 shell 요소

와이어프레임을 PyQt로 전환할 때 다음 요소는 그대로 옮기지 않는다.

| 금지 요소 | 이유 |
| --- | --- |
| `RoboCare OS` 브랜드 | 제품명은 `ROPI`로 통일 |
| `Operational Console` global title | 페이지 제목과 중복되고 제품명이 아님 |
| `CONTROL SERVICE / DATABASE / ROS2 / AI SERVER` top nav | navigation이 아니라 상태 정보임 |
| 페이지별 중복 sidebar 구현 | PyQt에서는 shell의 단일 sidebar만 사용 |
| 페이지별 fixed/sticky topbar | PyQt layout과 맞지 않고 중복 상태를 만든다 |
| dark mode class | phase 1 light theme 기준 |
| 실제 기능 없는 `Manual Override` | 안전 기능이므로 backend 연동 전 노출 금지 |

### 6-2-2. Sidebar 통일 기준

관리자 sidebar는 모든 페이지에서 동일한 컴포넌트를 사용한다.

| 항목 | 기준 |
| --- | --- |
| 브랜드 | `ROPI` |
| 부제 | `관리자 콘솔` 또는 생략 |
| 폭 | 260px |
| 배경 | `color-surface-soft` |
| 활성 메뉴 | `color-primary` 왼쪽 indicator 또는 채운 배경 |
| 하단 영역 | 로그아웃 또는 현재 사용자 정보만 표시 |

메뉴 순서는 다음으로 고정한다.

```text
홈
작업 요청
작업 모니터
좌표/구역 설정
로봇 상태
재고 관리
어르신 정보
알림/로그
```

`Settings`, `Support` 같은 일반 설정 메뉴는 phase 1 제품 메뉴에서 제외한다. 단, 운반/순찰 task 실행에 직접 필요한 DB 기반 좌표와 구역 설정은 별도 업무 페이지인 `좌표/구역 설정`으로 제공한다. 독립 시스템 상태 페이지도 홈, 로봇 상태, 알림/로그와 기능이 겹치므로 phase 1 제품 메뉴에서 제외한다.

### 6-3. PyQt 크기 대응 정책

PyQt6는 Tailwind CSS처럼 breakpoint class를 선언하는 방식이 아니다. 창 크기 대응은 Qt layout system을 기준으로 설계한다.

사용 기준:

| 기술 | 사용 목적 |
| --- | --- |
| `QVBoxLayout`, `QHBoxLayout`, `QGridLayout` | 기본 배치 |
| `QSizePolicy.Expanding` | 남는 공간을 채워야 하는 카드, 테이블, 보드 |
| `QSizePolicy.Fixed` | 사이드바, 상태 칩, 고정 버튼 |
| layout stretch factor | 좌우 패널 비율 조절 |
| `minimumSize`, `minimumWidth` | 화면이 지나치게 무너지는 것 방지 |
| `QScrollArea` | 작은 화면에서 세로 스크롤 제공 |
| `resizeEvent()` | compact, regular, wide layout 전환 |

권장 breakpoint는 다음과 같다.

| 창 너비 | 레이아웃 기준 |
| --- | --- |
| `< 1280px` | compact. 주요 콘텐츠는 1-column, 긴 테이블/보드는 scroll 사용 |
| `1280-1599px` | regular. 기본 관리자 layout, 사이드바 + 본문 1-2 column |
| `>= 1600px` | wide. 대시보드 카드와 상세 패널을 동시에 노출 |

모든 위젯을 비율로 무작정 늘리지 않는다. KPI 카드, 상태 칩, 버튼은 최소/최대 크기를 둔다. 테이블, 작업 보드, 로그 리스트처럼 데이터가 많은 영역만 우선적으로 확장한다.

### 6-4. 데이터 갱신 정책

인터페이스 스펙상 custom TCP session push가 존재하므로, 운영성 데이터는 push-first로 설계한다. Polling은 push를 대체하는 기본 전략이 아니라 초기 snapshot, reconnect 보정, phase 1 fallback을 위한 보조 전략이다.

권장 갱신 방식:

| 데이터 | 권장 갱신 방식 |
| --- | --- |
| 작업 상태 변경 | TCP session push 우선, reconnect 후 snapshot query |
| 작업 feedback | TCP session push 우선 |
| 취소 결과 | TCP session push 우선, 요청 응답에는 접수 여부 표시 |
| 로봇 상태 | push 또는 1-2초 상태 topic 집계 push, fallback polling |
| 알림/운영 이벤트 | push 우선, 로그 페이지 진입 시 query |
| 홈 KPI/작업 보드 | 초기 snapshot query + 이후 push 반영 |
| 작업 모니터 | 초기 query + 이후 push 반영 |
| 재고 | 진입 시 조회 + 수동 새로고침 |
| 어르신 정보 | 검색 시 조회 |
| 시스템 health | heartbeat + 수동 재확인, 필요 시 fallback polling |

서버 요청은 PyQt UI thread를 막지 않아야 한다. 현재 구조처럼 `QThread` worker 또는 비동기 bridge를 사용해 UI freeze를 방지한다.

push 기반 UI를 구현할 때는 persistent TCP session을 UI thread 밖에서 읽고, Qt signal을 통해 main thread로 전달한다. response frame과 push frame은 demux되어야 하며, reconnect 후에는 누락 가능성을 보정하기 위해 최신 snapshot을 다시 조회한다.

관리자 shell은 dashboard-oriented page를 위한 공유 IF-COM-003 subscription 하나를 소유한다. Shell은 hard-coded page tuple을 유지하지 않고, 등록된 shell page 중 `apply_stream_event(event)`를 노출하는 page를 열거해 event object를 fan-out한다. Task Monitor처럼 독립 event stream을 소유하는 page는 공유 관리자 fan-out에서 명시적으로 opt-out한다.

Admin UI page는 stream event-loop 공통 동작을 page마다 timer/state로 중복 구현하지 않고 shared stream refresh helper를 사용한다. 공통 helper 범위는 의도적으로 좁게 둔다.

- 반복 stream-triggered refresh 요청을 하나의 callback으로 debounce
- page가 숨겨진 동안 visible-page refresh 작업을 지연하고 다시 보일 때 재개
- stream auto-reconnect 요청 상태를 page의 worker-thread lifecycle과 분리

payload contract와 렌더 대상이 page마다 다르므로 page-specific event patching은 각 page 안에 남긴다.

---

## 7. 페이지 설계

### 7-1. 관리자 인증 화면

#### 목적

관리자/관제 운영자 앱에 로그인하고 현재 사용자 식별자를 세션에 저장한다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| 브랜드 영역 | `ROPI`, 관리자/관제 운영 콘솔 제목, 관리자 앱 설명 |
| 로그인 카드 | 관리자/관제 운영자 로그인 제목, 아이디, 비밀번호 |
| 액션 | 로그인 버튼. 역할 선택/방문자 진입/뒤로가기 버튼은 표시하지 않음 |
| 서버 상태 | Control Service 연결 상태를 작은 chip으로 표시 |
| 상태 | 인증 실패, 서버 오류, 요청 중 inline 표시 |

#### 검증 규칙

- 아이디는 빈 값이면 안 된다.
- 비밀번호는 빈 값이면 안 된다.
- 서버 응답 실패 시 입력값을 유지하고 오류 메시지를 표시한다.
- 로그인 성공 시 `current_user.user_id`를 요청자 식별자로 사용한다. 현재 Control Service payload에서는 호환을 위해 계속 `caregiver_id`로 매핑한다.
- Enter 키로 로그인 요청을 실행할 수 있어야 한다.
- 관리자 앱 인증 화면은 현재 호환을 위해 `role=caregiver`로 로그인 요청을 보내지만, 화면 문구는 요양보호사가 아니라 관리자/관제 운영자로 표시한다.
- Control Service 상태 확인은 로그인 화면의 입력과 렌더링을 막지 않도록 UI thread 밖에서 수행한다.

#### 오류 메시지 기준

| 오류 | 메시지 기준 |
| --- | --- |
| 입력 누락 | `아이디와 비밀번호를 입력하세요.` |
| 인증 실패 | `아이디 또는 비밀번호가 올바르지 않습니다.` |
| 서버 연결 실패 | `관제 서버에 연결할 수 없습니다.` |

---

### 7-2. 홈 대시보드

#### 목적

관리자/관제 운영자가 현재 운영 상태를 10초 안에 파악하는 첫 화면이다.

홈 대시보드는 상세 분석 화면이 아니라 운영 요약 화면이다. 단, 작업 취소나 실패 인지는 홈에서도 가능해야 한다.

#### 주요 질문

홈 대시보드는 다음 질문에 답해야 한다.

- 지금 사용 가능한 로봇이 몇 대인가
- 진행 중인 작업이 있는가
- 대기 중인 작업이 밀려 있는가
- 최근 실패나 취소가 있었는가
- 어떤 로봇이 어떤 작업을 수행 중인가
- 로봇/작업 상태가 시스템 상태 화면으로 이동해야 할 정도로 비정상인가

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Page Header | 홈 전용 hero panel. 제목 `운영 대시보드`, 설명, heartbeat 기반 시스템 상태 chip, 별도 수동 새로고침/time card |
| KPI Row | 사용 가능 로봇, 대기 작업, 진행 작업, 경고/오류 |
| Robot Board | 로봇별 상태 카드 |
| Task Flow Board | 상태별 작업 칸반 |
| Recent Timeline | 최근 이벤트/작업 변화 |

#### KPI 카드

| 카드 | 표시 데이터 |
| --- | --- |
| 사용 가능 로봇 | available robot count, 전체 robot count |
| 대기 작업 | `WAITING_DISPATCH` 또는 `READY` 상태 count |
| 진행 작업 | `RUNNING`, `ASSIGNED`, `IN_PROGRESS` 계열 count |
| 경고/오류 | 최근 24시간 warning/error count |

KPI 카드는 숫자를 가장 크게 표시하고, 아래에 전일/최근 변화 대신 현재 운영 의미를 짧게 표시한다. 각 카드는 운영자가 빠르게 상태를 스캔할 수 있도록 의미 기반 tone/accent를 가진다. 사용 가능 로봇은 0대가 아니면 teal/green, 대기 작업은 조치가 필요하면 amber, 진행 작업은 수행 중이면 green/blue, 경고/오류는 0건이 아니면 red를 사용한다. 중립 상태 카드는 대비를 낮춘다.

홈 header는 단순 raw text block으로 두지 않는다. 공통 lightweight hero/card header의 연한 배경 tint와 left accent를 사용한다. 제목 위 별도 eyebrow label은 추가하지 않고, 무거운 card 안 card 구조도 만들지 않는다.

작업 취소 실패 같은 일시적 운영 alert는 time/refresh card 안에 렌더링하지 않는다. top row 아래, KPI row 위에 전체 폭 inline banner로 표시한다. 이렇게 해야 긴 오류 메시지가 top row 높이를 키우면서 페이지 제목/설명 영역까지 늘어나 보이는 문제를 막을 수 있다.

#### 로딩/갱신 동작

Home header의 heartbeat 기반 시스템 상태 chip은 무거운 dashboard bundle 조회와 분리해서 갱신한다. Home이 표시되는 동안 UI는 header chip 전용 경량 주기 heartbeat 조회를 수행해 `ROS2`, `DB`, `AI` 상태 변화가 수동 dashboard 새로고침이나 task/robot stream event 없이도 반영되게 한다.

경량 heartbeat 갱신은 KPI row, robot board, task flow board, timeline을 다시 로드하지 않는다. 해당 영역은 명시적인 dashboard load와 IF-COM-003 stream event 기반 dashboard 수렴 경로로 갱신한다.

IF-COM-003 stream event 기반 dashboard 수렴은 Home이 보이는 동안에만 수행하거나, Home이 다시 보일 때까지 지연해야 한다. 숨겨진 Home page에서 stream event가 계속 full dashboard bundle reload를 수행하면 안 된다.

빈번한 robot status event는 Home snapshot이 이미 렌더링된 상태에서 full dashboard bundle을 다시 조회하지 않는다. `PINKY_UPDATED`와 `ARM_UPDATED`는 event payload로 해당 Robot Board card를 patch하고 Home 마지막 갱신 표시만 갱신한다. `TASK_UPDATED`는 초기 task-flow snapshot이 있고 event payload가 task identity/status 등 최소 렌더링 필드를 포함하면 기존 task card를 patch하거나 새 task card를 추가한 뒤 렌더링된 task flow 기준으로 대기/진행 KPI를 재계산할 수 있다. `ALERT_CREATED` / `FALL_ALERT_CREATED`와 `TASK_UPDATED.fall_alert`에 실린 동일 alert object는 초기 Home snapshot이 이미 있을 때 alert당 한 번만 Home warning/error KPI를 증가시키고 최근 timeline row를 앞에 추가한다. 이전 snapshot이 없거나 reconnect 이후 보정이 필요하거나 event payload만으로 local patch를 만들 수 없으면 full dashboard reload 수렴 경로를 유지한다.

예:

```text
진행 작업
2
운반 1건, 순찰 1건
```

#### Robot Board

로봇 카드는 다음 필드를 표시한다.

| 필드 | 설명 |
| --- | --- |
| `robot_id` | 예: `pinky1`, `pinky2`, `pinky3`, `jetcobot1`, `jetcobot2` |
| `robot_type` | 모바일 로봇, 로봇팔 같은 하드웨어 구분 |
| `capabilities` | DELIVERY, PATROL, GUIDE, MANIPULATION 같은 스케줄러용 지원 기능 |
| `connection_status` | ONLINE, OFFLINE, DEGRADED |
| `battery_percent` | 모바일 로봇에 표시 |
| `current_location` | 알 수 없으면 `-` |
| `current_task_id` | 현재 작업이 있으면 표시 |
| `last_seen_at` | 마지막 상태 수신 시각 |

로봇 카드는 robot ID를 고정 시나리오 역할처럼 취급하지 않는다. 운반/순찰 모바일 로봇은 scheduling/current task assignment로 결정한다. 운반 픽업/목적지 arm 같은 고정 station robot만 station assignment 데이터로 설명한다.

로봇 카드는 홈 작업 카드와 같은 2열 label/value 패턴을 사용한다. 헤더는 고유 로봇 이름/ID인 `robot_id`만 표시한다. 예를 들어 `pinky2`, `jetcobot1`처럼 보여주며, `ARM jetcobot1`, `Jetcobot · jetcobot1`, `Pinky Pro · pinky2`처럼 타입/표시명/ID를 제목에 이어 붙이지 않는다. connection status chip은 우측에 둔다. 구분, 지원 기능, 현재 작업, 위치, 배터리, 마지막 수신 같은 key는 compact badge로 분리한다. `ONLINE`, `OFFLINE`, `DEGRADED` 상태별로 카드 tone을 다르게 적용하며, offline 카드는 muted tone으로 낮추고 stale 상태의 이유가 되는 마지막 수신 시각을 명확히 보여준다.

로봇 온라인 여부는 seed 또는 오래된 runtime row가 아니라 최근 runtime heartbeat 기준으로 판단한다. `last_seen_at`이 없거나 Control Service freshness threshold보다 오래되면 `OFFLINE`으로 표시한다. `current_location`은 IP 주소로 fallback하지 않는다. 구역 매핑이 구현되기 전에는 pose가 있으면 좌표 라벨로 표시하고, pose가 없으면 위치 미수신으로 표시한다. 시간 값은 `T`가 포함된 raw ISO 문자열이 아니라 `2026-05-03 12:00:00`처럼 운영자가 읽기 쉬운 형식으로 표시한다.

#### Task Flow Board

작업 flow board는 칸반 형태를 사용한다. board 제목은 scroll 영역 바로 위에만 표시하고, "현재 요청된 작업을 상태별로 분류해 보여줍니다." 같은 별도 설명 문구는 두지 않는다.

작업 카드가 많아져도 전체 대시보드가 과도하게 길어지지 않도록 board 내부에 별도 scroll 영역을 둔다. 컬럼 분류는 KPI row와 같은 기준을 사용한다. 예를 들어 `READY`는 배정 작업이 아니라 대기 작업이다.

권장 컬럼:

| 컬럼 | 포함 상태 |
| --- | --- |
| 대기 | `WAITING_DISPATCH`, `READY` |
| 배정 | `ASSIGNED` |
| 진행 | `RUNNING`, `IN_PROGRESS` |
| 취소 중 | `CANCEL_REQUESTED`, `CANCELLING`, `PREEMPTING` |
| 완료/실패 | `COMPLETED`, `FAILED`, `CANCELLED` |

작업 카드 표시 필드:

| 필드 | 설명 |
| --- | --- |
| `task_id` | 가장 눈에 띄게 표시 |
| `task_type` | DELIVERY, PATROL, GUIDE, FOLLOW |
| `priority` | NORMAL, URGENT, HIGHEST |
| `assigned_robot_id` | 배정 로봇 |
| `phase` | 현재 단계 |
| `destination_label` | 사람이 읽는 목적지 |
| `feedback_summary` | 최근 feedback 요약 |
| `reason_code` | 실패/거절/취소 사유가 있을 때 표시 |
| `cancellable` | 취소 버튼 노출 여부 결정 |

작업 카드는 `#6 DELIVERY / WAITING_DISPATCH` 같은 단일 raw multi-line 문자열로 표시하지 않는다. 카드 헤더는 `작업 #6 · 운반`처럼 사람이 읽는 제목과 `배차 대기` 같은 별도 상태 chip으로 구성한다. 본문은 로봇, 단계, 목적지, feedback, 사유를 짧은 label/value row로 표시한다. raw `result_message` 또는 exception text는 운영자 요약 뒤의 작은 상세 행에서만 표시한다.

홈에서는 task type, task status, phase를 짧은 한국어 라벨로 표시한다. 알 수 없는 code는 fallback으로 표시할 수 있지만, phase 1에서 자주 나오는 `DELIVERY`, `PATROL`, `WAITING_DISPATCH`, `RUNNING`, `MOVE_TO_PICKUP`, `ROS_SERVICE_UNAVAILABLE`, ROS IPC 실패는 운영자가 읽을 수 있는 문구로 매핑해야 한다.

취소 버튼은 `cancellable=true`이고 상태가 취소 가능한 경우에만 활성화한다. `CANCEL_REQUESTED` 상태에서는 버튼을 비활성화하고 `취소 처리 중`으로 표시한다.

취소 결과는 `result_code / reason_code: message` raw text가 아니라 구조화된 inline banner로 표시한다. banner는 제목(`취소 요청 접수` 또는 `작업 취소 실패`), 운영자 요약, 선택적 상세 행을 가진다. ROS가 없는 로컬 개발 환경에서 발생하는 ROS bridge 연결 실패는 `ROS 브릿지에 연결할 수 없습니다`로 요약하고, raw transport error는 상세 행에서만 보여준다.

#### Recent Timeline

타임라인은 최근 운영 흐름을 보여준다.

표시 필드:

| 필드 | 설명 |
| --- | --- |
| `occurred_at` | 이벤트 발생 시각 |
| `severity` | INFO, WARNING, ERROR, CRITICAL |
| `source_component` | UI, Control Service, ROS Adapter, DB Writer 등 |
| `task_id` | 관련 작업 ID |
| `robot_id` | 관련 로봇 ID |
| `event_type` | 이벤트 종류 |
| `message` | 사람이 읽는 설명 |

홈에서는 최근 10-20개만 표시한다. 전체 조회는 알림/로그 페이지에서 처리한다.

---

### 7-3. 작업 요청 페이지

#### 목적

관리자/관제 운영자가 운반, 순찰 task를 생성하는 화면이다. 안내 요청은 관리자 작업 요청 화면에서 제외하고 방문자 키오스크 흐름에서 다룬다. 추종은 phase 1 완성 범위가 아니므로 제출 가능한 form 없이 비활성 탭으로만 표시한다.

화면 구조는 실제 제출 가능한 시나리오와 비활성 확장 시나리오를 명확히 구분한다. 탭 라벨은 운영자가 실제 선택 가능한 항목처럼 오해하지 않도록 `물품 운반`, `순찰`, `추종`만 표시하고, `추종` 버튼은 disabled 상태로 둔다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Page Header | `작업 요청`, 설명. 시스템 상태 strip은 이 화면에서는 기본 노출하지 않음 |
| Scenario Tabs | 물품 운반, 순찰, 추종. 추종은 disabled |
| Main Form | 선택한 시나리오 입력 폼 |
| Side Panel | 요청 미리보기, 실시간 로봇 상태, 최근 요청 결과, 주의사항 |

#### 공통 요청 구조

모든 시나리오 요청은 다음 공통 필드를 가진다.

| 필드 | 설명 |
| --- | --- |
| `task_type` | DELIVERY, PATROL |
| `caregiver_id` | 로그인 사용자 |
| `priority` | NORMAL, URGENT, HIGHEST |
| `notes` | 요청 메모 |
| `request_id` | UI 요청 추적 ID |
| `idempotency_key` | 중복 요청 방지 |

#### 운반 요청 폼

운반 요청은 현재 실제 서버 연동이 완료된 form이다. UI에서는 시나리오 탭 중 하나로 배치하고, 실제 제출 가능 상태를 명확히 표시한다.

입력 필드:

| 필드 | UI 요소 | 필수 | 설명 |
| --- | --- | --- | --- |
| `item_id` | 검색 가능한 combo box | Y | 운반할 물품. 운영자에게는 물품명과 재고만 표시하고 payload는 숫자형 `item_id`만 사용 |
| `quantity` | number stepper 또는 spin box | Y | 요청 수량. 기본 Qt 회색 화살표 subcontrol을 그대로 쓰지 않고 앱 스타일의 stepper로 덮어쓴다 |
| `destination_id` | 검색 가능한 combo box | Y | 예: `delivery_room_301`, `room_301`. 현재 phase 1은 실제 서버 설정된 목적지만 활성화 |
| `priority` | segmented button | Y | 화면 라벨은 `일반`, `긴급`, `최우선` 한글로 표시하고 payload는 인터페이스 스펙 기준 `NORMAL`, `URGENT`, `HIGHEST`를 사용 |
| `notes` | 낮은 textarea | N | 요청 메모. 폼 균형을 위해 72-88px 수준으로 제한하고 label과 textarea 사이 여백은 2px 수준의 compact spacing을 사용 |

작업 요청 폼의 row 간격은 일반 카드 간격보다 좁게 유지한다. 특히 `priority` segmented button과 `notes` textarea 사이의 grid row spacing은 6px 이하로 제한해, 우선순위와 추가 메모가 하나의 요청 옵션 묶음처럼 보이게 한다.

작업 요청 좌측 form card는 남는 화면 높이를 억지로 채우지 않는다. 현재 선택된 form content의 높이만큼 scroll/container 높이를 잡고, 버튼 아래에 빈 card 영역이 크게 생기지 않게 한다. form이 실제로 화면보다 길어지는 시나리오에서만 scroll이 의미 있게 동작해야 한다.

검색 가능한 combo box, field group, priority segmented button은 시나리오별 form 클래스에 중복 구현하지 않고 공통 form control helper로 만든다. 순찰 form이 운반 form의 private/static helper를 호출하는 식의 교차 의존은 금지한다.

요청 payload 생성, preview payload 생성, 서버 응답 정규화는 QWidget 내부에 직접 구현하지 않고 pure builder 함수로 분리한다. QWidget은 현재 입력값을 읽고 builder를 호출하며, 검증 오류 메시지를 inline status로 표시하는 역할만 맡는다.

작업 요청 페이지 구현은 shell/page orchestration과 시나리오별 form을 파일 단위로 분리한다. `task_request_page.py`는 page 조립, 탭 전환, side panel 연결만 담당하고, 운반/순찰 form과 worker는 별도 모듈에서 관리한다. 비활성 추종 탭은 제출 form을 만들지 않는다.

작업 요청 옵션 조회는 운반 물품 전용 로더로 명명하지 않는다. 물품 목록, 운반 목적지, 순찰 구역처럼 여러 시나리오가 공유하는 조회는 `TaskRequestOptionsLoadWorker`처럼 작업 요청 옵션 전체를 나타내는 이름과 payload 구조를 사용한다.

자동 설정 필드:

| 필드 | 설정 방식 |
| --- | --- |
| `caregiver_id` | 로그인 사용자 세션 |
| `request_id` | UI에서 생성하는 요청 추적 ID |
| `idempotency_key` | 중복 요청 방지용 hidden field |
| `assigned_robot_id` | phase 1에서는 서버가 `pinky2`로 응답 |

#### 운반 요청 미리보기

전송 전에 오른쪽 패널에 다음을 표시한다. 물품과 목적지는 검색 가능한 combo box에서 선택한 값을 기준으로 동기화한다. 사이드 패널의 정보는 `key: value` 텍스트 나열이 아니라 한글 label/value row와 상태 chip으로 표현한다. 미리보기 카드는 작업 요청 페이지의 다른 카드와 같은 밝은 카드 톤을 사용하고, 혼자 어두운 배경을 쓰지 않는다.

```text
요청자: caregiver_id
물품: item_name
수량: quantity
목적지: destination label / destination_id
우선순위: priority
```

미리보기에는 서버가 확정하기 전인 `task_id`를 표시하지 않는다.

오른쪽 패널에는 phase 1 placeholder로 `실시간 로봇 상태` card를 둔다. 실제 feedback stream이 연결되기 전에는 `assigned_robot_id`, `state`, `pose`, `destination_id`, 지도 placeholder를 표시하고, 작업 생성 또는 preview 변경 시 가능한 필드만 갱신한다.

IF-COM-003 event stream이 연결된 후에는 Task Request page shell이 `TASK_UPDATED`와 `ACTION_FEEDBACK_UPDATED` event를 side panel로 전달해야 한다. 최근 요청 결과와 실시간 로봇 상태 card는 page 이동이나 수동 새로고침 없이 현재 작업 기준으로 갱신되어야 한다.

`요청 미리보기`, `실시간 로봇 상태`, `최근 요청 결과` card에는 별도 설명 문구를 두지 않는다. card 제목과 row label만으로 의미를 전달한다. payload field 이름은 내부 테스트/연동 계약에는 남기되, 화면에는 `요청자`, `물품`, `수량`, `목적지`, `우선순위`, `로봇`, `상태`, `위치`처럼 운영자가 읽는 label을 우선한다.

Side Panel은 하나의 거대한 QWidget이 아니라 다음 카드 컴포넌트의 조합으로 구현한다. `RequestPreviewCard`, `RobotStatusCard`, `RequestResultCard`, `NoticeCard`는 각자의 label과 update 책임만 가진다. `TaskRequestSidePanel`은 카드 조립과 시나리오별 adapter 호출만 담당한다.

#### 검증 규칙

| 조건 | UI 동작 |
| --- | --- |
| 물품 미선택 | `물품을 선택하세요.` 표시 |
| 수량 0 이하 | `수량은 1개 이상이어야 합니다.` 표시 |
| 재고 부족 | warning 표시 후 요청 버튼 비활성 또는 확인 필요 |
| 목적지 미선택 | `목적지를 선택하세요.` 표시 |
| 서버 연결 실패 | 요청 버튼 비활성 또는 에러 표시 |

#### 요청 결과 패널

운반 요청 응답은 다음 필드를 표시한다.

| 필드 | 표시 방식 |
| --- | --- |
| `result_code` | 성공/거절 상태 chip |
| `result_message` | 사람이 읽는 메시지 |
| `reason_code` | 거절/실패 시 원인 코드 |
| `task_id` | 성공 시 크게 표시 |
| `task_status` | 예: `WAITING_DISPATCH` |
| `assigned_robot_id` | 예: `pinky2` |
| `cancellable` | 취소 버튼 활성화 판단. 응답에 없으면 `task_status` 기반 fallback 사용 |

작업 요청 화면의 `최근 요청 결과` card에는 운반 task 취소 버튼을 둔다. 버튼은 `task_id`가 있고 `cancellable=true`이거나 상태가 `WAITING`, `WAITING_DISPATCH`, `READY`, `ASSIGNED`, `RUNNING`일 때만 활성화한다. `CANCEL_REQUESTED`, `CANCELLING`, `PREEMPTING`, `CANCELLED`, `COMPLETED`, `FAILED` 상태에서는 비활성화하고, 취소 요청 전송 중에도 중복 클릭을 막는다.

취소 응답도 같은 card에 표시한다. 즉 `IF-COM-002` 응답의 `result_code`, `result_message`, `reason_code`, `task_id`, `task_status`, `assigned_robot_id`, `cancel_requested`를 기존 요청 결과 row에 반영한다.

성공 예:

```text
작업이 접수되었습니다.
작업 번호: 1001
상태: WAITING_DISPATCH
배정 로봇: pinky2
```

거절 예:

```text
작업 요청이 거절되었습니다.
reason_code: OUT_OF_STOCK
메시지: 요청 수량이 현재 재고보다 많습니다.
```

#### 순찰 요청 탭

순찰 탭은 `IF-PAT-001 Create Patrol Task`를 기준으로 설계한다. 운반과 달리 작업 요청 form은 waypoint/path를 직접 만들지 않는다. form은 `patrol_area` 테이블의 순찰 구역을 선택하고, Control Service가 `patrol_area_id`를 서버 관리 순찰 경로 snapshot으로 해석해 `patrol_area_revision`과 실제 `nav_msgs/Path`를 확정한다. 순찰 waypoint/path 편집은 별도 좌표/구역 설정 페이지가 담당한다.

Phase 1에서 순찰 탭은 운반 탭과 같은 작업 요청 화면 안에 배치하되, 입력 폼과 요청 미리보기/생성 결과 패널만 순찰 scenario에 맞게 바꾼다.

#### 순찰 화면 책임 분리

순찰 UI는 **요청 생성**과 **진행 중 작업 처리**를 분리한다.

| 화면/영역 | 책임 | 포함할 항목 |
| --- | --- | --- |
| 순찰 요청 탭 | 새 순찰 task 생성 | 순찰 구역 선택, 우선순위, 요청 메모 preview, 요청 제출, 생성 결과 |
| 작업 모니터 상세 패널 | 생성된 task의 진행/대응 처리 | task 상태, waypoint 진행률, 로봇 feedback, 낙상 알림, 낙상 사진 보기, 재개/중단 |
| 낙상 사진 dialog | 증거 이미지 확인 | `IF-PAT-007` 조회 결과 이미지, 감지 메타데이터, 만료/미존재 오류 |
| 순찰 재개 modal | 현장 조치 audit 입력 후 재개 | `member_id`, `action_memo`, 재개 제출 |

순찰 요청 탭에는 `WAITING_FALL_RESPONSE` 대응 UI를 직접 넣지 않는다. 요청 탭은 아직 task가 생성되기 전의 입력 화면이고, 낙상 대응은 이미 생성되어 실행 중인 task에 대한 조치이기 때문이다.

MVP에서는 별도 `순찰 현황` 페이지를 새로 만들기보다, 기존 `작업 모니터`의 상세 패널을 순찰 task 선택 시 확장하는 편이 맞다. 이후 여러 순찰 task를 동시에 관제하거나 지도 기반 모니터링이 필요해지면 `순찰 현황` 전용 페이지로 분리한다.

입력 필드:

| 필드 | UI 요소 | 필수 | 설명 |
| --- | --- | --- | --- |
| `patrol_area_id` | 검색 가능한 combo box | Y | 순찰할 구역 ID. 표시 텍스트는 구역명을 우선하고, 필요 시 구역 ID를 보조 텍스트로만 보여준다 |
| `patrol_area_name` | 선택 결과 표시 | N | 서버/설정에서 내려온 사람이 읽는 구역명. payload에는 넣지 않고 preview용으로 사용 |
| `map_id`, `waypoint_count`, `path_frame_id` | 순찰 요청 폼에는 표시하지 않음 | N | DB의 순찰 경로 설정 검증용 기술 정보다. 일반 요양보호사 요청 UI가 아니라 별도 좌표/구역 설정 페이지에서 다룬다 |
| `priority` | segmented button | Y | 화면 라벨은 `일반`, `긴급`, `최우선`; payload는 `NORMAL`, `URGENT`, `HIGHEST` |
| `notes` | 낮은 textarea | N | 순찰 요청 메모. PAT-001 payload에는 없으므로 phase 1에서는 UI preview/log용으로만 두거나, 서버 스펙 확장 전에는 payload에 포함하지 않는다 |

자동 설정 필드:

| 필드 | 설정 방식 |
| --- | --- |
| `request_id` | UI에서 생성하는 요청 추적 ID |
| `caregiver_id` | 로그인 사용자 세션 |
| `idempotency_key` | 중복 요청 방지용 hidden field |
| `assigned_robot_id` | UI 상수나 patrol area 옵션으로 만들지 않는다. PAT-001 서버 응답 또는 task update의 `task.assigned_robot_id`를 표시한다 |

PAT-001 요청 payload:

```json
{
  "request_id": "req_patrol_001",
  "caregiver_id": 1,
  "patrol_area_id": "patrol_ward_night_01",
  "priority": "NORMAL",
  "idempotency_key": "idem_patrol_001"
}
```

PAT-001 응답에서 오른쪽 결과 패널에 표시할 필드:

| 필드 | 표시 방식 |
| --- | --- |
| `result_code` | 성공/거절 상태 chip |
| `result_message` | 사람이 읽는 메시지 |
| `reason_code` | 거절/실패 시 원인 코드 |
| `task_id` | 성공 시 크게 표시 |
| `task_status` | 예: `WAITING_DISPATCH` |
| `assigned_robot_id` | 예: `pinky3` |
| `patrol_area_id` | 확정된 구역 ID |
| `patrol_area_name` | 확정된 구역명 |
| `patrol_area_revision` | 생성 시 고정된 구역 revision |

거절 reason code는 운영자가 바로 조치할 수 있게 메시지와 함께 표시한다.

| `reason_code` | UI 표시 의도 |
| --- | --- |
| `REQUESTER_NOT_AUTHORIZED` | 권한 문제. 로그인 계정/역할 확인 유도 |
| `PATROL_AREA_ID_INVALID` | UI 선택값 또는 설정 오류 |
| `PRIORITY_INVALID` | 우선순위 코드 매핑 오류 |
| `PATROL_AREA_NOT_FOUND` | 구역 설정 누락 |
| `PATROL_AREA_DISABLED` | 비활성 구역 선택 |
| `PATROL_AREA_OUT_OF_SCHEDULE` | 현재 시간 정책상 순찰 불가 |
| `PATROL_PATH_CONFIG_MISSING` | 구역은 있으나 waypoint/path 설정 누락 |
| `NO_ELIGIBLE_PINKY` | 순찰 가능한 Pinky 없음 |
| `PATROL_PATH_SERVICE_UNAVAILABLE` | 경로 생성/내비게이션 설정 또는 관련 서비스 불가 |

#### 순찰 요청 미리보기

전송 전 오른쪽 패널의 `요청 미리보기` card는 선택된 순찰 구역과 요청 payload 기준 필드를 표시한다.

| Row label | 표시 값 |
| --- | --- |
| 요청자 | `caregiver_id` |
| 순찰 구역 | `patrol_area_name` |
| 구역 ID | `patrol_area_id` |
| 우선순위 | 한글 priority chip |

미리보기에는 서버가 확정하기 전인 `task_id`, `patrol_area_revision`을 표시하지 않는다. revision은 응답 이후 결과 패널에서 표시한다.

순찰 요청 폼에는 `map_id`, waypoint 수, frame을 노출하지 않는다. 이 값들은 요청자가 판단해야 하는 입력값이 아니라 서버가 순찰 구역을 실제 `nav_msgs/Path`로 해석하기 위한 설정값이다. 편집/검증 UI가 필요하면 작업 요청 화면이 아니라 좌표/구역 설정 페이지에서 제공한다.

#### 순찰/추종 탭 상태

현재 phase 1 구현 상태는 다음 방식으로 표현한다.

| 탭 | 표현 |
| --- | --- |
| 순찰 | PAT-001 기준 구역 선택 form, 요청 미리보기, 생성 결과, 작업 모니터의 낙상 대응 UI를 제공. 실제 DB/ROS/AI 검증은 server-side runtime environment에서 수행 |
| 추종 | 탭 라벨은 `추종`으로 표시하되 disabled 처리한다. 관리자 UI phase 1 완성 범위에 포함하지 않으므로 제출 form, 준비 중 문구, 서버 요청 버튼을 만들지 않는다 |

향후 실제 연동 시나리오별 form은 다음 구조를 기준으로 확장한다.

| 시나리오 | 주요 입력 필드 | 비고 |
| --- | --- | --- |
| 순찰 | `patrol_area_id`, `priority`, `notes` | 로봇 배정은 patrol area 속성이 아니라 서버 task 생성/스케줄링 결과다. `patrol_area_name`, `patrol_area_revision`은 응답/표시 필드 |
| 안내 | `member_id`, `visitor_id`, `start_location_id`, `destination_id`, `priority`, `notes` | 키오스크 안내 요청과 연결 |
| 추종 | `target_caregiver_id`, `follow_mode`, `start_location_id`, `priority`, `notes` | phase 1 관리자 UI에서는 비활성 탭만 제공하고 form 구현은 보류 |

---

### 7-4. 작업 모니터 페이지

#### 목적

작업 모니터는 전체 작업을 상태, 종류, 로봇, 시간 기준으로 조회하고 취소 또는 상세 확인을 수행하는 화면이다.

홈 대시보드보다 상세하고, 알림/로그 페이지보다 작업 중심이다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| 필터 바 | 작업 종류, 상태, 로봇, 기간, 검색 |
| 작업 테이블 | 전체 작업 목록 |
| 상세 패널 | 선택한 작업의 세부 정보 |
| 액션 영역 | 취소 요청, 새로고침, 스트림 재연결, 로그 보기 |

#### 작업 테이블 필드

| 컬럼 | 설명 |
| --- | --- |
| `task_id` | 숫자형 ID |
| `task_type` | DELIVERY, PATROL, GUIDE, FOLLOW |
| `task_status` | 현재 상태 |
| `phase` | 내부 단계 |
| `priority` | 우선순위 |
| `assigned_robot_id` | 배정 로봇 |
| `created_at` | 생성 시각 |
| `updated_at` | 마지막 갱신 시각 |
| `result` | 완료/실패/취소 결과 |

#### 스트림 및 새로고침 상태

작업 목록 상단에는 수동 복구용 action을 둔다.

| 액션 | 동작 |
| --- | --- |
| `새로고침` | Control Service의 task monitor snapshot을 다시 조회한다. 기존 event stream이 살아 있으면 끊지 않고 snapshot만 덮어쓴다 |
| `스트림 재연결` | 현재 task event stream client를 닫고, UI가 알고 있는 마지막 `batch_end_seq` 이후부터 IF-COM-003 stream을 다시 구독한다 |

상태 표시는 다음을 포함한다.

| 표시 | 규칙 |
| --- | --- |
| stream status | 초기 상태 조회 중, 조회 완료, 이벤트 스트림 연결 중, 수신 중, 중단/실패 메시지 |
| 마지막 업데이트 | snapshot 반영, event batch 반영, 취소/재개 응답 반영 시각을 표시한다. 초기값은 `마지막 업데이트: -` |
| 재연결 | stream 중단 시 버튼을 사용할 수 있어야 한다. 수동 재연결은 마지막 수신 seq를 보존해서 중복/누락 가능성을 줄인다 |

event stream이 일시적인 서버/네트워크 문제로 끊기면 page는 마지막 수신 seq 이후부터 자동 재연결을 예약해야 한다. 명시적인 운영자 복구를 위해 수동 재연결 action은 유지하며, 알려진 sequence cursor를 초기화하면 안 된다.

#### 상세 패널

작업을 선택하면 오른쪽 또는 하단 패널에 다음을 표시한다.

| 영역 | 내용 |
| --- | --- |
| 작업 요약 | `task_id`, type, status, phase, priority |
| 요청 정보 | 요청자, 요청 시각, 목적지, 메모 |
| 로봇 정보 | `assigned_robot_id`, 현재 위치, 최근 feedback |
| 결과 정보 | `reason_code`, failure message, completed_at |
| 이벤트 | 해당 task의 최근 이벤트 5-10개 |

결과 정보는 항상 같은 위치에 표시한다. 아직 결과가 없으면 `-`로 둔다.

| Row label | 표시 값 |
| --- | --- |
| 결과 | `result_code` 또는 snapshot의 `task_outcome` |
| 사유 | `reason_code` 또는 `latest_reason_code` |
| 메시지 | `result_message` 또는 event/응답 message |

`FAILED`, `REJECTED`, `CANCEL_REQUESTED`, `CANCELLED` 상태이거나 result code가 `FAILED`, `REJECTED`, `CLIENT_ERROR`, `NOT_ALLOWED`, `NOT_FOUND`, `CANCEL_REQUESTED`, `CANCELLED`이면 결과 정보 card를 강조한다. 운영자가 실패/거절/취소 원인을 바로 볼 수 있어야 하므로, 취소/재개/증거사진 조회 응답도 가능한 경우 같은 `result_code`, `reason_code`, `result_message` 필드로 상세 패널에 반영한다.

#### 시나리오별 상세 패널

작업 모니터의 기본 필드는 모든 task에 공통으로 표시한다. 시나리오별 고유 데이터는 상세 패널 안에서 별도 section으로 분리한다.

| 시나리오 | 상세 section |
| --- | --- |
| DELIVERY | 물품, 수량, 목적지, pickup/destination arm robot |
| PATROL | 순찰 구역, waypoint/path 진행률, 낙상 감지 이벤트, 낙상 증거 이미지 조회 상태 |
| GUIDE | 방문자/어르신 연결 정보, 출발지, 목적지, 안내 진행 상태 |
| FOLLOW | 추종 대상, 추종 모드, 복귀/중단 상태 |

GUIDE 상세 패널은 다음 row를 고정으로 표시한다.

| Row label | Source field |
| --- | --- |
| 안내 단계 | `guide_detail.guide_phase`, 없으면 공통 `phase` |
| 추적 ID | `guide_detail.target_track_id` |
| 방문자 | `guide_detail.visitor_id`, `guide_detail.visitor_name`, `guide_detail.relation_name` |
| 어르신 | `guide_detail.member_id`, `guide_detail.resident_name`, `guide_detail.room_no` |
| 목적지 | `guide_detail.destination_id`, `guide_detail.destination_zone_id`, `guide_detail.destination_zone_name` |

GUIDE의 거절, 취소, ROS runtime 실패 원인은 이 section에 중복 표시하지 않는다. 공통 결과 정보 card에서 `result_code` 또는 `task_outcome`, `reason_code` 또는 `latest_reason_code`, `result_message`로 표시한다.

PATROL 상세 패널은 다음 sub-section으로 고정한다.

| Sub-section | 내용 |
| --- | --- |
| 순찰 요약 | `patrol_area_name`, `patrol_area_revision`, `assigned_robot_id` |
| 진행 상태 | `patrol_status`, `current_waypoint_index`, `total_waypoints`, `distance_remaining_m` |
| 지도 | 순찰 경로, waypoint, 로봇 현재 위치, 낙상 감지 지점 marker |
| 낙상 알림 | `ALERT_CREATED` 요약, `zone_name`, `confidence`, `frame_ts`, `evidence_image_available` |
| 액션 | `낙상 사진 보기`, `현장 조치 완료 후 순찰 재개`, `순찰 중단` |
| 이벤트 | 최근 `FALL_ALERT_CREATED`, `PATROL_RESUMED`, `COMMAND_FAILED` 등 |

PATROL 상세 패널 액션은 task 상태에 따라 노출한다.

| 상태 | 노출 액션 |
| --- | --- |
| `WAITING_DISPATCH`, `ASSIGNED`, `RUNNING` | `순찰 중단` |
| `WAITING_FALL_RESPONSE` | `낙상 사진 보기`, `현장 조치 완료 후 순찰 재개`, `순찰 중단` |
| `RECOVERING` | 중복 재개 방지를 위해 재개 버튼 비활성, 상태 메시지만 표시 |
| `COMPLETED`, `CANCELLED`, `FAILED` | 조회 액션만 유지하고 mutation 액션 비활성 |

`현장 조치 완료 후 순찰 재개`는 상세 패널 안에 inline form을 펼치지 않고 modal로 연다. 작업 테이블을 보면서 여러 task를 전환할 수 있으므로, form 입력 중 task 선택이 바뀌는 혼선을 줄이기 위해 modal이 더 안전하다.

##### PATROL 진행 상태 표시

`IF-PAT-003 Execute Patrol Path` feedback은 PATROL 상세 패널에서 다음 의미로 표시한다.

| `patrol_status` | UI 표시 |
| --- | --- |
| `ACCEPTED` | 순찰 접수 |
| `MOVING` | 순찰 중 |
| `WAITING_FALL_RESPONSE` | 낙상 대응 대기 |
| `RECOVERING` | 순찰 재개 처리 중 |
| `FAILED` | 순찰 실패 |

진행률은 `current_waypoint_index`, `total_waypoints`를 기준으로 계산한다.

```text
progress = (current_waypoint_index + 1) / total_waypoints
```

단, `total_waypoints`가 0이거나 미수신이면 진행률은 표시하지 않고 `waypoint: 미수신`으로 둔다.

로봇/진행 상태는 다음 row로 표시한다.

| Row label | 표시 값 |
| --- | --- |
| 로봇 | task update의 `assigned_robot_id`; 미배정이면 `미정` |
| 상태 | `patrol_status`, 초기값 `상태 업데이트 대기` |
| waypoint | `current_waypoint_index + 1 / total_waypoints`, 미수신이면 `미수신` |
| 남은 거리 | `distance_remaining_m`, 미수신이면 `미수신` |
| 위치 | `current_pose`, 미수신이면 `미수신` |
| 낙상 알림 | `ALERT_CREATED` 또는 task update의 `fall_alert` 요약. 없으면 `없음` |

PATROL runtime 상세 패널은 실제 지도 overlay가 표시되는 경우에도 위 진행
row를 유지해야 한다. 지도는 공간 확인용이고, 고정 row는 runtime feedback,
frame mismatch, map asset 로드 실패 상황에서도 운영자가 읽을 수 있는 fallback이다.

##### PATROL 지도 overlay

지도 overlay는 PATROL 상세 패널의 runtime view다. 순찰 요청 탭에는 지도 overlay를 넣지 않는다.

MVP에서 지도 렌더링이 아직 없으면 같은 데이터를 좌표 텍스트로 fallback 표시한다. 지도 렌더링이 들어오면 다음 layer를 순서대로 표시한다.

| Layer | 데이터 원천 | 표시 |
| --- | --- | --- |
| 지도 배경 | `map_profile`의 선택 map metadata와 배포된 map asset | 병원 평면/occupancy map |
| 순찰 경로 | `patrol_task_detail.path_snapshot_json` 또는 task detail 응답 | polyline + waypoint marker |
| 로봇 현재 위치 | 최신 `PINKY_UPDATED` 또는 `ACTION_FEEDBACK_UPDATED.current_pose` | robot marker |
| 낙상 감지 지점 | `ALERT_CREATED.payload.alert_pose` | fall alert marker |

`ACTION_FEEDBACK_UPDATED`는 `patrol_status`, `current_waypoint_index`,
`total_waypoints`, `current_pose`, `distance_remaining_m`를 포함할 수 있다.
UI는 `current_pose`를 공통 runtime `pose` 필드로 정규화해서 지도 marker에
사용하고, 선택 task의 `patrol_path.current_waypoint_index`만 갱신한다. 순찰
경로 snapshot 자체는 task detail 기준을 유지한다.

작업 모니터의 PATROL runtime panel은 `task_type=PATROL`인 작업에서만 표시한다. DELIVERY 등 비순찰 작업이나 선택된 작업이 없는 상태에서는 map overlay 영역 자체를 숨기고, overlay 안에 "순찰 작업이 아님" 같은 비순찰 안내 문구를 표시하지 않는다.

현재 데모 범위에서는 map asset 자체의 revision 변경이 드물다고 보고, 작업 모니터는 별도 `patrol_task_detail` map revision snapshot 없이 `task.map_id -> map_profile`로 map YAML/PGM을 조회한다. 좌표 조정 가능성이 큰 요소는 `goal_pose`, `operation_zone.boundary_json`, `patrol_area.revision/path_json`을 기준으로 표시하고, 향후 map/좌표 편집 페이지에서도 같은 map overlay/좌표 변환 컴포넌트를 재사용한다.

낙상 감지 지점 marker 규칙:

- marker 좌표는 `ALERT_CREATED.payload.alert_pose`를 사용한다.
- `alert_pose.frame_id`가 지도 frame과 다르면 marker를 표시하지 않고 좌표 텍스트와 frame mismatch 경고를 표시한다.
- marker label은 `zone_name`이 있으면 `zone_name`을 우선 사용하고, 없으면 `alert_pose.x`, `alert_pose.y`를 표시한다.
- marker 클릭 시 PATROL 상세 패널의 낙상 알림 card를 focus하거나, 이미 상세 패널이 열려 있으면 낙상 사진 dialog를 열 수 있는 액션을 노출한다.
- `evidence_image_available=true`이면 marker tooltip 또는 popover에 `낙상 사진 보기` 액션을 표시한다.
- 낙상 marker는 task가 `WAITING_FALL_RESPONSE`, `RECOVERING`, `COMPLETED`, `FAILED`로 바뀌어도 해당 task 상세 조회 동안 유지한다. 단, 새 순찰 task 지도에는 이전 task marker를 섞지 않는다.

지도 placeholder는 순찰 경로, waypoint 진행률, 로봇 현재 위치, 낙상 감지 지점을 나중에 표시할 수 있게 남긴다. phase 1에서 실제 지도 rendering이 없으면 다음 문구만 둔다.

```text
순찰 경로 / waypoint / 로봇 위치 / 낙상 지점 placeholder
```

##### PATROL 낙상 대응 UI

낙상 감지 후 `WAITING_FALL_RESPONSE` 상태에서는 PATROL 상세 패널에 낙상 알림 card와 대응 액션을 표시한다.

낙상 알림 card에는 다음 정보를 표시한다.

| 필드 | 표시 방식 |
| --- | --- |
| `alert_pose` | 지도/좌표 영역에 표시. 지도 미구현이면 좌표 텍스트 |
| `zone_name` | 있으면 사람 읽는 위치명으로 우선 표시 |
| `confidence` | 퍼센트 또는 소수점 2자리 |
| `frame_ts` | 감지 기준 프레임 시각 |
| `fall_streak_ms` | AI 서버 판단 근거용 보조 정보. UI가 재판정 기준으로 쓰지 않음 |
| `evidence_image_available` | 사진 버튼 활성화 기준 |
| `evidence_image_id` | 화면에 크게 노출하지 않고 tooltip/debug 정보로만 표시 |

`낙상 사진 보기`는 별도 이미지 dialog로 처리한다. 재개 modal 안에 이미지를 끼워 넣지 않는다. 증거 확인과 현장 조치 기록은 목적이 다르므로 모달을 분리해야 한다.

`낙상 사진 보기` 동작:

```text
사용자 클릭
-> GUI가 Control Service에 IF-PAT-007 요청(task_id + alert_id + evidence_image_id)
-> Control Service가 AI Service에 IF-PAT-006 요청
-> OK이면 bbox가 이미 그려진 이미지 표시
-> EXPIRED/NOT_FOUND이면 "사진 보관 시간이 만료되었습니다" 또는 "사진을 찾을 수 없습니다" 표시
```

이미지 dialog 표시 규칙:

- `image_data`는 `image_format`과 `image_encoding=base64`를 기준으로 표시한다.
- `image_width_px`, `image_height_px`는 이미지 크기와 bbox 좌표 기준을 검증하는 메타데이터다.
- AI 서버가 bbox를 이미 그린 이미지를 내려주므로, 기본 UI는 별도 overlay를 그리지 않아도 된다.
- `detections[].bbox_xyxy`는 상세 정보/디버깅 overlay가 필요할 때만 사용한다.
- 이미지 조회 실패가 순찰 재개 버튼을 막으면 안 된다. 현장 조치와 순찰 재개는 `IF-PAT-002`로 독립 처리한다.

##### PATROL 재개 modal

재개 입력은 별도 modal로 처리한다. 상세 패널에는 `현장 조치 완료 후 순찰 재개` 버튼만 두고, 버튼 클릭 시 modal을 연다.

재개 modal 구성:

| 영역 | 내용 |
| --- | --- |
| 헤더 | `순찰 재개` |
| task 요약 | `task_id`, 순찰 구역, 로봇, 현재 상태 |
| 낙상 요약 | `zone_name`, `frame_ts`, `confidence`, 사진 보기 버튼 |
| 조치 입력 | `member_id`, `action_memo` |
| footer 액션 | `취소`, `재개` |

재개 modal의 `재개` 버튼은 `member_id`와 `action_memo`가 모두 유효할 때만 활성화한다. 제출 중에는 중복 클릭을 막고, 성공 시 modal을 닫은 뒤 상세 패널 상태를 `RECOVERING` 또는 서버가 push한 최신 상태로 갱신한다. 실패 시 modal을 유지하고 `result_message`와 `reason_code`를 표시한다.

`IF-PAT-002` 요청 payload:

```json
{
  "task_id": 2001,
  "caregiver_id": 1,
  "member_id": 301,
  "action_memo": "119 신고 후 구급대원이 어르신을 병원으로 이송"
}
```

`action_memo`는 낙상 대응 후 현장에서 실제로 취한 조치를 남기는 audit 필드이며, 순찰 재개 요청의 필수 payload로 취급한다.

`IF-PAT-002`는 일반 종료용 API가 아니다. UI는 이를 `재개` 버튼으로만 표현하고, `중단/종료`는 반드시 공통 취소 API로 보낸다.

낙상 대응 상태에서 입력 form은 다음 순서로 배치한다.

| 입력 | UI 요소 | 필수 | 설명 |
| --- | --- | --- | --- |
| `member_id` | 어르신 검색 combo box | Y | 현장 조치 대상자 |
| `action_memo` | 다중 행 textarea | Y | 실제 조치 내용 |
| 재개 버튼 | primary button | Y | 두 필드가 모두 유효할 때만 활성화 |

#### 취소 액션

작업 모니터 상세 패널에는 선택된 task 기준의 mutation 액션을 둔다. 운반 task는 `작업 취소`, 순찰 task는 `순찰 중단`으로 표시한다. 두 버튼은 별도 UI가 아니라 같은 상세 패널 action button을 task type에 따라 라벨만 바꿔 사용한다.

취소 버튼 노출 기준:

- 서버가 `cancellable=true`를 반환한다.
- 작업 상태가 `WAITING_DISPATCH`, `ASSIGNED`, `RUNNING` 계열이다.
- 이미 `CANCEL_REQUESTED`, `CANCELLED`, `COMPLETED`, `FAILED`이면 버튼을 비활성화한다.
- 선택 task가 없거나 `task_id`가 없으면 버튼을 비활성화한다.

취소 요청 후 UI 상태:

```text
취소 요청 전송 중
-> 취소 요청 접수됨
-> 취소 처리 중
-> 취소 완료 또는 취소 실패
```

취소 실패 시 `reason_code`와 메시지를 함께 표시한다.

취소 요청 응답은 상세 패널의 현재 task snapshot에 즉시 반영한다. 응답에 `task_id`, `task_status`, `phase`, `assigned_robot_id`, `result_code`, `result_message`, `reason_code`, `cancellable`이 있으면 task row와 상세 패널을 갱신하고, 이후 IF-COM-003 push가 오면 서버 상태를 최종 기준으로 다시 덮어쓴다.

순찰 중단은 `IF-PAT-002` 재개 API가 아니라 공통 취소 API로 보낸다. 서버는 순찰 취소 요청을 `CANCEL_REQUESTED` 상태와 `PATROL_TASK_CANCEL_REQUESTED` 이벤트로 기록하고, ROS cancel action 결과가 수락되지 않으면 task 상태를 변경하지 않은 채 `reason_code`와 메시지를 반환한다.

---

### 7-5. 좌표/구역 설정 페이지

#### 페이지 이름

페이지명은 `맵 편집`이 아니라 `좌표/구역 설정`으로 한다.

이 페이지는 PGM/YAML map asset 자체를 수정하지 않는다. 벽, 장애물, 경로 픽셀 같은 occupancy map 편집은 GIMP 등 외부 map 편집 도구에서 수행하고, 이 UI는 이미 배포된 map asset 위에서 DB에 저장되는 운영 좌표와 구역 메타데이터를 관리한다.

#### 목적

운반, 순찰, 안내에서 사용하는 실내 위치 기준 데이터를 SQL이나 `.env` 직접 수정 없이 운영자가 조정할 수 있게 한다.

주요 목적은 다음과 같다.

- 운반 task에서 Pinky가 정밀 주차해야 하는 pickup, destination, dock 좌표를 Control Service를 통해 DB 기준으로 조회/수정한다.
- `301호`, `보호사실`, `물품 적재 위치`, `충전소` 같은 사람이 이해하는 구역을 관리한다.
- map image 위에서 현재 좌표 위치를 확인하고, map object 클릭/drag 또는 입력 form 미세 조정으로 좌표를 조정한다.
- `.env`에 있던 delivery goal pose 설정을 `goal_pose` 중심 DB 설정으로 이전한 뒤에도 운영자/관리자가 값을 쉽게 확인한다.
- 1차에서 `patrol_area.path_json`에 저장되는 순찰 path waypoint를 같은 map overlay와 좌표 변환 컴포넌트 위에서 편집한다.
- 2차 FMS 준비를 위해 phase 1 `goal_pose`와 `patrol_area.path_json`을 대체하지 않고, 같은 map 위에서 운영자가 이름 붙인 공용 waypoint와 재사용 route를 관리할 수 있게 한다.

#### 범위와 비범위

| 구분 | 포함 여부 | 설명 |
| --- | --- | --- |
| PGM/YAML map asset 표시 | 포함 | `map_profile.yaml_path`, `map_profile.pgm_path`를 읽어 배경으로 표시 |
| PGM 픽셀 편집 | 제외 | 벽/장애물/occupancy pixel 편집은 GIMP 등 외부 도구 사용 |
| `operation_zone` 관리 | 포함 | 구역 ID, 이름, 유형, 활성 여부, 선택적 map-frame polygon boundary 관리 |
| `goal_pose` 관리 | 포함 | 정밀 주차/목적지/dock 좌표와 yaw 관리 |
| `patrol_area.path_json` 관리 | 1차 포함 | 순찰 구역을 생성/선택/비활성화하고, 순서가 있는 waypoint/path를 표시하며, waypoint 추가/이동/삭제/순서 변경 후 Control Service로 저장 |
| FMS waypoint/route 관리 | 2차 | 운반, 순찰, 안내가 함께 쓸 수 있는 운영자 지정 공용 통행 node, edge, 재사용 route template |
| FMS reservation/scheduling 제어 | 이후 단계 | runtime 선점/reservation, task scheduling, 통과 우선순위, conflict 계산은 좌표 편집과 분리 |
| map revision snapshot 정책 | 제외 | 데모 범위에서는 `task.map_id -> map_profile` 기준 유지 |
| UI의 DB 직접 접근 | 제외 | PyQt UI는 DB connection을 열지 않는다. 모든 DB 조회/저장은 Control Service가 수행한다 |
| UI의 ROS 직접 접근 | 제외 | PyQt UI는 ROS package를 import하거나 ROS API를 호출하지 않는다. 로봇 측 검증이 필요하면 Control Service interface로 노출하고 서버/ROS adapter가 실행한다 |

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Page Header | 제목 `좌표/구역 설정`, 설명, `새로고침`, `저장`, `변경 취소` |
| 선택 맵 Bar | 맵 선택 콤보, 현재 편집 `map_profile`, map revision, YAML/PGM 경로, frame |
| Map Canvas | PGM map 배경, zone boundary polygon/꼭짓점, goal pose marker, patrol waypoint/path marker, FMS waypoint/edge/route overlay, 선택 좌표 crosshair |
| Zone List | `operation_zone` 목록, zone type filter, 활성/비활성, 카드 헤더 row action |
| Goal Pose List | `goal_pose` 목록, purpose filter, zone 연결 상태, 카드 헤더 row action |
| Patrol Area List | `patrol_area` 목록, path revision, waypoint 수, 편집 mode, 카드 헤더 row action |
| FMS Waypoint/Route List | 2차 공용 waypoint graph, route template, edge 상태, reservation read-only 상태, 카드 헤더 row action |
| Edit Panel | 선택한 zone, goal pose, patrol area, patrol waypoint, FMS waypoint, FMS route item 상세 폼; row 생성/비활성화/되돌리기 control은 여기에 두지 않음 |
| Validation Panel | 좌표 범위, frame mismatch, 필수값 누락, waypoint/path 검증, 저장 전 변경 요약 |

좌표/구역 설정 page는 일반 편집 작업에서 page-level scroll을 요구하지
않도록 main desktop viewport에 맞춘다. DB 기반 6개 list surface는 내부
table scroll을 가진 tabbed table area로 묶어서, `operation_zone`,
`goal_pose`, `patrol_area`, FMS graph table 사이를 전환해도 map canvas와
선택 Edit Panel이 계속 보이게 한다.
좌표 page의 map card와 tabbed DB table card는 compact margin을 사용하고,
map image 내부 gutter도 작게 유지해서 빈 padding 때문에 세로 scroll이
커지지 않게 한다. 단, DB table tab content는 row를 훑어볼 수 있을 만큼
충분히 높은 내부 scroll surface를 유지해야 한다.

#### 선택 맵

좌표/구역 설정 페이지는 한 번에 하나의 선택 맵을 편집한다. active/default `map_profile`은 페이지 진입 시 초기 선택일 뿐이며, 운반 좌표는 `map_test12_0506`에서 편집하고 순찰/안내 데이터는 `map_0504`에 남길 수 있다.

| 필드 | 표시 |
| --- | --- |
| `map_id` | 현재 편집 기준 map |
| `map_name` | 운영자가 읽는 map 이름 |
| `map_revision` | 참고용 metadata |
| `frame_id` | 보통 `map` |
| `yaml_path` | 상대 경로 표시 |
| `pgm_path` | 상대 경로 표시 |

`yaml_path`, `pgm_path`는 개발 checkout 경로가 아니라 Control Service가 내려주는 map asset 식별자다. 배포된 UI가 같은 asset path에 접근할 수 있을 때만 UI가 파일을 직접 로드한다. UI와 서버가 filesystem을 공유하지 않는 구조라면 Control Service가 TCP 기반 map asset/metadata interface를 제공해서 UI가 로컬 repository 경로에 의존하지 않고 같은 선택 맵을 렌더링해야 한다.

map asset 파일이 없거나 로드에 실패하면 좌표 저장 버튼을 비활성화하고, 파일 경로와 오류 메시지를 표시한다. DB 좌표만 편집 가능한 fallback은 만들지 않는다. 좌표가 실제 map 위 어디인지 확인하지 못하면 오입력 위험이 크기 때문이다.

#### Map Canvas 표시 규칙

기존 작업 모니터의 `PatrolMapOverlay`에서 사용한 PGM/YAML 로드와 map-frame 좌표 변환 로직을 재사용한다.

| Marker | 데이터 | 표시 |
| --- | --- | --- |
| Zone boundary | `operation_zone.boundary_json` | 반투명 polygon, boundary stroke, 편집 가능한 꼭짓점, polygon centroid label anchor 표시 |
| Zone fallback marker | `boundary_json`이 없는 `operation_zone` | 연결된 `goal_pose`가 있으면 해당 goal pose 위치에 zone label fallback anchor 표시 |
| Goal pose marker | `goal_pose.pose_x`, `pose_y`, `pose_yaw` | purpose별 색상 marker + yaw 방향 |
| Pickup | `purpose=PICKUP` 또는 `PICKUP_STATION` | 물품 적재/픽업 지점 |
| Destination | `purpose=DESTINATION` 또는 `DELIVERY_DESTINATION` | 병실/보호사실 등 운반 목적지 |
| Dock | `purpose=DOCK`, `RETURN_TO_DOCK`, `CHARGING_DOCK` | 복귀/충전 지점 |
| Patrol path | `patrol_area.path_json` | 1차에서 편집 가능한 순서 있는 waypoint marker + polyline |
| FMS waypoint | `fms_waypoint.pose_x`, `pose_y`, `pose_yaw`, `display_name` | 이름 있는 통행 node marker, label, yaw 방향 |
| FMS edge | `fms_edge` | waypoint 간 연결선; 비활성 edge는 muted 표시 |
| FMS route | `fms_route_waypoint[]` | 선택 route를 순서 번호가 있는 overlay로 강조 |
| FMS reservation | `fms_reservation` | waypoint 또는 edge 위에 read-only 선점/대기 badge 표시 |

marker, waypoint, zone 꼭짓점을 클릭하면 오른쪽 Edit Panel이 해당 row로 전환되고 해당 map object가 선택된다. 숫자 x/y/yaw 입력은 정밀 보정 수단이지 기본 편집 방식이 아니다. 기본 사용자 흐름은 map-first여야 한다. 즉 map 위에서 선택하거나 drag하고, 필요한 경우 form 숫자로 미세 조정한다.

yaw가 있는 object를 선택하면 방향이 map 위에서 보여야 한다. 최소 대상은 선택된 `goal_pose`, 순찰 path waypoint, FMS waypoint marker다. Heading arrow/handle은 map에서 방향을 preview하고, form은 radian 저장과 degree 보조 표시를 담당한다.

#### Map 편집 모드

Map canvas는 명시적인 편집 모드를 제공해야 한다. 활성 모드에 따라 강조 overlay, click 의미, drag 가능 대상, Edit Panel control이 달라진다.

| 모드 | 주요 대상 | 클릭 동작 | Drag 동작 | 오른쪽 panel |
| --- | --- | --- | --- | --- |
| 선택 | 모든 표시 overlay | marker, waypoint, polygon, 꼭짓점 선택; 빈 영역 클릭은 선택 해제 | 없음 | 선택 object 요약 |
| 목표 좌표 편집 | `goal_pose` marker | 현재 marker를 선택하거나 클릭 위치로 이동 | 선택 marker drag로 x/y preview 갱신; heading handle drag로 yaw만 갱신 | goal pose form과 x/y/yaw 미세 조정 |
| 순찰 path 편집 | `patrol_area.path_json.poses[]` | 빈 map 클릭으로 waypoint 끝에 추가 또는 insert mode에 따라 선택 waypoint 뒤 삽입; waypoint 클릭은 선택 | 선택 waypoint drag로 x/y preview 갱신; heading handle drag로 yaw만 갱신 | waypoint list, x/y/yaw 미세 조정, 순서 변경/삭제 control |
| 구역 boundary 편집 | `operation_zone.boundary_json.vertices[]` | 빈 map 클릭으로 polygon 꼭짓점 추가/삽입; 꼭짓점 클릭은 선택; polygon 클릭은 zone 선택 | 선택 꼭짓점 drag로 polygon preview 갱신 | zone metadata form과 boundary 꼭짓점 list/edit control |
| FMS waypoint 편집 | `fms_waypoint` | 빈 map 클릭으로 이름 붙일 waypoint draft 생성; waypoint 클릭은 선택 | 선택 waypoint drag로 x/y preview 갱신; heading handle drag로 yaw만 갱신 | waypoint 이름/유형/pose/yaw/grid snap control |
| FMS route 편집 | `fms_route_waypoint[]` | waypoint 클릭으로 선택 route에 waypoint 참조 추가/삽입 | waypoint 자체 위치 변경은 waypoint edit mode에서만 수행; route edit은 참조 순서를 변경 | route sequence, yaw policy, stop/dwell control |
| FMS reservation 보기 | `fms_reservation` | reservation badge/resource 선택으로 상세 보기 | 없음 | owner/waiting task와 robot 상태 read-only 표시 |

모드별 규칙:

- toolbar 또는 segmented control로 현재 모드를 명확히 표시한다.
- 활성 layer만 쓰기 interaction을 받는다. 비활성 layer는 보이지만 read-only/select-only다.
- Drag는 local preview와 dirty 상태만 갱신한다. 저장 전에는 Control Service mutation을 호출하지 않는다.
- Escape 또는 변경 취소는 local preview를 마지막 서버 snapshot으로 되돌린다.
- map이 로드되지 않으면 모든 map write mode를 비활성화한다.

#### 구역 설정

`operation_zone`은 사람이 이해하는 장소/구역 이름이다. 로봇이 실제로 이동할 좌표는 `goal_pose`가 가진다.

`operation_zone.boundary_json`은 UI가 구역의 시각적 범위를 표시하기 위한 선택적 semantic polygon이다. 이것은 occupancy map, costmap obstacle, robot target, patrol route, FMS traffic-control area가 아니다.

테이블 필드:

| 컬럼 | 설명 |
| --- | --- |
| `zone_id` | 안정적인 구역 ID. 예: `room_301`, `caregiver_room`, `dock` |
| `zone_name` | 화면 표시명. 예: `301호`, `보호사실`, `충전소` |
| `zone_type` | ROOM, STAFF_STATION, SUPPLY_STATION, DOCK 등 |
| `map_id` | 소속 map |
| `revision` | 구역 정의 revision |
| `boundary_json` | 시각적 구역 범위를 나타내는 선택적 map-frame polygon vertices |
| `is_enabled` | 선택 가능 여부 |

구역 edit form:

| 필드 | 입력 |
| --- | --- |
| 구역 ID | 신규 생성 시 입력, 생성 후 변경 금지 |
| 구역명 | text input |
| 구역 유형 | combo box |
| Boundary | map 꼭짓점 편집과 vertex list; 숫자 x/y는 미세 조정 용도 |
| 활성 여부 | switch/checkbox |

Phase 1에는 operation zone 생성, 수정, 비활성화를 포함한다. 구역 제거의 기본 동작은 삭제가 아니라 비활성화다. 이미 `goal_pose`, task history, patrol area가 참조할 수 있으므로 hard delete는 phase 1 UI에서 제공하지 않는다.

Boundary 편집 동작:

| 액션 | 동작 |
| --- | --- |
| 구역 선택 | `boundary_json` polygon이 있으면 표시하고, 없으면 연결된 `goal_pose` 기준 zone label fallback anchor 표시 |
| Boundary 생성 | 구역 boundary 편집 모드에서 map 클릭으로 polygon 꼭짓점을 순서대로 추가 |
| 꼭짓점 이동 | 꼭짓점 drag 또는 form에서 vertex x/y 수정 |
| 꼭짓점 삭제 | 선택 꼭짓점을 확인 후 삭제 |
| 꼭짓점 삽입 | 선택 꼭짓점 뒤에 삽입, 선택이 없으면 끝에 추가 |
| Boundary 초기화 | 확인 후 `boundary_json=null` 설정 |
| Boundary 저장 | 전체 boundary polygon을 Control Service로 전송하고 갱신된 `operation_zone.revision`을 받음 |

`boundary_json` 형태:

```json
{
  "type": "POLYGON",
  "header": {"frame_id": "map"},
  "vertices": [
    {"x": 0.0, "y": 0.2},
    {"x": 1.2, "y": 0.2},
    {"x": 1.2, "y": 1.1},
    {"x": 0.0, "y": 1.1}
  ]
}
```

마지막 꼭짓점에서 첫 꼭짓점으로 이어지는 closing edge는 암묵적으로 처리한다. 저장되는 non-null boundary는 최소 3개 꼭짓점을 가져야 한다.

#### 정밀 주차/목적지 좌표 설정

`goal_pose`는 Pinky가 실제로 이동하거나 정밀 주차해야 하는 2D pose다. `.env`에 있던 pickup, destination, dock 좌표는 이 테이블을 기본 source of truth로 삼는다.

테이블 필드:

| 컬럼 | 설명 |
| --- | --- |
| `goal_pose_id` | 안정적인 좌표 ID. 예: `pickup_supply`, `delivery_room_301`, `dock_home` |
| `zone_id` | 연결된 구역. nullable |
| `purpose` | PICKUP, DESTINATION, RETURN_TO_DOCK 등 |
| `pose_x` | map frame x |
| `pose_y` | map frame y |
| `pose_yaw` | radian 기준 heading |
| `frame_id` | 보통 `map` |
| `is_enabled` | 요청/실행에서 사용 가능 여부 |

좌표 edit form:

| 필드 | 입력 |
| --- | --- |
| 좌표 ID | 신규 생성 시 입력, 생성 후 변경 금지 |
| 연결 구역 | `operation_zone` combo box |
| 용도 | purpose combo box |
| x / y | decimal spinbox |
| yaw | radian 입력과 degree 보조 표시를 함께 제공 |
| 활성 여부 | switch/checkbox |

지도에서 marker를 선택하면 x/y/yaw form이 갱신된다. form 값을 수정하면 marker 위치와 방향이 즉시 preview된다. 저장 전 변경 상태는 dirty 표시로 보여준다.

Goal pose row action:

| 액션 | 동작 |
| --- | --- |
| 새 goal pose | Goal Pose list header에서 local draft row를 추가한 뒤 `goal_pose_id`, 용도, pose, 선택 구역, 활성 상태를 입력하고 저장 |
| goal pose 비활성화 | `is_enabled=false`를 local draft로 표시하고, 저장 시 일반 요청/실행 선택에서 제외되도록 persisted row를 비활성화 |
| goal pose 되돌리기 | 선택한 persisted row를 최신 서버 snapshot으로 복원하고, 저장 전 신규 row는 local에서 폐기 |

#### 순찰 Path Waypoint 설정

`patrol_area.path_json`은 작업 요청 화면에서 `patrol_area_id`를 제출했을 때 사용하는 순서 있는 순찰 경로 정의다. 순찰 데모의 운영 경로 설정에 해당하므로 phase 1에 이 waypoint 편집을 포함한다.

이 기능은 FMS 교통정리 waypoint 관리가 아니다. 순찰 waypoint는 특정 순찰 route가 어디를 지나갈지 정의한다. FMS waypoint/control node는 여러 로봇의 통행, 선점, 우선순위, conflict rule을 정의한다. UI label, API 이름, DB modeling에서 두 개념을 분리한다.

Patrol area 필드:

| 컬럼 | 설명 |
| --- | --- |
| `patrol_area_id` | 안정적인 순찰 구역 ID. 예: `patrol_ward_night_01` |
| `patrol_area_name` | 운영자가 읽는 순찰 구역명 |
| `map_id` | 소속 map |
| `revision` | 순찰 path 정의 revision |
| `path_json` | 순서 있는 waypoint list/polyline source of truth |
| `is_enabled` | 작업 요청에서 선택 가능 여부 |

Waypoint 편집 동작:

| 액션 | 동작 |
| --- | --- |
| 새 순찰 구역 | Patrol Area list header에서 local draft row를 추가한 뒤 `patrol_area_id`, `patrol_area_name`, 최소 2개 waypoint를 입력하고 저장 |
| 순찰 구역 선택 | 현재 `path_json`을 순서 있는 marker와 polyline으로 표시 |
| 순찰 구역 비활성화 | `is_enabled=false`를 local draft로 표시하고, 저장 시 일반 순찰 요청에서 선택되지 않도록 persisted row를 비활성화 |
| 순찰 구역 되돌리기 | 선택한 persisted row를 최신 서버 snapshot으로 복원하고, 저장 전 신규 row는 local에서 폐기 |
| waypoint 추가 | 순찰 path 편집 모드에서 map click으로 끝에 추가하거나 insert mode에 따라 선택 waypoint 뒤에 삽입 |
| waypoint 이동 | marker drag 또는 x/y/yaw form 수정; map drag가 기본 workflow이고 숫자 입력은 미세 조정 |
| waypoint 삭제 | 선택 waypoint를 확인 후 삭제 |
| waypoint 순서 변경 | waypoint list에서 선택 waypoint를 위/아래로 이동 |
| 순찰 구역 저장 | 전체 ordered path와 표시명/활성 상태를 Control Service로 전송하고, 서버 검증 후 갱신된 revision을 받음 |

UI는 저장 전 route diff summary를 표시한다. 추가 waypoint 수, 삭제 waypoint 수, 이동 waypoint 수, 순서 변경 여부를 보여준다. 로봇 간 traffic conflict는 계산하지 않으며, 이는 이후 FMS waypoint 관리에서 다룬다.

#### FMS Waypoint와 Route 설정

FMS 설정은 같은 페이지에 추가되는 2차 기능이다. 운반, 순찰, 안내가 함께 재사용할 수 있는 이름 있는 공용 waypoint와 route template을 도입하되, phase 1 `goal_pose`와 `patrol_area.path_json` 계약은 유지한다.

공용 waypoint 필드:

| 필드 | 입력/표시 |
| --- | --- |
| Waypoint ID | 안정적인 ID. 신규 생성 시 입력, 생성 후 변경 금지 |
| 표시 이름 | map 위에 보이는 운영자 label. 예: `복도1`, `복도2`, `301호앞` |
| 유형 | `CORRIDOR`, `ROOM_ENTRY`, `DOCK_ENTRY`, `WAIT_POINT`, `INTERSECTION` 등 |
| x / y | decimal spinbox와 map drag |
| yaw | heading arrow/handle과 radian 입력, degree 보조 표시 |
| Grid snap | 선택 toggle/group. 복도 정렬에는 snap을 쓰되 자유 배치도 허용 |
| 활성 여부 | switch/checkbox |

Waypoint label 규칙:

- 선택된 waypoint label은 모든 zoom 수준에서 표시한다.
- route edit mode에서는 route 주변 label을 우선 표시한다.
- 낮은 zoom에서 label이 겹치면 선택되지 않은 label은 숨기거나 약하게 표시한다.
- map 위 기본 text는 raw ID보다 표시 이름을 우선하고, ID는 상세 panel에서 확인하게 한다.

Route 필드:

| 필드 | 입력/표시 |
| --- | --- |
| Route ID | 안정적인 route ID. 생성 후 변경 금지 |
| Route 이름 | 운영자가 읽는 이름 |
| Route 범위 | `COMMON`, `DELIVERY`, `PATROL`, `GUIDE` |
| Revision | 서버가 관리하는 route revision |
| Waypoint sequence | 공용 FMS waypoint에 대한 순서 있는 참조 |
| Yaw policy | route 지점별 `AUTO_NEXT`, `FIXED`, `GOAL_POSE`, `KEEP_CURRENT` |
| Stop/dwell | 선택적 stop-required와 dwell seconds |
| 활성 여부 | switch/checkbox |

Route 편집 동작:

| 액션 | 동작 |
| --- | --- |
| waypoint 생성 | FMS waypoint edit mode에서 map 클릭으로 draft point를 만들고 표시 이름/유형을 입력 |
| waypoint 이동 | marker drag 또는 form x/y/yaw 수정; route는 같은 waypoint를 참조하므로 시각적으로 함께 갱신 |
| edge 생성 | 두 waypoint를 연결하고 방향/양방향 여부, 선택적 priority/cost 설정 |
| route 구성 | route edit mode에서 waypoint를 통과 순서대로 클릭하여 참조를 추가/삽입 |
| route 순서 변경 | sequence list에서 선택 route item을 위/아래로 이동 |
| route yaw policy | 기본은 `AUTO_NEXT`; 명시 heading은 `FIXED`, 최종 정밀 정차 맞춤은 `GOAL_POSE` 사용 |
| route materialize | 기존 runtime path consumer와 호환되도록 `{"header":{"frame_id":"map"},"poses":[...]}` 형태로 preview |

Reservation 표시 동작:

- 이 설정 페이지에서 reservation 상태는 read-only다.
- `HELD` resource는 소유 robot/task를 표시하고, `WAITING` resource는 대기 robot/task를 표시한다.
- 좌표 페이지에서 운영자용 수동 reservation/release control은 제공하지 않는다. Reservation 변경은 scheduler/runtime service 책임이다.
- 교통정리 때문에 대기하는 task는 `WAITING_FMS_RESERVATION` 같은 구체 reason을 노출해야 하며, 일반 `WAITING` 상태에 조용히 머물면 안 된다.

#### 저장 정책

좌표/구역 설정은 draft 우선 저장 정책을 사용한다. row를 수정하면 로컬
draft가 갱신되고 해당 row가 dirty로 표시된다. 다른 row로 이동해도 이전
row의 미저장 값이 사라지면 안 된다. 페이지 상단 `저장`은 모든 pending
draft 변경을 정해진 순서로 저장하고, 실패한 row만 dirty 상태로 유지한다.
페이지 상단 action은 `새로고침`, `저장`, `변경 취소`로 제한한다. row
생성, soft 비활성화, 선택 row 되돌리기는 Edit Panel이 아니라 해당 table
card header에 둔다.

| 액션 | 동작 |
| --- | --- |
| 페이지 진입 | 로드된 map이 없고 로컬 dirty draft가 없으면 기본 선택 map/location bundle을 자동 조회 |
| 맵 선택 변경 | `get_map_bundle(map_id=selected_map_id)`, YAML/PGM asset, FMS graph를 선택 맵 기준으로 다시 조회한다. 저장되지 않은 draft가 있으면 전환을 막는다 |
| 새로고침 | 서버에서 선택 맵, zones, goal poses, patrol areas를 다시 조회 |
| 좌표 draft 저장 | 신규 `goal_pose` draft row를 생성하고 dirty 상태인 기존 `goal_pose` row를 업데이트 |
| 구역 draft 생성 | 선택 맵에 새 `operation_zone` draft row를 만들고 저장 시 insert |
| 구역 draft 저장 | dirty 상태인 모든 `operation_zone` metadata row 업데이트 |
| 구역 boundary 저장 | 선택된 `operation_zone.boundary_json`을 업데이트하고 새 zone revision을 반영 |
| 순찰 path 저장 | 선택된 `patrol_area.path_json`을 업데이트하고 서버가 반환한 새 path revision을 반영 |
| FMS waypoint draft 저장 | dirty 상태인 모든 `fms_waypoint` row upsert |
| FMS edge draft 저장 | dirty 상태인 모든 `fms_edge` row upsert |
| FMS route draft 저장 | dirty 상태인 모든 `fms_route` row upsert 및 route revision 반영 |
| row 비활성화 | 저장된 row는 `is_enabled=false` draft 변경으로 표시하고, 미저장 draft row는 로컬에서 제거 |
| 선택 row 되돌리기 | 선택한 row만 마지막 서버 snapshot 값으로 복원하고 해당 row의 dirty/실패 상태를 해제 |
| 변경 취소 | 모든 로컬 draft를 마지막 서버 snapshot 값으로 되돌림 |

키보드 단축키도 같은 draft-first 정책을 따른다. `Ctrl+S`는 저장이 가능할
때 페이지 상단 `저장` action을 실행하고, `Ctrl+Z`는 선택된 editor의 이전
local edit snapshot으로 되돌리며, `Ctrl+Shift+Z`는 다음 local edit
snapshot을 다시 적용한다. Undo/redo는 local preview, dirty 상태, table,
form만 갱신하며, 운영자가 저장하기 전에는 Control Service를 호출하지
않는다.
단축키 handler는 spin box나 line edit 같은 form widget이 자체 `Ctrl+Z`
동작으로 shortcut override 또는 key press event를 소비하기 전에 page
단축키를 먼저 처리해야 한다. 또한 좌표 page가 보이는 동안에는
AdminShell/window level로 들어오는 shortcut event도 처리해야 한다.
맵 drag 편집은 완료된 drag 1회당 undo step 1개로 취급한다. 포인터 drag가
시작될 때 이전 상태를 캡처하고, 이동 중에는 반복 snapshot을 추가하지 않은
채 local preview만 갱신하며, left mouse button이 release될 때 실제 변경이
있으면 post-drag snapshot을 1개만 추가한다.

저장 성공 후에는 Control Service 응답 기준으로 저장된 row의 revision/`updated_at`과 UI dirty 상태를 갱신한다. row 저장 실패 시 해당 row의 draft 값을 유지하고 dirty 상태를 유지한다. 의존성 순서상 가능한 경우 이후 row 저장은 계속 진행하며, 실패한 `reason_code`와 메시지를 Validation Panel에 표시한다.

편집 가능한 좌표/FMS 목록은 로컬 상태 컬럼을 제공한다. 상태 값은 `-`,
`변경됨`, `비활성화 예정`, `저장 실패` 중 하나다. 페이지 수준 변경 요약
라벨은 미저장 row 총 개수와 데이터 종류별 개수, batch 저장 이후 실패
row 개수를 표시한다. 실패 row는 다시 저장, row 재수정, 선택 row 되돌리기,
전체 변경 취소, 새로고침 전까지 retry 가능한 dirty 상태로 유지한다.

구역 metadata 저장과 구역 boundary 저장은 독립 동작이다. 둘 다 dirty인 상태에서 `operation_zone` metadata 저장만 성공하면 boundary editor는 `coordinate_config.update_operation_zone_boundary` 성공 전까지 dirty 상태를 유지해야 한다. 변경 취소는 미저장 local polygon preview가 아니라 마지막으로 서버가 확정한 boundary snapshot으로 되돌린다.
선택된 operation zone의 metadata와 boundary가 모두 dirty이면 운영자의 `저장` 클릭 한 번으로 metadata 저장 중 boundary draft를 보존하고, 반환된 zone revision을 사용해 boundary 저장까지 이어서 수행한다.
선택된 `operation_zone` metadata form에 로컬 수정이 있으면 페이지 상단 `저장` 클릭은 반드시 `coordinate_config.update_operation_zone`/`create_operation_zone`을 전송하거나 구체적인 validation 사유를 표시해야 한다. 조용히 아무 동작도 하지 않는 no-op이면 안 된다.

#### 검증 규칙

| 조건 | UI 동작 |
| --- | --- |
| map 미로드 | 저장 비활성, map asset 오류 표시 |
| `frame_id`가 선택 맵 frame과 다름 | 저장 전 경고, phase 1에서는 저장 차단 |
| x/y가 map bounds 밖 | 저장 차단 |
| `goal_pose_id` 중복 | 생성 차단 |
| `zone_id` 중복 | 생성 차단 |
| 구역 boundary 꼭짓점이 3개 미만 | 구역 boundary 저장 차단 |
| 구역 boundary 꼭짓점이 map bounds 밖 | 편집기에서 경고하되, migration/legacy boundary polygon을 운영자가 꼭짓점 단위로 보정할 수 있도록 저장은 허용 |
| 구역 boundary frame이 선택 맵 frame과 다름 | 구역 boundary 저장 차단 |
| 비활성 zone에 연결 | 허용하되 경고 표시 |
| purpose 누락 | 저장 차단 |
| 순찰 path waypoint가 2개 미만 | 순찰 path 저장 차단 |
| 순찰 waypoint가 map bounds 밖 | 순찰 path 저장 차단 |
| 순찰 waypoint frame이 선택 맵 frame과 다름 | 순찰 path 저장 차단 |
| yaw 입력 단위 혼동 | radian 저장, degree는 보조 표시만 사용 |
| FMS waypoint 또는 route ID 중복 | 생성 차단 |
| FMS route가 없는 waypoint를 참조 | route 저장 차단 |
| FMS route가 비활성 waypoint/edge를 참조 | route 상태 정책에 따라 경고 또는 차단 |
| FMS route의 인접 waypoint가 edge로 연결되지 않음 | draft mode에서는 경고, 활성 route 저장은 차단 |

UI 측 검증은 preview guard일 뿐이다. DB 상태를 바꾸는 데 중요한 검증은 Control Service가 저장 직전에 다시 수행해야 한다.

#### 서버/API 기대 형태

관리자 UI는 기존 custom TCP internal RPC transport 위에서 좌표/구역 설정 전용 service client를 사용한다. UI process에 DB connector나 ROS dependency를 추가하지 않으며, 기존 task request API에 설정 저장 기능을 섞지 않는다.

예상 RPC 형태:

```text
send_request(
  MESSAGE_CODE_INTERNAL_RPC,
  {
    "service": "coordinate_config",
    "method": "...",
    "kwargs": { ... }
  }
)
```

예상 service method:

```text
coordinate_config.get_map_bundle(map_id=selected_map_id)
coordinate_config.update_goal_pose(...)
coordinate_config.create_operation_zone(...)
coordinate_config.update_operation_zone(...)
coordinate_config.update_operation_zone_boundary(...)
coordinate_config.update_patrol_area_path(...)
coordinate_config.get_map_asset(...)          # UI가 pgm/yaml path에 직접 접근할 수 없을 때만
coordinate_config.validate_goal_pose_runtime(...)  # 향후 선택 기능: ROS adapter를 통한 로봇 측 검증
fms_config.get_active_graph_bundle(...)       # 2차, coordinate_config와 분리
fms_config.upsert_waypoint(...)
fms_config.upsert_edge(...)
fms_config.upsert_route(...)
fms_config.materialize_route(...)
fms_runtime.get_reservation_snapshot(...)     # UI read-only 표시
```

`get_map_bundle(map_id)` 응답 예:

```json
{
  "result_code": "OK",
  "map_profile": {
    "map_id": "map_test12_0506",
    "map_name": "map_test12_0506",
    "map_revision": 1,
    "frame_id": "map",
    "yaml_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test12_0506.yaml",
    "pgm_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test12_0506.pgm"
  },
  "operation_zones": [],
  "goal_poses": [],
  "patrol_areas": [
    {
      "patrol_area_id": "patrol_ward_night_01",
      "patrol_area_name": "Night ward patrol",
      "map_id": "map_test12_0506",
      "revision": 3,
      "path_json": {
        "header": {"frame_id": "map"},
        "poses": [
          {"x": 1.2, "y": 0.4, "yaw": 0.0},
          {"x": 2.5, "y": 0.8, "yaw": 1.57}
        ]
      },
      "is_enabled": true
    }
  ]
}
```

#### 구현 우선순위

1차 MVP:

- 선택 맵 로드와 read-only 표시
- `operation_zone` 목록 조회, 생성, 수정, 비활성화
- `goal_pose` 목록 조회
- goal pose marker 표시
- goal pose x/y/yaw form 수정 및 저장
- map click으로 선택된 goal pose x/y preview
- `patrol_area` 목록 조회와 path overlay
- patrol waypoint 추가/이동/삭제/순서 변경
- 서버가 반환하는 revision과 저장 전 diff summary를 포함한 patrol path 저장

2차:

- goal pose 생성/비활성화
- purpose별 marker 색상/필터
- goal pose, patrol waypoint, FMS waypoint marker의 yaw heading arrow/handle 편집
- map label과 선택적 grid snap을 포함한 FMS waypoint/control node CRUD
- route 연결성과 교통정리를 위한 FMS edge 관리
- common, delivery, patrol, guide route template을 위한 FMS route editor
- 기존 path JSON 형태로 FMS route materialization preview
- 어떤 robot이 waypoint 또는 edge를 선점했거나 대기 중인지 보여주는 FMS reservation/ownership read-only 상태 표시

3차:

- 실제 로봇 정밀 주차 테스트 결과 feedback 연결
- FMS scheduler/runtime reservation write path, 통과 우선순위, conflict 처리, task 상태 전이 통합

---

### 7-6. 로봇 상태 페이지

#### 목적

로봇별 연결 상태, 현재 작업, 배터리, 위치, 최근 상태 수신 시각을 확인한다.

작업 모니터가 task 중심이라면 로봇 상태 페이지는 robot 중심이다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Fleet Summary | 전체 로봇 수, 온라인, 오프라인, 주의 |
| Robot Cards | 로봇별 카드와 주 맵 기반 위치 패널 |
| Robot Table | 상세 목록 |
| Detail Panel | 선택 로봇 상세 |
| Location Visualization | 좁은 side placeholder가 아니라 로봇 카드 영역에 포함된 큰 PGM/YAML 맵 패널 |

#### Phase 1 데이터 소스

이 페이지는 Control Service TCP/RPC 메서드 `caregiver.get_robot_status_bundle`을 사용한다.
UI는 DB나 ROS에 직접 연결하지 않는다. bundle은 `summary`, `robots`, `delivery_composition`을 포함한다.

`scenario_role`은 `robot_id`에서 유도하지 않는다. 현재 데모 범위에서는 로봇 capability용 DB 스키마를 추가하지 않는다. Control Service가 phase 1 고정 정책에서 표시용 기능을 만든다. 모든 Pinky mobile robot은 안내, 운반, 순찰을 지원하고, `jetcobot1`, `jetcobot2`는 운반 station arm으로 고정한다.

#### 로딩과 새로고침 동작

로봇 상태 새로고침은 페이지 높이를 바꾸는 page-level 상태 row를 삽입하거나 제거하지 않는다. snapshot refresh 중에도 주요 로봇 카드, 테이블, 상세 패널, 맵 영역의 치수는 안정적으로 유지한다. 로딩 상태는 새로고침 버튼의 텍스트/상태와 고정된 header 상태 필드처럼 레이아웃을 밀지 않는 방식으로 표시한다. 오류 메시지는 예약된 header/status 영역에 표시할 수 있지만 로봇 콘텐츠를 아래로 밀어내면 안 된다.

주기적 robot snapshot refresh는 변경되지 않은 map profile/YAML/PGM asset을 매번 다시 다운로드하거나 location configuration service를 다시 조회하지 않는다. 1-2초 fallback refresh 경로는 runtime robot status만 조회한다. 선택된 `map_id`별로 map asset을 cache하고, 초기 로드, 선택 map 변경, cache 비어 있음 복구, 또는 명시적인 수동 새로고침이 map refresh를 요구하는 경우에만 map profile/asset을 다시 로드한다. refresh와 stream update는 해당 로봇이 여전히 존재하면 운영자가 선택한 로봇 상세를 유지해야 한다.

#### 로봇 카드

카드 표시 필드:

| 필드 | 설명 |
| --- | --- |
| `robot_id` | 예: `pinky2` |
| `display_name` | 예: `Pinky Pro` |
| `robot_type` | MOBILE, ARM |
| `capabilities` | DELIVERY, PATROL, GUIDE, MANIPULATION 같은 스케줄러용 지원 기능 |
| `station_roles` | station robot의 표시용 고정 스테이션 배정, 예: DELIVERY/PICKUP |
| `connection_status` | ONLINE, OFFLINE, DEGRADED |
| `battery_percent` | 모바일 로봇 중심 |
| `current_task_id` | 작업 중이면 표시 |
| `current_phase` | 작업 단계 |
| `current_location` | 위치명 또는 좌표 라벨 |
| `last_seen_at` | 마지막 수신 |

로봇 카드 제목은 홈과 같은 규칙을 사용한다. `robot_id`만 표시한다. `display_name`과 `robot_type`은 상세 필드 또는 상태/category badge로만 표시하며 제목 앞뒤에 붙이지 않는다.

#### 로봇 위치 맵

로봇 상태 페이지는 Control Service의 위치 설정 인터페이스를 재사용해 실제 map asset을 렌더링한다. 페이지는 사용 가능한 `map_profiles`를 불러오고, 운영자가 하나의 맵을 선택하면 `coordinate_config.get_map_asset`으로 해당 맵의 YAML/PGM asset을 로드한다.

위치 패널의 맵 선택 box는 `운반 맵 (map_test12_0506)`처럼 운영자용 맵 이름과 `map_id`를 함께 보여줘도 일반 관리자 layout에서 잘리지 않을 만큼 넓어야 한다. Header stretch가 combo box를 과도하게 압축하지 않도록 고정 최소 폭 또는 contents-length 정책을 사용한다.

맵 marker는 선택된 맵에 속한 현재 pose가 있는 로봇만 표시한다. 로봇 목록, 로봇 카드, 상세 테이블은 모든 로봇을 계속 보여준다. pose가 없거나, map identity가 없거나, stale pose이거나, 다른 맵 pose를 가진 로봇은 목록에는 남기되 현재 선택 맵에는 그리지 않는다. map identity가 있는 로봇을 선택하면 맵 선택을 해당 맵으로 전환할 수 있다.

현재 phase-1 로봇 pose 계약:

| 필드 | 규칙 |
| --- | --- |
| `current_pose.map_id` | 맵 marker 렌더링에 필수다. 현재 DB 모델에서는 active task의 `map_id`에서 유도한다. active task map이 없으면 map 불명 pose로 보고 marker를 그리지 않는다. |
| `current_pose.frame_id` | 맵 frame과 일치해야 한다. 보통 `map`이다. |
| `current_pose.x`, `current_pose.y`, `current_pose.yaw` | marker와 heading 표시용 map-frame 로봇 pose다. |
| `current_pose.updated_at` | 운영자용 freshness timestamp다. |

운반/이송 맵과 순찰/안내 맵을 하나의 시각화에 합치지 않는다. `map_0504`와 `map_test12_0506`은 좌표계가 다르므로 같은 x/y 값도 다른 실제 위치를 뜻할 수 있다.

#### 복합 로봇 작업 표현

일부 시나리오는 하나의 task에 여러 로봇이 관여한다. 현재 대표 사례는 운반 시나리오이며, Pinky mobile robot과 Jetcobot arm이 함께 동작한다.

화면에서는 다음 관계를 사람이 이해하기 쉽게 표현한다.

```text
Pickup Arm Robot: jetcobot1
Destination Arm Robot: jetcobot2
ROS adapter arm_id: arm1 / arm2
```

UI에서는 물리 로봇 ID인 `jetcobot1`, `jetcobot2`를 표시한다. `arm1`, `arm2`는 ROS action adapter boundary에서 사용하는 내부 ID로 설명 영역에만 표시한다. 운반 mobile robot은 scheduler/current task assignment가 결정하므로 robot status bundle에서 전역으로 하드코딩하지 않는다.

---

### 7-7. 재고 관리 페이지

#### 목적

운반 가능한 물품과 재고 수량을 조회하고 수정한다.

재고는 현재 운반 시나리오와 직접 연결된다. 향후 다른 시나리오에서 물품이나 장비가 필요해지면 같은 inventory 구조를 확장한다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Summary Cards | 전체 물품 수, 부족 물품 수, 최근 수정 |
| Inventory Table | 물품 목록 |
| Edit Form | 재고 추가/수정 |
| Low Stock Panel | 부족 재고 경고 |

#### 테이블 필드

| 컬럼 | 설명 |
| --- | --- |
| `item_id` | 물품 ID |
| `item_name` | 물품명 |
| `item_type` | 약품, 소모품 등. phase 1에서는 현재 DB 컬럼을 카테고리 라벨로 사용 |
| `quantity` | 현재 수량 |
| `updated_at` | 마지막 수정 시각 |

재고 테이블 헤더와 상세 키는 DB 필드명이 아니라 운영자용 한글 라벨로 표시한다. 예를 들어 `item_id`는 `물품 ID`, `item_type`은 `분류`, `quantity`는 `현재 수량`, `updated_at`은 `마지막 수정`으로 표시한다. 시간 값은 raw ISO `T` 문자열이 아니라 공통 운영자 시간 형식을 사용한다.

`safety_stock`과 `delivery_enabled`는 phase 1 DB 컬럼이 아니다. UI에서 이를 수정 가능한 물품 상태처럼 하드코딩하지 않는다. 서버는 `quantity`에 운영 임계값을 적용해 임시 부족 재고 경고를 반환할 수 있으며, 물품별 안전 재고와 운반 가능 여부가 필요해지면 후속 스키마 작업으로 추가한다.

#### 액션

| 액션 | 동작 |
| --- | --- |
| 재고 추가 | 기존 수량에 더한다 |
| 재고 수정 | 현재 수량을 직접 변경한다 |
| 새로고침 | 서버에서 다시 조회한다 |

#### Phase 1 데이터 소스

Admin UI는 Control Service TCP/RPC 계층으로만 통신한다.

| UI 필요 기능 | Control Service RPC | 비고 |
| --- | --- | --- |
| 재고 화면 로드 | `inventory.get_inventory_bundle` | `item` 테이블에서 파생한 `summary`, `items`, `low_stock_items` 반환 |
| 재고 수량 추가 | `inventory.add_item_quantity(item_id, quantity_delta)` | 양의 정수만 허용하며 `item_id`로 갱신 |
| 현재 수량 직접 수정 | `inventory.set_item_quantity(item_id, quantity)` | 0 이상 정수만 허용하며 `item_id`로 갱신 |

phase 1에서 복잡한 재고 차감 정책은 운영하지 않는다. 단, UI는 향후 운반 완료 시 재고 차감 정책이 들어올 수 있도록 `item_id` 중심으로 설계한다.

---

### 7-8. 어르신 정보 페이지

#### 목적

어르신 정보를 검색하고, 선호/비선호, 최근 이벤트, 처방전/주의사항을 확인한다.

이 화면은 안내 시나리오와 방문자 키오스크의 기반 데이터가 될 수 있다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Search Panel | 이름 또는 호실 일부 검색 |
| Candidate List | 입력 중 검색 필드 바로 아래에 표시되는 어르신 후보 목록 |
| Profile Summary | 기본 정보 카드 |
| Preference Panel | 선호/비선호 |
| Recent Member Events | 최근 member_event |
| Prescription/Notes | 처방전 이미지 경로, 주의사항 |

#### 검색 필드

| 필드 | 설명 |
| --- | --- |
| name | 어르신 이름 |
| room_no | 호실 |

둘 중 하나만 입력해도 검색 가능해야 한다. 동명이인과 호실 일부 검색의 모호성이 있으므로 운영자가 입력하는 동안 검색 필드 바로 아래에 후보 목록을 표시한다.

별도의 조회 미리보기 카드는 사용하지 않는다. 후보 행은 `김영수 · 301호 · #1`처럼 운영자가 구분하기 쉬운 압축 형식으로 표시한다. 후보를 선택하면 `member_id` 기준으로 상세 정보를 조회한다. 검색 결과 값은 Qt label에 적용하기 전에 문자열로 정규화해야 하며, 숫자 ID나 date 객체 때문에 UI가 종료되면 안 된다.

#### 서비스 계약

| RPC | 목적 |
| --- | --- |
| `patient.search_patient_candidates(name, room_no, limit)` | 후보 목록 조회. `name` 또는 `room_no`는 비어 있을 수 있지만 UI는 둘 중 하나 이상을 입력한 뒤 호출한다. |
| `patient.get_patient_info(member_id)` | 후보 선택 후 상세 조회. 관리자 UI의 기본 어르신 상세 조회 흐름이다. |
| `patient.search_patient_info(name, room_no)` | 호환성용 기존 정확 조회. 신규 관리자 UI는 후보 선택 후 `member_id` 상세 조회를 우선 사용한다. |

#### 표시 필드

| 필드 | 설명 |
| --- | --- |
| `member_id` | 어르신 ID |
| `name` | 이름 |
| `room_no` | 호실 |
| `admission_date` | 입소일 |
| `preference` | 선호 정보 |
| `dislike` | 비선호 정보 |
| `comment` | 케어 메모 |
| `events` | 최근 member_event |
| `prescription_paths` | 처방전 이미지 경로 |

#### 이벤트 표현

어르신 관련 이벤트는 `member_event` 기준으로 표시한다.

| 필드 | 설명 |
| --- | --- |
| `event_at` | 발생 시각 |
| `event_type` | 이벤트 종류 |
| `severity` | 중요도 |
| `description` | 설명 |

severity 기준이 없는 이벤트는 기본 `INFO`로 표시한다.

어르신 최근 이벤트 시각은 공통 운영자 시간 형식으로 표시한다. `2026-05-03T12:00:00` 같은 raw ISO 문자열은 최근 이벤트 텍스트 영역에 그대로 노출하지 않는다.

---

### 7-9. 알림/로그 페이지

#### 목적

운영 중 발생한 이벤트, 오류, 작업 실패, 취소 실패, 통신 문제를 추적한다.

이 페이지는 개발자 디버그 콘솔이 아니라 운영자용 문제 추적 화면이다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Filter Bar | 기간, severity, source, task_id, robot_id |
| Event List/Table | 운영 이벤트 목록 |
| Detail Drawer | 선택 이벤트 상세 |
| Related Links | 관련 작업/로봇으로 이동 |

#### Phase 1 데이터 소스

이 페이지는 Control Service TCP/RPC 메서드 `caregiver.get_alert_log_bundle`을 사용한다.
UI는 DB나 ROS에 직접 연결하지 않는다. bundle은 `task_event_log` 기반의 operator-facing `summary`와 `events`를 포함한다.
이벤트 테이블 헤더, 필터 라벨, 상세 키는 운영자용 라벨로 표시한다. `occurred_at`, `source_component`, `event_type` 같은 raw 필드는 payload에 남아도 되지만 화면에는 `발생 시각`, `출처`, `이벤트 종류`처럼 표시한다. 이벤트 시각은 raw ISO `T` 문자열이 아니라 공통 운영자 시간 형식을 사용한다.

상세 drawer의 key column은 `상세 payload` 같은 라벨을 모두 표시할 수 있는 폭을 예약한다. 값 텍스트는 줄바꿈될 수 있지만, 긴 payload 값 때문에 key 라벨 자체가 잘리면 안 된다. 큰 payload 값은 한 줄 value label에 욱여넣지 않고, 일반 상세 항목과 같은 key/value row 안에서 key chip은 다른 상세 row와 같은 고정 key column 폭을 쓰고 value 쪽만 read-only, line-wrap text 영역으로 표시한다. Payload text 영역은 별도 전체 폭 박스가 아니라 해당 row의 value 영역처럼 보여야 하며, 다른 상세 value와 같은 기본 폰트와 굵은 weight를 사용한다.

알림/로그 page는 관리자 IF-COM-003 stream fan-out을 통해 관련 task, alert, robot, action-feedback event를 받으면 현재 filter를 유지한 채 갱신한다. Stream 기반 갱신은 debounce하고, 서버 요청이 이미 진행 중이면 후속 갱신을 최대 한 번만 queue한다.

#### 필터

| 필터 | 설명 |
| --- | --- |
| 기간 | 오늘, 최근 1시간, 최근 24시간, 직접 선택 |
| severity | INFO, WARNING, ERROR, CRITICAL |
| source_component | UI, Control Service, ROS Adapter, DB Writer, AI Server |
| task_id | 특정 작업 |
| robot_id | 특정 로봇 |
| event_type | TASK_CREATED, TASK_FAILED, CANCEL_REQUESTED 등 |

필터 값이 바뀌면 별도의 새로고침 클릭 없이 이벤트 목록을 다시 조회한다. 콤보박스 필터는 즉시 조회하고, 텍스트 필터는 입력 중 짧은 debounce 후 조회한다. 운영 이벤트 목록 테이블이 검색 후보 목록 역할을 한다. `source_component`, `robot_id`, `event_type` 텍스트 필터는 일부만 입력해도 후보 이벤트가 나오도록 부분 일치 검색을 사용한다. `task_id`는 숫자 ID이므로 정확 일치 필터로 유지한다. 서버 요청이 이미 진행 중일 때 필터가 다시 바뀌면, 현재 요청이 끝난 직후 최신 필터 값으로 한 번 더 조회한다.

#### severity 기준

| severity | 판단 기준 |
| --- | --- |
| INFO | 정상 운영 흐름, 사용자 액션, 작업 생성/완료 |
| WARNING | 복구 가능하지만 운영자가 알아야 하는 지연, 일시 통신 오류, 재고 부족 |
| ERROR | 작업 실패, 명령 실패, DB write 실패, ROS action 실패 |
| CRITICAL | 안전 문제, 긴급 호출, 시스템 전체 운영 불가 |

사람이 매번 수동으로 severity를 판단하지 않는다. 서버와 각 컴포넌트가 이벤트 종류와 결과에 따라 severity를 결정하고, UI는 그 결과를 표시한다.

#### 이벤트 로그와 데이터 로그 구분

UI에서는 운영자에게 이벤트 로그를 우선 보여준다.

- 이벤트 로그: 사용자 액션, 명령 전송, 작업 상태 변경, 실패 사유
- 데이터 로그: 로봇 상태 샘플, 위치, 센서, AI stream metric

데이터 로그는 운영자 화면에서는 요약 또는 상세 진단 링크로만 제공한다. 모든 raw data log를 테이블로 노출하면 운영자가 중요한 이벤트를 놓칠 수 있다.

---

### 7-10. 시스템 상태 페이지

#### 목적

Control Service, DB, ROS2, AI Server, 로봇 연결 상태를 운영자가 한 곳에서 확인하는 화면이다.

phase 1에서는 관리자 sidebar에서 이 페이지를 제거한다. 범위는 홈 대시보드 heartbeat 상태 chip, 로봇 상태 페이지, 알림/로그 페이지로 흡수한다. 이 절은 phase 2 이후 운영 진단 화면 후보를 위한 참고 설계로만 유지한다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Service Health Cards | Control Service, DB, ROS2, AI Server 상태 |
| Runtime Config Summary | 현재 서버 host/port, DB name, robot config 요약 |
| Recent Health Events | 연결 끊김, 재연결, timeout 이벤트 |
| Manual Check Actions | 상태 재확인, 로그 화면으로 이동 |

#### 표시 필드

| 필드 | 설명 |
| --- | --- |
| `component_name` | Control Service, MariaDB, ROS2, AI Server 등 |
| `status` | ONLINE, OFFLINE, DEGRADED, UNKNOWN |
| `last_checked_at` | 마지막 확인 시각 |
| `latency_ms` | 확인 가능한 경우 응답 시간 |
| `message` | 상태 설명 |

이 화면은 설정을 직접 수정하는 화면이 아니다. `.env`나 배포 설정 변경은 phase 1 관리자 UI에서 다루지 않는다. 운영자는 상태를 확인하고, 문제가 있으면 알림/로그 또는 외부 실행 환경을 확인한다.

---

## 8. 인터랙션 정책

### 8-1. 요청 중 UI

서버 요청 중에는 같은 요청 버튼을 중복 클릭할 수 없게 한다.

예:

```text
물품 운반 요청
-> 요청 전송 중...
-> 접수 완료 또는 실패
```

운반 요청은 idempotency key를 사용하지만, UI에서도 중복 클릭을 막아야 한다. idempotency는 네트워크 재시도 방어이고, 버튼 disable은 사용자 경험 방어이다.

작업 요청 화면의 서버 조회와 제출 worker는 PyQt UI thread를 막지 않아야 하며, 화면이 닫힐 때 실행 중인 worker thread를 정리한다.
물품 목록 조회가 실패한 경우에는 같은 화면에서 다시 진입하거나 새로고침할 때 재시도할 수 있어야 한다. 실패 상태가 내부 loaded flag로 고정되어서는 안 된다.
옵션 조회 로딩 상태는 boolean flag가 아니라 `idle`, `loading`, `loaded`, `failed` 같은 명시적 상태로 관리한다. 실패 후 재시도, 성공 후 중복 조회 방지, 수동 새로고침 동작이 상태값만 보고 판단 가능해야 한다.

### 8-2. 실패 메시지

실패 메시지는 사람용 메시지와 기계용 코드를 함께 보여준다.

```text
요청 실패
reason_code: ROBOT_UNAVAILABLE
메시지: 현재 운반 가능한 로봇이 없습니다.
```

`reason_code`를 숨기지 않는다. 운영 중 문제 분석과 팀 간 디버깅에 필요하기 때문이다.

### 8-3. 취소 UX

취소는 위험도가 있는 액션이다.

권장 UX:

1. 취소 버튼 클릭
2. 확인 dialog 표시
3. 취소 요청 전송
4. `CANCEL_REQUESTED` 상태 표시
5. 최종 `CANCELLED` 또는 `CANCEL_FAILED` 표시

취소 확인 dialog에는 다음 정보를 포함한다.

- `task_id`
- 현재 상태
- 배정 로봇
- 현재 phase

### 8-4. 빈 상태

데이터가 없는 경우 빈 테이블만 보여주지 않는다.

예:

```text
현재 진행 중인 작업이 없습니다.
새 작업을 요청하려면 [작업 요청]으로 이동하세요.
```

### 8-5. 준비 중 기능

준비 중인 기능은 버튼만 비활성화하지 않는다. 왜 사용할 수 없는지와 대체 가능한 기능을 설명한다.

예:

```text
순찰 요청은 아직 서버 workflow와 연결되지 않았습니다.
현재 제출 가능한 시나리오는 작업 요청 화면에서 확인할 수 있습니다.
```

---

## 9. 데이터 표시 규칙

### 9-1. ID 표시

| ID | 표시 규칙 |
| --- | --- |
| `task_id` | `#1001` 형태로 표시 가능하나 원본 값은 숫자 |
| `item_id` | 작업 요청 화면에서는 표시하지 않고 payload와 내부 추적에만 사용 |
| `caregiver_id` | 상단 사용자 정보 또는 상세 패널에 표시 |
| `assigned_robot_id` | task card와 robot card에 명확히 표시 |

### 9-2. 시간 표시

운영 화면에서는 상대 시간과 절대 시간을 함께 쓰는 것이 좋다.

예:

```text
방금 전
2026-04-28 14:31:05
```

좁은 테이블에서는 절대 시간만 표시하고, 상세 패널에서 상대 시간을 추가한다.

관리자 UI의 공통 절대 시간 형식은 `YYYY.MM.DD HH:mm`이다. 날짜만 있는 값은 `YYYY.MM.DD`로 표시한다. 화면에 보이는 테이블 셀, 카드, 텍스트 영역, key/value 상세 행에는 raw ISO 구분자인 `T`, timezone suffix, fractional seconds를 그대로 노출하지 않는다.

### 9-3. 상태 표시

DB/API 원본 상태값은 유지하되, 화면에는 한글 보조 라벨을 함께 표시한다.

예:

```text
RUNNING
진행 중
```

운영자 교육과 개발자 디버깅을 동시에 고려하기 위해 원본 enum을 완전히 숨기지 않는다.

### 9-4. Key/Value 상세 표시

운영자용 상세 패널의 핵심 데이터는 `robot_id: pinky2`, `status: ONLINE` 같은 raw multi-line 문자열로 표시하지 않는다. `KeyValueRow` 형태를 사용해 key를 작은 배지, 굵기, 색상으로 value와 명확히 구분한다.

테이블은 밀도를 위해 원본 컬럼 값을 유지할 수 있다. 상세 패널, 사이드 패널, 로봇 카드, 요청 미리보기, 결과 패널, active map 요약, 경고 목록, 관련 객체 패널은 key/value label을 분리한다. 원본 exception text나 payload JSON은 운영자 요약 뒤의 muted detail text로만 노출한다.

---

## 10. 현재 구현 대비 개선 항목

관리자 UI 설계 기준으로 현재 구현에서 개선할 항목은 다음과 같다.

| 항목 | 현재 | 개선 방향 |
| --- | --- | --- |
| 테마 | 연한 파란색/흰색 카드 중심 | 상태 대비가 강한 운영 콘솔 톤으로 정리 |
| 홈 갱신 | 진입/수동 로드 중심 | 초기 snapshot + TCP push 반영, fallback polling |
| 로봇 상태 | 사이드바 진입 구조는 있으나 상세 runtime 데이터 연동은 제한적 | 로봇별 연결/배터리/위치/현재 작업 데이터를 서버 응답과 정합화 |
| 작업 모니터 | 별도 페이지와 순찰 낙상 대응 UI 존재 | 필터, 취소/중단 액션, delivery/guide 상세 section 보강 |
| 알림/로그 | mock list 중심 | severity/filter/detail 구조로 변경 |
| 요청 응답 표시 | 기본 성공 메시지 중심 | `task_id`, `assigned_robot_id`, `reason_code` 명시 |
| 취소 | 서버 기능 존재, UI 노출 부족 | task card/detail panel에서 취소 가능 상태 표시 |
| 순찰/안내/추종 | 순찰은 phase 1 연동/UI 존재, 안내는 키오스크 연동 보강 대상, 추종은 준비 중 | admin/kiosk 완성 범위에 맞춰 노출 상태와 입력 구조 정리 |
| 와이어프레임 브랜드 | `RoboCare OS`, `Operational Console` 혼재 | `ROPI`로 통일 |
| 와이어프레임 shell | 페이지마다 sidebar/topbar 중복 | 공통 `AdminShell`로 통합 |
| Top nav | service label이 nav처럼 배치 | `SystemStatusStrip` 상태 chip으로 변경 |
| Sidebar 폭 | 260px/280px 혼재 | 260px 기준으로 통일 |
| 안전 액션 | `Manual Override`가 활성 버튼처럼 표시 | backend 안전 기능 전에는 제거 또는 disabled |

---

## 11. phase 1 화면 우선순위

phase 1에서 실제 구현 우선순위는 관리자 UI와 키오스크 UI 완성을 기준으로 한다. 모바일 앱이나 별도 방문자 `user_ui` 제품화는 이 문서의 phase 1 완성 범위에 포함하지 않는다.

| 우선순위 | 화면 | 이유 |
| --- | --- | --- |
| 1 | 홈 대시보드 | 모든 시나리오의 운영 상태를 보는 시작점 |
| 2 | 작업 요청 | 공통 task 생성 구조와 현재 제출 가능한 시나리오 제공 |
| 3 | 작업 모니터 | 취소, 실패, 진행 상태 추적 필요 |
| 4 | 좌표/구역 설정 | 운반/순찰 데모의 DB 기반 좌표 설정을 SQL/.env 수정 없이 보정 |
| 5 | 로봇 상태 | 로봇 연결/배터리/작업 상태 확인 |
| 6 | 알림/로그 | 문제 분석과 운영 로그 확인 |
| 7 | 재고 관리 | 현재 운반 시나리오 입력 데이터와 직접 연결 |
| 8 | 어르신 정보 | 안내/방문자 UI와 연결될 기반 데이터 |
| 9 | 키오스크 홈/검색/안내/직원 호출 | 방문자용 제품 진입점이며 admin UI와 별도 앱으로 완성 |

운반은 현재 구현 우선순위가 높지만, 전체 UI 정보 구조의 중심은 특정 시나리오가 아니라 `task`, `robot`, `event`, `member`, `inventory`이다.

---

## 12. 와이어프레임 작성 기준

와이어프레임은 다음 산출물을 포함해야 한다.

- 관리자 로그인 화면
- 홈 대시보드
- 작업 요청 페이지
- 작업 모니터 페이지
- 좌표/구역 설정 페이지
- 로봇 상태 페이지
- 재고 관리 페이지
- 어르신 정보 페이지
- 알림/로그 페이지
- 시스템 상태 페이지는 phase 1에서 제외하고 phase 2 진단 화면 참고안으로만 유지
- 공통 컴포넌트 스타일 가이드
- 상태별 화면 예시: loading, empty, error, success, disabled

각 페이지는 최소한 다음을 표현해야 한다.

- 페이지 목적
- 주요 사용자 행동
- 주요 데이터 필드
- 성공 상태
- 실패 상태
- 비어 있는 상태
- 서버 연결 실패 상태
- 다음 화면 이동

### 12-1. 현재 와이어프레임 적용 우선순위

현재 `wireframes/stitch_carebot_operations_dashboard/`의 관리자 와이어프레임은 다음 기준으로 적용한다.

| 와이어프레임 | 적용 기준 |
| --- | --- |
| `login` | 중앙 로그인 card와 서버 상태 card만 참고. 비활성 sidebar/topbar는 제거 |
| `operational_dashboard` | KPI, robot board, timeline, task flow board 배치 참고 |
| `task_request_ui_sync` | 작업 요청 기준안으로 채택 |
| `task_request` | 중복안. 필요한 세부 card만 참고하고 기준안으로 쓰지 않음 |
| `task_monitor` | table/detail panel/timeline 구조 참고 |
| `robot_status` | 지도 placeholder, fleet card, robot detail panel 구조 참고 |
| `inventory_management` | inventory table, low stock, edit form 구조 참고 |
| `senior_info` | 검색 결과, preference, event, prescription card 구조 참고 |
| `logs_notifications` | filter, event table, detail drawer 구조 참고 |
| `system_health` | phase 2 진단 화면 참고용. phase 1 sidebar에는 추가하지 않음 |

와이어프레임의 색상 톤과 카드 구성은 참고한다. 그러나 shell, 브랜드, top nav, sidebar, 폰트, dark mode는 이 설계서 기준으로 정규화한다.

### 12-2. HTML/Tailwind에서 PyQt로 옮길 때의 정규화 규칙

HTML/Tailwind 와이어프레임을 PyQt로 옮길 때는 다음 규칙을 따른다.

| HTML/Tailwind 요소 | PyQt 변환 기준 |
| --- | --- |
| page-level `<aside>` | `AdminSidebar` 단일 공통 컴포넌트 |
| page-level `<header>` topbar | 제거. 필요한 정보는 `PageHeader`로 이동 |
| top nav service labels | `SystemStatusStrip` 상태 chip |
| `RoboCare OS` | `ROPI` |
| `Operational Console` | 제거 또는 페이지별 한글 제목으로 대체 |
| `fixed`, `sticky` layout | `QHBoxLayout`, `QVBoxLayout`, `QGridLayout`, `QScrollArea` |
| card `<div>` | `QFrame` |
| Tailwind grid | `QGridLayout` |
| Tailwind flex row/col | `QHBoxLayout`, `QVBoxLayout` |
| table | `QTableWidget` 또는 `QTableView` |
| badge/chip | `QLabel` + QSS objectName |
| icon | local SVG/QIcon 또는 text label |
| dark mode class | 제거 |

페이지 구현자는 HTML 구조를 그대로 복사하지 않는다. 각 페이지의 body content만 분석하고, shell은 `CaregiverMainWindow`의 공통 layout과 공통 component를 사용한다.

입력 컨트롤은 Qt 기본 subcontrol이 남으면 와이어프레임과 시각적으로 어긋난다. 따라서 `QComboBox::drop-down`, `QComboBox::down-arrow`, `QComboBox QAbstractItemView`, `QSpinBox::up-button`, `QSpinBox::down-button`, `QSpinBox::up-arrow`, `QSpinBox::down-arrow`를 QSS에서 명시적으로 정의한다. 아이콘은 로컬 SVG를 사용하고, 스타일시트 로딩 시 실행 위치와 무관하게 절대 경로로 해석되도록 처리한다.

### 12-3. PyQt 공통 컴포넌트 우선 구현 순서

와이어프레임을 실제 PyQt UI로 구현할 때는 페이지보다 공통 컴포넌트를 먼저 만든다.

권장 순서:

1. `AdminShell`
2. `AdminSidebar`
3. `PageHeader`
4. `SystemStatusStrip`
5. `StatusChip`
6. `CardFrame`
7. `KpiCard`
8. `FormFieldGroup`
9. `SearchableComboBox`
10. `PrioritySegment`
11. `DataTable`
12. `TaskCard`
13. `ResultPanel`

공통 shell과 component가 없으면 페이지별 구현이 서로 달라진다. 따라서 각 페이지가 sidebar, topbar, status chip을 직접 만들지 않도록 한다.

### 12-4. 와이어프레임 검수 체크리스트

와이어프레임 또는 PyQt 구현 결과는 다음 체크리스트를 통과해야 한다.

| 항목 | 기준 |
| --- | --- |
| 브랜드 | 화면에 `ROPI`만 표시된다 |
| 금지 브랜드 | `RoboCare OS`, `CareBot`, `Operational Console`이 표시되지 않는다 |
| navigation | 페이지 이동은 좌측 sidebar로만 한다 |
| service status | Control Service, DB, ROS2, AI Server는 상태 chip으로만 표시된다 |
| sidebar | 모든 관리자 페이지의 메뉴명, 순서, 폭이 같다 |
| topbar | 독립 top nav bar가 없다 |
| font | Pretendard/Noto Sans KR 기준이다 |
| dark mode | phase 1 관리자 화면에는 dark mode class/스타일이 없다 |
| unsafe action | backend 없는 `Manual Override`가 활성화되어 있지 않다 |
| PyQt feasibility | `QLayout`, `QFrame`, `QStackedWidget`, `QScrollArea`로 구현 가능한 구조다 |

---

## 13. 방문자 키오스크 UI 범위

방문자 키오스크 UI는 관리자/관제 운영자 UI와 별도 앱으로 설계한다.

관리자 UI가 운영 관제와 작업 추적을 목적으로 한다면, 키오스크 UI는 방문자가 시설 로비에서 짧은 시간 안에 방문 등록, 어르신 찾기, 로봇 안내 요청, 직원 호출을 수행하는 것을 목적으로 한다.

키오스크 UI의 핵심 목표는 다음과 같다.

- 방문자가 별도 교육 없이 첫 화면에서 필요한 행동을 선택할 수 있어야 한다.
- 입력 단계는 짧고, 터치 가능한 버튼은 충분히 커야 한다.
- 방문자 개인정보와 어르신 개인정보를 과하게 노출하지 않아야 한다.
- 로봇 안내 가능 여부와 직원 호출 상태를 명확히 알려야 한다.
- 오류가 발생해도 방문자가 다음 행동을 이해할 수 있어야 한다.

제품 기준으로 키오스크 앱에는 관리자 로그인, 관리자 사이드바, 작업 모니터, 재고 관리, 운영 로그가 들어가지 않는다.

로봇 안내에서 키오스크는 **주행 전 handoff UI**다. 방문 등록, 안내 태스크 생성, Pinky의 키오스크/안내 시작 위치 이동, 안내자 인식, 안내 시작 버튼까지만 표시한다. `START_GUIDANCE`가 수락되면 방문자는 로봇을 따라 떠나므로, 키오스크는 방문자 세션을 지우고 Home으로 돌아가며 시작 뒤 runtime phase를 계속 표시하지 않는다. 수락 전 거절/실패는 방문자가 아직 키오스크 앞에 있으므로 재시도, 취소, 직원 호출을 위해 계속 표시한다.

안내 주행 시작 버튼은 최신 Control-facing guide phase가 `READY_TO_START_GUIDANCE`이고, 키오스크가 0 이상의 numeric `target_track_id`를 확보한 경우에만 활성화한다. target ID만 있거나 ready phase만 있는 상태로는 활성화하지 않는다.

---

## 14. 키오스크 현재 구현 기준

현재 코드에는 `ui/kiosk_ui` 아래에 키오스크 홈, 어르신 검색, 안내 확인, 안내 진행 화면 일부가 구현되어 있다. `ui/user_ui`에도 기존 방문자용 화면이 남아 있지만, phase 1 제품 완성 기준은 `ui/kiosk_ui`를 별도 앱으로 완성하는 것이다.

제품 설계 기준 명칭은 `Kiosk UI`로 통일한다. 필요한 경우 기존 `ui/user_ui`와 `ui/utils/pages/visitor`의 구현을 참고하거나 공통 컴포넌트로 흡수하되, 최종 진입점은 `ui/kiosk_ui/main.py`와 `KioskHomeWindow` 기준으로 정리한다.

현재 방문자 UI 관련 파일은 다음과 같다.

| 화면 | 현재 코드 위치 | 현재 상태 |
| --- | --- | --- |
| 키오스크 홈/검색/안내 흐름 | `ui/kiosk_ui/main_window.py` | 홈 action card, 어르신 검색, 안내 확인, 진행 화면 일부 존재 |
| 기존 방문자 홈 | `ui/user_ui/main_window.py` | 어르신 찾기, 직원 호출 action card 존재. phase 1 제품 진입점은 아님 |
| 방문 안내 | `ui/utils/pages/visitor/visit_guide_page.py` | 어르신 검색, 로봇 안내 시작 구조 존재 |
| 직원 호출 | `ui/utils/pages/visitor/staff_call_page.py` | 호출 유형, 상세 입력, 제출 구조 존재 |
| 방문 등록 | `ui/utils/pages/visitor/visitor_register_page.py` | 등록 form은 존재하나 현재 main window 연결은 약함 |

관련 service client는 다음과 같다.

| 기능 | service client |
| --- | --- |
| 어르신 검색/안내 시작 | `VisitGuideRemoteService` |
| 방문자 정보 조회 | `VisitorInfoRemoteService` |
| 방문 등록 | `VisitorRegisterRemoteService` |
| 직원 호출 | `StaffCallRemoteService` |

키오스크 UI 설계와 구현은 `kiosk_ui` 별도 앱을 기준으로 한다. `user_ui`는 기존 구현 참고용 또는 후속 정리 대상으로 취급한다.

---

## 15. 키오스크 사용자와 운영 환경

### 15-1. 주요 사용자

키오스크의 1차 사용자는 방문자이다.

방문자는 시스템 구조, 로봇 상태, task 상태 enum을 알 필요가 없다. 화면은 다음 질문에 답해야 한다.

- 내가 어디서 시작하면 되는가
- 어르신을 찾을 수 있는가
- 방문 등록이 필요한가
- 로봇이 나를 안내할 수 있는가
- 도움이 필요하면 직원을 부를 수 있는가
- 요청이 접수되었는가
- 실패했다면 무엇을 해야 하는가

### 15-2. 운영 환경

키오스크는 로비 또는 접수 공간의 터치스크린을 기준으로 한다.

| 항목 | 기준 |
| --- | --- |
| 기준 해상도 | 1920x1080 |
| 최소 해상도 | 1280x800 |
| 입력 방식 | 터치 우선, 필요 시 키보드/마우스 |
| 운영 방식 | full-screen 권장 |
| 터치 타깃 | 주요 버튼 최소 높이 72px 이상 |
| 본문 글자 | 최소 18px 이상 |
| 주요 액션 글자 | 24-32px 권장 |
| idle timeout | 60초 무입력 시 홈 복귀 권장 |

관리자 UI와 달리 정보 밀도를 높이지 않는다. 한 화면에는 하나의 주요 행동만 두고, 선택지는 2-4개 수준으로 제한한다.

---

## 16. 키오스크 디자인 시스템

### 16-1. 시각 방향

키오스크 UI는 "따뜻한 안내 데스크"에 가까워야 한다.

관리자 UI의 관제 콘솔 톤과 달리, 방문자가 긴장하지 않도록 큰 여백, 높은 가독성, 부드러운 색상, 명확한 안내 문구를 사용한다.

### 16-2. 색상 토큰

| 토큰 | 색상 | 사용처 |
| --- | --- | --- |
| `kiosk-bg` | `#FFF8EE` | 키오스크 전체 배경 |
| `kiosk-surface` | `#FFFFFF` | 카드, 입력 영역 |
| `kiosk-text-primary` | `#1E293B` | 주요 텍스트 |
| `kiosk-text-secondary` | `#64748B` | 설명 텍스트 |
| `kiosk-primary` | `#2F855A` | 기본 주요 액션 |
| `kiosk-guide-blue` | `#2B6CB0` | 로봇 안내, 정보성 액션 |
| `kiosk-coral` | `#E76F51` | 직원 호출, 주의 액션 |
| `kiosk-warning` | `#F59E0B` | 대기, 확인 필요 |
| `kiosk-danger` | `#DC2626` | 실패, 긴급 |
| `kiosk-border` | `#E8DED2` | 카드 경계 |

### 16-3. 폰트

관리자 UI와 동일하게 Pretendard를 기본으로 사용한다.

키오스크는 멀리서 읽어야 하므로 작은 글자를 피한다.

| 용도 | 크기 기준 |
| --- | --- |
| 홈 메인 제목 | 40-56px |
| 페이지 제목 | 32-44px |
| action card 제목 | 28-36px |
| 버튼 텍스트 | 24-30px |
| 설명 텍스트 | 18-22px |
| 보조 정보 | 16-18px |

폰트 로딩은 관리자 UI와 동일하게 앱 assets의 폰트를 `QFontDatabase.addApplicationFont()`로 로드한다.

### 16-4. 공통 컴포넌트

| 컴포넌트 | 목적 |
| --- | --- |
| `KioskRoot` | full-screen 배경과 전체 여백 |
| `KioskHeader` | 현재 단계, 홈 버튼, 뒤로가기 버튼 |
| `LargeActionCard` | 홈의 주요 행동 선택 |
| `StepIndicator` | 방문 등록/안내 요청의 현재 단계 표시 |
| `LargeInputField` | 터치 입력용 큰 입력 필드 |
| `PrimaryTouchButton` | 주요 제출/다음 버튼 |
| `SecondaryTouchButton` | 뒤로가기/다시 검색 |
| `CallStaffButton` | 직원 호출 고정 보조 액션 |
| `ResultStatePanel` | 성공/실패/대기 결과 표시 |
| `IdleWarningDialog` | 무입력 홈 복귀 전 안내 |

---

## 17. 키오스크 네비게이션 구조

키오스크는 좌측 사이드바를 사용하지 않는다.

기본 구조는 다음과 같다.

```text
Kiosk App
-> Home
   -> Visitor Registration
   -> Resident Search
      -> Guide Confirmation
      -> Robot Guidance Progress
   -> Staff Call
```

상단에는 항상 다음 액션을 제공한다.

| 액션 | 기준 |
| --- | --- |
| 처음으로 | 모든 페이지에서 제공 |
| 뒤로가기 | 홈을 제외한 대부분의 페이지에서 제공 |
| 직원 호출 | 홈 또는 안내 실패/로봇 불가 상태에서 강조 |

키오스크는 방문자에게 복잡한 task enum을 직접 보여주지 않는다. 단, 디버깅과 운영 추적을 위해 완료 화면 하단에 작은 글씨로 `요청번호` 또는 `task_id`를 표시할 수 있다.

---

## 18. 키오스크 페이지 설계

### 18-1. 키오스크 홈

#### 목적

방문자가 처음 보는 시작 화면이다. 방문자가 해야 할 일을 3초 안에 고를 수 있어야 한다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Welcome Header | 시설명, `무엇을 도와드릴까요?` |
| Main Actions | 방문 등록, 직원 호출 |
| Info Strip | 현재 위치, 운영 시간, 안내 로봇 상태 |
| Footer | 개인정보 안내, 버전/연결 상태 축약 |

#### 와이어프레임 이식 기준

phase 1 PyQt 홈 화면은
`wireframes/stitch_ropi_kiosk_visitor_service/kiosk_home`의 시각 방향을 따른다.

PyQt로 이식할 때는 따뜻한 안내 데스크 테마, 큰 상단 app bar, 중앙 welcome
message, 2개의 대형 action card, 하단 정보 bar를 유지한다. 와이어프레임에
남아 있는 `Call Staff`, `Current Location`, `Hours`, `Robot: Ready` 같은 영어
문구는 방문자용 한국어 라벨로 정리한다. action card 내부의 중복 micro CTA는
제거하고 card 전체를 터치 target으로 사용한다.

#### 주요 액션

| 액션 | 이동 |
| --- | --- |
| 방문 등록 | Visitor Registration |
| 직원 호출 | Staff Call |

phase 1에서 홈 화면은 별도 `어르신 찾기` action을 노출하지 않는다. 어르신
조회는 방문자 등록 페이지 안에서만 제공하며, 방문자 필수 정보와 개인정보 동의가
입력된 뒤 같은 폼 안의 방문 대상 어르신 검색 섹션을 사용한다. 기존 안내 검색
API를 호출하지 않는다.

#### 상태

| 상태 | UI 표현 |
| --- | --- |
| 정상 | 3개 action card 활성 |
| 서버 연결 실패 | action 비활성 또는 제한, 직원 호출 안내 강조 |
| 로봇 안내 불가 | 어르신 찾기는 가능, 로봇 안내 card에 `현재 안내 로봇 점검 중` 표시 |
| 운영 시간 외 | 방문 등록/직원 호출 중심 안내 |

---

### 18-2. 방문 등록 페이지

#### 목적

방문자가 본인 정보, 개인정보 동의, 방문 대상 어르신 선택을 한 페이지에서 완료한다.
이 페이지가 phase 1 키오스크 로그인 경계다. 제출 성공 시 `visitor` row를
생성/재사용하고, Kiosk App 프로세스 메모리에 `visitor_id`를 보관한다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Step Header | `방문 등록` 제목, 1-2단계 표시 |
| Visitor Form | 이름, 연락처, 관계, 방문 목적 선택 카드 |
| Target Resident Search | 어르신 검색 입력, 후보 목록, 선택된 어르신 요약 |
| Privacy Notice | 개인정보 수집 안내와 동의 |
| Action Row | 이전, 등록하기 |

#### 입력 필드

| 필드 | 설명 |
| --- | --- |
| `visitor_name` | 방문자 이름 |
| `phone_no` | 연락처 |
| `visit_purpose` | 선택된 방문 목적 카드 값 |
| `relationship` | 가족, 지인, 기타 |
| `privacy_agreed` | 개인정보 동의 |
| `target_member_id` | embedded search 결과에서 선택한 숨은 어르신 ID |

#### 방문 목적 선택

방문 목적은 방문 등록 와이어프레임 기준에 맞춰 자유 입력이 아니라 큰 아이콘
카드로 선택한다.

| 규칙 | 설명 |
| --- | --- |
| 선택지 | 가족 면회, 지인 방문, 상담/문의, 기타 |
| 인터랙션 | 카드 하나를 선택하면 선택 상태를 표시하고 `visit_purpose`로 저장 |
| 검증 | 방문 목적 카드가 선택되기 전에는 어르신 검색과 최종 등록을 비활성화 |
| 터치 영역 | 각 목적 카드는 키오스크 터치 기준 높이 이상이며 아이콘과 라벨을 함께 표시 |

#### 검증 규칙

| 조건 | UI 동작 |
| --- | --- |
| 이름 누락 | `이름을 입력해주세요.` |
| 연락처 누락 | `연락처를 입력해주세요.` |
| 개인정보 미동의 | `방문 등록을 위해 개인정보 동의가 필요합니다.` |
| 어르신 미선택 | `방문 대상 어르신을 선택해 주세요.` |
| 서버 실패 | 입력값 유지, 직원 호출 안내 제공 |

#### 내장 어르신 검색

방문 대상 어르신 검색은 별도 페이지가 아니라 방문자 등록 폼 안의 섹션이다.

| 규칙 | 설명 |
| --- | --- |
| 활성화 | 방문자 필수 정보와 개인정보 동의가 입력된 뒤 검색 활성화 |
| 조회 | `IF-GUI-008`에 `keyword`, `limit`을 전달한다. 기존 안내 검색 API를 쓰지 않는다 |
| 후보 표시 | 방문자에게 `display_name`, `birth_date`, `room_no`를 표시 |
| 숨은 상태 | `member_id`, `visit_available`, `guide_available`는 내부 선택 상태로 유지 |
| 선택 | 후보 선택 시 `target_member_id`를 저장하고 compact 선택 요약을 표시 |

#### 성공 상태

`IF-GUI-009` 등록 성공 시 다음을 표시하고 `visitor_id`는 Kiosk App 프로세스 메모리에만
보관한다.

```text
방문 등록이 완료되었습니다.
필요하면 로봇 안내를 시작하거나 허용된 케어 정보를 확인할 수 있습니다.
```

---

### 18-3. 내장 어르신 검색 섹션

#### 목적

phase 1에서는 독립 페이지로 제공하지 않는다. 어르신 조회는 방문자 등록 페이지 안의
방문 대상 검색 섹션으로 흡수한다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Search Header | 방문자 등록의 단계/섹션 제목으로 대체 |
| Search Form | 방문자 등록 안의 방문 대상 검색 섹션 |
| Result Area | 방문자 등록 안의 후보 목록 |
| Action Row | 방문자 등록 action row |

#### 와이어프레임 이식 기준

`wireframes/stitch_ropi_kiosk_visitor_service/resident_search`의 시각 요소는 방문자
등록 안의 embedded search block으로 가져온다. 큰 검색 입력, 초록색 icon-only 검색
버튼, 후보 card의 person icon, 굵은 후보 이름, 명확한 선택 상태는 유지하되, 페이지
단위 헤더/푸터는 유지하지 않는다.

#### 입력 필드

| 필드 | 설명 |
| --- | --- |
| `keyword` | 이름 또는 호실 |
| `target_member_id` | 선택된 숨은 어르신 ID |

#### 결과 카드

개인정보 보호를 위해 결과 카드에는 필요한 최소 정보만 표시한다.

| 필드 | 표시 방식 |
| --- | --- |
| `member_id` | 화면에는 숨기거나 작은 요청번호 수준으로 표시 |
| `display_name` | 첫 글자와 마지막 글자를 보여주고 가운데를 마스킹 |
| `birth_date` | 동명이인 구분을 위해 표시 |
| `room_no` | 같은 검색 필드가 호실 일부 검색을 허용하므로 표시 |
| `visit_available` | 방문 가능 여부 |
| `guide_available` | 로봇 안내 가능 여부 |

#### 상태

| 상태 | UI 표현 |
| --- | --- |
| 방문자 필수 정보/개인정보 동의 누락 | 어르신 검색 비활성화 및 필요한 입력 안내 |
| 검색 전 | 방문자 등록 안의 큰 입력창과 예시 문구 |
| 검색 중 | `어르신 정보를 찾고 있습니다.` |
| 결과 있음 | 방문자 등록 안의 후보 목록 |
| 결과 없음 | `일치하는 정보를 찾지 못했습니다.` + 직원 호출 |
| 방문 제한 | 제한 사유를 과하게 노출하지 않고 직원 문의 유도 |

방문자 등록 폼을 제출하면 `IF-GUI-009`로 방문 등록을 최종 확정한다. 이 시점 이후에만
키오스크는 등록된 `visitor_id`를 기반으로 안내 시작과 방문자용 케어 이력 조회를
제공할 수 있다.

---

### 18-4. 안내 확인 페이지

#### 목적

검색된 어르신 또는 목적지에 대해 로봇 안내를 시작하기 전 최종 확인을 받는다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Target Summary | 선택한 방문 대상 또는 목적지 |
| Robot Availability | 안내 로봇 가능 여부 |
| Guide Notice | 로봇을 따라갈 때 주의사항 |
| Action Row | 안내 시작, 직원 호출, 뒤로가기 |

#### 표시 필드

| 필드 | 설명 |
| --- | --- |
| `member_id` | 내부 요청용, 화면에는 최소 노출 |
| `destination_id` | 안내 목적지 |
| `destination_label` | 사람이 읽는 목적지 |
| `guide_available` | 안내 가능 여부 |
| `assigned_robot_id` | 안내 시작 후 표시 |

#### 안내 시작 응답

안내 task 생성 또는 안내 시작 응답은 다음 정보를 사용한다.

| 필드 | 표시 방식 |
| --- | --- |
| `result_code` | 성공/거절 상태 |
| `result_message` | 방문자용 문구 |
| `reason_code` | 운영자 확인용, 방문자 화면에서는 필요 시 숨김 |
| `task_id` | 요청번호로 작게 표시 |
| `assigned_robot_id` | 예: `pinky1` |

방문자에게는 `GUIDE_TASK_ACCEPTED` 같은 내부 enum보다 `안내 로봇을 배정했습니다.` 같은 문구를 우선 표시한다.

---

### 18-5. 로봇 안내 진행 페이지

#### 목적

로봇 안내 요청 후 안내 주행 시작 전까지 방문자가 현재 상태를 이해하고 다음 행동을 할 수 있게 한다.

범위 경계:

- 키오스크는 `방문 등록 -> 안내 task 생성 -> 로봇이 키오스크 앞까지 이동 -> target tracking 확보 -> 안내 주행 시작`까지만 담당한다.
- 안내 주행 시작 이후의 안내자 이탈 복구, 재인식, 케어 이력 표시 등은 Pinky에 장착된 Display App이 담당한다.
- 키오스크 진행 화면 진입은 ROS 명령 성공에 의존하지 않는다. DB 기반 안내 task 생성이 수락되면 진행 화면으로 이동할 수 있고, 로봇 호출 명령 실패는 같은 진행 화면의 상태/경고 문구로 표시한다.
- 태스크가 `WAIT_GUIDE_START_CONFIRM`, `WAIT_TARGET_TRACKING` 같은 주행 전 phase에 머무는 동안에는 task status payload의 최신 거절 결과(`task_outcome`/`latest_reason_code`/`result_message`)를 계속 경고 문구로 표시한다. 정상 tracking snapshot이 들어와도 이 경고 문구를 덮어쓰면 안 되며, 다만 `tracking_status=TRACKING`이고 `active_track_id`가 있으면 재시도용 안내 주행 시작 버튼은 활성화할 수 있다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Progress Header | `안내를 준비하고 있습니다` 또는 `로봇을 따라 이동해주세요` |
| Robot Card | 배정 로봇, 현재 상태 |
| Progress Steps | 요청 접수, 로봇 이동, 안내 시작, 이동 중, 도착 |
| Safety Notice | 로봇과 적정 거리 유지 안내 |
| Action Row | 직원 호출, 안내 중단, 처음으로 |

#### 상태

| 상태 | 방문자 문구 |
| --- | --- |
| `WAITING_DISPATCH` | `안내 요청을 접수했습니다.` |
| `ASSIGNED` | `안내 로봇을 배정했습니다.` |
| `RUNNING` | `로봇을 따라 이동해주세요.` |
| `COMPLETED` | `목적지에 도착했습니다.` |
| `FAILED` | `안내를 시작하지 못했습니다. 직원에게 도움을 요청해주세요.` |
| `CANCELLED` | `안내가 중단되었습니다.` |
| 주행 전 최신 `REJECTED` | 서버 `result_message`를 표시하고, 없으면 `latest_reason_code` 기준의 짧은 대체 문구를 표시한다. |

#### 피드백 표시

방문자 화면에는 상세 ROS feedback을 그대로 노출하지 않는다.

표시 가능한 요약:

- 로봇이 이동 중입니다.
- 잠시만 기다려주세요.
- 목적지 근처에 도착했습니다.
- 안내를 계속하려면 로봇을 따라와 주세요.

---

### 18-6. 직원 호출 페이지

#### 목적

방문자가 직접 도움을 요청한다.

#### 화면 구성

| 영역 | 구성 |
| --- | --- |
| Header | `직원 호출` |
| Quick Reason Buttons | 길 안내, 방문 등록 도움, 면회 문의, 긴급 도움, 기타 |
| Optional Detail | 상세 입력 |
| Action Row | 호출하기, 뒤로가기 |
| Result Panel | 호출 접수 결과 |

#### 입력 필드

| 필드 | 설명 |
| --- | --- |
| `call_type` | 호출 유형 |
| `description` | 상세 내용, 선택 |
| `member_id` | 어르신 검색 흐름에서 온 경우 연결 가능 |
| `visitor_id` | 방문 등록 후 호출한 경우 연결 가능 |

#### 상태

| 상태 | UI 표현 |
| --- | --- |
| 호출 전 | 큰 사유 선택 버튼 |
| 제출 중 | `직원을 호출하고 있습니다.` |
| 접수 완료 | `직원이 곧 도착합니다.` |
| 실패 | `호출에 실패했습니다. 접수 데스크에 문의해주세요.` |

긴급 도움은 다른 호출 사유보다 더 강한 색상과 확인 dialog를 사용한다. 실수로 누르는 것을 막되, 실제 긴급 상황에서는 빠르게 제출할 수 있어야 한다.

---

### 18-7. 키오스크 오류/대기 화면

#### 목적

네트워크 오류, 서버 오류, 로봇 이용 불가, 무입력 timeout 상황에서 방문자가 혼란스럽지 않게 안내한다.

#### 오류 상태

| 상태 | 문구 | 다음 행동 |
| --- | --- | --- |
| 서버 연결 실패 | `현재 안내 시스템에 연결할 수 없습니다.` | 직원 호출 또는 접수 데스크 안내 |
| 로봇 안내 불가 | `현재 로봇 안내를 사용할 수 없습니다.` | 직원 호출 |
| 검색 실패 | `정보를 불러오지 못했습니다.` | 다시 시도, 직원 호출 |
| 무입력 timeout | `처음 화면으로 돌아갑니다.` | 5초 countdown 후 홈 |

#### idle timeout

60초 동안 입력이 없으면 경고 dialog를 표시한다.

```text
계속 이용하시겠습니까?
입력이 없으면 처음 화면으로 돌아갑니다.
```

경고 후 5-10초 동안 입력이 없으면 홈으로 복귀하고, 입력 중이던 개인정보는 화면에서 제거한다.

---

## 19. 키오스크 데이터 표시 규칙

키오스크는 관리자 UI보다 개인정보 노출을 더 엄격히 제한한다.

| 데이터 | 표시 기준 |
| --- | --- |
| `visitor_id` | 완료 화면에서 접수 번호로 표시 가능 |
| `member_id` | 화면에 직접 노출하지 않는 것이 기본 |
| 어르신 이름 | 필요 시 일부 마스킹 가능 |
| 호실 | 안내에 필요한 경우에만 표시 |
| `task_id` | 방문자에게는 `요청번호`로 작게 표시 |
| `assigned_robot_id` | `안내 로봇` 이름으로 표시 |
| `reason_code` | 방문자 화면에는 숨기고 운영 로그에 남김 |

방문자용 문구는 내부 enum을 그대로 보여주지 않는다. 예를 들어 `WAITING_DISPATCH` 대신 `요청을 접수했습니다.`를 표시한다.

---

## 20. 키오스크 PyQt 구현 기준

키오스크 앱은 관리자 앱과 같은 PyQt6 기반이지만 layout 전략이 다르다.

| 구현 요소 | 기준 |
| --- | --- |
| 화면 전환 | `QStackedWidget` |
| 홈 action card | 큰 `QFrame` 또는 `QPushButton` 기반 card |
| 입력 화면 | `QVBoxLayout` 중심, 한 화면 한 목적 |
| 결과 화면 | `ResultStatePanel` 형태의 큰 안내 card |
| idle timeout | `QTimer` |
| full-screen | `showFullScreen()` 또는 kiosk 실행 옵션 |
| 터치 입력 | 큰 input, 큰 button, 필요 시 OS virtual keyboard 고려 |
| 상태 전달 | 서버 request/response + 안내 진행은 push-first |

키오스크에서 복잡한 테이블은 사용하지 않는다. 목록이 필요하면 card list를 사용하고, 한 화면에 많은 행을 표시하지 않는다.

---

## 21. 키오스크 와이어프레임 작성 기준

키오스크 와이어프레임은 다음 산출물을 포함해야 한다.

- 키오스크 홈
- 내장 어르신 검색을 포함한 방문 등록 페이지
- 안내 확인 페이지
- 로봇 안내 진행 페이지
- 직원 호출 페이지
- 오류/서버 연결 실패 화면
- idle timeout 화면
- 공통 touch component 스타일

각 페이지는 최소한 다음을 표현해야 한다.

- 페이지 목적
- 방문자가 눌러야 하는 주요 버튼
- 입력 필드
- 성공 상태
- 실패 상태
- 서버 연결 실패 상태
- 처음으로/뒤로가기 위치
- 개인정보가 노출되는 영역과 숨겨야 하는 영역

---

## 22. 제품 발표용 Admin 데모 UI

이 섹션은 최종 발표에서 사용할 제품형 관리자 데모 UI를 정의한다.
실제 통합 환경은 Pinky 이동 로봇과 Jetcobot 팔을 사용하지만, 발표에서 보여줄 제품 개념은 이들을 하나의 통합 로봇 제품인 ROPI로 노출한다.

데모 UI는 production Control Service 계약을 대체하지 않는다.
기존 Admin UI의 시각 언어를 재사용하되, 전면 표시 로봇명, 데모 데이터, 페이지 범위를 발표 목적에 맞춰 바꾸는 별도 presentation shell이다.

### 22-1. 데모 목적과 경계

데모는 DB, ROS, Pinky, Jetcobot runtime이 없어도 일관된 ROPI 제품 운영 화면을 보여줘야 한다.

| 항목 | 데모 기준 |
| --- | --- |
| 제품명 | 제품/로봇군 이름은 `ROPI`를 사용 |
| 로봇 표시명 | 모든 전면 UI에서 `ROPI 1`, `ROPI 2`, `ROPI 3` 사용 |
| 내부 로봇명 | `pinky1`, `pinky2`, `pinky3`, `jetcobot1`, `jetcobot2`, `arm1`, `arm2`는 숨겨진 fixture/internal mapping 값으로만 허용 |
| 노출 페이지 | 홈, 작업 요청, 작업 모니터, 알림/로그 |
| 숨김 페이지 | 좌표/구역 설정, 로봇 상태, 재고 관리, 어르신 정보, 시스템 상태, 기타 비데모 페이지 |
| runtime 의존성 | Control Service, DB, ROS endpoint, 가짜 ROS node 없이 렌더링과 상호작용 가능 |
| Git 정책 | 데모 앱, 데모 fixture, 데모 테스트는 ignored scratch 파일이 아니라 추적되는 source file |
| 실행 명령 | page-neutral 명령인 `uv run ropi-admin-demo` 사용. home 전용 이름인 `ropi-admin-home-demo`는 폐기 |

데모 shell은 maximized 상태로 열고 기존 Admin UI의 sidebar/header 스타일을 유지한다.
sidebar에는 발표에서 사용할 다음 페이지 노출만 둔다.

- `홈`
- `작업 요청`
- `작업 모니터`
- `알림/로그`

### 22-2. 데모 페이지 범위

| 페이지 | 데모 동작 |
| --- | --- |
| 홈 | 운영 KPI, ROPI 로봇 보드, 현재 ROPI marker가 있는 PGM 운영 맵, 짧은 작업 흐름, 최근 이벤트 표시 |
| 작업 요청 | Admin 작업 요청과 같은 핵심 상호작용으로 안내, 운반, 순찰 데모 작업 생성 가능 |
| 작업 모니터 | seed 작업과 생성된 데모 작업을 한국어 작업 유형/상태/단계 label로 표시하고, 선택 작업 detail과 취소/중단 affordance 제공 |
| 알림/로그 | 한국어 severity/event label, 관련 ROPI/task label, 읽기 쉬운 key/value detail 표시 |

작업 요청은 정적인 mock이 아니어야 한다.
발표자가 데모 요청을 제출하면 데모 runtime은 in-memory task record를 만들고, ROPI를 배정하고, timeline/event record를 추가하며, 그 결과가 홈, 작업 모니터, 알림/로그에 보여야 한다.

### 22-3. 데모 데이터 모델

데모는 실제 Control Service 호출 대신 작은 in-memory store를 사용한다.
최소한 다음 record를 지원해야 한다.

| record | 필수 필드 |
| --- | --- |
| DemoRobot | `internal_robot_id`, `display_robot_name`, `task_type`, `status_label`, `location_label`, `battery_percent`, `tone` |
| DemoTask | `task_id`, `task_type`, `status`, `phase`, `assigned_robot_name`, `destination_label`, `summary`, `created_at`, `updated_at` |
| DemoAlertLog | `event_id`, `severity`, `event_type`, `task_id`, `robot_name`, `title`, `message`, `occurred_at`, `detail_rows` |
| DemoMapMarker | `robot_name`, `x`, `y`, `yaw`, `task_label`, `tone` |

작업 ID는 `#1034` 같은 발표용 ID로 표시할 수 있지만, 기존 widget 호환을 위해 내부 numeric ID는 유지할 수 있다.

### 22-4. ROPI 표시명 매핑

모든 노출 페이지는 아래 product-facing mapping을 사용한다.

| 내부 runtime 역할 | 숨김 내부 ID | 표시 로봇명 | 기본 데모 업무 |
| --- | --- | --- | --- |
| 안내 이동 로봇 | `pinky1` | `ROPI 1` | 안내 |
| 운반 이동 로봇 | `pinky2` | `ROPI 2` | 운반 |
| 순찰 이동 로봇 | `pinky3` | `ROPI 3` | 순찰 |
| 픽업 팔 | `arm1` / `jetcobot1` | 로봇으로 표시하지 않음 | 운반 단계 text로만 표현 |
| 목적지 팔 | `arm2` / `jetcobot2` | 로봇으로 표시하지 않음 | 운반 단계 text로만 표현 |

운반 UI는 `적재 완료`, `전달 대기`, `물품 인계 중`처럼 표현할 수 있다.
`arm1`, `arm2`, `jetcobot1`, `jetcobot2`는 보이는 장치명으로 표시하지 않는다.

### 22-5. 한국어 표시 정책

데모 UI는 raw English enum보다 한국어 label과 한국어 value를 우선한다.
raw enum/debug 값은 숨겨진 데이터나 선택적 개발자 진단에만 남길 수 있고, 발표용 주요 화면에는 표시하지 않는다.

| raw/key 값 | 데모 표시 |
| --- | --- |
| `task_id` | `작업 ID` |
| `task_type` | `작업 유형` |
| `assigned_robot_id` | `담당 ROPI` |
| `robot_id` | `로봇` 또는 `ROPI` |
| `task_status` / `status` | `상태` |
| `phase` | `현재 단계` |
| `destination_label` | `목적지` |
| `reason_code` | `처리 사유` |
| `result_message` | `결과 메시지` |
| `payload` | `상세 내용` |
| `created_at` | `요청 시각` |
| `updated_at` | `갱신 시각` |
| `DELIVERY` | `운반` |
| `PATROL` | `순찰` |
| `GUIDE` | `안내` |
| `RUNNING` | `진행 중` |
| `WAITING_DISPATCH` | `배정 대기` |
| `COMPLETED` | `완료` |
| `FAILED` | `실패` |
| `CANCEL_REQUESTED` | `취소 요청` |
| `ONLINE` | `정상` |
| `OFFLINE` | `연결 끊김` |
| `DEGRADED` | `주의` |
| `INFO` | `정보` |
| `WARNING` | `주의` |
| `ERROR` | `오류` |
| `CRITICAL` | `긴급` |

알려진 작업 phase도 한국어로 표시한다.

| raw phase | 데모 표시 |
| --- | --- |
| `WAITING_DISPATCH` | `작업 배정 대기` |
| `MOVE_TO_PICKUP` | `픽업지 이동` |
| `DELIVERY_PICKUP` | `물품 적재` |
| `DELIVERY_DESTINATION` | `목적지 이동` |
| `HANDOVER_WAITING` | `전달 대기` |
| `RETURN_TO_DOCK` | `복귀 중` |
| `WAIT_TARGET_TRACKING` | `안내 대상 확인` |
| `READY_TO_START_GUIDANCE` | `안내 시작 준비` |
| `GUIDANCE_RUNNING` | `안내 주행 중` |
| `PATROL_RUNNING` | `순찰 중` |
| `WAIT_FALL_RESPONSE` | `낙상 의심 확인` |
| `TASK_COMPLETED` | `작업 완료` |

detail panel은 `task_id: 1034`, `assigned_robot_id: pinky2` 같은 raw dictionary string을 렌더링하지 않는다.
한국어 key와 product-facing value를 분리한 key/value row를 사용한다.

### 22-6. 작업 요청 데모 흐름

작업 요청은 production Admin UI와 같은 상호작용 개념을 유지하되, 데모 안전 입력과 in-memory 결과를 사용한다.

| 요청 유형 | 필수 입력 | 데모 배정 | 결과 동작 |
| --- | --- | --- | --- |
| 안내 | 목적지/대상 label | `ROPI 1` | 진행 중 안내 작업과 안내 event 생성 |
| 운반 | 물품, 목적지 | `ROPI 2` | 진행 중 운반 작업과 운반 event 생성 |
| 순찰 | 순찰 구역 | `ROPI 3` | 진행 중 순찰 작업과 순찰 event 생성 |

submit 결과 panel에는 다음을 표시한다.

- `요청 결과`
- `작업 ID`
- `담당 ROPI`
- `현재 상태`
- `다음 단계`

정상 성공 경로에서는 `result_code`, `CLIENT_ERROR`, `runtime precheck` 같은 transport/server 용어를 전면 표시하지 않는다.

### 22-7. 홈 데모 요구사항

홈은 현재 데모 방향을 유지한다.

- `ROPI 1`, `ROPI 2`, `ROPI 3` 표시.
- 현재 작업명은 `안내`, `운반`, `순찰`로 표시.
- 위치 label은 `복도1`, `303호`, `복도3`, `보호사실`, `충전소`처럼 DB 구역명처럼 보이는 값을 사용.
- 저장소의 실제 PGM/YAML map asset 사용.
- 세 개 marker를 표시하되 로봇끼리 route line으로 연결하지 않음.
- marker label은 작게 유지하고 벽 겹침을 피함.
- 운영 맵과 짧은 작업 흐름을 한 row에 배치.
- compact board가 표시될 경우 데모 첫 viewport에서는 production full-width flow board를 숨김.

### 22-8. 작업 모니터 데모 요구사항

작업 모니터는 요청이 실제 운영으로 관측되는 것을 보여주는 핵심 페이지이다.

표시 기준은 다음과 같다.

- 한국어 작업 유형 chip: `안내`, `운반`, `순찰`.
- 한국어 상태 chip: `진행 중`, `완료`, `주의`, `실패`, `취소 요청`.
- product-facing 로봇명만 표시: `ROPI 1`, `ROPI 2`, `ROPI 3`.
- 선택 작업 detail panel은 한국어 key/value label 사용.
- 시나리오별 진행 text는 한국어로 표시.
- 취소/중단 action label은 `작업 취소`, `순찰 중단`처럼 한국어로 표시.

보이는 primary cell이나 detail row에 `pinky`, `jetcobot`, `arm1`, `arm2`, `DELIVERY`, `PATROL`, `GUIDE`, `RUNNING` 같은 raw enum/string을 표시하지 않는다.

### 22-9. 알림/로그 데모 요구사항

알림/로그는 작업 요청과 로봇 이벤트 이후 운영 이력이 남는 느낌을 만들어야 한다.

표시 기준은 다음과 같다.

- severity label은 `정보`, `주의`, `오류`, `긴급`.
- event title은 `작업 생성`, `운반 목적지 도착`, `순찰 낙상 의심`, `안내 시작`처럼 표시.
- 관련 작업은 `#1034` 형식 ID로 표시.
- 관련 로봇은 `ROPI 1`, `ROPI 2`, `ROPI 3`로 표시.
- detail row는 한국어 key와 읽기 쉬운 한국어 value 사용.

raw JSON payload를 첫 번째 표현으로 표시하지 않는다.
payload 성격의 detail이 필요하면 먼저 한국어 요약을 보여주고, raw debug detail은 muted/secondary 영역으로 밀어낸다.

### 22-10. 구현 및 테스트 기준

구현은 가능한 한 production page와 데모 코드를 분리한다.

| 영역 | 기준 |
| --- | --- |
| package | `ui/presentation_demo` 또는 `ui/admin_demo` |
| entry point | `ropi-admin-demo` |
| shell | `AdminShell` 스타일 재사용, navigation은 데모 페이지로 제한 |
| store | 페이지 간 signal/callback update가 가능한 in-memory demo store |
| production safety | demo-only 동작 때문에 Control Service RPC 계약을 변경하지 않음 |
| tracking | demo source와 test는 commit 대상. 생성 screenshot/export만 ignored 유지 |

테스트는 다음을 검증한다.

- console script가 `ropi-admin-demo`로 존재한다.
- demo source directory가 ignore되지 않는다.
- Control Service 없이 데모가 열린다.
- sidebar에는 홈, 작업 요청, 작업 모니터, 알림/로그만 있다.
- 작업 요청 submit 후 작업 모니터와 홈에 작업이 보인다.
- 데모 요청 생성 후 알림/로그에 한국어 event가 생긴다.
- 보이는 로봇명은 `ROPI 1`, `ROPI 2`, `ROPI 3`만 사용한다.
- 주요 UI 전면 text에는 `pinky`, `jetcobot`, `arm1`, `arm2`가 나오지 않는다.
- 한국어 표시값이 있는 raw enum은 주요 UI 전면 text에 나오지 않는다.
- 홈 운영 맵은 저장소의 PGM/YAML을 로드하고 marker 3개를 표시한다.
