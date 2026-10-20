# AGENTS.md

## Cursor Cloud specific instructions

This repo (`nogi-broadcaster` / `buffwatcher`) is a **Windows desktop** voice-alert tool for the game
*Mabinogi*. It parses game network packets and plays short voice alerts. Keep the following in mind when
developing in the cloud (Linux) environment.

### What can and cannot run on Linux
- The full background app (`run_standalone.py` / `buffwatcher.standalone`) needs `vendor/mabicat.exe`
  (a Windows-only packet-capture backend, **not committed to the repo**) plus live game traffic, so it
  **cannot run end-to-end on Linux**. Windows-only modules (`winsound`, `msvcrt`) are import-guarded, so
  importing the packages still works.
- What does run on Linux: the **Tkinter GUIs** (`run_settings.py`, `run_launcher.py`, `run_overlay.py`)
  and the **test suite**.

### Environment
- Python deps are installed into `.venv` by the startup update script. Use `.venv/bin/python` (it has
  access to system `tkinter` via `python3-tk`). Required system package: `python3-tk`.
- There is no `requirements.txt`/`pyproject.toml`. Runtime GUI dependency is only `tkinter` (stdlib +
  `python3-tk`). `edge_tts` / `imageio_ffmpeg` are used **only** by dev voice-asset scripts
  (`scripts/generate_xiaoyi_voice_assets.py`); `certifi` is optional/guarded in `updater.py`.
- Requires **Python < 3.13**: `buffwatcher/alerting.py` imports `audioop` (removed in 3.13). The VM's
  Python 3.12 works and only emits a DeprecationWarning.

### Running GUIs
- GUIs need a display. The VM desktop is `DISPLAY=:1`; run e.g. `DISPLAY=:1 .venv/bin/python run_settings.py`
  so computer-use can see the window.
- The settings page saves to `buffwatcher.config.local.json` (gitignored); defaults are read from
  `buffwatcher.config.defaults.json`.

### Testing / lint
- Tests are `unittest`-based; run with `DISPLAY=:1 .venv/bin/python -m pytest -q` (or
  `python -m unittest discover -s tests`). Some GUI tests instantiate `Tk()` and need the display.
- No linter or CI is configured. Use `.venv/bin/python -m compileall buffwatcher run_*.py` for a quick
  syntax check.
