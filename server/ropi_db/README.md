# ROPI DB 초기화/더미 데이터 실행

이 폴더는 MariaDB 스키마와 seed 데이터를 관리한다.

## 파일 역할

| 파일 | 역할 |
| --- | --- |
| `init_tables.sql` | 기존 테이블을 drop하고 현재 설계 기준 테이블을 다시 생성한다. |
| `insert_dummies.sql` | 개발/통합 테스트용 seed 데이터를 넣는다. |
| `ropi-db-migrate-multimap` | 기존 DB를 멀티맵 좌표 설정 계약으로 보정하는 CLI. |

## 실행 방법

SQL 파일 안에서 DB 이름을 고정하지 않는다. 실행할 때 대상 DB를 명시한다.

```bash
mysql -u care_user -p care_service < server/ropi_db/init_tables.sql
mysql -u care_user -p care_service < server/ropi_db/insert_dummies.sql
```

검증용 임시 DB를 사용할 때만 `.env`의 `DB_NAME`을 별도 DB명으로 바꾼다. 기본 개발 DB명은 `care_service`다.

```dotenv
DB_NAME=care_service
```

## 기존 DB 멀티맵 마이그레이션

이미 운영/개발 중인 DB를 drop하지 않고 현재 멀티맵 좌표 계약으로 맞출 때 사용한다.

```bash
uv run ropi-db-migrate-multimap
uv run ropi-db-migrate-multimap --apply
```

첫 명령은 dry-run이며 실행할 step만 출력한다. 두 번째 명령이 실제 DB에 적용한다.

적용 내용:

- `map_0504`, `map_test12_0506` map profile 보장
- 삭제된 `map_test11_0423` 참조 재매핑
  - DELIVERY task와 운반 goal pose: `map_test12_0506`
  - PATROL/GUIDE/default 좌표 데이터: `map_0504`
- `operation_zone` primary key를 `(map_id, zone_id)`로 보정
- `goal_pose(map_id, zone_id)` -> `operation_zone(map_id, zone_id)` 복합 FK 보정
- 운반팀 `room1`/`room2`/`home` 좌표를 관제 ID `pickup_supply`/`delivery_room_301`/`dock_home`에 반영
- 기존 `map_test11_0423` map profile 삭제

마이그레이션 성공 후 `ropi_schema_migration`에 적용 이력을 남긴다. 이미 적용된 DB에서는 기본 실행이 no-op이며, 재실행이 꼭 필요할 때만 `--force --apply`를 사용한다.

## 주의사항

- `init_tables.sql`은 drop/create를 수행하므로 기존 데이터가 삭제된다.
- `insert_dummies.sql`은 먼저 관련 테이블을 `DELETE`한 뒤 seed를 넣는다.
- `care_user`가 대상 DB 권한을 가져야 한다.

```sql
GRANT ALL PRIVILEGES ON care_service.* TO 'care_user'@'%';
FLUSH PRIVILEGES;
```
