from server.ropi_main_service.persistence.repositories import task_monitor_repository


class FakeCursor:
    def __init__(self):
        self.calls = []
        self._index = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return {"last_event_seq": 7}

    def fetchall(self):
        return [
            {
                "task_id": 2001,
                "task_type": "PATROL",
                "task_status": "RUNNING",
            }
        ]


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.began = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def begin(self):
        self.began = True

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_task_monitor_repository_reads_watermark_and_tasks_in_one_transaction(
    monkeypatch,
):
    fake_connection = FakeConnection()
    monkeypatch.setattr(
        task_monitor_repository,
        "get_connection",
        lambda: fake_connection,
    )

    result = task_monitor_repository.TaskMonitorRepository().get_task_monitor_snapshot(
        task_types=("PATROL",),
        statuses=("RUNNING", "WAIT_FALL_RESPONSE"),
        limit=25,
    )

    assert result == {
        "last_event_seq": 7,
        "tasks": [
            {
                "task_id": 2001,
                "task_type": "PATROL",
                "task_status": "RUNNING",
            }
        ],
    }
    assert fake_connection.began is True
    assert fake_connection.committed is True
    assert fake_connection.rolled_back is False
    assert fake_connection.closed is True

    watermark_query, watermark_params = fake_connection.cursor_obj.calls[0]
    task_query, task_params = fake_connection.cursor_obj.calls[1]
    assert "MAX(task_event_log_id)" in watermark_query
    assert watermark_params is None
    assert "FROM task t" in task_query
    assert "t.task_type IN (%s)" in task_query
    assert "t.task_status IN (%s, %s)" in task_query
    assert task_params == ("PATROL", "RUNNING", "WAIT_FALL_RESPONSE", 25)


def test_task_monitor_repository_fetches_fall_evidence_alert_candidates(monkeypatch):
    calls = []

    def fake_fetch_all(query, params=None):
        calls.append((query, params))
        return [
            {
                "task_id": 2001,
                "task_type": "PATROL",
                "alert_id": 17,
                "payload_json": {"trigger_result": {"evidence_image_id": "img-1"}},
            }
        ]

    monkeypatch.setattr(task_monitor_repository, "fetch_all", fake_fetch_all)

    rows = task_monitor_repository.TaskMonitorRepository().get_fall_evidence_alert_candidates(
        task_id=2001,
        limit=20,
    )

    assert rows[0]["alert_id"] == 17
    query, params = calls[0]
    assert "FROM task t" in query
    assert "LEFT JOIN task_event_log tel" in query
    assert "FALL_ALERT_CREATED" in query
    assert params == (2001, 20)
