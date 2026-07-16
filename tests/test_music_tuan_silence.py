from __future__ import annotations

import unittest

from buffwatcher.alerting import AlertEngine, BuffSpec, MUSIC_BUFF_CCIDS, TUAN_SONG_CCID


class MusicTuanSilenceTests(unittest.TestCase):
    def test_default_keeps_music_reminders_enabled_when_tuan_is_active(self) -> None:
        engine = AlertEngine([])

        self.assertFalse(engine.music_tuan_silence_enabled)

    @staticmethod
    def _engine(enabled: bool) -> tuple[AlertEngine, object]:
        music = BuffSpec(
            name="活跃曲",
            ccid=min(MUSIC_BUFF_CCIDS),
            suppress_remaining_if_active_ccids={TUAN_SONG_CCID},
            suppress_ended_if_active_ccids={TUAN_SONG_CCID},
        )
        tuan = BuffSpec(name="徒安之歌", ccid=TUAN_SONG_CCID)
        engine = AlertEngine(
            [music, tuan],
            music_strong_reminder_enabled=True,
            music_tuan_silence_enabled=enabled,
        )
        music_state = engine.states[music.ccid]
        music_state.active = True
        music_state.end_ms = 10_000
        tuan_state = engine.states[TUAN_SONG_CCID]
        tuan_state.active = True
        tuan_state.end_ms = 20_000
        return engine, music_state

    def test_enabled_switch_silences_remaining_ended_and_strong_reminders(self) -> None:
        engine, music_state = self._engine(True)

        self.assertTrue(engine._should_suppress_remaining_alert(music_state, 5_000, 5))
        self.assertTrue(
            engine._should_suppress_ended_alert(music_state.spec, at_ms=5_000)
        )
        self.assertFalse(engine._music_strong_reminder_should_apply(music_state, 5_000))

    def test_disabled_switch_keeps_music_reminders_even_with_tuan_active(self) -> None:
        engine, music_state = self._engine(False)

        self.assertFalse(engine._should_suppress_remaining_alert(music_state, 5_000, 5))
        self.assertFalse(
            engine._should_suppress_ended_alert(music_state.spec, at_ms=5_000)
        )
        self.assertTrue(engine._music_strong_reminder_should_apply(music_state, 5_000))


if __name__ == "__main__":
    unittest.main()
