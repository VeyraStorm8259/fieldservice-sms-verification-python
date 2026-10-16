from field_service import InfraiClient, WorkOrder, resend_stuck_verification


class FakeSms:
    def __init__(self):
        self.calls = []
        self.states = [[{"status": "stuck"}], [{"status": "delivered"}]]

    def events(self, message_id):
        self.calls.append(("events", message_id))
        return self.states.pop(0)

    def resend(self, message_id):
        self.calls.append(("resend", message_id))


class FakeClient:
    def __init__(self):
        self.sms = FakeSms()


def test_stuck_code_is_resent_and_state_is_refreshed():
    client = FakeClient()
    result = resend_stuck_verification(WorkOrder("WO-1", "tech-1", "msg-9"), client)
    assert result.resent is True
    assert result.delivery_state == "delivered"
    assert client.sms.calls == [("events", "msg-9"), ("resend", "msg-9"), ("events", "msg-9")]
