from __future__ import annotations

import codecs
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

from .console_launcher import (
    CREATE_NEW_PROCESS_GROUP,
    CREATE_NO_WINDOW,
    assign_to_job,
    close_handle,
    create_log_session_dir,
    create_kill_on_close_job,
    kill_stale_processes,
    LOG_SESSION_DIR_ENV,
    log_dir,
    package_root,
    package_title,
    process_is_running,
    read_new_log_text,
    stop_process,
    watcher_dir,
    watcher_exe,
    write_launcher_status,
)
from .updater import (
    PreparedUpdate,
    UpdateInfo,
    UpdateProgress,
    current_version_code,
    fetch_latest_update,
    prepare_update,
    start_update,
)


COLORS = {
    "bg": "#d8d0c2",
    "panel": "#e7e1d6",
    "title": "#d4c4ad",
    "row": "#ece9df",
    "button": "#d8c9b8",
    "button_active": "#f1aa57",
    "text": "#5b4736",
    "muted": "#8a7a68",
    "ok": "#2f8c4d",
    "pending": "#c8872f",
    "bad": "#b0443e",
    "update": "#d1841f",
}


def executable(root: Path, folder: str, name: str) -> Path:
    return root / folder / name


class LauncherApp:
    def __init__(self, root_window: tk.Tk) -> None:
        self.root_window = root_window
        self.root = package_root()
        self.display_title = package_title(self.root)
        self.core_dir = watcher_dir(self.root)
        self.core_exe = watcher_exe(self.root)
        self.logs = log_dir(self.root)
        self.log_path: Path | None = None
        self.session_logs: Path | None = None
        self.log_offset = 0
        self.log_stream = None
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.process: subprocess.Popen[bytes] | None = None
        self.job = None
        self.connected = False
        self.ready = False
        self.last_status_text = ""
        self.micopunch_order_warning_shown = False
        self.update_info: UpdateInfo | None = None
        self.update_check_started = False
        self.update_check_running = False
        self.update_in_progress = False
        self.update_progress_fraction = 0.0

        self.root_window.title(self.display_title)
        self.root_window.configure(bg=COLORS["bg"])
        self.root_window.resizable(False, False)
        self.root_window.protocol("WM_DELETE_WINDOW", self.close)
        self._set_icon()
        self._build()
        self.start_core()
        self.root_window.after(1500, self.check_for_updates_async)
        self.root_window.after(
            15000,
            lambda: self.check_for_updates_async(force=True, reason="startup-retry"),
        )
        self.root_window.after(300, self.poll_status)

    def _set_icon(self) -> None:
        for image_path in [
            self.core_dir / "assets" / "icon" / "buffwatcher_icon.png",
            self.root / "assets" / "icon" / "buffwatcher_icon.png",
        ]:
            if not image_path.is_file():
                continue
            try:
                self.window_icon_image = tk.PhotoImage(file=str(image_path))
                self.root_window.iconphoto(True, self.window_icon_image)
                break
            except tk.TclError:
                continue
        for icon_path in [
            self.core_dir / "assets" / "icon" / "buffwatcher.ico",
            self.root / "assets" / "icon" / "buffwatcher.ico",
        ]:
            if not icon_path.is_file():
                continue
            try:
                self.root_window.iconbitmap(str(icon_path))
                return
            except tk.TclError:
                continue

    def _build(self) -> None:
        outer = tk.Frame(self.root_window, bg=COLORS["panel"], bd=1, relief="solid")
        outer.grid(row=0, column=0, padx=14, pady=14, sticky="nsew")

        title = tk.Frame(outer, bg=COLORS["title"])
        title.grid(row=0, column=0, columnspan=4, sticky="ew")
        title.columnconfigure(0, weight=1)
        tk.Label(
            title,
            text=self.display_title,
            bg=COLORS["title"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 12, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=(14, 8), pady=(10, 8))
        self.update_badge = tk.Frame(
            title,
            bg=COLORS["title"],
            cursor="hand2",
        )
        self.update_badge.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=(3, 3))
        self.update_icon = tk.Label(
            self.update_badge,
            text="𝄞",
            bg=COLORS["title"],
            fg=COLORS["update"],
            font=("Segoe UI Symbol", 17, "bold"),
            cursor="hand2",
            width=2,
        )
        self.update_icon.pack(side="top")
        self.update_label = tk.Label(
            self.update_badge,
            text="有更新",
            bg=COLORS["title"],
            fg=COLORS["update"],
            font=("Microsoft YaHei UI", 7, "bold"),
            cursor="hand2",
        )
        self.update_label.pack(side="top")
        self.update_badge.grid_remove()
        self.update_badge.bind("<Button-1>", self.show_update_prompt)
        self.update_icon.bind("<Button-1>", self.show_update_prompt)
        self.update_label.bind("<Button-1>", self.show_update_prompt)

        status_row = tk.Frame(outer, bg=COLORS["row"])
        status_row.grid(row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=(10, 8))
        self.status_icon = tk.Label(
            status_row,
            text="X",
            bg=COLORS["row"],
            fg=COLORS["bad"],
            font=("Microsoft YaHei UI", 22, "bold"),
            width=2,
        )
        self.status_icon.pack(side="left", padx=(12, 8), pady=8)
        status_content = tk.Frame(status_row, bg=COLORS["row"])
        status_content.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 12),
            pady=(7, 7),
        )
        self.status_text = tk.Label(
            status_content,
            text="正在连接",
            bg=COLORS["row"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
            width=30,
        )
        self.status_text.pack(side="top", fill="x", expand=True)
        self.update_progress_canvas = tk.Canvas(
            status_content,
            height=9,
            bg=COLORS["panel"],
            highlightbackground=COLORS["muted"],
            highlightthickness=1,
            bd=0,
        )
        self.update_progress_fill = self.update_progress_canvas.create_rectangle(
            0,
            0,
            0,
            9,
            fill=COLORS["update"],
            outline=COLORS["update"],
        )
        self.update_progress_canvas.bind(
            "<Configure>", self._redraw_update_progress
        )

        button_row = tk.Frame(outer, bg=COLORS["panel"])
        button_row.grid(row=2, column=0, columnspan=4, sticky="ew", padx=10, pady=(2, 12))
        for index in range(4):
            button_row.columnconfigure(index, weight=1)

        self._button(button_row, "参数设置", self.open_settings).grid(
            row=0, column=0, padx=4, pady=4, sticky="ew"
        )
        self._button(button_row, "后台状态", self.open_console).grid(
            row=0, column=1, padx=4, pady=4, sticky="ew"
        )
        self._button(button_row, "BUG报告", self.open_contact).grid(
            row=0, column=2, padx=4, pady=4, sticky="ew"
        )
        self._button(button_row, "特别致谢", self.open_special_thanks).grid(
            row=0, column=3, padx=4, pady=4, sticky="ew"
        )

    def _button(self, parent: tk.Misc, text: str, command: object) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=COLORS["button"],
            fg=COLORS["text"],
            activebackground=COLORS["button_active"],
            activeforeground=COLORS["text"],
            relief="raised",
            bd=1,
            font=("Microsoft YaHei UI", 10, "bold"),
            padx=10,
            pady=6,
        )

    def start_core(self) -> None:
        self.logs.mkdir(parents=True, exist_ok=True)
        if not self.core_exe.is_file():
            self.set_status(False, f"找不到后台程序: {self.core_exe.name}")
            return

        kill_stale_processes()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.session_logs = create_log_session_dir(self.root, stamp=stamp)
        self.log_path = self.session_logs / "launcher.log"
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env[LOG_SESSION_DIR_ENV] = str(self.session_logs)
        creationflags = 0
        if os.name == "nt":
            creationflags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

        try:
            self.log_stream = self.log_path.open("ab", buffering=0)
            self.process = subprocess.Popen(
                [
                    str(self.core_exe),
                    "--no-bell",
                    "--block-if-micopunch-running",
                ],
                cwd=str(self.core_dir),
                stdin=subprocess.DEVNULL,
                stdout=self.log_stream,
                stderr=subprocess.STDOUT,
                env=env,
                creationflags=creationflags,
            )
            self.job = create_kill_on_close_job()
            assign_to_job(self.job, self.process)
            write_launcher_status(
                self.root,
                pid=self.process.pid,
                log_path=self.log_path,
                started_by="gui",
            )
            self.set_status(False, "正在连接")
        except OSError as exc:
            if self.log_stream is not None:
                try:
                    self.log_stream.close()
                except OSError:
                    pass
                self.log_stream = None
            self.set_status(False, f"后台启动失败: {exc}")

    def append_launcher_log(self, message: str) -> None:
        try:
            self.logs.mkdir(parents=True, exist_ok=True)
            if self.log_path is None:
                self.session_logs = create_log_session_dir(self.root)
                self.log_path = self.session_logs / "launcher-update.log"
            path = self.log_path
            line = f"[launcher] {time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n"
            with path.open("ab") as stream:
                stream.write(line.encode("utf-8", "replace"))
        except OSError:
            pass

    def check_for_updates_async(
        self,
        *,
        force: bool = False,
        reason: str = "startup",
    ) -> None:
        if self.update_in_progress or self.update_info is not None:
            return
        if self.update_check_running:
            return
        if self.update_check_started and not force:
            return
        self.update_check_started = True
        self.update_check_running = True
        self.append_launcher_log(f"update check start reason={reason}")

        def worker() -> None:
            info = None
            error = None
            current_code = 0
            try:
                current_code = current_version_code(self.root, self.display_title)
            except Exception as exc:
                error = exc
            if error is None:
                for attempt in range(1, 4):
                    try:
                        info = fetch_latest_update(
                            self.root,
                            self.display_title,
                            timeout_seconds=12.0,
                        )
                        error = None
                        break
                    except Exception as exc:
                        error = exc
                        self.append_launcher_log(
                            "update check attempt failed "
                            f"reason={reason} attempt={attempt} "
                            f"error={type(exc).__name__}: {exc}"
                        )
                        time.sleep(1.5 * attempt)
            if error is not None:
                self.append_launcher_log(
                    f"update check failed reason={reason} error={type(error).__name__}: {error}"
                )
            elif info is None:
                self.append_launcher_log(
                    f"update check ok reason={reason} current_code={current_code} available=0"
                )
            else:
                self.append_launcher_log(
                    "update check ok "
                    f"reason={reason} current_code={current_code} "
                    f"available=1 latest_code={info.version_code} latest={info.version}"
                )

            def finish() -> None:
                self.update_check_running = False
                if info is not None:
                    self.show_update_available(info)

            if info is not None:
                try:
                    self.root_window.after(0, finish)
                except RuntimeError as exc:
                    self.update_check_running = False
                    self.append_launcher_log(f"update badge failed: {exc}")
            else:
                try:
                    self.root_window.after(
                        0,
                        lambda: setattr(self, "update_check_running", False),
                    )
                except RuntimeError:
                    self.update_check_running = False

        threading.Thread(target=worker, name="update-check", daemon=True).start()

    def show_update_available(self, info: UpdateInfo) -> None:
        if self.update_in_progress:
            return
        self.update_info = info
        self.update_badge.grid()

    def show_update_prompt(self, _event: object | None = None) -> None:
        if self.update_in_progress or self.update_info is None:
            return
        notes = "\n".join(f"· {note}" for note in self.update_info.notes[:5])
        detail = f"发现新版本：{self.update_info.release_name}"
        if notes:
            detail += f"\n\n{notes}"
        detail += "\n\n是否现在更新？更新完成后会自动重启。"
        if not messagebox.askyesno("发现新版本", detail):
            return
        self.begin_update(self.update_info)

    def begin_update(self, info: UpdateInfo) -> None:
        if self.update_in_progress:
            return
        self.update_in_progress = True
        self.update_badge.grid_remove()
        self._show_update_progress()
        self._set_update_progress_fraction(0.0)
        self.set_update_status("正在准备下载更新……")

        def worker() -> None:
            try:
                prepared = prepare_update(
                    self.root,
                    info,
                    progress_callback=self._queue_update_progress,
                )
            except Exception as exc:
                self.root_window.after(0, lambda: self.update_failed(str(exc)))
                return
            self.root_window.after(0, lambda: self.apply_prepared_update(prepared))

        threading.Thread(target=worker, name="update-download", daemon=True).start()

    def apply_prepared_update(self, prepared: PreparedUpdate) -> None:
        self._set_update_progress_fraction(1.0)
        self.set_update_status("更新包已就绪，正在重启……")
        core_pid = self.process.pid if self.process is not None else 0
        try:
            start_update(
                prepared,
                self.root,
                launcher_pid=os.getpid(),
                core_pid=core_pid,
            )
        except Exception as exc:
            self.update_failed(str(exc))
            return
        self.root_window.after(700, self.close)

    def update_failed(self, message: str) -> None:
        self.update_in_progress = False
        self._hide_update_progress()
        self.last_status_text = ""
        if self.ready:
            self.set_status(True, "播报已启用")
        elif self.connected:
            self.set_pending_status("请开关魔法盾")
        else:
            self.set_status(False, "正在连接")
        messagebox.showerror("更新失败", f"{message}\n\n请稍后重试，或手动下载最新版。")

    def set_update_status(self, text: str) -> None:
        self.last_status_text = text
        self.status_icon.configure(text="𝄞", fg=COLORS["update"])
        self.status_text.configure(text=text)

    def _show_update_progress(self) -> None:
        if not self.update_progress_canvas.winfo_manager():
            self.update_progress_canvas.pack(
                side="top",
                fill="x",
                pady=(6, 0),
            )

    def _hide_update_progress(self) -> None:
        self.update_progress_canvas.pack_forget()
        self._set_update_progress_fraction(0.0)

    def _redraw_update_progress(self, _event: object | None = None) -> None:
        width = max(0, int(self.update_progress_canvas.winfo_width()) - 2)
        height = max(1, int(self.update_progress_canvas.winfo_height()) - 2)
        filled = int(round(width * self.update_progress_fraction))
        self.update_progress_canvas.coords(
            self.update_progress_fill,
            1,
            1,
            max(1, filled),
            height,
        )

    def _set_update_progress_fraction(self, value: float) -> None:
        self.update_progress_fraction = min(1.0, max(0.0, float(value)))
        self._redraw_update_progress()

    @staticmethod
    def _format_update_bytes(value: int) -> str:
        return f"{max(0, value) / (1024 * 1024):.1f} MB"

    def _queue_update_progress(self, progress: UpdateProgress) -> None:
        self.append_launcher_log(
            "update progress "
            f"stage={progress.stage} source={progress.source_name or '-'} "
            f"downloaded={progress.downloaded} total={progress.total} "
            f"detail={progress.detail or '-'}"
        )
        try:
            self.root_window.after(
                0,
                lambda current=progress: self._apply_update_progress(current),
            )
        except RuntimeError:
            return

    def _apply_update_progress(self, progress: UpdateProgress) -> None:
        self._show_update_progress()
        if progress.stage == "connecting":
            self._set_update_progress_fraction(0.0)
            self.set_update_status(f"正在连接{progress.source_name}……")
            return
        if progress.stage == "downloading":
            if progress.total > 0:
                fraction = min(1.0, progress.downloaded / progress.total)
                percent = int(fraction * 100)
                self._set_update_progress_fraction(fraction)
                self.set_update_status(
                    f"正在从{progress.source_name}下载：{percent}% "
                    f"（{self._format_update_bytes(progress.downloaded)} / "
                    f"{self._format_update_bytes(progress.total)}）"
                )
            else:
                self.set_update_status(
                    f"正在从{progress.source_name}下载："
                    f"{self._format_update_bytes(progress.downloaded)}"
                )
            return
        if progress.stage == "source_failed":
            self._set_update_progress_fraction(0.0)
            if progress.detail:
                self.set_update_status(
                    f"{progress.source_name}失败，正在切换{progress.detail}……"
                )
            else:
                self.set_update_status(f"{progress.source_name}下载失败")
            return
        if progress.stage == "verifying":
            self._set_update_progress_fraction(1.0)
            self.set_update_status(f"{progress.source_name}下载完成，正在校验……")
            return
        if progress.stage == "extracting":
            self._set_update_progress_fraction(1.0)
            self.set_update_status("校验通过，正在解压更新包……")
            return
        if progress.stage == "ready":
            self._set_update_progress_fraction(1.0)
            self.set_update_status("更新包准备完成，正在重启……")

    def poll_status(self) -> None:
        if self.log_path is not None:
            self.log_offset, text = read_new_log_text(
                self.log_path,
                self.log_offset,
                self.decoder,
            )
            if text and not self.update_in_progress:
                self.update_status_from_log(text)
            if not self.update_in_progress:
                self.sync_status_from_log_markers()

        if self.process is not None:
            code = self.process.poll()
            if code is not None:
                if self.update_in_progress:
                    return
                if code == 3:
                    self.show_micopunch_order_warning()
                else:
                    self.set_status(False, "后台已停止")
                self.process = None
                close_handle(self.job)
                self.job = None
                if self.log_stream is not None:
                    try:
                        self.log_stream.close()
                    except OSError:
                        pass
                    self.log_stream = None
                self.root_window.after(
                    200,
                    lambda exit_code=code: self.check_for_updates_async(
                        force=True,
                        reason=f"backend-exit-{exit_code}",
                    ),
                )
                return

        self.root_window.after(500, self.poll_status)

    def update_status_from_log(self, text: str) -> None:
        for line in text.splitlines():
            self.update_status_from_log_line(line)

    def update_status_from_log_line(self, line: str) -> None:
        if (
            "[standalone] starting packet backend; waiting for game data" in line
            or "[backend] still waiting for game data" in line
        ):
            self.connected = False
            self.set_status(False, "等待游戏数据")
        if "[live] websocket connected" in line:
            self.connected = True
            if self.ready:
                self.set_status(True, "播报已启用")
            else:
                self.set_pending_status("请开关魔法盾")
        if "[live] websocket disconnected" in line:
            self.connected = False
            self.set_status(False, "正在连接")
        if "[live] reset self id:" in line:
            self.ready = False
            if self.connected:
                self.set_pending_status("请开关魔法盾")
            else:
                self.set_status(False, "正在连接")
        if "[live] learned self id:" in line or "[live] updated self id:" in line:
            self.ready = True
            self.set_status(True, "播报已启用")
        if "洛奇播报小助手 is already running" in line or "BUFF Watcher is already running" in line:
            self.connected = False
            self.ready = False
            self.set_status(False, "已有一个提醒器正在运行")
        if "MicoPunch is already running" in line:
            self.show_micopunch_order_warning()

    def sync_status_from_log_markers(self) -> None:
        if self.log_path is None:
            return
        try:
            with self.log_path.open("rb") as stream:
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                stream.seek(max(0, size - 262144))
                data = stream.read()
        except OSError:
            return

        learned_at = max(
            data.rfind(b"[live] learned self id:"),
            data.rfind(b"[live] updated self id:"),
        )
        reset_at = data.rfind(b"[live] reset self id:")
        connected_at = data.rfind(b"[live] websocket connected")
        disconnected_at = data.rfind(b"[live] websocket disconnected")

        if connected_at > disconnected_at:
            self.connected = True
        elif disconnected_at > connected_at:
            self.connected = False

        if reset_at > learned_at:
            if self.ready:
                self.ready = False
                if self.connected:
                    self.set_pending_status("请开关魔法盾")
                else:
                    self.set_status(False, "正在连接")
            return

        if learned_at >= 0:
            self.ready = True
            if self.connected:
                self.set_status(True, "播报已启用")

    def show_micopunch_order_warning(self) -> None:
        self.connected = False
        self.ready = False
        self.set_status(False, "启动顺序冲突")
        if self.micopunch_order_warning_shown:
            return
        self.micopunch_order_warning_shown = True
        messagebox.showwarning(
            "启动顺序提示",
            "请先启动本工具，再启动Micopunch，否则可能会发生冲突",
        )

    def set_pending_status(self, text: str) -> None:
        if text == self.last_status_text:
            return
        self.last_status_text = text
        self.status_icon.configure(text="O", fg=COLORS["pending"])
        self.status_text.configure(text=text)

    def set_status(self, connected: bool, text: str) -> None:
        self.connected = connected
        if text == self.last_status_text:
            return
        self.last_status_text = text
        self.status_icon.configure(
            text="√" if connected else "X",
            fg=COLORS["ok"] if connected else COLORS["bad"],
        )
        self.status_text.configure(text=text)

    def open_settings(self) -> None:
        settings_exe = executable(
            self.root,
            "BuffWatcherSettings",
            "BuffWatcherSettings.exe",
        )
        config_path = self.core_dir / "buffwatcher.config.local.json"
        if not settings_exe.is_file():
            messagebox.showerror("参数设置", f"找不到设置程序:\n{settings_exe}")
            return
        subprocess.Popen(
            [str(settings_exe), "--config", str(config_path)],
            cwd=str(settings_exe.parent),
        )

    def open_console(self) -> None:
        console_exe = executable(
            self.root,
            "BuffWatcherConsole",
            "BuffWatcherConsole.exe",
        )
        if not console_exe.is_file():
            messagebox.showerror("后台状态", f"找不到后台状态程序:\n{console_exe}")
            return
        subprocess.Popen([str(console_exe)], cwd=str(console_exe.parent))

    def open_contact(self) -> None:
        dialog = tk.Toplevel(self.root_window)
        dialog.title("BUG报告")
        dialog.configure(bg=COLORS["bg"])
        dialog.resizable(False, False)
        dialog.transient(self.root_window)
        dialog.grab_set()

        panel = tk.Frame(dialog, bg=COLORS["panel"], bd=1, relief="solid")
        panel.grid(row=0, column=0, padx=16, pady=16)
        tk.Label(
            panel,
            text="BUG修复和功能建议，请联系亚特 无染渊，谢谢qwq",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
            wraplength=320,
            justify="left",
        ).grid(row=0, column=0, padx=18, pady=(18, 12))
        self._button(panel, "确定", dialog.destroy).grid(row=1, column=0, pady=(0, 16))

    def open_special_thanks(self) -> None:
        dialog = tk.Toplevel(self.root_window)
        dialog.title("特别致谢")
        dialog.configure(bg=COLORS["bg"])
        dialog.resizable(False, False)
        dialog.transient(self.root_window)
        dialog.grab_set()

        panel = tk.Frame(dialog, bg=COLORS["panel"], bd=1, relief="solid")
        panel.grid(row=0, column=0, padx=16, pady=16)
        tk.Label(
            panel,
            text=(
                "Micopunch的作者，提供了设计思路；虽然我并不认识你，"
                "但这个插件的核心机制全都借鉴自你的作品。感谢！\n\n"
                "草莓很快乐，我的会长和导师；不知疲倦地解答我的问题，"
                "教会我如何玩这个游戏。虽然愚钝的我，学得一塌糊涂qwq。。"
                "但还是，谢谢你！\n\n"
                "王诗韵老师，王诗韵系列优化补丁的作者；是你的无私奉献与分享，"
                "让我有了做这个补丁的念头与驱动力。在艾琳的日子，"
                "因你而变得更加轻松惬意。让我们一起努力吧？(＾o＾)ﾉ"
            ),
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 10),
            wraplength=460,
            justify="left",
        ).grid(row=0, column=0, padx=18, pady=(18, 12))
        self._button(panel, "确定", dialog.destroy).grid(row=1, column=0, pady=(0, 16))

    def close(self) -> None:
        if self.process is not None:
            stop_process(self.process, self.job)
            self.process = None
            self.job = None
        else:
            close_handle(self.job)
        if self.log_stream is not None:
            try:
                self.log_stream.close()
            except OSError:
                pass
            self.log_stream = None
        self.root_window.destroy()


def main() -> int:
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
