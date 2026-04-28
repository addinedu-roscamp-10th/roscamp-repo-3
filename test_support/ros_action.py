class FakeFuture:
    def __init__(self, result=None, exception=None):
        self._result = result
        self._exception = exception

    def add_done_callback(self, callback):
        callback(self)

    def result(self):
        if self._exception is not None:
            raise self._exception
        return self._result


class FakeCancelResponse:
    def __init__(self, *, goals_canceling=None):
        self.goals_canceling = [object()] if goals_canceling is None else goals_canceling


class FakeGoalHandle:
    def __init__(self, *, accepted, result_wrapper=None):
        self.accepted = accepted
        self._result_wrapper = result_wrapper
        self.cancel_calls = 0
        self.cancel_response = FakeCancelResponse()

    def get_result_async(self):
        return FakeFuture(result=self._result_wrapper)

    def cancel_goal_async(self):
        self.cancel_calls += 1
        return FakeFuture(result=self.cancel_response)


class FakeActionResultWrapper:
    def __init__(self, *, status, result):
        self.status = status
        self.result = result


class FakeActionClient:
    def __init__(self, node, action_type, action_name):
        self.node = node
        self.action_type = action_type
        self.action_name = action_name
        self.wait_calls = []
        self.sent_goals = []
        self.server_available = True
        self.goal_handle = None

    def wait_for_server(self, timeout_sec=None):
        self.wait_calls.append(timeout_sec)
        return self.server_available

    def send_goal_async(self, goal_msg):
        self.sent_goals.append(goal_msg)
        return FakeFuture(result=self.goal_handle)


__all__ = [
    "FakeActionClient",
    "FakeActionResultWrapper",
    "FakeCancelResponse",
    "FakeFuture",
    "FakeGoalHandle",
]
