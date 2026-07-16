from __future__ import annotations

import io
import queue
import socket
from contextlib import redirect_stdout
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from buffwatcher.backend import MabicatBackend
from buffwatcher.launcher_gui import LauncherApp
from buffwatcher.live import build_parser as build_live_parser
from buffwatcher.live import advance_live_time
from buffwatcher.live import cmd_watch_ws
from buffwatcher.standalone import build_parser as build_standalone_parser
from buffwatcher.standalone import is_transient_backend_traffic_error


class FakeClient:
    def __init__(self, receive_steps: list[BaseException]) -> None:
        self.receive_steps = list(receive_steps)
        self.connect_count = 0
        self.close_count = 0
        self.port = 18_000
        self.url = "ws://127.0.0.1:18000/ws"

    def connect(self) -> None:
        self.connect_count += 1

    def recv_text(self) -> str | None:
        step = self.receive_steps.pop(0)
        raise step

    def close(self) -> None:
        self.close_count += 1


class FakeResource:
    path = None

    def start(self) -> None:
        return

    def close(self) -> None:
        return


def watch_args(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "config": "unused.json",
        "host": "127.0.0.1",
        "port": 18_000,
        "path": "/ws",
        "record_events": "",
        "record_alerts": "",
        "max_seconds": 0,
        "status_interval": 0,
        "reconnect_seconds": 0,
        "idle_reconnect_seconds": 0.001,
        "no_audio": True,
        "no_bell": True,
        "verbose_events": False,
        "backend_is_alive": lambda: True,
        "restart_backend": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ConnectionStabilityTests(unittest.TestCase):
    def test_time_refresh_keeps_astrology_tracker_in_overlay_snapshot(self) -> None:
        tracker = object()
        overlay = Mock()
        engine = SimpleNamespace(
            states={},
            key_enemy_debuff_alert=None,
            key_enemy_debuff_entity_states={},
            short_cooldown_test_target_active=False,
            astrology_tracking_context_active=True,
            self_entity_id="self",
            astrology_card_tracker=tracker,
            boss_hp_alert_states_by_max_hp={},
            advance_time=Mock(return_value=[]),
        )

        advance_live_time(
            engine,
            no_audio=True,
            bell=False,
            suppress_alerts=True,
            music_overlay=overlay,
        )

        overlay.sync_states.assert_called_once_with(
            engine.states,
            key_enemy_debuff_alert=None,
            key_enemy_debuff_states={},
            short_cooldown_test_target_active=False,
            astrology_tracking_active=True,
            self_identity_confirmed=True,
            astrology_card_tracker=tracker,
            boss_hp_states_by_max_hp={},
            miracle_orb_hp_states=None,
            miracle_orb_selected_entity_id=None,
            boss_laser_states_by_max_hp=None,
        )

    def run_watcher(
        self,
        client: FakeClient,
        args: SimpleNamespace,
        *,
        self_filter: object | None = None,
    ) -> str:
        overlay = FakeResource()
        event_recorder = FakeResource()
        alert_recorder = FakeResource()
        clock_recorder = FakeResource()
        server_clock = SimpleNamespace(
            settings=SimpleNamespace(enabled=False, mode="off")
        )
        self_filter = self_filter or SimpleNamespace(self_id="123")
        output = io.StringIO()
        with (
            patch("buffwatcher.live.make_engine", return_value=(object(), self_filter, server_clock)),
            patch("buffwatcher.live.MusicOverlayPublisher", return_value=overlay),
            patch("buffwatcher.live.LocalWebSocket", return_value=client),
            patch("buffwatcher.live.EventRecorder", return_value=event_recorder),
            patch("buffwatcher.live.AlertRecorder", return_value=alert_recorder),
            patch(
                "buffwatcher.live.ServerClockDiagnosticRecorder",
                return_value=clock_recorder,
            ),
            patch("buffwatcher.live.advance_live_time"),
            patch("buffwatcher.live.print_common_start"),
            redirect_stdout(output),
        ):
            self.assertEqual(cmd_watch_ws(args), 0)
        return output.getvalue()

    def test_quiet_socket_never_forces_idle_reconnect(self) -> None:
        client = FakeClient(
            [socket.timeout() for _ in range(5)] + [KeyboardInterrupt()]
        )

        output = self.run_watcher(client, watch_args())

        self.assertEqual(client.connect_count, 1)
        self.assertNotIn("websocket idle", output)
        self.assertNotIn("idle reconnect", output)

    def test_real_backend_exit_restarts_without_clearing_self_id(self) -> None:
        client = FakeClient([socket.timeout(), KeyboardInterrupt()])
        restart_backend = Mock(return_value=19_000)
        self_filter = SimpleNamespace(self_id="4503599639695197")

        output = self.run_watcher(
            client,
            watch_args(
                backend_is_alive=lambda: False,
                restart_backend=restart_backend,
            ),
            self_filter=self_filter,
        )

        self.assertEqual(client.connect_count, 2)
        restart_backend.assert_called_once_with()
        self.assertEqual(self_filter.self_id, "4503599639695197")
        self.assertIn("without clearing the confirmed self id", output)

    def test_backend_wait_notice_does_not_terminate_healthy_process(self) -> None:
        class FakeProcess:
            stdout = None
            stderr = None

            def __init__(self) -> None:
                self.poll_count = 0
                self.terminated = False

            def poll(self) -> int | None:
                self.poll_count += 1
                return None if self.poll_count == 1 else 7

            def terminate(self) -> None:
                self.terminated = True

        process = FakeProcess()
        backend = MabicatBackend(SimpleNamespace())  # type: ignore[arg-type]
        backend._lines = Mock()
        backend._lines.get.side_effect = queue.Empty
        output = io.StringIO()

        with (
            patch("buffwatcher.backend.subprocess.Popen", return_value=process),
            patch("buffwatcher.backend.time.monotonic", side_effect=[0.0, 0.02]),
            redirect_stdout(output),
        ):
            with self.assertRaisesRegex(RuntimeError, "exited with code 7"):
                backend.start(waiting_notice_seconds=0.01)

        self.assertFalse(process.terminated)
        self.assertIn("remains running and will not be restarted", output.getvalue())

    def test_command_line_defaults_disable_idle_recovery(self) -> None:
        standalone_args = build_standalone_parser().parse_args([])
        live_args = build_live_parser().parse_args([])

        self.assertEqual(standalone_args.idle_reconnect_seconds, 0)
        self.assertEqual(standalone_args.backend_idle_reconnects, 0)
        self.assertEqual(live_args.idle_reconnect_seconds, 0)

    def test_any_real_backend_process_exit_is_retryable(self) -> None:
        self.assertTrue(
            is_transient_backend_traffic_error(
                RuntimeError("backend exited with code 7: no backend output")
            )
        )

    def test_launcher_explains_healthy_waiting_state(self) -> None:
        app = LauncherApp.__new__(LauncherApp)
        app.connected = False
        app.ready = False
        app.set_status = Mock()
        app.set_pending_status = Mock()

        app.update_status_from_log_line(
            "[backend] still waiting for game data; Mabicat remains running"
        )

        app.set_status.assert_called_with(
            False,
            "等待游戏数据",
        )


if __name__ == "__main__":
    unittest.main()
