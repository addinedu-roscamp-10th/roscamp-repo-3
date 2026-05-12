# GUI Design

## 1. Document Scope

This document defines the PyQt6 GUI design for the ROPI control system.

The current scope covers the administrator/control-operator UI and the visitor kiosk UI. Both UIs are based on PyQt6, but they are designed as separate product applications.

The administrator/control-operator UI has the following goals.

- Allow trained control operators or administrators to request robot tasks and quickly check task progress.
- Allow control operators to track robots, tasks, events, inventory, and resident information within a single screen flow.
- Display delivery, patrol, guide, and follow scenarios consistently from a common `task` perspective.
- Separate scenario-specific details into each detail panel.
- When a failure occurs, the cause must be traceable using `task_id`, `assigned_robot_id`, `reason_code`, and event logs.

Product-facing Admin UI copy must not describe this app as a caregiver console. A real caregiver-facing screen is a separate simplified workflow with plain Korean labels and lower information density. The implementation may keep package names such as `caregiver` and payload fields such as `caregiver_id` for compatibility with the current Control Service and DB contract, but visible Admin UI labels should use `관리자`, `관제 운영자`, or operation-oriented wording.

The visitor kiosk UI has the following goals.

- Allow visitors to register visits, find residents, request robot guidance, and call staff from the lobby.
- Guide visitors with visitor-facing status messages without exposing administrator-facing operational information or internal enums.
- Provide large buttons, short steps, and clear error-recovery flows for a touchscreen environment.

This document is a design specification, not a prompt document. When creating wireframes, each page section can be copied as page-specific requirements.

---

## 2. Current Implementation Baseline

### 2-1. Current UI Structure

The previous code had `LoginRoleWindow`, but under the product design baseline, the administrator app and visitor kiosk app are separated, so the role-selection window is removed.

The administrator app product entry flow is as follows.

```text
Admin App
-> CaregiverLoginWindow
-> CaregiverMainWindow
```

The visitor kiosk starts as a separate app.

```text
Kiosk App
-> KioskHomeWindow
```

`LoginRoleWindow` is not included in the product IA and must not remain in product code.
Even after logout from the administrator app, the app returns to the administrator login screen instead of the role-selection screen.
The visitor kiosk starts from the visitor home screen and does not reuse the administrator app login screen or role-selection screen.
When the visitor kiosk needs to end or reset a session, it returns to the kiosk home screen and does not open `LoginRoleWindow`.

The current main screens of `CaregiverMainWindow` are as follows.

| Screen | Current code location | Current state |
| --- | --- | --- |
| Home dashboard | `ui/admin_ui/main_window.py` | Server dashboard bundle query structure exists |
| Task request | `ui/utils/pages/caregiver/task_request_page.py` | Delivery/patrol requests have a server-integration structure; guide is excluded from the admin task request tab; follow is a disabled tab |
| Task monitor | `ui/utils/pages/caregiver/task_monitor_page.py` | Task snapshot/push reflection, patrol fall alert, evidence image, and resume UI exist |
| Coordinate/zone settings | Planned | DB-based zone and precision parking coordinate settings page |
| Inventory management | `ui/utils/pages/caregiver/inventory_management_page.py` | Server query/add integration exists |
| Resident information | `ui/utils/pages/caregiver/patient_info_page.py` | Server query integration exists |
| Alerts/errors | `ui/utils/pages/caregiver/alert_log_page.py` | Currently centered on mock data |
| Robot status | `ui/utils/pages/caregiver/robot_status_page.py` | Main sidebar entry structure exists; detailed data integration needs reinforcement |

### 2-2. Current Wireframe Review Baseline

The current `wireframes/stitch_carebot_operations_dashboard/` directory contains HTML/Tailwind wireframes and PNG screens for the administrator console.

The wireframes are used as reference material for colors, card layout, and page-level information density. However, the HTML app shell must not be ported directly to PyQt.

The normalization items identified during review are as follows.

| Item | Current wireframe state | Design reflection baseline |
| --- | --- | --- |
| Brand | Mixed use of `RoboCare OS`, `Admin Console`, and `Operational Console` | Unify product brand as `ROPI` |
| Top nav bar | `CONTROL SERVICE`, `DATABASE`, `ROS2`, `AI SERVER` nav repeated on each page | Remove global top nav; show only as status chips |
| Sidebar width | Mixed `280px` and `260px` | Administrator console baseline is fixed `260px` |
| Sidebar menu | Menu names/order differ slightly by page | Unify under the common sidebar menu from the information architecture |
| Header | Fixed/sticky topbars differ by page | Place title, subtitle, and status strip inside common `PageHeader` |
| Font | Some wireframes use Manrope/Inter | PyQt app uses Pretendard/Noto Sans KR baseline |
| Dark mode | Some HTML contains dark classes | Phase 1 administrator UI is designed only for light theme |
| Duplicate pages | `task_request` and `task_request_ui_sync` are duplicated | Use `task_request_ui_sync` as the task request baseline |
| Unsafe action | `Manual Override` exposed without real functionality | Remove or disable until backend safety functionality exists |

### 2-3. Current Scenario Integration State

The GUI design handles all scenarios through a common task model. However, the implementation completion level differs by scenario, so the wireframes and implementation priority must distinguish these states.

| Scenario | Target robot | Current integration level | UI design baseline |
| --- | --- | --- | --- |
| Delivery | `pinky2`, `jetcobot1`, `jetcobot2` | Control server integration succeeded | Display actual request/status/cancel/result details |
| Patrol | `pinky3` | Phase 1 server integration and related UI implementation in progress | Create tasks, track status, and connect fall-response UI to the task monitor |
| Guide | `pinky1` | Kiosk guide flow partially implemented; server integration needs reinforcement | Complete the task structure connected to the visitor kiosk. Do not expose in the administrator task request tab |
| Follow | Undecided or extension | Shown only as a disabled tab on the administrator task request screen | Excluded from the phase 1 completion scope |

The flows treated as actually integrated in phase 1 are delivery and patrol.

The administrator task request screen does not expose the guide tab in phase 1. Guide is handled separately in the visitor kiosk flow. Follow remains only as a disabled tab to show future extensibility, and the tab label must not include wording such as `Coming soon`.

- Delivery task creation is sent to the server through `DeliveryRequestRemoteService.create_delivery_task()`.
- The server response must include `result_code`, `result_message`, `reason_code`, `task_id`, `task_status`, and `assigned_robot_id`.
- In the current phase 1, delivery tasks are immediately assigned to `pinky2`.
- After task creation, the actual robot workflow proceeds as a background task in the Control Service.
- Task completion, failure, and cancellation results are critical writes to the server and DB.
- Patrol task creation is sent to the server through `DeliveryRequestRemoteService.create_patrol_task()`.
- The task monitor reflects task snapshots and task event pushes, and includes patrol fall alerts, evidence image query, and resume UI after on-site action.
- Actual ROS/DB/AI integration verification for patrol is performed in the server-side runtime environment that owns Control Service, ROS adapters, and DB connectivity.

The overall screen structure in this document is not designed only for delivery. Delivery-specific fields are placed only in the `Delivery` form of task request and the `Delivery detail` area of task detail.

### 2-4. UI/API Field Name Baseline

The standard field names used in the new UI design follow the table below.

| Concept | UI/API standard name | Note |
| --- | --- | --- |
| Task ID | `task_id` | Numeric `u64`; displayed as an integer on screen |
| Request owner ID | `caregiver_id` | Numeric. Current DB/API compatibility field; display as operator/request owner identity on screen |
| Resident ID | `member_id` | Numeric |
| Visitor ID | `visitor_id` | Numeric |
| Item ID | `item_id` | Numeric |
| Primary execution robot | `assigned_robot_id` | Example: `pinky2` |
| Task status | `task_status` | Example: `WAITING_DISPATCH`, `RUNNING`, `COMPLETED` |
| Task phase | `phase` | Internal scenario step |
| Failure/rejection reason | `reason_code` | Displayed together with a human-readable message |

The new UI does not use `assigned_pinky_id`. Names such as `pinky_id` may appear only inside robot-local or ROS adapter internals.

---

## 3. Users and Operational Context

### 3-1. Primary Users

The primary user of the administrator/control-operator UI is a trained control operator or facility administrator, not a regular caregiver.

Operators are not robot engineers, but they can handle denser operational information than a caregiver-facing quick request screen. They must be able to quickly understand the following information.

- Which robots are currently available
- Whether my request has been accepted
- How far the task has progressed
- If the task failed, why it failed
- Whether the task can be canceled
- Whether there is a robot or server connection issue

The regular caregiver-facing UI is separated from this Admin UI and should only expose simplified request/status wording such as item, destination, current progress, urgent alert, and staff action.

Control operators use the Admin UI and see diagnostic information.

- Robot-level status and recent heartbeat
- Task workflow status
- Event logs and `reason_code`
- DB, Control Service, ROS2, and AI Server connection status

### 3-2. Operating Environment

The administrator UI is based on a PyQt6 app that runs on a desktop or laptop.

- Baseline resolution: 1280x800
- Recommended resolution: 1440x900 or higher
- On wide screens, dashboard information density is increased.
- On narrow screens, a scroll area is used to prevent the left sidebar and main cards from overlapping.

---

## 4. Information Architecture

The recommended sidebar structure for the administrator/control-operator UI is as follows.

| Menu | Purpose | Phase 1 priority |
| --- | --- | --- |
| Home | Check overall operational status and recent tasks | High |
| Task request | Create delivery and patrol tasks; display disabled follow tab | High |
| Task monitor | Track pending/in-progress/completed/failed tasks and cancel tasks | High |
| Coordinate/zone settings | DB-based zones, precision parking coordinates, and destination coordinates | High |
| Robot status | Check robot-level connection, battery, location, and current task | Medium |
| Inventory management | Manage deliverable items and quantities | High |
| Resident information | Search residents, preferences/dislikes, and recent events | Medium |
| Alerts/logs | Track operational events, errors, and failure reasons | Medium |

The current implementation is centered on Home, Task Request, Inventory Management, Resident Information, and Alerts/Errors. In the design, it is better to separate `Task monitor` and `Robot status`. The reason is that the home dashboard is for quick summary, while fault analysis and cancellation processing require more detailed task/robot-level screens.

To reduce phase 1 implementation burden, `Task monitor` may start as a detailed version of the home dashboard. However, it is advantageous to keep it as a separate page in the wireframes and design for later expansion.

The standalone System Status page is not included in the phase 1 sidebar. Service health is summarized on Home, robot connectivity is handled on Robot Status, and failures are investigated through Alerts/logs.

---

## 5. Design System

### 5-1. Visual Direction

The administrator UI should be closer to a calm operational control console than a warm caregiving service interface.

However, because it is used in a medical/care facility, it should avoid an excessively dark or aggressive control-room appearance. Keep the background bright and stable, while using sufficient contrast in status chips and task cards so operational priority is visible immediately.

### 5-2. Color Tokens

| Token | Color | Use |
| --- | --- | --- |
| `color-bg` | `#F5F7FA` | Entire app background |
| `color-surface` | `#FFFFFF` | Cards, forms, table areas |
| `color-surface-soft` | `#EEF4F7` | Sidebar, secondary panels |
| `color-text-primary` | `#16202A` | Primary text |
| `color-text-secondary` | `#5B6775` | Description and secondary text |
| `color-border` | `#D8E0E8` | Card/table borders |
| `color-primary` | `#005C55` | Primary actions and current selected menu |
| `color-primary-strong` | `#004C46` | Primary button hover/pressed |
| `color-primary-accent` | `#0F766E` | Status emphasis and secondary teal accent |
| `color-action-blue` | `#2563EB` | In-progress and informational actions |
| `color-warning` | `#F59E0B` | Delay and caution |
| `color-danger` | `#DC2626` | Failure, cancellation, emergency |
| `color-success` | `#16A34A` | Complete and normal |
| `color-muted` | `#94A3B8` | Disabled and waiting |

### 5-3. Fonts

Recommended fonts are as follows.

| Use | Font |
| --- | --- |
| Default Korean UI | Pretendard |
| Korean fallback UI | Noto Sans KR |
| Numbers/KPI | Pretendard SemiBold or a bold weight from the same family |

In a PyQt6 environment, installed fonts may vary by local machine. Therefore, QSS should specify fonts in this order: `"Pretendard", "Noto Sans KR", sans-serif`.

PyQt6 is not a browser, so it must not rely on CDN-based web fonts or `@font-face` like web CSS. The recommended approach is to include `.ttf` or `.otf` font files in app assets and load them at app startup using `QFontDatabase.addApplicationFont()`.

Recommended policy:

| Item | Baseline |
| --- | --- |
| Default method | Include Pretendard font files in app assets |
| Loading method | `QFontDatabase.addApplicationFont()` |
| Fallback | System-installed `Noto Sans KR`, then Qt default sans-serif |
| Deployment assumption | Do not assume the target machine necessarily has the font installed |

### 5-4. Common Components

| Component | Purpose |
| --- | --- |
| `SidebarButton` | Left menu navigation |
| `PageHeader` | Display page title, description, and primary actions. System status strip appears only on screens where explicitly requested |
| `PageTimeCard` | Display the current clock/date and optional last-update/status/actions in the header area |
| `SystemStatusStrip` | Display status chips for Control Service, DB, ROS2, and AI Server |
| `KeyValueRow` | Display detail data as a compact label badge and separated value instead of raw `key: value` text |
| `KpiCard` | Display numeric operational metrics |
| `StatusChip` | Display status with color and text |
| `RobotCard` | Summarize per-robot current status |
| `TaskCard` | Display task ID, status, robot, destination, and cancellability |
| `FlowColumn` | Kanban column by task status |
| `DataTable` | Display inventory, logs, robots, and task lists |
| `FormCard` | Group input forms |
| `ResultPanel` | Display request results, failure reason, and next action |
| `EmptyState` | Empty data guidance |
| `LoadingState` | Server request-in-progress state |
| `ErrorState` | Network/server/validation failure state |

### 5-5. Status Chip Baseline

| Status | Color | Display examples |
| --- | --- | --- |
| Normal | Green | `Normal`, `Connected`, `Completed` |
| In progress | Blue | `In progress`, `Moving`, `Processing request` |
| Waiting | Slate/Gray | `Waiting`, `Unassigned`, `Preparing` |
| Caution | Amber | `Delayed`, `Low stock`, `Waiting for response` |
| Failed | Red | `Failed`, `Disconnected`, `Cancel failed` |
| Disabled | Muted | `Unsupported`, `Preparing` |

Do not distinguish status by color alone. Use chip text and an icon or short explanation together.

---

## 6. Common Layout

### 6-1. App Frame

The administrator app uses the following structure as its baseline.

No global top navigation bar is used. The left sidebar handles page navigation. Service connection status is not shown by default on every page; it is shown as `SystemStatusStrip` only on screens that provide real status context, such as the Home dashboard health block.

```text
+---------------------------------------------------------------+
| Sidebar | PageHeader: title / subtitle / optional status      |
|         |-----------------------------------------------------|
|         | Main Content                                        |
|         |                                                     |
|         |                                                     |
+---------------------------------------------------------------+
```

Recommended sizes:

| Area | Baseline |
| --- | --- |
| Sidebar width | Fixed 240px baseline |
| PageHeader height | 72-96px; page-specific primary actions allowed |
| Page horizontal margin | 24px |
| Card radius | 16-20px |
| Card padding | 18-24px |
| Primary button height | 44-48px |
| Table row height | 40-48px |

### 6-2. PageHeader and SystemStatusStrip

`PageHeader` is maintained on every administrator screen. However, it is not an independent top nav bar; it is placed as the first common component inside the page content area.

Visually, `PageHeader` uses a lightweight hero/card treatment across administrator pages: tinted surface, left accent, title, and subtitle. It does not include an eyebrow label above the title. This keeps page titles from looking like raw text while preserving a single shared shell component.

Display elements:

- Page title
- Page description
- Shared `PageTimeCard` beside the header: current time/date on every administrator page, optional last-updated text, status text, and page actions
- Page-specific primary actions, such as refresh, export, or reset filters
- Optional `SystemStatusStrip`: status chips for Control Service, DB, ROS2, and AI Server
- Current logged-in user name and `caregiver_id`, displayed in the right auxiliary area when needed
- Last updated time

`PageTimeCard` must use a stable width and height across administrator pages. Different page actions such as refresh, save, discard, and stream reconnect are placed in a reserved action row inside the card instead of being stacked vertically. Optional status and last-updated text reserve their slots even when empty, so entering another page or changing a page's available actions does not change the header height. Header action buttons must keep enough vertical height for the shared button padding and must not clip Korean labels. The card must also reserve enough vertical slack below the action row so the lower rounded corners are not clipped; code-owned fixed button geometry should not be combined with conflicting QSS min/max height rules.

`SystemStatusStrip` is not a default display element of `PageHeader`. If `checking` status is repeatedly exposed on screens without real status-query integration, operators may misunderstand it as a fault or delay. Therefore, Home must update the strip from Control Service heartbeat data instead of leaving default `checking` chips visible.

Service status chips are not nav items. If click navigation is needed, use only an auxiliary action to navigate to the alerts/logs page.

When status is abnormal, display the chip in amber/red and, if needed, allow movement to the alerts/logs page.

### 6-2-1. Prohibited Administrator Shell Elements

When converting wireframes to PyQt, the following elements must not be ported directly.

| Prohibited element | Reason |
| --- | --- |
| `RoboCare OS` brand | Product name is unified as `ROPI` |
| `Operational Console` global title | Duplicates the page title and is not the product name |
| `CONTROL SERVICE / DATABASE / ROS2 / AI SERVER` top nav | These are status information, not navigation |
| Page-level duplicate sidebar implementations | PyQt uses a single shell sidebar |
| Page-level fixed/sticky topbar | Does not fit PyQt layout well and creates duplicate status |
| Dark mode class | Phase 1 light theme baseline |
| Functionless `Manual Override` | Safety feature; do not expose before backend integration |

### 6-2-2. Sidebar Unification Baseline

The administrator sidebar uses the same component on every page.

| Item | Baseline |
| --- | --- |
| Brand | `ROPI` |
| Subtitle | `Administrator Console` or omitted |
| Width | 260px |
| Background | `color-surface-soft` |
| Active menu | `color-primary` left indicator or filled background |
| Bottom area | Logout or current user info only |

The menu order is fixed as follows.

```text
Home
Task request
Task monitor
Coordinate/zone settings
Robot status
Inventory management
Resident information
Alerts/logs
```

Generic settings menus such as `Settings` and `Support` are excluded from the phase 1 product menu. However, DB-based coordinate and zone settings directly needed to execute delivery/patrol tasks are provided as a separate business page named `Coordinate/zone settings`. The standalone system status page is also excluded from the phase 1 product menu because its health checks overlap with Home, Robot status, and Alerts/logs.

### 6-3. PyQt Size Responsiveness Policy

PyQt6 does not declare breakpoint classes like Tailwind CSS. Window-size responsiveness is designed around the Qt layout system.

Usage baseline:

| Technique | Purpose |
| --- | --- |
| `QVBoxLayout`, `QHBoxLayout`, `QGridLayout` | Basic layout |
| `QSizePolicy.Expanding` | Cards, tables, and boards that should fill remaining space |
| `QSizePolicy.Fixed` | Sidebar, status chips, fixed buttons |
| Layout stretch factor | Control left/right panel ratios |
| `minimumSize`, `minimumWidth` | Prevent screens from collapsing excessively |
| `QScrollArea` | Provide vertical scrolling on small screens |
| `resizeEvent()` | Switch compact, regular, and wide layouts |

Recommended breakpoints:

| Window width | Layout baseline |
| --- | --- |
| `< 1280px` | Compact. Main content uses one column; long tables/boards use scrolling |
| `1280-1599px` | Regular. Default administrator layout, sidebar + body in 1-2 columns |
| `>= 1600px` | Wide. Dashboard cards and detail panels can be shown simultaneously |

Do not stretch every widget by ratio indiscriminately. KPI cards, status chips, and buttons should have minimum/maximum sizes. Data-heavy areas such as tables, task boards, and log lists should expand first.

### 6-4. Data Refresh Policy

Because the interface specification includes custom TCP session push, operational data is designed push-first. Polling is not the default replacement for push; it is a supplementary strategy for the initial snapshot, reconnect correction, and phase 1 fallback.

Recommended refresh method:

| Data | Recommended refresh method |
| --- | --- |
| Task status changes | TCP session push first; snapshot query after reconnect |
| Task feedback | TCP session push first |
| Cancellation result | TCP session push first; request response only shows acceptance |
| Robot status | IF-COM-003 `PINKY_UPDATED` / `ARM_UPDATED` push first; 1-2 second snapshot polling only as a fallback while the page is visible |
| Alerts/operational events | Push first; query when entering the logs page |
| Home KPI/task board | Initial snapshot query + subsequent IF-COM-003 push-triggered refresh/reflection |
| Task monitor | Initial query + subsequent push reflection |
| Inventory | Query on entry + manual refresh |
| Resident information | Query on search |
| System health | Heartbeat + manual recheck; fallback polling when needed |

Server requests must not block the PyQt UI thread. Use a `QThread` worker or asynchronous bridge, as in the current structure, to prevent UI freezes.

When implementing push-based UI, the persistent TCP session should be read outside the UI thread, and delivered to the main thread through Qt signals. Response frames and push frames must be demuxed, and after reconnecting, the latest snapshot should be queried again to correct possible missed events.

The administrator shell owns one shared IF-COM-003 subscription for dashboard-oriented pages. It fans out event objects by enumerating registered shell pages that expose `apply_stream_event(event)` instead of maintaining a hard-coded page tuple. Pages that own an independent event stream, such as the Task Monitor snapshot-handoff subscription, explicitly opt out of the shared administrator fan-out.

Admin UI pages should use shared stream refresh helpers for common event-loop behavior instead of duplicating timer state per page. The common helper scope is intentionally narrow:

- debounce repeated stream-triggered refresh requests into one callback
- defer visible-page refresh work while a page is hidden and resume once shown
- keep stream auto-reconnect request state separate from the page's worker-thread lifecycle

Page-specific event patching remains inside each page because payload contracts and render targets differ.

---

## 7. Page Design

### 7-1. Administrator Authentication Screen

#### Purpose

Log in to the administrator/control-operator app and store the current user identifier in the session.

#### Screen Composition

| Area | Components |
| --- | --- |
| Brand area | `ROPI`, administrator/control-operator console title, administrator app description |
| Login card | Administrator/control-operator login title, ID, password |
| Actions | Login button. Do not display role selection, visitor entry, or back buttons |
| Server status | Small chip for Control Service connection status |
| State | Inline display for authentication failure, server error, and request in progress |

#### Validation Rules

- ID must not be empty.
- Password must not be empty.
- When the server response fails, keep the input values and display an error message.
- On successful login, use `current_user.user_id` as the request owner ID. It is still mapped to `caregiver_id` in the current Control Service payload for compatibility.
- The Enter key must execute the login request.
- The administrator app authentication screen currently sends the login request with `role=caregiver` for compatibility, but visible copy must say administrator/control operator instead of caregiver.
- Control Service status checks must run outside the UI thread so they do not block input or rendering on the login screen.

#### Error Message Baseline

| Error | Message baseline |
| --- | --- |
| Missing input | `Enter your ID and password.` |
| Authentication failure | `The ID or password is incorrect.` |
| Server connection failure | `Cannot connect to the control server.` |

---

### 7-2. Home Dashboard

#### Purpose

The home dashboard is the first screen where an administrator/control operator can understand the current operational state within 10 seconds.

The home dashboard is a summary screen, not a detailed analysis screen. However, task cancellation and failure recognition must still be possible from Home.

#### Key Questions

The home dashboard must answer the following questions.

- How many robots are currently available?
- Are there tasks in progress?
- Are waiting tasks accumulating?
- Were there recent failures or cancellations?
- Which robot is performing which task?
- Are robot/task states abnormal enough to require moving to the system status screen?

#### Screen Composition

| Area | Components |
| --- | --- |
| Page Header | Home-only hero panel with title `Operations Dashboard`, description, heartbeat-based system status chips, and a separate manual refresh/time card |
| KPI Row | Available robots, waiting tasks, in-progress tasks, warnings/errors |
| Operations Map + Task Flow Row | DB-backed operations map on the left and the task flow board on the right |
| Robot Board | Per-robot status cards |
| Task Flow Board | Task Kanban by status |
| Recent Timeline | Recent events/task changes |

#### KPI Cards

| Card | Display data |
| --- | --- |
| Available robots | Available robot count and total robot count |
| Waiting tasks | Count of `WAITING_DISPATCH` or `READY` tasks |
| In-progress tasks | Count of `RUNNING`, `ASSIGNED`, `IN_PROGRESS`, and related statuses |
| Warnings/errors | Warning/error count in the last 24 hours |

KPI cards display the number most prominently, with a short line below that explains the current operational meaning rather than prior-day/recent changes. Each card uses a semantic tone/accent so operators can scan state quickly: available robots use teal/green when non-zero, waiting tasks use amber when action is needed, in-progress tasks use green/blue when active, and warnings/errors use red when non-zero. Neutral cards remain low contrast.

The Home header is not a plain text block. It uses the shared lightweight hero/card header with a subtle background tint and left accent. Do not add a separate eyebrow label above the title, and do not add a heavy card-within-card hierarchy.

Transient operation alerts, such as cancel failure, are not rendered inside the time/refresh card. They are shown as a full-width inline banner below the top row and above the KPI row. This prevents a long error message from increasing the top row height and visually stretching the page title/description area.

#### Loading and Refresh Behavior

The heartbeat-based system status chips in the Home header refresh independently from the heavier dashboard bundle. While Home is visible, the UI should run a lightweight periodic heartbeat refresh for the header chips so `ROS2`, `DB`, and `AI` status changes are reflected without requiring a manual dashboard refresh or a task/robot stream event.

The lightweight heartbeat refresh must not reload the KPI row, robot board, task flow board, or timeline. Those areas continue to update through explicit dashboard loads and IF-COM-003 stream-triggered dashboard convergence.

IF-COM-003 stream-triggered dashboard convergence should run only when Home is visible or should be deferred until Home becomes visible. Hidden-page stream events must not continuously run full dashboard bundle reloads in the background.

High-frequency robot status events should not reload the full dashboard bundle when a Home snapshot is already rendered. `PINKY_UPDATED` and `ARM_UPDATED` should patch the matching Robot Board card from the event payload and update the Home last-refresh indicator. For `TASK_UPDATED`, Home may patch an existing task card or add a new task card, then recompute the waiting/running task KPI from the rendered task flow, when an initial task-flow snapshot exists and the event payload includes the minimum renderable task identity/status fields. `ALERT_CREATED` / `FALL_ALERT_CREATED`, including the same alert object carried as `TASK_UPDATED.fall_alert`, should increment the Home warning/error KPI once per alert and prepend one recent timeline row when an initial Home snapshot already exists. A full dashboard reload remains the convergence fallback when no prior snapshot exists, after reconnect, or when the event payload is insufficient to build a local patch.

#### Operations Map

Home displays an operations map in the main dashboard area, visually matching the presentation demo's map-and-flow split but using live Control Service data only. The map loads DB-managed `map_profile` and map assets through `coordinate_config` RPC, not bundled demo assets or hard-coded sample data. Robot markers are derived from the dashboard bundle's `robots[*].current_pose`; robots without a current pose or whose pose belongs to a different selected map are not plotted.

The map is a quick operational context panel, not the full coordinate editor. It should show the selected map ID, plotted robot count, and a concise loading/error state. If map assets are unavailable, Home keeps the rest of the dashboard usable and shows an operator-facing map status message.

Example:

```text
In-progress tasks
2
1 delivery, 1 patrol
```

#### Robot Board

Robot cards display the following fields.

| Field | Description |
| --- | --- |
| `robot_id` | Example: `pinky1`, `pinky2`, `pinky3`, `jetcobot1`, `jetcobot2` |
| `robot_type` | Hardware category such as mobile robot or arm robot |
| `capabilities` | Supported scheduler capabilities such as DELIVERY, PATROL, GUIDE, MANIPULATION |
| `connection_status` | ONLINE, OFFLINE, DEGRADED |
| `battery_percent` | Displayed for mobile robots |
| `current_location` | `-` if unknown |
| `current_task_id` | Displayed if a current task exists |
| `last_seen_at` | Last status received time |

Robot cards must not treat a robot ID as a fixed scenario role. Delivery and patrol mobile robots are decided by scheduling/current task assignment. Fixed station robots, such as delivery pickup and destination arms, are described by station assignment data.

Robot cards use the same two-column label/value pattern as Home task cards. The header shows only the unique robot name/ID (`robot_id`), for example `pinky2` or `jetcobot1`; it must not concatenate type/display-name/ID into titles such as `ARM jetcobot1`, `Jetcobot · jetcobot1`, or `Pinky Pro · pinky2`. The connection status chip stays on the right. Field keys such as type, capability, current task, location, battery, and last received time are visually separated as compact badges. `ONLINE`, `OFFLINE`, and `DEGRADED` cards use different tones; offline cards are muted and emphasize why the status is stale.

Robot online state is based on recent runtime heartbeat, not on seeded or stale runtime rows. If `last_seen_at` is missing or older than the Control Service freshness threshold, display `OFFLINE`. `current_location` must not fall back to IP address. Until zone mapping is implemented, pose data may be shown as a coordinate label and missing pose is shown as unknown. Time values must be formatted for operators, for example `2026-05-03 12:00:00` rather than raw ISO text with `T`.

#### Task Flow Board

On Home, the task flow board is a compact one-column list placed to the right of the operations map. It displays the board title directly above the scroll area and does not add a separate explanatory subtitle such as "shows requested tasks by status."

The board must continue to render the real DB-backed `flow_data` from `caregiver.get_dashboard_bundle`; it must not use presentation-demo fixtures. Home flattens the server-provided status buckets into a single operator scan list, prioritizing canceling/running/assigned/waiting work before recently completed or failed work. KPI counts remain responsible for status distribution. Detailed status-by-status inspection belongs on Task Monitor, not Home.

The board should have its own scroll area so many task cards do not stretch the whole dashboard. The flattened list must still use the same waiting/running definitions as the KPI row; for example `READY` is a waiting task, not an assigned task.

Task card display fields:

| Field | Description |
| --- | --- |
| `task_id` | Display most prominently |
| `task_type` | DELIVERY, PATROL, GUIDE, FOLLOW |
| `priority` | NORMAL, URGENT, HIGHEST |
| `assigned_robot_id` | Assigned robot |
| `phase` | Current phase |
| `destination_label` | Human-readable destination |
| `feedback_summary` | Recent feedback summary |
| `reason_code` | Display when a failure/rejection/cancellation reason exists |
| `cancellable` | Determines whether to expose the cancel button |

Task cards must not render a single raw multi-line string such as `#6 DELIVERY / WAITING_DISPATCH`. The card header displays a human-readable title like `Task #6 · Delivery` and a separate status chip such as `Waiting for dispatch`. The body uses short label/value rows for robot, phase, destination, feedback, and reason. Raw `result_message` or exception text is shown only as a muted detail line after a summarized operator message.

Home uses compact Korean labels for task type, task status, and phase. Unknown codes may be shown as fallback text, but common phase 1 codes such as `DELIVERY`, `PATROL`, `WAITING_DISPATCH`, `RUNNING`, `MOVE_TO_PICKUP`, `ROS_SERVICE_UNAVAILABLE`, and ROS IPC failures must be mapped to operator-readable text.

The cancel button is enabled only when `cancellable=true` and the status is cancellable. In `CANCEL_REQUESTED` status, disable the button and display `Canceling`.

Cancel results are displayed as a structured inline banner, not as raw `result_code / reason_code: message` text. The banner contains a title (`Cancel requested` or `Cancel failed`), an operator summary, and an optional muted detail line. In local development without ROS, ROS bridge connection failures are summarized as `ROS bridge is not connected` while the raw transport error remains available only in the detail line.

#### Recent Timeline

The timeline shows recent operational flow.

Display fields:

| Field | Description |
| --- | --- |
| `occurred_at` | Event occurrence time |
| `severity` | INFO, WARNING, ERROR, CRITICAL |
| `source_component` | UI, Control Service, ROS Adapter, DB Writer, etc. |
| `task_id` | Related task ID |
| `robot_id` | Related robot ID |
| `event_type` | Event type |
| `message` | Human-readable description |

On Home, show only the most recent 10-20 items. Full query is handled on the alerts/logs page.

---

### 7-3. Task Request Page

#### Purpose

This screen lets administrators/control operators create delivery and patrol tasks. Guide requests are excluded from the administrator task request screen and are handled in the visitor kiosk flow. Follow is outside the phase 1 completion scope, so it is shown only as a disabled tab without a submittable form.

The screen structure must clearly distinguish actually submittable scenarios from disabled expansion scenarios. Tab labels should display only `Item delivery`, `Patrol`, and `Follow`, and the `Follow` button should be disabled so operators do not misinterpret it as a selectable production feature.

#### Screen Composition

| Area | Components |
| --- | --- |
| Page Header | `Task Request`, description. System status strip is not shown by default on this screen |
| Scenario Tabs | Item delivery, Patrol, Follow. Follow is disabled |
| Main Form | Input form for the selected scenario |
| Side Panel | Request preview, real-time robot status, recent request result, notices |

#### Common Request Structure

Every scenario request has the following common fields.

| Field | Description |
| --- | --- |
| `task_type` | DELIVERY, PATROL |
| `caregiver_id` | Logged-in user |
| `priority` | NORMAL, URGENT, HIGHEST |
| `notes` | Request memo |
| `request_id` | UI request tracking ID |
| `idempotency_key` | Duplicate request prevention |

#### Delivery Request Form

The delivery request is the currently server-integrated form. In the UI, place it as one of the scenario tabs and clearly display that it is actually submittable.

Input fields:

| Field | UI element | Required | Description |
| --- | --- | --- | --- |
| `item_id` | Searchable combo box | Y | Item to deliver. Show operators only item name and stock; payload uses only numeric `item_id` |
| `quantity` | Number stepper or spin box | Y | Request quantity. Do not leave the default Qt gray arrow subcontrol as-is; cover it with the app-styled stepper |
| `destination_id` | Searchable combo box | Y | Example: `delivery_room_301`, `room_301`. In current phase 1, enable only destinations configured on the real server |
| `priority` | Segmented button | Y | Screen labels are `Normal`, `Urgent`, `Highest`; payload uses interface spec values `NORMAL`, `URGENT`, `HIGHEST` |
| `notes` | Low textarea | N | Request memo. Limit to about 72-88px for form balance, and use compact spacing of about 2px between label and textarea |

Row spacing in the task request form should remain tighter than general card spacing. In particular, grid row spacing between the `priority` segmented button and the `notes` textarea should be 6px or less, so priority and additional memo appear as one request-options group.

The left form card on the task request page must not forcibly fill the remaining screen height. Set the scroll/container height according to the actual selected form content so that a large empty card area does not appear below the button. Scrolling should become meaningful only when the form actually becomes longer than the screen.

Searchable combo box, field group, and priority segmented button controls must not be duplicated in each scenario form class. Implement them as common form-control helpers. Cross-dependencies such as a patrol form calling a private/static helper from a delivery form are prohibited.

Request payload generation, preview payload generation, and server response normalization must be separated into pure builder functions instead of being implemented directly inside QWidget. QWidget is responsible only for reading current input values, calling the builder, and displaying validation errors as inline status.

The task request page implementation is split by file into shell/page orchestration and scenario-specific forms. `task_request_page.py` is responsible only for page assembly, tab switching, and side panel connection; delivery/patrol forms and workers are managed in separate modules. The disabled follow tab does not create a submit form.

Task request option loading must not be named as a delivery-item-only loader. Shared queries such as item list, delivery destination, and patrol area should use a name and payload structure that represents overall task request options, such as `TaskRequestOptionsLoadWorker`.

Automatically set fields:

| Field | Setting method |
| --- | --- |
| `caregiver_id` | Logged-in user session |
| `request_id` | Request tracking ID generated by the UI |
| `idempotency_key` | Hidden field for duplicate request prevention |
| `assigned_robot_id` | In phase 1, server responds with `pinky2` |

#### Delivery Request Preview

Before sending, display the following in the right panel. Item and destination are synchronized from the selected values in the searchable combo boxes. Side-panel information should not be rendered as a `key: value` text list; use label/value rows and status chips. Keep the preview card in the same light card tone as the rest of the task request page; do not use a standalone dark card background.

```text
Requester: caregiver_id
Item: item_name
Quantity: quantity
Destination: destination label / destination_id
Priority: priority
```

Do not display `task_id` in the preview before the server has confirmed it.

The right panel includes a `Real-time robot status` card as a phase 1 placeholder. Before the real feedback stream is connected, display `assigned_robot_id`, `state`, `pose`, `destination_id`, and a map placeholder, and update only the available fields when a task is created or the preview changes.

After the IF-COM-003 event stream is connected, the Task Request page shell must forward `TASK_UPDATED` and `ACTION_FEEDBACK_UPDATED` events to the side panel. The recent request result and real-time robot status cards should update for the current task without requiring page navigation or a manual refresh.

Do not add separate descriptive copy to the `Request preview`, `Real-time robot status`, and `Recent request result` cards. Use only card titles and row labels to communicate meaning. Payload field names remain in internal tests/integration contracts, but the screen should prioritize operator-readable labels such as `Requester`, `Item`, `Quantity`, `Destination`, `Priority`, `Robot`, `Status`, and `Location`.

The Side Panel is not one giant QWidget; it is a composition of card components. `RequestPreviewCard`, `RobotStatusCard`, `RequestResultCard`, and `NoticeCard` each own their labels and update responsibilities. `TaskRequestSidePanel` handles only card assembly and scenario-specific adapter calls.

#### Validation Rules

| Condition | UI behavior |
| --- | --- |
| No item selected | Display `Select an item.` |
| Quantity is 0 or below | Display `Quantity must be at least 1.` |
| Out of stock | Display warning and disable request button or require confirmation |
| No destination selected | Display `Select a destination.` |
| Server connection failure | Disable request button or display error |

#### Request Result Panel

The delivery request response displays the following fields.

| Field | Display method |
| --- | --- |
| `result_code` | Success/rejection status chip |
| `result_message` | Human-readable message |
| `reason_code` | Cause code when rejected/failed |
| `task_id` | Display prominently on success |
| `task_status` | Example: `WAITING_DISPATCH` |
| `assigned_robot_id` | Example: `pinky2` |
| `cancellable` | Determines cancel button enablement. If absent, fall back using `task_status` |

The `Recent request result` card on the task request screen includes a cancel button for the delivery task. The button is enabled only when `task_id` exists and `cancellable=true`, or when the status is one of `WAITING`, `WAITING_DISPATCH`, `READY`, `ASSIGNED`, or `RUNNING`. For `CANCEL_REQUESTED`, `CANCELLING`, `PREEMPTING`, `CANCELLED`, `COMPLETED`, and `FAILED`, disable it. Also prevent duplicate clicks while a cancel request is being sent.

Cancel responses are displayed in the same card. That is, the `IF-COM-002` response fields `result_code`, `result_message`, `reason_code`, `task_id`, `task_status`, `assigned_robot_id`, and `cancel_requested` are reflected in the existing request-result rows.

Success example:

```text
The task has been accepted.
Task number: 1001
Status: WAITING_DISPATCH
Assigned robot: pinky2
```

Rejection example:

```text
The task request was rejected.
reason_code: OUT_OF_STOCK
Message: The requested quantity is greater than current stock.
```

#### Patrol Request Tab

The patrol tab is designed around `IF-PAT-001 Create Patrol Task`. Unlike delivery, the task request form does not directly create waypoints or paths. The form selects a patrol area from the `patrol_area` table, and the Control Service interprets `patrol_area_id` as a server-managed patrol-path snapshot, then confirms `patrol_area_revision` and the actual `nav_msgs/Path`. Patrol waypoint/path editing belongs to the separate coordinate/zone settings page.

In phase 1, place the patrol tab inside the same task request screen as the delivery tab, but switch the input form and request preview/creation result panel to match the patrol scenario.

#### Patrol Screen Responsibility Separation

The patrol UI separates **request creation** from **in-progress task handling**.

| Screen/area | Responsibility | Included items |
| --- | --- | --- |
| Patrol request tab | Create new patrol task | Patrol area selection, priority, request memo preview, request submit, creation result |
| Task monitor detail panel | Handle the created task's progress and response actions | Task status, waypoint progress, robot feedback, fall alert, view fall photo, resume/stop |
| Fall photo dialog | Check evidence image | Image from `IF-PAT-007`, detection metadata, expired/missing errors |
| Patrol resume modal | Resume after on-site action audit input | `member_id`, `action_memo`, resume submit |

Do not put `WAITING_FALL_RESPONSE` response UI directly inside the patrol request tab. The request tab is an input screen before a task is created; fall response is an action on an already-created and running task.

For MVP, rather than creating a separate `Patrol Status` page, it is better to extend the existing `Task Monitor` detail panel when a patrol task is selected. If later multiple patrol tasks must be controlled simultaneously or map-based monitoring is needed, separate it into a dedicated `Patrol Status` page.

Input fields:

| Field | UI element | Required | Description |
| --- | --- | --- | --- |
| `patrol_area_id` | Searchable combo box | Y | Patrol area ID. Prefer the area name for display text, and show the area ID only as secondary text when needed |
| `patrol_area_name` | Selected result display | N | Human-readable area name from server/settings. Used only for preview, not payload |
| `map_id`, `waypoint_count`, `path_frame_id` | Not displayed in the patrol request form | N | Technical information for validating DB patrol path settings. Handled in the separate coordinate/zone settings page, not the regular caregiver request UI |
| `priority` | Segmented button | Y | Screen labels are `Normal`, `Urgent`, `Highest`; payload uses `NORMAL`, `URGENT`, `HIGHEST` |
| `notes` | Low textarea | N | Patrol request memo. Since it is not in the PAT-001 payload, in phase 1 it is kept only for UI preview/logging, or not included in payload until the server spec is extended |

Automatically set fields:

| Field | Setting method |
| --- | --- |
| `request_id` | Request tracking ID generated by the UI |
| `caregiver_id` | Logged-in user session |
| `idempotency_key` | Hidden field for duplicate request prevention |
| `assigned_robot_id` | Do not create it from a UI constant or patrol area option. Display `task.assigned_robot_id` from the PAT-001 server response or task update |

PAT-001 request payload:

```json
{
  "request_id": "req_patrol_001",
  "caregiver_id": 1,
  "patrol_area_id": "patrol_ward_night_01",
  "priority": "NORMAL",
  "idempotency_key": "idem_patrol_001"
}
```

Fields to display in the right result panel from the PAT-001 response:

| Field | Display method |
| --- | --- |
| `result_code` | Success/rejection status chip |
| `result_message` | Human-readable message |
| `reason_code` | Cause code when rejected/failed |
| `task_id` | Display prominently on success |
| `task_status` | Example: `WAITING_DISPATCH` |
| `assigned_robot_id` | Example: `pinky3` |
| `patrol_area_id` | Confirmed area ID |
| `patrol_area_name` | Confirmed area name |
| `patrol_area_revision` | Area revision fixed at creation time |

Rejection reason codes should be displayed with messages so the operator can act immediately.

| `reason_code` | UI display intent |
| --- | --- |
| `REQUESTER_NOT_AUTHORIZED` | Authorization issue. Guide the operator to check login account/role |
| `PATROL_AREA_ID_INVALID` | UI selected value or setting error |
| `PRIORITY_INVALID` | Priority code mapping error |
| `PATROL_AREA_NOT_FOUND` | Missing area setting |
| `PATROL_AREA_DISABLED` | Disabled area selected |
| `PATROL_AREA_OUT_OF_SCHEDULE` | Patrol is unavailable under the current time policy |
| `PATROL_PATH_CONFIG_MISSING` | Area exists but waypoint/path settings are missing |
| `NO_ELIGIBLE_PINKY` | No Pinky available for patrol |
| `PATROL_PATH_SERVICE_UNAVAILABLE` | Path creation/navigation setting or related service unavailable |

#### Patrol Request Preview

Before sending, the right panel's `Request preview` card displays the selected patrol area and request payload baseline fields.

| Row label | Display value |
| --- | --- |
| Requester | `caregiver_id` |
| Patrol area | `patrol_area_name` |
| Area ID | `patrol_area_id` |
| Priority | English priority chip |

Do not display server-confirmed fields such as `task_id` or `patrol_area_revision` in the preview before submission. Revision is shown in the result panel after response.

Do not expose `map_id`, waypoint count, or frame in the patrol request form. These values are not inputs the requester must decide; they are settings used by the server to interpret the patrol area as an actual `nav_msgs/Path`. If an editing/validation UI is needed, provide it in the coordinate/zone settings page, not in the task request screen.

#### Patrol/Follow Tab State

The current phase 1 implementation state is represented as follows.

| Tab | Expression |
| --- | --- |
| Patrol | Provide a PAT-001-based area selection form, request preview, creation result, and fall-response UI in the task monitor. Actual DB/ROS/AI verification is performed in the server-side runtime environment |
| Follow | Display the tab label as `Follow` but disable it. Since it is not included in the phase 1 administrator UI completion scope, do not create a submit form, coming-soon text, or server request button |

Future scenario-specific forms expand around the following structure.

| Scenario | Main input fields | Note |
| --- | --- | --- |
| Patrol | `patrol_area_id`, `priority`, `notes` | Robot assignment is not a patrol area attribute; it is the result of server task creation/scheduling. `patrol_area_name` and `patrol_area_revision` are response/display fields |
| Guide | `member_id`, `visitor_id`, `start_location_id`, `destination_id`, `priority`, `notes` | Connected to kiosk guide request |
| Follow | `target_caregiver_id`, `follow_mode`, `start_location_id`, `priority`, `notes` | In phase 1 administrator UI, only the disabled tab is provided and form implementation is deferred |

---

### 7-4. Task Monitor Page

#### Purpose

The task monitor is a screen for querying all tasks by status, type, robot, and time, and for performing cancellation or detailed inspection.

It is more detailed than the home dashboard and more task-centered than the alerts/logs page.

#### Screen Composition

| Area | Components |
| --- | --- |
| Filter bar | Task type, status, robot, period, search |
| Task table | Full task list |
| Detail panel | Details for the selected task |
| Action area | Cancel request, refresh, stream reconnect, view logs |

#### Task Table Fields

| Column | Description |
| --- | --- |
| `task_id` | Numeric ID |
| `task_type` | DELIVERY, PATROL, GUIDE, FOLLOW |
| `task_status` | Current status |
| `phase` | Internal phase |
| `priority` | Priority |
| `assigned_robot_id` | Assigned robot |
| `created_at` | Created time |
| `updated_at` | Last updated time |
| `result` | Completion/failure/cancellation result |

#### Stream and Refresh State

Manual recovery actions are placed at the top of the task list.

| Action | Behavior |
| --- | --- |
| `Refresh` | Re-query the task monitor snapshot from the Control Service. If the existing event stream is alive, do not disconnect it; only overwrite with the snapshot |
| `Reconnect stream` | Close the current task event stream client and resubscribe to the IF-COM-003 stream from after the last `batch_end_seq` known to the UI |

Status display includes the following.

| Display | Rule |
| --- | --- |
| Stream status | Initial status querying, query complete, event stream connecting, receiving, stopped/failed message |
| Last update | Display the time when a snapshot, event batch, cancel response, or resume response was reflected. Initial value is `Last update: -` |
| Reconnect | When the stream is interrupted, the button must be usable. Manual reconnect preserves the last received seq to reduce duplicates/misses |

If the event stream is interrupted by a transient server/network failure, the page should schedule an automatic reconnect from the last received sequence. The manual reconnect action remains available for explicit operator recovery and must not reset the known sequence cursor.

#### Detail Panel

When a task is selected, the right or lower panel displays the following.

| Area | Content |
| --- | --- |
| Task summary | `task_id`, type, status, phase, priority |
| Request information | Requester, request time, destination, memo |
| Robot information | `assigned_robot_id`, current location, recent feedback |
| Result information | `reason_code`, failure message, completed_at |
| Events | Recent 5-10 events for the task |

Result information is always displayed in the same location. If there is no result yet, display `-`.

| Row label | Display value |
| --- | --- |
| Result | `result_code` or snapshot `task_outcome` |
| Reason | `reason_code` or `latest_reason_code` |
| Message | `result_message` or event/response message |

Highlight the result information card when the status is `FAILED`, `REJECTED`, `CANCEL_REQUESTED`, or `CANCELLED`, or when the result code is `FAILED`, `REJECTED`, `CLIENT_ERROR`, `NOT_ALLOWED`, `NOT_FOUND`, `CANCEL_REQUESTED`, or `CANCELLED`. Operators must be able to see failure/rejection/cancellation causes immediately, so cancellation/resume/evidence-image query responses should also be reflected in the detail panel using `result_code`, `reason_code`, and `result_message` when possible.

#### Scenario-Specific Detail Panels

The task monitor displays common fields for all tasks. Scenario-specific data is separated into dedicated sections inside the detail panel.

| Scenario | Detail section |
| --- | --- |
| DELIVERY | Item, quantity, destination, pickup/destination arm robot |
| PATROL | Patrol area, waypoint/path progress, fall-detection event, fall evidence image query status |
| GUIDE | Visitor/resident connection information, start location, destination, guide progress status |
| FOLLOW | Follow target, follow mode, return/stop status |

The GUIDE detail panel has the following fixed rows.

| Row label | Source field |
| --- | --- |
| Guide phase | `guide_detail.guide_phase`, fallback to common `phase` |
| Target track ID | `guide_detail.target_track_id` |
| Visitor | `guide_detail.visitor_id`, `guide_detail.visitor_name`, `guide_detail.relation_name` |
| Resident | `guide_detail.member_id`, `guide_detail.resident_name`, `guide_detail.room_no` |
| Destination | `guide_detail.destination_id`, `guide_detail.destination_zone_id`, `guide_detail.destination_zone_name` |

GUIDE result, rejection, cancellation, and ROS-runtime failure causes are not duplicated in this section. They stay in the common result information card through `result_code` or `task_outcome`, `reason_code` or `latest_reason_code`, and `result_message`.

The PATROL detail panel has the following fixed sub-sections.

| Sub-section | Content |
| --- | --- |
| Patrol summary | `patrol_area_name`, `patrol_area_revision`, `assigned_robot_id` |
| Progress status | `patrol_status`, `current_waypoint_index`, `total_waypoints`, `distance_remaining_m` |
| Map | Patrol route, waypoints, robot current location, fall detection point marker |
| Fall alert | `ALERT_CREATED` summary, `zone_name`, `confidence`, `frame_ts`, `evidence_image_available` |
| Actions | `View fall photo`, `Resume patrol after on-site action`, `Stop patrol` |
| Events | Recent `FALL_ALERT_CREATED`, `PATROL_RESUMED`, `COMMAND_FAILED`, etc. |

PATROL detail panel actions are exposed according to task status.

| Status | Exposed actions |
| --- | --- |
| `WAITING_DISPATCH`, `ASSIGNED`, `RUNNING` | `Stop patrol` |
| `WAITING_FALL_RESPONSE` | `View fall photo`, `Resume patrol after on-site action`, `Stop patrol` |
| `RECOVERING` | Disable resume button to prevent duplicate resume; show only status message |
| `COMPLETED`, `CANCELLED`, `FAILED` | Keep query actions only; disable mutation actions |

`Resume patrol after on-site action` opens a modal rather than expanding an inline form inside the detail panel. Since users may switch between multiple tasks while viewing the task table, a modal is safer because it reduces confusion if the selected task changes while a form is being entered.

##### PATROL Progress Status Display

`IF-PAT-003 Execute Patrol Path` feedback is displayed in the PATROL detail panel with the following meanings.

| `patrol_status` | UI display |
| --- | --- |
| `ACCEPTED` | Patrol accepted |
| `MOVING` | Patrolling |
| `WAITING_FALL_RESPONSE` | Waiting for fall response |
| `RECOVERING` | Processing patrol resume |
| `FAILED` | Patrol failed |

Progress is calculated from `current_waypoint_index` and `total_waypoints`.

```text
progress = (current_waypoint_index + 1) / total_waypoints
```

If `total_waypoints` is 0 or not received, do not display progress; show `waypoint: not received` instead.

Robot/progress status is displayed as the following rows.

| Row label | Display value |
| --- | --- |
| Robot | `assigned_robot_id` from task update; `Unassigned` if not assigned |
| Status | `patrol_status`; initial value `feedback not received` |
| Waypoint | `current_waypoint_index + 1 / total_waypoints`; `not received` if unavailable |
| Distance remaining | `distance_remaining_m`; `not received` if unavailable |
| Location | `current_pose`; `not received` if unavailable |
| Fall alert | `ALERT_CREATED` or `fall_alert` summary from task update. `None` if absent |

The PATROL runtime detail panel must keep these progress rows even when the
visual map is available. The map helps spatial inspection, but the fixed rows
remain the operator-readable fallback for runtime feedback, frame mismatch, or
map asset loading failure.

##### PATROL Map Overlay

The map overlay is the runtime view of the PATROL detail panel. Do not include the map overlay in the patrol request tab.

If map rendering is not yet available in MVP, show the same data as coordinate text fallback. When map rendering is added, display the following layers in order.

| Layer | Data source | Display |
| --- | --- | --- |
| Map background | Active map metadata and deployed map asset from `map_profile` | Hospital floor plan/occupancy map |
| Patrol route | `patrol_task_detail.path_snapshot_json` or task detail response | Polyline + waypoint markers |
| Robot current location | Latest `PINKY_UPDATED` or `ACTION_FEEDBACK_UPDATED.current_pose` | Robot marker |
| Fall detection point | `ALERT_CREATED.payload.alert_pose` | Fall alert marker |

`ACTION_FEEDBACK_UPDATED` may carry `patrol_status`,
`current_waypoint_index`, `total_waypoints`, `current_pose`, and
`distance_remaining_m`. The UI normalizes `current_pose` into the common
runtime `pose` field for the map marker, updates the selected task's
`patrol_path.current_waypoint_index`, and keeps the route snapshot itself from
the task detail baseline.

The PATROL runtime panel in the task monitor is displayed only for tasks where `task_type=PATROL`. For non-patrol tasks such as DELIVERY, or when no task is selected, hide the map overlay area itself. Do not show copy such as "This is not a patrol task" inside the overlay.

For the current demo scope, map asset revision changes are considered rare. The task monitor queries map YAML/PGM using `task.map_id -> map_profile` without a separate `patrol_task_detail` map revision snapshot. Elements likely to be adjusted, such as `goal_pose`, `operation_zone.boundary_json`, and `patrol_area.revision/path_json`, are displayed using their own baselines. The future map/coordinate editing page should reuse the same map overlay/coordinate conversion component.

Fall detection marker rules:

- Use `ALERT_CREATED.payload.alert_pose` for marker coordinates.
- If `alert_pose.frame_id` differs from the map frame, do not display the marker; display coordinate text and a frame mismatch warning.
- For the marker label, prefer `zone_name` if available; otherwise display `alert_pose.x`, `alert_pose.y`.
- When the marker is clicked, focus the fall alert card in the PATROL detail panel, or if the detail panel is already open, expose an action to open the fall photo dialog.
- If `evidence_image_available=true`, show a `View fall photo` action in the marker tooltip or popover.
- The fall marker remains visible during the selected task detail query even if the task changes to `WAITING_FALL_RESPONSE`, `RECOVERING`, `COMPLETED`, or `FAILED`. However, do not mix a previous task marker into a new patrol task map.

The map placeholder remains available for future display of patrol path, waypoint progress, robot current location, and fall detection point. If actual map rendering is not available in phase 1, show only the following text.

```text
Patrol route / waypoint / robot location / fall point placeholder
```

##### PATROL Fall-Response UI

After fall detection, when the state is `WAITING_FALL_RESPONSE`, display the fall alert card and response actions in the PATROL detail panel.

The fall alert card displays the following information.

| Field | Display method |
| --- | --- |
| `alert_pose` | Display on map/coordinate area. If map is not implemented, display coordinate text |
| `zone_name` | If available, prefer it as the human-readable location name |
| `confidence` | Percent or two decimal places |
| `frame_ts` | Detection frame timestamp |
| `fall_streak_ms` | Auxiliary information for AI server judgment. UI does not use it as a reclassification criterion |
| `evidence_image_available` | Basis for enabling the photo button |
| `evidence_image_id` | Do not expose prominently; show only in tooltip/debug information |

`View fall photo` is handled in a separate image dialog. Do not insert the image into the resume modal. Evidence confirmation and on-site action logging are different purposes, so the modals should be separated.

`View fall photo` behavior:

```text
User clicks
-> GUI sends IF-PAT-007 request to Control Service (task_id + alert_id + evidence_image_id)
-> Control Service sends IF-PAT-006 request to AI Service
-> If OK, display image with bbox already drawn
-> If EXPIRED/NOT_FOUND, display "Photo retention time has expired" or "Photo not found"
```

Image dialog display rules:

- Display `image_data` based on `image_format` and `image_encoding=base64`.
- `image_width_px` and `image_height_px` are metadata used to validate image size and bbox coordinate baseline.
- Since the AI server returns an image with bbox already drawn, the default UI does not need to draw a separate overlay.
- Use `detections[].bbox_xyxy` only when detailed information/debug overlay is needed.
- Image query failure must not block the patrol resume button. On-site action and patrol resume are handled independently through `IF-PAT-002`.

##### PATROL Resume Modal

Resume input is handled in a separate modal. The detail panel contains only the `Resume patrol after on-site action` button, and clicking it opens the modal.

Resume modal composition:

| Area | Content |
| --- | --- |
| Header | `Resume patrol` |
| Task summary | `task_id`, patrol area, robot, current status |
| Fall summary | `zone_name`, `frame_ts`, `confidence`, view photo button |
| Action input | `member_id`, `action_memo` |
| Footer actions | `Cancel`, `Resume` |

The `Resume` button in the resume modal is enabled only when both `member_id` and `action_memo` are valid. During submission, prevent duplicate clicks. On success, close the modal and update the detail panel state to `RECOVERING` or the latest state pushed by the server. On failure, keep the modal open and display `result_message` and `reason_code`.

`IF-PAT-002` request payload:

```json
{
  "task_id": 2001,
  "caregiver_id": 1,
  "member_id": 301,
  "action_memo": "Called emergency services, and paramedics transported the resident to the hospital"
}
```

`action_memo` is an audit field that records the actual on-site action taken after fall response, and is treated as a required payload field for the patrol resume request.

`IF-PAT-002` is not a general termination API. The UI represents it only as a `Resume` button, while `Stop/End` must always be sent through the common cancel API.

In the fall-response state, input fields are placed in the following order.

| Input | UI element | Required | Description |
| --- | --- | --- | --- |
| `member_id` | Resident search combo box | Y | Person involved in the on-site action |
| `action_memo` | Multi-line textarea | Y | Actual action content |
| Resume button | Primary button | Y | Enabled only when both fields are valid |

#### Cancel Action

The task monitor detail panel contains mutation actions for the selected task. For delivery tasks, display `Cancel task`; for patrol tasks, display `Stop patrol`. These are not separate UI elements; use the same detail-panel action button and change only the label based on task type.

Cancel button exposure criteria:

- Server returns `cancellable=true`.
- Task status is in the `WAITING_DISPATCH`, `ASSIGNED`, or `RUNNING` family.
- If already `CANCEL_REQUESTED`, `CANCELLED`, `COMPLETED`, or `FAILED`, disable the button.
- If no task is selected or there is no `task_id`, disable the button.

UI state after cancel request:

```text
Sending cancel request
-> Cancel request accepted
-> Canceling
-> Cancel complete or cancel failed
```

When cancellation fails, display `reason_code` together with the message.

The cancel request response is immediately reflected in the current task snapshot in the detail panel. If the response includes `task_id`, `task_status`, `phase`, `assigned_robot_id`, `result_code`, `result_message`, `reason_code`, and `cancellable`, update the task row and detail panel. When a later IF-COM-003 push arrives, overwrite again using the server state as the final baseline.

Patrol stop is sent through the common cancel API, not the `IF-PAT-002` resume API. The server records the patrol cancel request as `CANCEL_REQUESTED` state and a `PATROL_TASK_CANCEL_REQUESTED` event. If the ROS cancel action result is not accepted, the server returns `reason_code` and message without changing task state.

---

### 7-5. Coordinate/Zone Settings Page

#### Page Name

The page name is `Coordinate/zone settings`, not `Map editor`.

This page does not modify the PGM/YAML map asset itself. Occupancy map edits such as walls, obstacles, and route pixels are performed in external map editing tools such as GIMP. This UI manages operational coordinates and zone metadata stored in the DB on top of an already deployed map asset.

#### Purpose

Allow operators to adjust indoor location baseline data used by delivery, patrol, and guide without directly modifying SQL or `.env`.

Main goals:

- Query and update DB-backed pickup, destination, and dock coordinates through Control Service where Pinky needs precision parking for delivery tasks.
- Manage human-understandable zones such as `Room 301`, `Caregiver station`, `Supply loading location`, and `Charging station`.
- Check current coordinate positions on the map image and adjust coordinates by clicking/dragging map objects or using the input form for fine tuning.
- After migrating delivery goal pose settings from `.env` to DB-centered `goal_pose`, allow operators/admins to easily check the values.
- Edit patrol path waypoints stored in `patrol_area.path_json` on the same map overlay and coordinate conversion component in phase 1.
- Prepare phase-2 fleet management by letting operators curate named common waypoints and reusable routes on the same map without replacing phase-1 `goal_pose` or `patrol_area.path_json`.

#### Scope and Non-Scope

| Category | Included | Description |
| --- | --- | --- |
| PGM/YAML map asset display | Included | Read and display `map_profile.yaml_path` and `map_profile.pgm_path` as background |
| PGM pixel editing | Excluded | Wall/obstacle/occupancy pixel editing is done with external tools such as GIMP |
| `operation_zone` management | Included | Manage zone ID, name, type, active state, and optional map-frame polygon boundary |
| `goal_pose` management | Included | Manage precision parking/destination/dock coordinates and yaw |
| `patrol_area.path_json` management | Included in phase 1 | Create/select/deactivate a patrol area, display its ordered waypoints/path, add/move/delete/reorder waypoints, and save the row through Control Service |
| FMS waypoint/route management | Second phase | Operator-curated common traffic nodes, edges, and reusable route templates for delivery, patrol, and guide |
| FMS reservation/scheduling control | Later phase | Runtime ownership/reservation, task scheduling, pass-order priority, and conflict calculation are separate from coordinate editing |
| Map revision snapshot policy | Excluded | For demo scope, keep `task.map_id -> map_profile` baseline |
| Direct DB access from UI | Excluded | The PyQt UI never opens a DB connection. All DB reads/writes are performed by Control Service |
| Direct ROS access from UI | Excluded | The PyQt UI never imports ROS packages or calls ROS APIs. Robot-side validation, if needed, must be exposed as a Control Service interface and executed by the server/ROS adapter |

#### Screen Composition

| Area | Components |
| --- | --- |
| Page Header | Title `Coordinate/zone settings`, description, `Refresh`, `Save`, `Discard changes` |
| Selected Map Bar | Map selector, current edit `map_profile`, map revision, YAML/PGM path, frame |
| Map Canvas | PGM map background, zone boundary polygons/vertices, goal pose markers, patrol waypoint/path markers, FMS waypoint/edge/route overlays, selected coordinate crosshair |
| Zone List | `operation_zone` list, zone type filter, active/inactive, card-header row actions |
| Goal Pose List | `goal_pose` list, purpose filter, zone connection status, card-header row actions |
| Patrol Area List | `patrol_area` list, path revision, waypoint count, edit mode, card-header row actions |
| FMS Waypoint/Route List | Phase-2 common waypoint graph, route templates, edge state, reservation read-only state, card-header row actions |
| Edit Panel | Detail form for selected zone, goal pose, patrol area, patrol waypoint, FMS waypoint, or FMS route item; row creation/deactivation/revert controls are not placed here |
| Validation Panel | Coordinate bounds, frame mismatch, missing required values, waypoint/path checks, pre-save change summary |

The coordinate/zone settings page should fit the main desktop viewport without
requiring page-level scrolling for normal editing. The six DB-backed list
surfaces are grouped into a tabbed table area with internal table scrolling, so
the map canvas and selected Edit Panel remain visible while switching between
`operation_zone`, `goal_pose`, `patrol_area`, and FMS graph tables.
The coordinate page should use compact local margins for the map card and the
tabbed DB table card; the map image itself should have only a small inner gutter
so blank padding does not force vertical scrolling. The DB table tab content
must still keep a sufficiently tall internal scroll surface for row scanning.

#### Selected Map

The coordinate/zone settings page edits one selected map at a time. The active/default `map_profile` is only the initial selection when the page opens; delivery coordinates may be edited on `map_test12_0506` while patrol/guide data remains on `map_0504`.

| Field | Display |
| --- | --- |
| `map_id` | Current selected edit baseline map |
| `map_name` | Operator-readable map name |
| `map_revision` | Reference metadata |
| `frame_id` | Usually `map` |
| `yaml_path` | Display relative path |
| `pgm_path` | Display relative path |

`yaml_path` and `pgm_path` are map asset identifiers returned by Control Service, not developer checkout assumptions. The UI may load those files directly only when the deployed UI has access to the same asset path. If the UI and server do not share a filesystem, Control Service must provide a TCP map asset/metadata interface so the UI can render the same selected map without depending on a local repository path.

If the map asset file is missing or fails to load, disable the coordinate save button and display the file path and error message. Do not create a fallback that allows editing only DB coordinates. If users cannot verify where a coordinate is on the actual map, the risk of wrong input is high.

#### Map Canvas Display Rules

Reuse the PGM/YAML loading and map-frame coordinate conversion logic used by the existing task monitor `PatrolMapOverlay`.

| Marker | Data | Display |
| --- | --- | --- |
| Zone boundary | `operation_zone.boundary_json` | Draw a semi-transparent polygon, boundary stroke, editable vertices, and a label anchor at the polygon centroid |
| Zone fallback marker | `operation_zone` without `boundary_json` | If connected `goal_pose` exists, display the zone label at that goal pose as a fallback anchor |
| Goal pose marker | `goal_pose.pose_x`, `pose_y`, `pose_yaw` | Purpose-specific marker + yaw direction |
| Pickup | `purpose=PICKUP` or `PICKUP_STATION` | Item loading/pickup point |
| Destination | `purpose=DESTINATION` or `DELIVERY_DESTINATION` | Delivery destination such as room/caregiver station |
| Dock | `purpose=DOCK`, `RETURN_TO_DOCK`, `CHARGING_DOCK` | Return/charging point |
| Patrol path | `patrol_area.path_json` | Editable ordered waypoint markers + polyline in phase 1 |
| FMS waypoint | `fms_waypoint.pose_x`, `pose_y`, `pose_yaw`, `display_name` | Named traffic node marker, label, and yaw direction |
| FMS edge | `fms_edge` | Connection line between waypoints; disabled edges are muted |
| FMS route | `fms_route_waypoint[]` | Highlighted ordered route overlay with sequence numbers |
| FMS reservation | `fms_reservation` | Read-only ownership/waiting badge on waypoint or edge |

Clicking a marker, waypoint, or zone vertex switches the right Edit Panel to the corresponding row and selects that map object. Numeric x/y/yaw fields are precision controls, not the primary editing mechanism. The default user flow should be map-first: select or drag objects on the map, then optionally fine-tune numbers in the form.

Marker direction must be visible whenever a selected object has yaw. At minimum this applies to selected `goal_pose`, patrol path waypoint, and FMS waypoint markers. A heading arrow/handle should preview direction on the map, while the form stores radians and may show degree helper text.

#### Map Editing Modes

The map canvas must expose an explicit edit mode. The active mode changes which overlay is emphasized, what a click means, what is draggable, and which controls are shown in the Edit Panel.

| Mode | Primary target | Click behavior | Drag behavior | Right panel |
| --- | --- | --- | --- | --- |
| Select | All visible overlays | Select marker, waypoint, polygon, or vertex; empty click clears selection | None | Selected object summary |
| Goal pose edit | `goal_pose` marker | Select/move the current marker to clicked map position | Drag selected marker to update x/y preview; drag the heading handle to update yaw only | Goal pose form with x/y/yaw fine tuning |
| Patrol path edit | `patrol_area.path_json.poses[]` | Empty map click appends or inserts a waypoint depending on insert mode; waypoint click selects it | Drag selected waypoint to update x/y preview; drag the heading handle to update yaw only | Waypoint list, x/y/yaw fine tuning, reorder/delete controls |
| Zone boundary edit | `operation_zone.boundary_json.vertices[]` | Empty map click appends/inserts a polygon vertex; vertex click selects it; polygon click selects the zone | Drag selected vertex to update the polygon preview | Zone metadata form plus boundary vertex list/edit controls |
| FMS waypoint edit | `fms_waypoint` | Empty map click creates a named waypoint draft; waypoint click selects it | Drag selected waypoint to update x/y preview; drag the heading handle to update yaw only | Waypoint name/type/pose/yaw/grid snap controls |
| FMS route edit | `fms_route_waypoint[]` | Waypoint click appends/inserts the waypoint into the selected route | Drag edits the underlying waypoint only in waypoint edit mode; route edit reorders route references | Route sequence, yaw policy, stop/dwell controls |
| FMS reservation view | `fms_reservation` | Select reservation badge/resource for details | None | Read-only owner/waiting task and robot state |

Mode-specific rules:

- A toolbar or segmented control must show the active mode clearly.
- Only the active layer should accept write interactions. Non-active layers are visible but read-only/select-only.
- Drag operations update local preview and dirty state only. No Control Service mutation occurs until Save.
- Pressing Escape or clicking Discard reverts local preview to the latest server snapshot.
- If the map is not loaded, all map write modes are disabled.

#### Zone Settings

`operation_zone` is a human-understandable place/zone name. The actual coordinates where the robot moves are owned by `goal_pose`.

`operation_zone.boundary_json` is an optional semantic polygon used by the UI to show the visible extent of the zone. It is not an occupancy map, costmap obstacle, robot target, patrol route, or FMS traffic-control area.

Table fields:

| Column | Description |
| --- | --- |
| `zone_id` | Stable zone ID. Examples: `room_301`, `caregiver_room`, `dock` |
| `zone_name` | Screen display name. Examples: `Room 301`, `Caregiver station`, `Charging station` |
| `zone_type` | ROOM, STAFF_STATION, SUPPLY_STATION, DOCK, etc. |
| `map_id` | Owning map |
| `revision` | Zone definition revision |
| `boundary_json` | Optional map-frame polygon vertices for visual zone extent |
| `is_enabled` | Whether it can be selected |

Zone edit form:

| Field | Input |
| --- | --- |
| Zone ID | Input on creation; immutable after creation |
| Zone name | Text input |
| Zone type | Combo box |
| Boundary | Map vertex editing plus vertex list; numeric x/y is only fine tuning |
| Active state | Switch/checkbox |

Phase 1 includes operation zone creation, modification, and deactivation. The default removal action is deactivation, not deletion. Since existing `goal_pose`, task history, and patrol areas may refer to the zone, hard delete is not provided in phase 1 UI.

Boundary edit behavior:

| Action | Behavior |
| --- | --- |
| Select zone | Display `boundary_json` polygon if present; otherwise show fallback zone label anchor from connected `goal_pose` |
| Create boundary | In Zone boundary edit mode, map clicks add polygon vertices in order |
| Move vertex | Drag a vertex or update vertex x/y in the form |
| Delete vertex | Remove selected vertex after confirmation |
| Insert vertex | Insert after the selected vertex, or append if no vertex is selected |
| Clear boundary | Set `boundary_json=null` after confirmation |
| Save boundary | Send full boundary polygon through Control Service and receive updated `operation_zone.revision` |

`boundary_json` shape:

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

The closing edge from the last vertex to the first vertex is implicit. A saved non-null boundary must contain at least three vertices.

#### Precision Parking/Destination Coordinate Settings

`goal_pose` is the 2D pose where Pinky actually moves or precision-parks. Pickup, destination, and dock coordinates previously stored in `.env` use this table as the source of truth.

Table fields:

| Column | Description |
| --- | --- |
| `goal_pose_id` | Stable coordinate ID. Examples: `pickup_supply`, `delivery_room_301`, `dock_home` |
| `zone_id` | Connected zone. Nullable |
| `purpose` | PICKUP, DESTINATION, RETURN_TO_DOCK, etc. |
| `pose_x` | Map frame x |
| `pose_y` | Map frame y |
| `pose_yaw` | Heading in radians |
| `frame_id` | Usually `map` |
| `is_enabled` | Whether it can be used in requests/execution |

Coordinate edit form:

| Field | Input |
| --- | --- |
| Coordinate ID | Input on creation; immutable after creation |
| Connected zone | `operation_zone` combo box |
| Purpose | Purpose combo box |
| x / y | Decimal spinbox |
| yaw | Radian input with degree helper display |
| Active state | Switch/checkbox |

When a marker is selected on the map, the x/y/yaw form is updated. When form values are modified, the marker position and direction are previewed immediately. Before save, show a dirty state.

Goal pose row actions:

| Action | Behavior |
| --- | --- |
| New goal pose | Add a local draft row from the Goal Pose list header, then enter `goal_pose_id`, purpose, pose, optional zone, and active state before saving |
| Deactivate goal pose | Set `is_enabled=false` locally; save persists the disabled row so it is hidden from regular request/runtime selection |
| Revert goal pose | Restore the selected persisted row from the latest server snapshot; unsaved new rows are discarded locally |

#### Patrol Path Waypoint Settings

`patrol_area.path_json` is the ordered patrol route definition used when the task request screen submits `patrol_area_id`. Phase 1 includes editing these patrol path waypoints because they are operational route settings for patrol demos.

This is not FMS traffic-control waypoint management. A patrol waypoint defines where one patrol route should go. An FMS waypoint/control node defines fleet-level passage, reservation, priority, and conflict rules for multiple robots. Keep those concepts separate in UI labels, API names, and DB modeling.

Patrol area fields:

| Column | Description |
| --- | --- |
| `patrol_area_id` | Stable patrol area ID. Example: `patrol_ward_night_01` |
| `patrol_area_name` | Operator-readable patrol area name |
| `map_id` | Owning map |
| `revision` | Patrol path definition revision |
| `path_json` | Ordered waypoint list/polyline source of truth |
| `is_enabled` | Whether the patrol area can be selected in requests |

Waypoint edit behavior:

| Action | Behavior |
| --- | --- |
| New patrol area | Add a local draft row from the Patrol Area list header, then enter `patrol_area_id`, `patrol_area_name`, and at least two waypoints before saving |
| Select patrol area | Display current `path_json` as ordered markers and a polyline |
| Deactivate patrol area | Set `is_enabled=false` locally; save persists the disabled row so it is hidden from regular patrol requests |
| Revert patrol area | Restore the selected persisted row from the latest server snapshot; unsaved new rows are discarded locally |
| Add waypoint | In Patrol path edit mode, map click appends a waypoint or inserts after the selected waypoint depending on insert mode |
| Move waypoint | Drag marker or edit x/y/yaw in the form; map drag is the primary workflow and numeric edit is fine tuning |
| Delete waypoint | Remove selected waypoint after confirmation |
| Reorder waypoint | Move selected waypoint up/down in the waypoint list |
| Save patrol path | Send the full ordered path to Control Service; server validates and returns the updated revision |

The UI displays the pre-save route diff summary: added waypoint count, deleted waypoint count, moved waypoint count, and order changes. It does not calculate robot traffic conflicts; that belongs to FMS waypoint management in a later phase.

#### FMS Waypoint and Route Settings

FMS settings are phase-2 additions to the same page. They introduce common named waypoints and route templates that delivery, patrol, and guide can reuse, while keeping phase-1 `goal_pose` and `patrol_area.path_json` contracts intact.

Common waypoint fields:

| Field | Input/Display |
| --- | --- |
| Waypoint ID | Stable ID; creation input, immutable after creation |
| Display name | Operator label shown on the map, such as `복도1`, `복도2`, `301호앞` |
| Type | `CORRIDOR`, `ROOM_ENTRY`, `DOCK_ENTRY`, `WAIT_POINT`, `INTERSECTION`, etc. |
| x / y | Decimal spinbox and map drag |
| yaw | Heading arrow/handle plus radian input with degree helper display |
| Grid snap | Optional toggle/group; snap helps corridor consistency but free placement remains allowed |
| Active state | Switch/checkbox |

Waypoint label rules:

- Show the selected waypoint label at all zoom levels.
- Show nearby route labels when route edit mode is active.
- At low zoom, hide or de-emphasize non-selected labels that collide visually.
- Use stable display names rather than raw IDs as the primary map text; keep IDs available in the detail panel.

Route fields:

| Field | Input/Display |
| --- | --- |
| Route ID | Stable route ID; immutable after creation |
| Route name | Operator-readable name |
| Route scope | `COMMON`, `DELIVERY`, `PATROL`, or `GUIDE` |
| Revision | Server-managed route revision |
| Waypoint sequence | Ordered references to common FMS waypoints |
| Yaw policy | Per-route-point `AUTO_NEXT`, `FIXED`, `GOAL_POSE`, or `KEEP_CURRENT` |
| Stop/dwell | Optional stop-required and dwell seconds |
| Active state | Switch/checkbox |

Route editing behavior:

| Action | Behavior |
| --- | --- |
| Create waypoint | In FMS waypoint edit mode, map click creates a draft point and prompts for display name/type |
| Move waypoint | Drag marker or edit x/y/yaw in the form; route references update visually because they point to the same waypoint |
| Create edge | Connect two selected waypoints, set direction/bidirectional state, and optional priority/cost |
| Build route | In route edit mode, click waypoints in pass order to append or insert references |
| Reorder route | Move selected route item up/down in the sequence list |
| Route yaw policy | Default to `AUTO_NEXT`; use `FIXED` for explicit heading or `GOAL_POSE` for final precision stop alignment |
| Materialize route | Preview the route as `{"header":{"frame_id":"map"},"poses":[...]}` for compatibility with existing runtime path consumers |

Reservation display behavior:

- Reservation state is read-only in this settings page.
- Show `HELD` resources with the owning robot/task and `WAITING` resources with the waiting robot/task.
- Do not provide manual reservation/release controls to operators in the coordinate page. Reservation changes belong to the scheduler/runtime service.
- A task waiting for traffic control must surface a specific reason such as `WAITING_FMS_RESERVATION`, not a silent generic waiting state.

#### Save Policy

Coordinate/zone settings uses a draft-first save policy. Editing a row updates
the local draft and marks that row dirty; switching to another row must not
discard the previous row's unsaved values. The page-level `Save` action saves all
pending draft changes in a deterministic order and keeps failed rows dirty.
Page-level actions are limited to `Refresh`, `Save`, and `Discard changes`.
Row creation, soft deactivation, and selected-row revert controls live in the
corresponding table card header, not in the Edit Panel.

| Action | Behavior |
| --- | --- |
| Enter page | Auto-load the default selected map/location bundle once when the page has no loaded map and no local dirty draft |
| Change map selector | Re-query `get_map_bundle(map_id=selected_map_id)`, YAML/PGM assets, and FMS graph for the selected map; block switching while local dirty drafts exist |
| Refresh | Re-query selected map, zones, goal poses, and patrol areas from the server |
| Save coordinate drafts | Create new `goal_pose` draft rows and update dirty persisted `goal_pose` rows |
| Create zone draft | Add a draft `operation_zone` row for the selected map, then insert it on Save |
| Save zone drafts | Update all dirty `operation_zone` metadata rows |
| Save zone boundary | Update selected `operation_zone.boundary_json` and receive the new zone revision |
| Save patrol path | Update the selected `patrol_area.path_json` and receive the new path revision from the server |
| Save FMS waypoint drafts | Upsert all dirty `fms_waypoint` rows |
| Save FMS edge drafts | Upsert all dirty `fms_edge` rows |
| Save FMS route drafts | Upsert all dirty `fms_route` rows and receive route revisions |
| Deactivate row | For persisted rows, mark `is_enabled=false` as a draft change; for unsaved drafts, remove the row locally |
| Revert selected row | Restore only the selected row from the latest server snapshot and clear its dirty/failure state |
| Discard changes | Revert all local drafts to the latest server snapshot values |

Keyboard shortcuts mirror the same draft-first policy: `Ctrl+S` triggers the
page-level `Save` action when saving is enabled, `Ctrl+Z` restores the previous
local edit snapshot for the selected editor, and `Ctrl+Shift+Z` reapplies the
next local edit snapshot. Undo/redo update only the local preview, dirty state,
tables, and forms; they do not call Control Service until the operator saves.
The shortcut handler must intercept `ShortcutOverride` and key press events
before focused form widgets such as spin boxes or line edits consume their own
`Ctrl+Z` behavior, and it must also handle AdminShell/window-level shortcut
events while the coordinate page is visible.
Map drag edits are one undo step per completed drag: capture the pre-drag state
when the pointer drag starts, update the local preview during movement without
adding repeated snapshots, and push one post-drag snapshot when the left mouse
button is released if the edit actually changed.

After a successful save, update each saved row's revision/`updated_at` and clear
only that row's dirty state from the Control Service response. When a row save
fails, keep that row's draft values, keep the row dirty, continue saving later
rows where the dependency order allows it, and display `reason_code` and message
in the Validation Panel.

Each editable coordinate/FMS list must expose a status column for local state:
`-`, `Changed`, `Will deactivate`, or `Save failed`. A page-level summary label
shows the total number of unsaved rows grouped by data type and the number of
failed rows after a batch save. Failed rows remain eligible for retry until the
operator saves again, re-edits the row, reverts the selected row, discards all
changes, or refreshes the bundle.

Zone metadata save and zone boundary save are independent operations. If both are dirty, a successful `operation_zone` metadata save must keep the boundary editor dirty until `coordinate_config.update_operation_zone_boundary` succeeds. Discard changes must always restore the latest server-confirmed boundary snapshot, not an unsaved local polygon preview.
When the selected operation zone has both metadata and boundary dirty state, one operator `Save` click should preserve the boundary draft through the metadata save and then continue with the boundary save using the returned zone revision.
When a selected `operation_zone` metadata form has local edits, the page-level `Save` click must either dispatch `coordinate_config.update_operation_zone`/`create_operation_zone` or show a specific validation reason. It must not be a silent no-op.

#### Validation Rules

| Condition | UI behavior |
| --- | --- |
| Map not loaded | Disable save and display map asset error |
| `frame_id` differs from selected map frame | Warn before save; block save in phase 1 |
| x/y outside map bounds | Block save |
| Duplicate `goal_pose_id` | Block creation |
| Duplicate `zone_id` | Block creation |
| Zone boundary has fewer than three vertices | Block zone boundary save |
| Zone boundary vertex outside map bounds | Warn in the editor but allow save so operators can repair migrated or legacy boundary polygons one vertex at a time |
| Zone boundary frame differs from selected map frame | Block zone boundary save |
| Connected to inactive zone | Allow but display warning |
| Missing purpose | Block save |
| Patrol path has fewer than two waypoints | Block patrol path save |
| Patrol waypoint outside map bounds | Block patrol path save |
| Patrol waypoint frame differs from selected map frame | Block patrol path save |
| Confusion over yaw unit | Store radians; degree is display helper only |
| Duplicate FMS waypoint or route ID | Block creation |
| FMS route references a missing waypoint | Block route save |
| FMS route has disabled waypoint/edge references | Warn or block depending on route status policy |
| FMS route has disconnected adjacent waypoints | Warn in draft mode; block enabled route save |

Client-side validation is only a preview guard. Control Service must repeat persistence-critical validation before updating DB state.

#### Expected Server/API Shape

The administrator UI uses a dedicated coordinate/zone settings service client over the existing custom TCP internal RPC transport. Do not add DB connectors or ROS dependencies to the UI process, and do not mix settings save functionality into the existing task request API.

Expected RPC shape:

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

Expected service methods:

```text
coordinate_config.get_map_bundle(map_id=selected_map_id)
coordinate_config.update_goal_pose(...)
coordinate_config.create_operation_zone(...)
coordinate_config.update_operation_zone(...)
coordinate_config.update_operation_zone_boundary(...)
coordinate_config.update_patrol_area_path(...)
coordinate_config.get_map_asset(...)          # only if the UI cannot access pgm/yaml paths directly
coordinate_config.validate_goal_pose_runtime(...)  # optional future robot-side validation via ROS adapter
fms_config.get_active_graph_bundle(...)       # phase 2, separate from coordinate_config
fms_config.upsert_waypoint(...)
fms_config.upsert_edge(...)
fms_config.upsert_route(...)
fms_config.materialize_route(...)
fms_runtime.get_reservation_snapshot(...)     # read-only UI display
```

`get_map_bundle(map_id)` response example:

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

#### Implementation Priority

First MVP:

- Active map load and read-only display
- `operation_zone` list query, creation, modification, and deactivation
- `goal_pose` list query
- Goal pose marker display
- Goal pose x/y/yaw form modification and save
- Preview selected goal pose x/y by map click
- `patrol_area` list query and path overlay
- `patrol_area` row creation, deactivation, and selected row revert
- Patrol waypoint add/move/delete/reorder
- Patrol area save with server-returned revision and pre-save diff summary

Second phase:

- Goal pose creation/deactivation
- Purpose-specific marker colors/filters
- Yaw heading arrow/handle editing for goal pose, patrol waypoint, and FMS waypoint markers
- FMS waypoint/control node CRUD with map labels and optional grid snap
- FMS edge management for route connectivity and traffic control
- FMS route editor for common, delivery, patrol, and guide route templates
- FMS route materialization preview into the existing path JSON shape
- FMS reservation/ownership read-only state display: which robot owns or is waiting for a waypoint or edge

Third phase:

- Connect actual robot precision parking test-result feedback
- FMS scheduler/runtime reservation write path, pass-order priority, conflict handling, and task state integration

---

### 7-6. Robot Status Page

#### Purpose

Check per-robot connection status, current task, battery, location, and recent status received time.

If the task monitor is task-centered, the robot status page is robot-centered.

#### Screen Composition

| Area | Components |
| --- | --- |
| Fleet Summary | Total robots, online, offline, caution |
| Robot Cards | Per-robot cards plus the primary map-backed robot location panel |
| Robot Table | Detailed list |
| Detail Panel | Details for selected robot |
| Location Visualization | Large PGM/YAML map panel embedded in the robot-card area, not a narrow side placeholder |

#### Phase 1 Data Source

The page uses the Control Service TCP/RPC method `caregiver.get_robot_status_bundle`.
The UI must not connect directly to DB or ROS. The bundle contains `summary`, `robots`, and `delivery_composition`.

`scenario_role` must not be derived from `robot_id`. For the current demo scope, the DB schema is not expanded for robot capabilities. Control Service derives display-only capabilities from fixed phase-1 policy: all Pinky mobile robots support guide, delivery, and patrol; `jetcobot1` and `jetcobot2` are fixed delivery station arms.

#### Loading and Refresh Behavior

Robot status refresh must not insert or remove a page-level status row that changes the page height. While a snapshot refresh is in progress, keep the main robot cards, table, detail panel, and map at stable dimensions. Show the loading state through a non-layout-shifting indicator such as refresh-button text/state and a fixed header status field. Error messages may appear in the reserved header/status area, but they must not push the robot content down.

Periodic robot snapshot refresh should not repeatedly download unchanged map profile/YAML/PGM assets or re-query the location configuration service. The 1-2 second fallback refresh path should fetch only runtime robot status. Cache map assets by selected `map_id` and reload map profile/assets only on initial load, selected-map change, empty cache recovery, or an explicit manual refresh that requires map refresh. Refresh and stream updates must preserve the operator-selected robot detail when that robot is still present.

#### Robot Card

Card display fields:

| Field | Description |
| --- | --- |
| `robot_id` | Example: `pinky2` |
| `display_name` | Example: `Pinky Pro` |
| `robot_type` | MOBILE, ARM |
| `capabilities` | Scheduler-facing supported capabilities such as DELIVERY, PATROL, GUIDE, MANIPULATION |
| `station_roles` | Display-only fixed station assignments for station robots, for example DELIVERY/PICKUP |
| `connection_status` | ONLINE, OFFLINE, DEGRADED |
| `battery_percent` | Mainly for mobile robots |
| `current_task_id` | Displayed if working on a task |
| `current_phase` | Task phase |
| `current_location` | Human-readable location or coordinate label if available |
| `last_seen_at` | Last received time |

Robot card titles follow the same rule as Home: show only `robot_id`. `display_name` and `robot_type` remain detail fields and status/category badges; they are not prepended or appended to the title.

#### Robot Location Map

The robot status page renders real map assets by reusing the Control Service location configuration interfaces. The page loads available `map_profiles`, lets the operator choose one map, then loads that map's YAML/PGM assets through `coordinate_config.get_map_asset`.

The map selector in the location panel must be wide enough to show the operator-facing map name and `map_id` together, for example `Delivery map (map_test12_0506)`, without clipping under the normal administrator layout. Use a fixed minimum width or content-length policy rather than allowing the header stretch to compress the combo box.

Only robots whose current pose belongs to the selected map are drawn as markers. The robot list, robot cards, and detail table still show all robots. Robots with no pose, no map identity, a stale pose, or a pose from another map remain visible in the list but are not drawn on the selected map. Selecting a robot with a known pose map may switch the map selector to that map.

Current phase-1 robot pose contract:

| Field | Rule |
| --- | --- |
| `current_pose.map_id` | Required for map marker rendering. In the current DB model this is derived from the active task `map_id`; if there is no active task map, the pose is treated as map-unknown. |
| `current_pose.frame_id` | Must match the map frame, usually `map`. |
| `current_pose.x`, `current_pose.y`, `current_pose.yaw` | Map-frame robot pose used for marker and heading display. |
| `current_pose.updated_at` | Operator-facing freshness timestamp. |

Do not merge the delivery/transport map and patrol/guide map into one visualization. `map_0504` and `map_test12_0506` have different coordinate frames; the same x/y values may mean different physical places.

#### Composite Robot Task Representation

Some scenarios involve multiple robots in one task. The current representative case is delivery, where a Pinky mobile robot and Jetcobot arms work together.

On screen, represent the relationship in a human-readable way.

```text
Pickup Arm Robot: jetcobot1
Destination Arm Robot: jetcobot2
ROS adapter arm_id: arm1 / arm2
```

In the UI, display physical robot IDs `jetcobot1` and `jetcobot2`. `arm1` and `arm2` are internal IDs used at the ROS action adapter boundary and should appear only in explanatory areas. The delivery mobile robot is selected by the scheduler/current task assignment and must not be globally hardcoded in the robot status bundle.

---

### 7-7. Inventory Management Page

#### Purpose

Query and modify deliverable items and inventory quantity.

Inventory is directly connected to the current delivery scenario. If items or equipment become needed in other scenarios later, extend the same inventory structure.

#### Screen Composition

| Area | Components |
| --- | --- |
| Summary Cards | Total item count, low-stock item count, recent modification |
| Inventory Table | Item list |
| Edit Form | Add/modify inventory |
| Low Stock Panel | Low-stock warnings |

#### Table Fields

| Column | Description |
| --- | --- |
| `item_id` | Item ID |
| `item_name` | Item name |
| `item_type` | Medication, consumable, etc. Current DB field used as the phase 1 category label |
| `quantity` | Current quantity |
| `updated_at` | Last modified time |

Inventory table headers and detail keys are operator-facing labels, not raw DB field names. For example, display `item_id` as `Item ID`, `item_type` as `Category`, `quantity` as `Current Quantity`, and `updated_at` as `Last Modified`. Time values must use the common operator time format instead of raw ISO `T` strings.

`safety_stock` and `delivery_enabled` are not phase 1 DB columns. Do not hard-code them in the UI as editable product state. The server may return a temporary low-stock warning by applying an operator threshold to `quantity`; future schema work can add item-level safety stock and delivery availability if needed.

#### Actions

| Action | Behavior |
| --- | --- |
| Add inventory | Add to existing quantity |
| Modify inventory | Directly change current quantity |
| Refresh | Re-query from the server |

#### Phase 1 Data Source

The Admin UI must communicate through the Control Service TCP/RPC layer only.

| UI Need | Control Service RPC | Notes |
| --- | --- | --- |
| Load inventory screen | `inventory.get_inventory_bundle` | Returns `summary`, `items`, and `low_stock_items` derived from the `item` table |
| Add inventory quantity | `inventory.add_item_quantity(item_id, quantity_delta)` | Positive integer only; updates by `item_id` |
| Directly set current quantity | `inventory.set_item_quantity(item_id, quantity)` | Non-negative integer only; updates by `item_id` |

Phase 1 does not operate a complex inventory deduction policy. However, the UI is designed around `item_id` so that future inventory deduction after delivery completion can be added.

---

### 7-8. Resident Information Page

#### Purpose

Search resident information and check preferences/dislikes, recent events, prescriptions, and cautions.

This screen can become base data for the guide scenario and visitor kiosk.

#### Screen Composition

| Area | Components |
| --- | --- |
| Search Panel | Search by partial name or partial room number |
| Candidate List | Inline resident candidates displayed below the search fields while typing |
| Profile Summary | Basic information card |
| Preference Panel | Preferences/dislikes |
| Recent Member Events | Recent `member_event` |
| Prescription/Notes | Prescription image paths and cautions |

#### Search Fields

| Field | Description |
| --- | --- |
| name | Resident name |
| room_no | Room number |

Searching must be allowed with either field only. Because duplicate names and ambiguous room queries are possible, the page displays an inline candidate list directly below the search fields while the operator types.

The page must not use a separate search preview card. Candidate rows should use an operator-readable compact format such as `김영수 · 301호 · #1`. Selecting a candidate loads the detail payload by `member_id`. Search result values must be normalized to display strings before applying them to Qt labels so numeric IDs or date objects do not crash the UI.

#### Service Contract

| RPC | Purpose |
| --- | --- |
| `patient.search_patient_candidates(name, room_no, limit)` | Lightweight candidate lookup. `name` or `room_no` may be empty, but at least one must be supplied by the UI. |
| `patient.get_patient_info(member_id)` | Detail lookup after candidate selection. This is the primary resident detail flow for the admin UI. |
| `patient.search_patient_info(name, room_no)` | Legacy exact lookup kept for compatibility. New admin UI must prefer candidate selection plus `member_id` detail lookup. |

#### Display Fields

| Field | Description |
| --- | --- |
| `member_id` | Resident ID |
| `name` | Name |
| `room_no` | Room number |
| `admission_date` | Admission date |
| `preference` | Preference information |
| `dislike` | Dislike information |
| `comment` | Care memo |
| `events` | Recent member events |
| `prescription_paths` | Prescription image paths |

#### Event Representation

Resident-related events are displayed based on `member_event`.

| Field | Description |
| --- | --- |
| `event_at` | Occurrence time |
| `event_type` | Event type |
| `severity` | Severity |
| `description` | Description |

Events without severity use default `INFO`.

Resident event times must use the common operator time format. Raw ISO strings such as `2026-05-03T12:00:00` must not be shown in the recent-event text box.

---

### 7-9. Alerts/Logs Page

#### Purpose

Track operational events, errors, task failures, cancellation failures, and communication issues.

This page is not a developer debug console; it is an operator-facing issue-tracking screen.

#### Screen Composition

| Area | Components |
| --- | --- |
| Filter Bar | Period, severity, source, task_id, robot_id |
| Event List/Table | Operational event list |
| Detail Drawer | Details for selected event |
| Related Links | Move to related task/robot |

#### Phase 1 Data Source

The page uses the Control Service TCP/RPC method `caregiver.get_alert_log_bundle`.
The UI must not connect directly to DB or ROS. The bundle contains `summary` and operator-facing `events` from `task_event_log`.
Event table headers, filter labels, and detail keys are operator-facing labels. Raw fields such as `occurred_at`, `source_component`, and `event_type` may remain in the payload, but the UI should show labels such as `Time`, `Source`, and `Event Type`. Event times must use the common operator time format instead of raw ISO `T` strings.

The detail drawer key column must reserve enough width for labels such as `Detailed payload`; value text may wrap, but the key label itself must not be clipped by long payload values. Large payload values must not be squeezed into a single-line value label. Render `payload` as a normal detail key/value row whose key chip uses the same fixed key-column width as the other detail rows, while the value side is a read-only wrapped text area for large warning/error payloads. The payload text area must visually read as the value side of that row, not as a separate full-width box, and it uses the same strong weight and base font as other detail values.

The Alerts/Logs page should subscribe through the administrator IF-COM-003 stream fan-out and refresh when relevant task, alert, robot, or action-feedback events arrive. Stream-triggered refreshes preserve the current filters, are debounced, and queue at most one follow-up refresh while a request is already running.

#### Filters

| Filter | Description |
| --- | --- |
| Period | Today, last 1 hour, last 24 hours, custom |
| severity | INFO, WARNING, ERROR, CRITICAL |
| source_component | UI, Control Service, ROS Adapter, DB Writer, AI Server |
| task_id | Specific task |
| robot_id | Specific robot |
| event_type | TASK_CREATED, TASK_FAILED, CANCEL_REQUESTED, etc. |

Filter changes should refresh the event list without requiring a separate refresh click. Combo-box filters refresh immediately. Text filters use a short debounce while typing, and the event table acts as the search candidate list. `source_component`, `robot_id`, and `event_type` text filters use partial matching so operators can type a few characters and see candidate events. `task_id` remains an exact numeric ID filter. If a new filter change happens while a server request is already running, the UI must queue one follow-up refresh with the latest filter values after the current request finishes.

#### Severity Baseline

| severity | Judgment baseline |
| --- | --- |
| INFO | Normal operational flow, user action, task creation/completion |
| WARNING | Recoverable but operator-relevant delay, temporary communication error, low stock |
| ERROR | Task failure, command failure, DB write failure, ROS action failure |
| CRITICAL | Safety issue, emergency call, system-wide operation unavailable |

Humans do not manually decide severity every time. The server and each component determine severity based on event type and result, and the UI displays the result.

#### Event Logs vs. Data Logs

In the UI, operator-facing event logs are prioritized.

- Event logs: user actions, command sends, task status changes, failure reasons
- Data logs: robot status samples, position, sensors, AI stream metrics

In the operator screen, data logs are provided only as summaries or detailed diagnosis links. If all raw data logs are exposed in a table, operators may miss important events.

---

### 7-10. System Status Page

#### Purpose

Allow operators to check the status of Control Service, DB, ROS2, AI Server, and robot connections in one place.

In phase 1, this page is removed from the administrator sidebar. Its scope is absorbed into the Home dashboard heartbeat status chips, Robot Status page, and Alerts/Logs page. Keep this section only as a future diagnostics reference for phase 2 or later.

#### Screen Composition

| Area | Components |
| --- | --- |
| Service Health Cards | Control Service, DB, ROS2, AI Server status |
| Runtime Config Summary | Current server host/port, DB name, robot config summary |
| Recent Health Events | Disconnection, reconnection, timeout events |
| Manual Check Actions | Recheck status, move to logs screen |

#### Display Fields

| Field | Description |
| --- | --- |
| `component_name` | Control Service, MariaDB, ROS2, AI Server, etc. |
| `status` | ONLINE, OFFLINE, DEGRADED, UNKNOWN |
| `last_checked_at` | Last checked time |
| `latency_ms` | Response time when measurable |
| `message` | Status description |

This screen is not a screen for directly modifying settings. `.env` or deployment setting changes are not handled in the phase 1 administrator UI. Operators check status here, and if there is a problem, check alerts/logs or the external runtime environment.

---

## 8. Interaction Policy

### 8-1. UI During Requests

During server requests, the same request button must not be clickable repeatedly.

Example:

```text
Item delivery request
-> Sending request...
-> Accepted or failed
```

Delivery requests use an idempotency key, but the UI must still prevent duplicate clicks. Idempotency protects against network retries, while button disabling protects user experience.

The server query and submit workers on the task request screen must not block the PyQt UI thread, and worker threads running when the screen closes must be cleaned up.
If item list query fails, retry must be possible when re-entering the same screen or refreshing. Failure state must not be fixed by an internal loaded flag.
Option query loading state should be managed by explicit states such as `idle`, `loading`, `loaded`, and `failed`, not a boolean flag. Retry after failure, duplicate-query prevention after success, and manual refresh behavior should be determinable from the state value alone.

### 8-2. Failure Messages

Failure messages show both human-readable messages and machine-readable codes.

```text
Request failed
reason_code: ROBOT_UNAVAILABLE
Message: No delivery-capable robot is currently available.
```

Do not hide `reason_code`. It is needed for operational issue analysis and team debugging.

### 8-3. Cancellation UX

Cancellation is a risky action.

Recommended UX:

1. Click cancel button
2. Show confirmation dialog
3. Send cancel request
4. Display `CANCEL_REQUESTED` status
5. Display final `CANCELLED` or `CANCEL_FAILED`

The cancellation confirmation dialog includes the following information.

- `task_id`
- Current status
- Assigned robot
- Current phase

### 8-4. Empty State

When there is no data, do not show only an empty table.

Example:

```text
There are no tasks currently in progress.
To request a new task, go to [Task Request].
```

### 8-5. Preparing Features

Do not just disable buttons for features that are not ready. Explain why they are unavailable and what alternative is available.

Example:

```text
Patrol request is not yet connected to the server workflow.
You can check currently submittable scenarios on the Task Request screen.
```

---

## 9. Data Display Rules

### 9-1. ID Display

| ID | Display rule |
| --- | --- |
| `task_id` | Can be displayed as `#1001`, but original value is numeric |
| `item_id` | Not shown on the task request screen; used only for payload and internal tracking |
| `caregiver_id` | Displayed in top user information or detail panel |
| `assigned_robot_id` | Clearly shown on task cards and robot cards |

### 9-2. Time Display

For operational screens, it is useful to display both relative and absolute time.

Example:

```text
Just now
2026-04-28 14:31:05
```

In narrow tables, display only absolute time; add relative time in the detail panel.

The common absolute format for operator-facing admin UI is `YYYY.MM.DD HH:mm`. Date-only values use `YYYY.MM.DD`. Do not show raw ISO separators such as `T`, timezone suffixes, or fractional seconds in visible table cells, cards, text boxes, or key/value detail rows.

### 9-3. Status Display

Keep DB/API raw status values, but show English helper labels on screen as well.

Example:

```text
RUNNING
In progress
```

To consider both operator education and developer debugging, do not completely hide the original enum.

### 9-4. Key/Value Detail Display

Operator-facing detail panels must not render primary data as raw multi-line strings such as `robot_id: pinky2` or `status: ONLINE`. Use `KeyValueRow`-style rows where the key is visually distinct from the value through a compact badge, font weight, and color.

Tables may keep raw column values for density. Detail panels, side panels, robot cards, request previews, result panels, active map summaries, warning lists, and related-object panels should use separated key/value labels. Raw exception text or payload JSON may remain visible only as muted detail text after an operator summary.

---

## 10. Improvements Compared to Current Implementation

The following items should be improved in the current implementation under the administrator UI design baseline.

| Item | Current | Improvement direction |
| --- | --- | --- |
| Theme | Pale blue/white card-centered | Organize into an operational console tone with stronger status contrast |
| Home refresh | Entry/manual load centered | Initial snapshot + IF-COM-003 push-triggered refresh/reflection |
| Robot status | Sidebar entry structure exists, but detailed runtime data integration is limited | Align per-robot connection/battery/location/current task data with server response and IF-COM-003 robot runtime events |
| Task monitor | Separate page and patrol fall-response UI exist | Reinforce filters, cancel/stop actions, and delivery/guide detail sections |
| Alerts/logs | Mock list centered | Change to severity/filter/detail structure |
| Request response display | Basic success message centered | Explicitly display `task_id`, `assigned_robot_id`, `reason_code` |
| Cancellation | Server function exists, UI exposure is insufficient | Display cancellable state from task card/detail panel |
| Patrol/guide/follow | Patrol has phase 1 integration/UI; guide needs kiosk integration reinforcement; follow is preparing | Organize exposure state and input structure according to admin/kiosk completion scope |
| Wireframe brand | Mixed `RoboCare OS`, `Operational Console` | Unify as `ROPI` |
| Wireframe shell | Sidebar/topbar duplicated per page | Integrate into common `AdminShell` |
| Top nav | Service labels placed like nav | Change to `SystemStatusStrip` status chips |
| Sidebar width | Mixed 260px/280px | Unify to 260px baseline |
| Safety action | `Manual Override` appears as active button | Remove or disable until backend safety functionality exists |

---

## 11. Phase 1 Screen Priority

Phase 1 actual implementation priority is based on completing the administrator UI and kiosk UI. Mobile apps or separate visitor `user_ui` productization are not included in this document's phase 1 completion scope.

| Priority | Screen | Reason |
| --- | --- | --- |
| 1 | Home dashboard | Starting point for viewing operational status across all scenarios |
| 2 | Task request | Provides common task creation structure and currently submittable scenarios |
| 3 | Task monitor | Needed for cancellation, failure, and progress tracking |
| 4 | Coordinate/zone settings | Enables DB-based coordinate adjustment for delivery/patrol demos without SQL/.env edits |
| 5 | Robot status | Check robot connection/battery/task state |
| 6 | Alerts/logs | Issue analysis and operational log check |
| 7 | Inventory management | Directly connected to current delivery scenario input data |
| 8 | Resident information | Base data connected to guide/visitor UI |
| 9 | Kiosk home/search/guide/staff call | Visitor-facing product entry point and separate app from admin UI |

Delivery currently has high implementation priority, but the center of the overall UI information architecture is not a specific scenario; it is `task`, `robot`, `event`, `member`, and `inventory`.

---

## 12. Wireframe Creation Baseline

Wireframes must include the following deliverables.

- Administrator login screen
- Home dashboard
- Task request page
- Task monitor page
- Coordinate/zone settings page
- Robot status page
- Inventory management page
- Resident information page
- Alerts/logs page
- System status page is excluded from phase 1; keep the wireframe only as a phase 2 diagnostics reference
- Common component style guide
- State examples by status: loading, empty, error, success, disabled

Each page must express at least the following.

- Page purpose
- Primary user actions
- Main data fields
- Success state
- Failure state
- Empty state
- Server connection failure state
- Next screen navigation

### 12-1. Current Wireframe Application Priority

The current administrator wireframes in `wireframes/stitch_carebot_operations_dashboard/` are applied according to the following baseline.

| Wireframe | Application baseline |
| --- | --- |
| `login` | Reference only central login card and server status card. Remove inactive sidebar/topbar |
| `operational_dashboard` | Reference KPI, robot board, timeline, and task flow board layout |
| `task_request_ui_sync` | Adopt as task request baseline |
| `task_request` | Duplicate proposal. Reference only necessary detailed cards and do not use as baseline |
| `task_monitor` | Reference table/detail panel/timeline structure |
| `robot_status` | Reference map placeholder, fleet card, and robot detail panel structure |
| `inventory_management` | Reference inventory table, low-stock, and edit form structure |
| `senior_info` | Reference search result, preference, event, and prescription card structure |
| `logs_notifications` | Reference filter, event table, and detail drawer structure |
| `system_health` | Phase 2 diagnostics reference only; do not add it to the phase 1 sidebar |

Use the wireframe color tone and card composition as reference. However, shell, brand, top nav, sidebar, font, and dark mode are normalized according to this design document.

### 12-2. Normalization Rules When Porting HTML/Tailwind to PyQt

When porting HTML/Tailwind wireframes to PyQt, follow these rules.

| HTML/Tailwind element | PyQt conversion baseline |
| --- | --- |
| Page-level `<aside>` | Single common `AdminSidebar` component |
| Page-level `<header>` topbar | Remove. Move necessary information to `PageHeader` |
| Top nav service labels | `SystemStatusStrip` status chips |
| `RoboCare OS` | `ROPI` |
| `Operational Console` | Remove or replace with page-specific English title |
| `fixed`, `sticky` layout | `QHBoxLayout`, `QVBoxLayout`, `QGridLayout`, `QScrollArea` |
| Card `<div>` | `QFrame` |
| Tailwind grid | `QGridLayout` |
| Tailwind flex row/col | `QHBoxLayout`, `QVBoxLayout` |
| Table | `QTableWidget` or `QTableView` |
| Badge/chip | `QLabel` + QSS objectName |
| Icon | Local SVG/QIcon or text label |
| Dark mode class | Remove |

Implementers must not copy the HTML structure as-is. Analyze only the body content of each page, and use the common layout and common components from `CaregiverMainWindow` for the shell.

If Qt default subcontrols remain in input controls, they visually deviate from the wireframe. Therefore, explicitly define `QComboBox::drop-down`, `QComboBox::down-arrow`, `QComboBox QAbstractItemView`, `QSpinBox::up-button`, `QSpinBox::down-button`, `QSpinBox::up-arrow`, and `QSpinBox::down-arrow` in QSS. Use local SVG icons, and resolve them as absolute paths during stylesheet loading so execution location does not matter.

### 12-3. PyQt Common Component Implementation Order

When implementing the wireframes as actual PyQt UI, build common components before pages.

Recommended order:

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

Without common shell and components, page-level implementations will diverge. Therefore, individual pages must not directly create their own sidebar, topbar, or status chip.

### 12-4. Wireframe Review Checklist

Wireframe or PyQt implementation results must pass the following checklist.

| Item | Baseline |
| --- | --- |
| Brand | Only `ROPI` is displayed on screen |
| Prohibited brands | `RoboCare OS`, `CareBot`, and `Operational Console` are not displayed |
| Navigation | Page navigation is handled only by the left sidebar |
| Service status | Control Service, DB, ROS2, and AI Server are displayed only as status chips |
| Sidebar | Menu names, order, and width are the same across all administrator pages |
| Topbar | There is no independent top nav bar |
| Font | Pretendard/Noto Sans KR baseline |
| Dark mode | No dark mode class/style exists in phase 1 administrator screens |
| Unsafe action | Backend-less `Manual Override` is not active |
| PyQt feasibility | Structure is implementable with `QLayout`, `QFrame`, `QStackedWidget`, and `QScrollArea` |

---

## 13. Visitor Kiosk UI Scope

The visitor kiosk UI is designed as a separate app from the administrator/control-operator UI.

If the administrator UI is for operational control and task tracking, the kiosk UI is for visitors in the facility lobby to perform visit registration, resident lookup, robot guide request, and staff call within a short time.

The core goals of the kiosk UI are as follows.

- Visitors must be able to choose the action they need from the first screen without separate training.
- Input steps should be short, and touchable buttons must be large enough.
- Visitor personal information and resident personal information must not be exposed excessively.
- Robot guide availability and staff call status must be communicated clearly.
- Even when an error occurs, visitors must understand the next action.

Under the product baseline, the kiosk app does not include administrator login, administrator sidebar, task monitor, inventory management, or operational logs.

For robot guidance, the kiosk is a **pre-driving handoff UI**. It shows visit registration, guide task creation, Pinky movement to the kiosk/guide-start side, target acquisition, and the guide-driving start button. Once `START_GUIDANCE` is accepted, the visitor leaves with the robot, so the kiosk should clear the visitor session and return to Home instead of showing post-start runtime phases. Rejection/failure before acceptance remains visible on the kiosk because the visitor can still retry, cancel, or call staff there.

The guide-driving start button is enabled only when the latest Control-facing guide phase is `READY_TO_START_GUIDANCE` and the kiosk has a valid numeric `target_track_id >= 0`. A target ID alone is not enough, and a ready phase without a target ID is not enough.

---

## 14. Current Kiosk Implementation Baseline

Current code has partially implemented kiosk home, resident search, guide confirmation, and guide progress screens under `ui/kiosk_ui`. Existing visitor-facing screens also remain under `ui/user_ui`, but the phase 1 product completion baseline is to complete `ui/kiosk_ui` as a separate app.

Unify the product design name as `Kiosk UI`. If needed, reference existing implementations in `ui/user_ui` and `ui/utils/pages/visitor` or absorb them into common components, but the final entry point is organized around `ui/kiosk_ui/main.py` and `KioskHomeWindow`.

Current visitor UI-related files are as follows.

| Screen | Current code location | Current state |
| --- | --- | --- |
| Kiosk home/search/guide flow | `ui/kiosk_ui/main_window.py` | Home action cards, resident search, guide confirmation, and guide progress screen partially exist |
| Existing visitor home | `ui/user_ui/main_window.py` | Resident lookup and staff call action cards exist. Not the phase 1 product entry point |
| Visit guide | `ui/utils/pages/visitor/visit_guide_page.py` | Resident search and robot guide start structure exists |
| Staff call | `ui/utils/pages/visitor/staff_call_page.py` | Call type, detail input, and submit structure exists |
| Visitor registration | `ui/utils/pages/visitor/visitor_register_page.py` | Registration form exists, but current main window connection is weak |

Related service clients are as follows.

| Function | Service client |
| --- | --- |
| Resident search / guide start | `VisitGuideRemoteService` |
| Visitor information query | `VisitorInfoRemoteService` |
| Visitor registration | `VisitorRegisterRemoteService` |
| Staff call | `StaffCallRemoteService` |

Kiosk UI design and implementation are based on the separate `kiosk_ui` app. `user_ui` is treated as a reference implementation or a later cleanup target.

---

## 15. Kiosk Users and Operating Environment

### 15-1. Primary Users

The primary users of the kiosk are visitors.

Visitors do not need to know the system structure, robot status, or task status enums. The screen must answer the following questions.

- Where should I start?
- Can I find the resident?
- Is visit registration needed?
- Can a robot guide me?
- Can I call staff if I need help?
- Has my request been accepted?
- If it failed, what should I do?

### 15-2. Operating Environment

The kiosk targets a touchscreen located in a lobby or reception space.

| Item | Baseline |
| --- | --- |
| Baseline resolution | 1920x1080 |
| Minimum resolution | 1280x800 |
| Input method | Touch first; keyboard/mouse if needed |
| Operation mode | Full-screen recommended |
| Touch target | Main buttons at least 72px high |
| Body text | At least 18px |
| Primary action text | 24-32px recommended |
| Idle timeout | Return to home after 60 seconds of inactivity recommended |

Unlike the administrator UI, do not increase information density. Put only one main action on one screen, and limit choices to roughly 2-4.

---

## 16. Kiosk Design System

### 16-1. Visual Direction

The kiosk UI should feel closer to a warm guidance desk.

Unlike the administrator UI's control-console tone, use large whitespace, high readability, soft colors, and clear guidance copy so visitors do not feel tense.

### 16-2. Color Tokens

| Token | Color | Use |
| --- | --- | --- |
| `kiosk-bg` | `#FFF8EE` | Entire kiosk background |
| `kiosk-surface` | `#FFFFFF` | Cards and input areas |
| `kiosk-text-primary` | `#1E293B` | Primary text |
| `kiosk-text-secondary` | `#64748B` | Description text |
| `kiosk-primary` | `#2F855A` | Default primary action |
| `kiosk-guide-blue` | `#2B6CB0` | Robot guide and informational actions |
| `kiosk-coral` | `#E76F51` | Staff call and caution actions |
| `kiosk-warning` | `#F59E0B` | Waiting and confirmation-needed states |
| `kiosk-danger` | `#DC2626` | Failure and emergency |
| `kiosk-border` | `#E8DED2` | Card border |

### 16-3. Fonts

Use Pretendard as the default, the same as the administrator UI.

The kiosk must be readable from a distance, so avoid small text.

| Use | Size baseline |
| --- | --- |
| Home main title | 40-56px |
| Page title | 32-44px |
| Action card title | 28-36px |
| Button text | 24-30px |
| Description text | 18-22px |
| Secondary information | 16-18px |

Font loading uses the same approach as the administrator UI: load fonts from app assets using `QFontDatabase.addApplicationFont()`.

### 16-4. Common Components

| Component | Purpose |
| --- | --- |
| `KioskRoot` | Full-screen background and overall spacing |
| `KioskHeader` | Current step, home button, back button |
| `LargeActionCard` | Select main action on Home |
| `StepIndicator` | Current step in visit registration/guide request |
| `LargeInputField` | Large touch-oriented input field |
| `PrimaryTouchButton` | Primary submit/next button |
| `SecondaryTouchButton` | Back/retry button |
| `CallStaffButton` | Fixed auxiliary staff-call action |
| `ResultStatePanel` | Success/failure/waiting result display |
| `IdleWarningDialog` | Guidance before returning home after inactivity |

---

## 17. Kiosk Navigation Structure

The kiosk does not use a left sidebar.

The base structure is as follows.

```text
Kiosk App
-> Home
   -> Visitor Registration
   -> Resident Search
      -> Guide Confirmation
      -> Robot Guidance Progress
   -> Staff Call
```

The top area always provides the following actions.

| Action | Baseline |
| --- | --- |
| Home | Provided on every page |
| Back | Provided on most pages except Home |
| Staff call | Emphasized on Home or when guide fails/robot unavailable |

The kiosk does not directly show complex task enums to visitors. However, for debugging and operational tracking, a small `request number` or `task_id` may be displayed at the bottom of the completion screen.

---

## 18. Kiosk Page Design

### 18-1. Kiosk Home

#### Purpose

This is the first screen visitors see. Visitors must be able to choose what they need within 3 seconds.

#### Screen Composition

| Area | Components |
| --- | --- |
| Welcome Header | Facility name, `How can we help you?` |
| Main Actions | Visit registration, staff call |
| Info Strip | Current location, operating hours, guide robot status |
| Footer | Privacy notice, version/connection status summary |

#### Wireframe Porting Baseline

The phase 1 PyQt home screen follows the visual language of
`wireframes/stitch_ropi_kiosk_visitor_service/kiosk_home`.

When porting the wireframe to PyQt, preserve the warm information-desk theme,
the large top app bar, the centered welcome message, the two oversized action
cards, and the bottom information bar. Normalize wireframe-only English copy
such as `Call Staff`, `Current Location`, `Hours`, and `Robot: Ready` into
Korean visitor-facing labels. Remove duplicate micro CTAs inside action cards;
the whole card is the touch target.

#### Main Actions

| Action | Destination |
| --- | --- |
| Visit registration | Visitor Registration |
| Staff call | Staff Call |

The Home screen does not expose a separate `Find resident` action in phase 1.
Resident lookup is only available inside Visitor Registration after the visitor
has filled the required visitor fields and privacy consent. The flow must not
call the legacy guide-search API.

#### States

| State | UI expression |
| --- | --- |
| Normal | All 3 action cards enabled |
| Server connection failure | Actions disabled or limited; emphasize staff-call guidance |
| Robot guide unavailable | Resident search remains possible; guide card displays `Guide robot is currently under inspection` |
| Outside operating hours | Center guidance on visit registration/staff call |

---

### 18-2. Visitor Registration Page

#### Purpose

The visitor enters their own information, privacy consent, and target resident
selection in one page. This page is the phase 1 kiosk login boundary: successful
submission creates or reuses the `visitor` row and stores `visitor_id` in the
Kiosk App process memory.

#### Screen Composition

| Area | Components |
| --- | --- |
| Step Header | `Visit Registration` title, 1-2 step display |
| Visitor Form | Name, phone number, relationship, visit-purpose selection cards |
| Target Resident Search | Resident keyword input, candidate list, selected resident summary |
| Privacy Notice | Personal information collection notice and consent |
| Action Row | Previous, Register |

#### Input Fields

| Field | Description |
| --- | --- |
| `visitor_name` | Visitor name |
| `phone_no` | Phone number |
| `visit_purpose` | Selected visit-purpose card value |
| `relationship` | Family, acquaintance, other |
| `privacy_agreed` | Privacy consent |
| `target_member_id` | Hidden selected resident ID from the embedded search result |

#### Visit Purpose Selection

The visit purpose follows the visitor-registration wireframe and is selected
through large icon cards rather than typed as a free-text input.

| Rule | Description |
| --- | --- |
| Options | Family visit, acquaintance/friend visit, consultation/inquiry, other |
| Interaction | Selecting one card marks it as selected and stores `visit_purpose` |
| Validation | Resident search and final registration remain disabled until one purpose card is selected |
| Touch target | Each purpose card must be at least kiosk touch-target height and include an icon plus label |

#### Validation Rules

| Condition | UI behavior |
| --- | --- |
| Missing name | `Please enter your name.` |
| Missing phone number | `Please enter your phone number.` |
| Privacy consent not checked | `Privacy consent is required for visit registration.` |
| Resident not selected | `Please select the resident you are visiting.` |
| Server failure | Keep input values and provide staff-call guidance |

#### Embedded Resident Search

The target resident search is part of the registration form, not a separate
page.

| Rule | Description |
| --- | --- |
| Activation | Enable search after required visitor fields and privacy consent are present |
| Query | Use `IF-GUI-008` with `keyword` and `limit`; do not use legacy guide-search API |
| Candidate display | Show `display_name`, `birth_date`, and `room_no` to the visitor |
| Hidden state | Keep `member_id`, `visit_available`, and `guide_available` as internal selection state |
| Selection | Selecting a candidate stores `target_member_id` and shows a compact selected-resident summary |

#### Success State

On successful `IF-GUI-009` registration, display the following and keep
`visitor_id` only in Kiosk App process memory.

```text
Visit registration is complete.
You can start robot guidance or view allowed care information if needed.
```

---

### 18-3. Embedded Resident Search Section

#### Purpose

Removed as a standalone phase 1 page. Resident lookup is embedded in Visitor
Registration.

#### Screen Composition

| Area | Components |
| --- | --- |
| Search Header | Replaced by Visitor Registration step/section header |
| Search Form | Embedded target-resident search section |
| Result Area | Candidate list inside Visitor Registration |
| Action Row | Visitor Registration action row |

#### Wireframe Porting Baseline

Use the visual treatment from
`wireframes/stitch_ropi_kiosk_visitor_service/resident_search` for the embedded
search block: large search input, icon-only green search button, person icon in
candidate cards, bold candidate name, and clear selected state. Normalize it to
fit inside Visitor Registration rather than keeping the page-level header/footer.

#### Input Fields

| Field | Description |
| --- | --- |
| `keyword` | Name or room number |
| `target_member_id` | Hidden selected resident ID |

#### Result Card

To protect personal information, result cards display only the minimum necessary information.

| Field | Display method |
| --- | --- |
| `member_id` | Hide on screen or display only as a small request number |
| `display_name` | Show first and last character with middle masked |
| `birth_date` | Display for disambiguation |
| `room_no` | Display because the same search field accepts room-number fragments |
| `visit_available` | Visit availability |
| `guide_available` | Robot guide availability |

#### States

| State | UI expression |
| --- | --- |
| Missing visitor fields/privacy consent | Disable resident search and show the required input guidance |
| Before search | Large input field inside Visitor Registration and example copy |
| Searching | `Searching for resident information.` |
| Results found | Candidate list inside Visitor Registration |
| No results | `No matching information was found.` + staff call |
| Visit restricted | Do not expose excessive restriction reason; guide user to ask staff |

Submitting the Visitor Registration form finalizes the visit through
`IF-GUI-009`. After that point, the kiosk may offer guide start and visitor
care-history lookup because it has a registered `visitor_id`.

---

### 18-4. Guide Confirmation Page

#### Purpose

Get final confirmation before starting robot guidance for the searched resident or destination.

#### Screen Composition

| Area | Components |
| --- | --- |
| Target Summary | Selected visit target or destination |
| Robot Availability | Guide robot availability |
| Guide Notice | Precautions when following the robot |
| Action Row | Start guidance, Call staff, Back |

#### Display Fields

| Field | Description |
| --- | --- |
| `member_id` | Internal request value; minimal screen exposure |
| `destination_id` | Guide destination |
| `destination_label` | Human-readable destination |
| `guide_available` | Whether guidance is available |
| `assigned_robot_id` | Displayed after guide start |

#### Guide Start Response

Guide task creation or guide start response uses the following information.

| Field | Display method |
| --- | --- |
| `result_code` | Success/rejection status |
| `result_message` | Visitor-facing copy |
| `reason_code` | For operator checking; hidden from visitor screen when appropriate |
| `task_id` | Display as a small request number |
| `assigned_robot_id` | Example: `pinky1` |

For visitors, prioritize copy such as `A guide robot has been assigned.` rather than internal enums such as `GUIDE_TASK_ACCEPTED`.

---

### 18-5. Robot Guidance Progress Page

#### Purpose

After a robot guidance request, help visitors understand current status and available next actions until guidance driving starts.

Scope boundary:

- The kiosk owns `visit registration -> guide task creation -> robot arrival at the kiosk -> target tracking acquisition -> guide driving start`.
- After guide driving starts, guide interaction such as target loss recovery, re-identification, and care-history display is owned by the Pinky-mounted Display App.
- The kiosk progress screen must not depend on a successful ROS command to enter the progress state. Once the DB-backed guide task is accepted, the progress screen can be shown; robot command failures are displayed as status/warning text while keeping the visitor in the guide flow.
- While the task stays in a pre-driving phase such as `WAIT_GUIDE_START_CONFIRM` or `WAIT_TARGET_TRACKING`, the progress screen must keep showing the latest rejected guide result from the task status payload (`task_outcome`/`latest_reason_code`/`result_message`) until a newer state clears it. A normal tracking snapshot must not overwrite this warning text, though it may still enable a retry when `tracking_status=TRACKING` and `active_track_id` is present.

#### Screen Composition

| Area | Components |
| --- | --- |
| Progress Header | `Preparing your guidance` or `Please follow the robot` |
| Robot Card | Assigned robot, current status |
| Progress Steps | Request accepted, robot moving, guide started, moving, arrived |
| Safety Notice | Notice to keep proper distance from the robot |
| Action Row | Call staff, Stop guidance, Home |

#### States

| Status | Visitor-facing copy |
| --- | --- |
| `WAITING_DISPATCH` | `Your guidance request has been accepted.` |
| `ASSIGNED` | `A guide robot has been assigned.` |
| `RUNNING` | `Please follow the robot.` |
| `COMPLETED` | `You have arrived at your destination.` |
| `FAILED` | `Guidance could not be started. Please ask staff for help.` |
| `CANCELLED` | `Guidance has been stopped.` |
| pre-driving latest `REJECTED` | Show the server `result_message`; use a short fallback based on `latest_reason_code` if no message is present. |

#### Feedback Display

Do not expose detailed ROS feedback as-is on the visitor screen.

Displayable summaries:

- The robot is moving.
- Please wait a moment.
- We have arrived near the destination.
- Please follow the robot to continue guidance.

---

### 18-6. Staff Call Page

#### Purpose

Allow visitors to request help directly.

#### Screen Composition

| Area | Components |
| --- | --- |
| Header | `Call Staff` |
| Quick Reason Buttons | Directions, help with visit registration, visitation inquiry, emergency help, other |
| Optional Detail | Detail input |
| Action Row | Call, Back |
| Result Panel | Call receipt result |

#### Input Fields

| Field | Description |
| --- | --- |
| `call_type` | Call type |
| `description` | Detail content, optional |
| `member_id` | Can be connected if coming from resident search flow |
| `visitor_id` | Can be connected if called after visit registration |

#### States

| State | UI expression |
| --- | --- |
| Before call | Large reason selection buttons |
| Submitting | `Calling staff.` |
| Accepted | `A staff member will arrive shortly.` |
| Failed | `The call failed. Please contact the reception desk.` |

Emergency help uses stronger color and a confirmation dialog than other call reasons. Prevent accidental taps, but still allow quick submission in an actual emergency.

---

### 18-7. Kiosk Error/Waiting Screens

#### Purpose

Guide visitors clearly during network errors, server errors, robot unavailable states, and inactivity timeout situations.

#### Error States

| State | Copy | Next action |
| --- | --- | --- |
| Server connection failure | `The guidance system is currently unavailable.` | Staff call or reception desk guidance |
| Robot guide unavailable | `Robot guidance is currently unavailable.` | Staff call |
| Search failure | `Information could not be loaded.` | Retry, staff call |
| Idle timeout | `Returning to the first screen.` | Return home after 5-second countdown |

#### Idle Timeout

After 60 seconds of no input, display a warning dialog.

```text
Would you like to continue?
If there is no input, we will return to the first screen.
```

If there is no input for 5-10 seconds after the warning, return home and remove any personal information being entered from the screen.

---

## 19. Kiosk Data Display Rules

The kiosk limits personal information exposure more strictly than the administrator UI.

| Data | Display baseline |
| --- | --- |
| `visitor_id` | Can be shown as receipt number on completion screen |
| `member_id` | Default is not to expose directly on screen |
| Resident name | May be partially masked if needed |
| Room number | Display only when needed for guidance |
| `task_id` | Display as `request number` in small text for visitors |
| `assigned_robot_id` | Display as `guide robot` name |
| `reason_code` | Hide from visitor screen and leave in operational logs |

Visitor-facing copy does not show internal enums as-is. For example, display `Your request has been accepted.` instead of `WAITING_DISPATCH`.

---

## 20. Kiosk PyQt Implementation Baseline

The kiosk app is based on the same PyQt6 stack as the administrator app, but its layout strategy differs.

| Implementation element | Baseline |
| --- | --- |
| Screen transition | `QStackedWidget` |
| Home action card | Large `QFrame` or `QPushButton`-based card |
| Input screen | `QVBoxLayout` centered; one purpose per screen |
| Result screen | Large guidance card in `ResultStatePanel` form |
| Idle timeout | `QTimer` |
| Full-screen | `showFullScreen()` or kiosk launch option |
| Touch input | Large inputs and buttons; consider OS virtual keyboard if needed |
| State propagation | Server request/response + guide progress is push-first |

Do not use complex tables in the kiosk. If a list is needed, use card lists and do not display many rows on a single screen.

---

## 21. Kiosk Wireframe Creation Baseline

Kiosk wireframes must include the following deliverables.

- Kiosk home
- Visitor registration page with embedded resident search
- Guide confirmation page
- Robot guidance progress page
- Staff call page
- Error/server connection failure screen
- Idle timeout screen
- Common touch component style

Each page must express at least the following.

- Page purpose
- Primary button the visitor should press
- Input fields
- Success state
- Failure state
- Server connection failure state
- Home/back button positions
- Areas where personal information is exposed and areas where it must be hidden

---

## 22. Product Presentation Admin Demo UI

This section defines the product-facing administrator demo used for the final presentation.
It is separate from the real runtime Admin UI because the real integration environment uses Pinky mobile robots and Jetcobot arms, while the presented product concept exposes one integrated robot product named ROPI.

The demo UI is not a replacement for the production Control Service contract.
It is a presentation shell that reuses the existing Admin visual language while replacing visible robot naming, demo data, and page scope.

### 22-1. Demo Purpose and Boundary

The demo must show a coherent ROPI product operation surface while keeping the current Home demo screen stable.
Home remains a hard-coded presentation snapshot, but Task Request, Task Monitor, and Alerts/Logs must use the same Control Service/DB-backed flow as the Admin UI.

| Item | Demo rule |
| --- | --- |
| Product name | Use `ROPI` as the product/robot family name |
| Robot display names | Use `ROPI 1`, `ROPI 2`, `ROPI 3` in all visible UI |
| Internal robot names | `pinky1`, `pinky2`, `pinky3`, `jetcobot1`, `jetcobot2`, `arm1`, `arm2` may remain only as hidden fixture/internal mapping values |
| Visible pages | Home, Task Request, Task Monitor, Alerts/Logs |
| Hidden pages | Coordinate/Zone Settings, Robot Status, Inventory, Resident Information, System Status, and any other non-demo page |
| Runtime dependency | Home can render without runtime dependencies. Task Request, Task Monitor, and Alerts/Logs require the normal Control Service/DB runtime for live operation; no fake ROS node or demo-only DB connector is introduced |
| Git policy | Demo app, demo fixtures, and demo tests are tracked source files, not ignored local scratch files |
| Run command | Use a page-neutral command such as `uv run ropi-admin-demo`; retire the home-only command name `ropi-admin-home-demo` |

The demo shell should open maximized and keep the same sidebar/header style as Admin UI.
The sidebar should contain only the pages used in the presentation:

- `홈`
- `작업 요청`
- `작업 모니터`
- `알림/로그`

### 22-2. Demo Page Scope

| Page | Demo behavior |
| --- | --- |
| Home | Show operating KPIs, ROPI robot board, PGM operation map with current ROPI markers, compact task flow, and recent timeline |
| Task Request | Reuse the current production Admin Task Request page directly so the form layout, options loading, validation, and submit behavior stay identical, but hide the disabled follow tab in the presentation shell |
| Task Monitor | Reuse the current production Admin Task Monitor page and Control Service stream/snapshot flow, with only product-facing robot display names adapted for presentation |
| Alerts/Logs | Reuse the current production Admin Alerts/Logs page and DB-backed log bundle flow, with only product-facing robot display names adapted for presentation |

Task Request must not be a static mock or in-memory-only workflow.
When the presenter submits a request, the production Admin request page must call the normal Control Service request path.
Task Monitor and Alerts/Logs then observe DB-backed task/log data through their normal Admin UI loading and stream behavior.

### 22-3. Demo Data Model

The demo uses a small in-memory store only for the Home presentation snapshot.
Task Request, Task Monitor, and Alerts/Logs must not use this store as their source of truth.
Their records come from the same Control Service/DB APIs as the production Admin UI.

| Record | Required fields |
| --- | --- |
| DemoRobot | `internal_robot_id`, `display_robot_name`, `task_type`, `status_label`, `location_label`, `battery_percent`, `tone` |
| DemoTask | Home-only presentation task card fields: `task_id`, `task_type`, `status`, `phase`, `assigned_robot_name`, `destination_label`, `summary`, `created_at`, `updated_at` |
| DemoAlertLog | Home-only presentation event fields: `event_id`, `severity`, `event_type`, `task_id`, `robot_name`, `title`, `message`, `occurred_at`, `detail_rows` |
| DemoMapMarker | `robot_name`, `x`, `y`, `yaw`, `task_label`, `tone` |

Task IDs may be presentation IDs such as `#1034`, but raw numeric IDs should remain available internally for compatibility with existing widgets.

### 22-4. ROPI Display Mapping

All visible pages must use the product-facing mapping below.

| Internal runtime role | Hidden internal ID | Visible robot name | Default demo role |
| --- | --- | --- | --- |
| Guide mobile robot | `pinky1` | `ROPI 1` | 안내 |
| Delivery mobile robot | `pinky2` | `ROPI 2` | 운반 |
| Patrol mobile robot | `pinky3` | `ROPI 3` | 순찰 |
| Pickup arm | `arm1` / `jetcobot1` | Do not show as robot | 운반 단계 text only |
| Destination arm | `arm2` / `jetcobot2` | Do not show as robot | 운반 단계 text only |

Delivery UI may say `적재 완료`, `전달 대기`, or `물품 인계 중`.
It must not show `arm1`, `arm2`, `jetcobot1`, or `jetcobot2` as visible device names.

### 22-5. Korean Display Policy

The demo UI should prefer Korean labels and Korean values over raw English enum values.
Raw enum/debug values may be retained only in hidden data or optional developer diagnostics, not in the main presentation surfaces.

| Raw/key value | Demo display |
| --- | --- |
| `task_id` | `작업 ID` |
| `task_type` | `작업 유형` |
| `assigned_robot_id` | `담당 ROPI` |
| `robot_id` | `로봇` or `ROPI` |
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

Known task phases should also be displayed in Korean.

| Raw phase | Demo display |
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

Detail panels must not render raw dictionary strings such as `task_id: 1034` or `assigned_robot_id: pinky2`.
Use key/value rows with Korean keys and product-facing values.

### 22-6. Task Request Demo Flow

Task Request must be the current production Admin UI page, not a simplified presentation form.
It keeps the existing delivery/patrol tabs, option loading, validation, submit result panel, cancel affordance, and Control Service calls.
Guidance remains outside the Admin Task Request page when the production page excludes it.
The presentation shell must hide the disabled `추종` button because it is not part of the final demo flow.

| Request type | Required input | Runtime behavior |
| --- | --- | --- |
| 운반 | Production Admin delivery form inputs | Calls the normal Control Service delivery request path |
| 순찰 | Production Admin patrol form inputs | Calls the normal Control Service patrol request path |
| 안내 | Not shown on this Admin page unless production Admin scope changes | Kiosk/guide flow remains outside this demo page |

The submit result panel is the production Admin result panel.
Do not fork the Task Request UI for the presentation demo.

Product-facing ROPI naming is required on Home, Task Monitor, and Alerts/Logs.
Task Request should remain visually identical to the current Admin page.

### 22-7. Home Demo Requirements

Home should continue the current demo direction.

- Show `ROPI 1`, `ROPI 2`, `ROPI 3`.
- Show current task names as `안내`, `운반`, `순찰`.
- Show DB-backed-looking location labels such as `복도1`, `303호`, `복도3`, `보호사실`, `충전소`.
- Use the real repository PGM/YAML map asset.
- Show three map markers without connecting route lines between robots.
- Keep marker labels small and avoid wall overlap.
- Put operation map and compact task flow in one row.
- Hide the full-width production flow board in the demo first viewport if the compact board is shown.

### 22-8. Task Monitor Demo Requirements

Task Monitor is the main page for proving that the request became an observable DB-backed operation.
The demo page must reuse the production `TaskMonitorPage` behavior, including snapshot refresh, task event stream, cancel/stop actions, patrol runtime detail, and evidence lookup.

It should show:

- Product-facing robot names only: `ROPI 1`, `ROPI 2`, `ROPI 3`.
- Korean display values for common raw codes such as task type, status, phase, result code, reason code, event type, severity, and action feedback state.
- Unknown uppercase snake-case codes and standalone uppercase code tokens should be decomposed into Korean words when possible so fragments such as `WAIT`, `WAITING`, `START`, `CONFIRM`, `TASK`, `WORKFLOW`, `RESULT`, and `UPDATED` do not remain mixed with Korean copy.
- The fall evidence image dialog opened from Task Monitor is also a presentation surface; labels such as `evidence_image_id` and `frame_id`, empty detection text such as `bbox`, and common detection class names such as `fall` and `person` should be displayed in Korean.
- The current production Admin Task Monitor UI structure.
- Live DB-backed tasks loaded through the normal Task Monitor Control Service snapshot.
- Normal task event stream updates when the runtime is available.
- The robot table column should be content-sized and must not consume the remaining table width.

It must not show `pinky`, `jetcobot`, `arm1`, or `arm2` as visible robot/device names.
It should not expose common raw English codes such as `DELIVERY`, `PATROL`, `GUIDE`, `RUNNING`, `REJECTED`, `TASK_UPDATED`, `WORKFLOW_RESULT_RECORDED`, `WAIT_GUIDE_START_CONFIRM`, or raw `*_id`-style payload keys in primary presentation text when a Korean value exists or can be composed from known code fragments.
The ROPI mapping is a presentation display adapter only and must not change Control Service payload keys or DB values.

### 22-9. Alerts/Logs Demo Requirements

Alerts/Logs should make the demo look operational after requests and robot events using the DB-backed production log bundle.
The demo page must reuse the production `AlertLogPage` behavior, including filters, refresh, selected event detail, related task/robot actions, and stream-triggered refresh.

It should show:

- Related robot as `ROPI 1`, `ROPI 2`, or `ROPI 3`.
- Korean display values for severity, event type, result code, reason code, task type, task status, phase, and payload field labels.
- Unknown uppercase snake-case event/reason/workflow codes should be decomposed into Korean words when possible.
- The current production Admin Alerts/Logs UI structure.
- Live DB-backed events loaded through `caregiver.get_alert_log_bundle`.

It must not show `pinky`, `jetcobot`, `arm1`, or `arm2` as visible robot/device names.
Payload details shown in the presentation shell should translate common raw keys such as `task_id`, `assigned_robot_id`, `result_code`, `reason_code`, `task_status`, and `event_type` into Korean labels, and translate uppercase snake-case values instead of leaving mixed English/Korean text.
The ROPI mapping is a presentation display adapter only and must not change Control Service payload keys or DB values.

### 22-10. Implementation and Test Baseline

Implementation should keep demo code separate from production pages as much as practical.

| Area | Baseline |
| --- | --- |
| Package | `ui/presentation_demo` or `ui/admin_demo` |
| Entry point | `ropi-admin-demo` |
| Shell | Reuse `AdminShell` styling, but restrict navigation to demo pages |
| Store | Home-only in-memory presentation snapshot. Task Request, Task Monitor, and Alerts/Logs use production Control Service/DB clients |
| Display adapter | Presentation-only recursive payload adapter maps `pinky1`, `pinky2`, `pinky3` to `ROPI 1`, `ROPI 2`, `ROPI 3`, translates common raw enum/code/key values, and decomposes unknown uppercase snake-case codes plus standalone uppercase code tokens before Monitor/Logs render visible text |
| Table sizing | Presentation Task Monitor keeps the robot column content-sized instead of stretching it |
| Production safety | Do not alter Control Service RPC contracts for demo-only behavior |
| Tracking | Demo source and tests are committed; generated screenshots/exports remain ignored |

Tests should cover:

- Console script exists as `ropi-admin-demo`.
- Demo source directory is not ignored.
- Demo smoke opens without starting a Qt event loop or requiring Control Service. Live request/monitor/log operation requires the normal Control Service/DB runtime.
- Sidebar contains only Home, Task Request, Task Monitor, Alerts/Logs.
- Task Request page is the production Admin Task Request page.
- Task Request hides the disabled follow tab in the presentation shell.
- Task Monitor page is production Admin Task Monitor behavior with ROPI display mapping.
- Alerts/Logs page is production Admin Alerts/Logs behavior with ROPI display mapping.
- Visible robot names are only `ROPI 1`, `ROPI 2`, `ROPI 3`.
- Visible main UI text does not contain `pinky`, `jetcobot`, `arm1`, `arm2`.
- Common raw English codes, unknown uppercase snake-case code fragments, and raw payload key names are translated on Monitor/Logs presentation surfaces.
- Task Monitor robot column remains narrow/content-sized after data is rendered.
- Home operation map loads the repository PGM/YAML and shows three markers.
