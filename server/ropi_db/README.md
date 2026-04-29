# ROPI DB 초기화/더미 데이터 실행

이 폴더는 MariaDB 스키마와 seed 데이터를 관리한다.

## 파일 역할

| 파일 | 역할 |
| --- | --- |
| `init_tables.sql` | 기존 테이블을 drop하고 현재 설계 기준 테이블을 다시 생성한다. |
| `insert_dummies.sql` | 개발/통합 테스트용 seed 데이터를 넣는다. |

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

## 주의사항

- `init_tables.sql`은 drop/create를 수행하므로 기존 데이터가 삭제된다.
- `insert_dummies.sql`은 먼저 관련 테이블을 `DELETE`한 뒤 seed를 넣는다.
- `care_user`가 대상 DB 권한을 가져야 한다.

```sql
GRANT ALL PRIVILEGES ON care_service.* TO 'care_user'@'%';
FLUSH PRIVILEGES;
```
