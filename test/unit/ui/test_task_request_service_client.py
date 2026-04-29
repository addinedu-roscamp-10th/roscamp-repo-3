from ui.utils.network.service_clients import DeliveryRequestRemoteService


def test_delivery_request_remote_service_exposes_option_rpc_methods(monkeypatch):
    calls = []

    def fake_rpc(self, method, **kwargs):
        calls.append((method, kwargs))
        return [{"ok": True}]

    monkeypatch.setattr(DeliveryRequestRemoteService, "_rpc", fake_rpc)

    service = DeliveryRequestRemoteService()

    assert service.get_delivery_destinations() == [{"ok": True}]
    assert service.get_patrol_areas() == [{"ok": True}]
    assert calls == [
        ("get_delivery_destinations", {}),
        ("get_patrol_areas", {}),
    ]
