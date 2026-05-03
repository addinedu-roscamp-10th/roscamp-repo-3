import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QFrame


_APP = None
REPO_ROOT = Path(__file__).resolve().parents[3]
INVENTORY_PAGE = (
    REPO_ROOT / "ui" / "utils" / "pages" / "caregiver" / "inventory_management_page.py"
)


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def _bundle():
    return {
        "summary": {
            "total_item_count": 3,
            "total_quantity": 33,
            "low_stock_item_count": 2,
            "empty_item_count": 1,
            "low_stock_threshold": 10,
            "last_updated_at": "2026-05-03T11:00:00",
        },
        "items": [
            {
                "item_id": "1",
                "item_type": "생활용품",
                "item_name": "기저귀",
                "quantity": 0,
                "updated_at": "2026-05-03T10:00:00",
            },
            {
                "item_id": "2",
                "item_type": "생활용품",
                "item_name": "물티슈",
                "quantity": 8,
                "updated_at": "2026-05-03T11:00:00",
            },
            {
                "item_id": "3",
                "item_type": "식료품",
                "item_name": "두유",
                "quantity": 25,
                "updated_at": "2026-05-03T09:00:00",
            },
        ],
        "low_stock_items": [
            {"item_id": "1", "item_name": "기저귀", "quantity": 0},
            {"item_id": "2", "item_name": "물티슈", "quantity": 8},
        ],
    }


def test_inventory_management_page_matches_phase1_layout_contract():
    _app()

    from ui.utils.pages.caregiver.inventory_management_page import (
        InventoryManagementPage,
    )

    page = InventoryManagementPage(autoload=False)

    try:
        labels = _label_texts(page)
        refresh_buttons = [
            button
            for button in page.findChildren(QPushButton)
            if button.property("inventory_action") == "refresh"
        ]

        assert "재고 관리" in labels
        assert "전체 품목" in labels
        assert "총 수량" in labels
        assert "부족 재고" in labels
        assert "품절" in labels
        assert "보급품 현황" in labels
        assert "재고 상세" in labels
        assert "재고 추가 / 직접 수정" in labels
        assert "부족 재고 경고" in labels
        assert "새로고침" in [button.text() for button in refresh_buttons]
    finally:
        page.close()


def test_inventory_management_page_applies_bundle_to_summary_table_detail_and_warning_panel():
    _app()

    from ui.utils.pages.caregiver.inventory_management_page import (
        InventoryManagementPage,
    )

    page = InventoryManagementPage(autoload=False)

    try:
        page.apply_inventory_bundle(_bundle())

        labels = _label_texts(page)
        assert "3종" in labels
        assert "33개" in labels
        assert "2종" in labels
        assert "1종" in labels
        assert page.table.rowCount() == 3
        assert page.table.item(0, 0).text() == "1"
        assert page.table.item(0, 1).text() == "생활용품"
        assert page.table.item(0, 2).text() == "기저귀"
        assert page.table.item(0, 3).text() == "0"
        assert page.item_combo.itemData(0) == "1"

        page.table.selectRow(1)
        page._handle_table_selection()

        labels = _label_texts(page)
        assert "선택 물품" in labels
        assert "물티슈" in labels
        assert "현재 수량" in labels
        assert "8개" in labels
        assert "기저귀" in labels
        assert "0개" in labels
        assert page.findChildren(QFrame, "keyValueRow")
        assert not any("선택 물품: 물티슈" in text for text in labels)
        assert not any("기저귀: 0개" in text for text in labels)
    finally:
        page.close()


def test_inventory_management_page_collects_item_id_based_adjust_payloads():
    _app()

    from ui.utils.pages.caregiver.inventory_management_page import (
        InventoryManagementPage,
    )

    page = InventoryManagementPage(autoload=False)

    try:
        page.apply_inventory_bundle(_bundle())
        page.item_combo.setCurrentIndex(1)
        page.quantity_spin.setValue(4)

        page.mode_combo.setCurrentIndex(page.mode_combo.findData("ADD"))
        assert page._collect_adjust_payload() == {
            "mode": "ADD",
            "item_id": "2",
            "quantity_delta": 4,
        }

        page.mode_combo.setCurrentIndex(page.mode_combo.findData("SET"))
        page.quantity_spin.setValue(12)
        assert page._collect_adjust_payload() == {
            "mode": "SET",
            "item_id": "2",
            "quantity": 12,
        }
    finally:
        page.close()


def test_inventory_workers_use_inventory_rpc(monkeypatch):
    _app()

    import ui.utils.pages.caregiver.inventory_management_page as inventory_page
    from ui.utils.pages.caregiver.inventory_management_page import (
        InventoryAdjustWorker,
        InventoryLoadWorker,
    )

    calls = []

    class FakeInventoryRemoteService:
        def get_inventory_bundle(self):
            calls.append(("get_inventory_bundle", {}))
            return _bundle()

        def add_item_quantity(self, *, item_id, quantity_delta):
            calls.append(
                (
                    "add_item_quantity",
                    {"item_id": item_id, "quantity_delta": quantity_delta},
                )
            )
            return {"result_code": "UPDATED"}

        def set_item_quantity(self, *, item_id, quantity):
            calls.append(
                ("set_item_quantity", {"item_id": item_id, "quantity": quantity})
            )
            return {"result_code": "UPDATED"}

    monkeypatch.setattr(
        inventory_page,
        "InventoryRemoteService",
        FakeInventoryRemoteService,
    )

    load_worker = InventoryLoadWorker()
    load_emitted = []
    load_worker.finished.connect(lambda ok, payload: load_emitted.append((ok, payload)))
    load_worker.run()

    add_worker = InventoryAdjustWorker(
        {"mode": "ADD", "item_id": "2", "quantity_delta": 4}
    )
    add_emitted = []
    add_worker.finished.connect(lambda ok, payload: add_emitted.append((ok, payload)))
    add_worker.run()

    set_worker = InventoryAdjustWorker({"mode": "SET", "item_id": "2", "quantity": 12})
    set_emitted = []
    set_worker.finished.connect(lambda ok, payload: set_emitted.append((ok, payload)))
    set_worker.run()

    assert load_emitted[0][0] is True
    assert load_emitted[0][1]["summary"]["total_item_count"] == 3
    assert add_emitted[0] == (True, {"result_code": "UPDATED"})
    assert set_emitted[0] == (True, {"result_code": "UPDATED"})
    assert calls == [
        ("get_inventory_bundle", {}),
        ("add_item_quantity", {"item_id": "2", "quantity_delta": 4}),
        ("set_item_quantity", {"item_id": "2", "quantity": 12}),
    ]


def test_inventory_management_page_uses_shared_worker_thread_helper():
    source = INVENTORY_PAGE.read_text(encoding="utf-8")

    assert "from ui.utils.core.worker_threads import" in source
    assert "start_worker_thread(" in source
    assert "stop_worker_thread(" in source
    assert "QThread(" not in source
    assert "ui.utils.mock_data" not in source
