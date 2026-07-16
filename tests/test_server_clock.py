from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from buffwatcher.alerting import AlertEngine, BuffSpec
from buffwatcher.server_clock import (
    CHANNEL_LOGIN_RESPONSE_OP,
    ENTITY_SERVER_TIME_OP,
    ServerClockCalibrator,
    ServerClockDiagnosticRecorder,
    ServerClockSettings,
    load_server_clock_settings,
)


LOCAL_LOGIN_AT = 1_783_843_284_728
SERVER_LOGIN_AT = 63_919_468_860_927
CHARACTER_ID = "4767482422892599"


def login_event(
    *,
    op: str = "0x4e23",
    character_id: str = CHARACTER_ID,
    server_at_ms: int = SERVER_LOGIN_AT,
    local_at_ms: int = LOCAL_LOGIN_AT,
) -> dict:
    return {
        "EventId": 0,
        "At": local_at_ms,
        "Id": "1152921504606846977",
        "Op": op,
        "Msg": [
            {"T": "byte", "V": "1"},
            {"T": "long", "V": character_id},
            {"T": "long", "V": str(server_at_ms)},
            {"T": "int", "V": "0"},
        ],
    }


def music_event(*, mcagt_delta_ms: int = 1_025) -> dict:
    return {
        "EventId": 4,
        "At": LOCAL_LOGIN_AT + 1_000,
        "Id": CHARACTER_ID,
        "CCId": 192,
        "ExtraData": {
            "MCAGT": SERVER_LOGIN_AT + mcagt_delta_ms,
            "SBT": SERVER_LOGIN_AT + 61_000,
        },
    }


class ServerClockCalibratorTests(unittest.TestCase):
    def test_channel_login_parses_exact_character_and_server_time(self) -> None:
        clock = ServerClockCalibrator(ServerClockSettings(mode="apply"))

        calibration = clock.observe(login_event())

        self.assertIsNotNone(calibration)
        assert calibration is not None
        self.assertEqual(calibration.character_id, CHARACTER_ID)
        self.assertEqual(calibration.server_at_ms, SERVER_LOGIN_AT)
        self.assertEqual(calibration.op, CHANNEL_LOGIN_RESPONSE_OP)
        self.assertEqual(clock.known_character_ids, (CHARACTER_ID,))

    def test_wrong_op_or_wrong_field_type_is_not_accepted(self) -> None:
        clock = ServerClockCalibrator(ServerClockSettings(mode="apply"))
        self.assertIsNone(clock.observe(login_event(op="0x659c")))
        malformed = login_event()
        malformed["Msg"][2]["T"] = "int"
        self.assertIsNone(clock.observe(malformed))
        self.assertEqual(clock.known_character_ids, ())

    def test_659c_is_diagnostic_only_and_never_becomes_calibration(self) -> None:
        clock = ServerClockCalibrator(ServerClockSettings(mode="shadow"))
        event = login_event(op="0x659c", character_id="4503599639695197")

        self.assertIsNone(clock.observe(event))
        diagnostic = clock.observe_entity_server_time(event)

        self.assertIsNotNone(diagnostic)
        assert diagnostic is not None
        self.assertEqual(diagnostic.op, ENTITY_SERVER_TIME_OP)
        self.assertEqual(diagnostic.entity_id, "4503599639695197")
        self.assertEqual(diagnostic.server_at_ms, SERVER_LOGIN_AT)
        self.assertEqual(clock.known_character_ids, ())
        self.assertIsNone(clock.latest_calibration)
        self.assertIsNone(clock.music_timing_comparison(music_event()))

    def test_659c_diagnostic_record_explicitly_says_not_applied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clock.ndjson"
            settings = ServerClockSettings(
                mode="shadow",
                diagnostic_log=str(path),
            )
            clock = ServerClockCalibrator(settings)
            diagnostic = clock.observe_entity_server_time(
                login_event(op="0x659c", character_id="4503599639695197")
            )
            assert diagnostic is not None
            recorder = ServerClockDiagnosticRecorder(settings)
            recorder.write_entity_server_time(diagnostic, self_id=CHARACTER_ID)
            recorder.close()

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["Type"], "entity_server_time_0x659c")
            self.assertEqual(payload["SelfId"], CHARACTER_ID)
            self.assertFalse(payload["Applied"])
            self.assertEqual(payload["op"], ENTITY_SERVER_TIME_OP)

    def test_music_comparison_is_bound_to_matching_character(self) -> None:
        clock = ServerClockCalibrator(ServerClockSettings(mode="apply"))
        clock.observe(login_event())

        comparison = clock.music_timing_comparison(music_event())

        self.assertIsNotNone(comparison)
        assert comparison is not None
        self.assertEqual(comparison.adjustment_ms, 25)
        self.assertTrue(comparison.eligible_to_apply)
        other = music_event()
        other["Id"] = "4767482422892600"
        self.assertIsNone(clock.music_timing_comparison(other))

    def test_large_adjustment_falls_back_to_current_formula(self) -> None:
        clock = ServerClockCalibrator(
            ServerClockSettings(mode="apply", max_apply_adjustment_seconds=2)
        )
        clock.observe(login_event())
        event = music_event(mcagt_delta_ms=5_000)

        comparison = clock.music_timing_comparison(event)

        self.assertIsNotNone(comparison)
        assert comparison is not None
        self.assertFalse(comparison.eligible_to_apply)
        self.assertEqual(
            comparison.rejection_reason, "adjustment_exceeds_safety_limit"
        )
        self.assertIsNone(clock.calibrated_music_end_ms(event))

    def test_global_clock_fallback_does_not_change_event_character(self) -> None:
        clock = ServerClockCalibrator(
            ServerClockSettings(mode="apply", allow_global_fallback=True)
        )
        clock.observe(login_event())
        event = music_event()
        event["Id"] = "4503599639695197"

        comparison = clock.music_timing_comparison(event)

        self.assertIsNotNone(comparison)
        assert comparison is not None
        self.assertEqual(comparison.character_id, "4503599639695197")
        self.assertEqual(comparison.calibration_character_id, CHARACTER_ID)
        self.assertEqual(comparison.calibration_binding, "global")
        self.assertEqual(comparison.adjustment_ms, 25)

    def test_alert_engine_applies_login_clock_only_in_apply_mode(self) -> None:
        event = music_event()
        apply_clock = ServerClockCalibrator(ServerClockSettings(mode="apply"))
        apply_clock.observe(login_event())
        apply_engine = AlertEngine(
            [BuffSpec(name="music", ccid=192)],
            server_clock_calibrator=apply_clock,
        )

        apply_engine.process_event(event)

        apply_state = apply_engine.states[192]
        self.assertEqual(
            apply_state.end_ms,
            LOCAL_LOGIN_AT + (event["ExtraData"]["SBT"] - SERVER_LOGIN_AT),
        )
        self.assertEqual(apply_state.last_timing_source, "music_login_server_clock")

        shadow_clock = ServerClockCalibrator(ServerClockSettings(mode="shadow"))
        shadow_clock.observe(login_event())
        shadow_engine = AlertEngine(
            [BuffSpec(name="music", ccid=192)],
            server_clock_calibrator=shadow_clock,
        )
        shadow_engine.process_event(event)
        shadow_state = shadow_engine.states[192]
        self.assertEqual(
            shadow_state.end_ms,
            event["At"]
            + event["ExtraData"]["SBT"]
            - event["ExtraData"]["MCAGT"],
        )
        self.assertEqual(
            shadow_state.last_timing_source, "music_sbt_mcagt_duration"
        )

    def test_local_only_settings_are_loaded_without_touching_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "local.json"
            config.write_text(
                json.dumps(
                    {
                        "tz_offset_hours": 8,
                        "experimental_login_server_clock": {
                            "mode": "apply",
                            "diagnostic_log": "logs/clock.ndjson",
                            "allow_global_fallback": "true",
                        },
                    }
                ),
                encoding="utf-8",
            )

            settings = load_server_clock_settings(config)

            self.assertEqual(settings.mode, "apply")
            self.assertTrue(settings.allow_global_fallback)
            self.assertEqual(
                Path(settings.diagnostic_log),
                Path(directory) / "logs" / "clock.ndjson",
            )


if __name__ == "__main__":
    unittest.main()
