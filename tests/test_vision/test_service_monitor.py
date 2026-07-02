from katrain.vision.config_service import VisionServiceConfig
from katrain.vision.ipc import CommandType
from katrain.vision.service import VisionService


class FakeWorker:
    def __init__(self):
        self.commands = []

    def send_command(self, cmd):
        self.commands.append(cmd)


def _service_with_fake():
    svc = VisionService(VisionServiceConfig())
    svc._worker = FakeWorker()
    return svc


class TestMonitorPauseArmCommands:
    def test_set_monitor_sends_command(self):
        svc = _service_with_fake()
        svc.set_monitor(True)
        cmd = svc._worker.commands[-1]
        assert cmd.action == CommandType.SET_MONITOR and cmd.data == {"active": True}

    def test_set_paused_sends_command(self):
        svc = _service_with_fake()
        svc.set_paused(True)
        cmd = svc._worker.commands[-1]
        assert cmd.action == CommandType.SET_PAUSED and cmd.data == {"paused": True}

    def test_set_move_armed_sends_command(self):
        svc = _service_with_fake()
        svc.set_move_armed(True)
        cmd = svc._worker.commands[-1]
        assert cmd.action == CommandType.SET_MOVE_ARMED and cmd.data == {"armed": True}

    def test_noop_without_worker(self):
        svc = VisionService(VisionServiceConfig())
        svc.set_monitor(True)  # must not raise
        svc.set_paused(False)
        svc.set_move_armed(False)
