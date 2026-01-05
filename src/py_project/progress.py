"""プログレスバー・ステータスバー表示モジュール"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

import rich.console
import rich.live
import rich.progress
import rich.table
import rich.text

if TYPE_CHECKING:
    pass

# ステータスバーの色定義
_STATUS_STYLE_NORMAL = "bold #FFFFFF on #6366F1"  # インディゴ
_STATUS_STYLE_ERROR = "bold white on red"


class _NullProgress:
    """非TTY環境用の何もしない Progress（Null Object パターン）"""

    def __init__(self) -> None:
        self.tasks: list[rich.progress.Task] = []

    def add_task(self, description: str, total: float | None = None) -> rich.progress.TaskID:
        return rich.progress.TaskID(0)

    def update(self, task_id: rich.progress.TaskID, advance: float = 1) -> None:
        pass

    def remove_task(self, task_id: rich.progress.TaskID) -> None:
        pass

    def __rich__(self) -> rich.text.Text:
        """Rich プロトコル対応（空のテキストを返す）"""
        return rich.text.Text("")


class _NullLive:
    """非TTY環境用の何もしない Live（Null Object パターン）"""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def refresh(self) -> None:
        pass


class _ProgressTask:
    """Rich Progress のタスクを管理するクラス"""

    def __init__(self, manager: ProgressManager, task_id: rich.progress.TaskID, total: int) -> None:
        self._manager = manager
        self._task_id = task_id
        self._total = total
        self._count = 0

    @property
    def total(self) -> int:
        return self._total

    @property
    def count(self) -> int:
        return self._count

    @property
    def task_id(self) -> rich.progress.TaskID:
        return self._task_id

    def update(self, advance: int = 1) -> None:
        """プログレスを進める"""
        self._count += advance
        self._manager._progress.update(self._task_id, advance=advance)
        self._manager._refresh_display()


class _DisplayRenderable:
    """Live 表示用の動的 renderable クラス"""

    def __init__(self, manager: ProgressManager) -> None:
        self._manager = manager

    def __rich__(self) -> Any:
        """Rich が描画時に呼び出すメソッド"""
        return self._manager._create_display()


class ProgressManager:
    """プログレス表示を管理するクラス"""

    def __init__(self, console: rich.console.Console | None = None) -> None:
        self._console = console if console is not None else rich.console.Console()
        self._progress: rich.progress.Progress | _NullProgress = _NullProgress()
        self._live: rich.live.Live | _NullLive = _NullLive()
        self._start_time: float = time.time()
        self._status_text: str = ""
        self._status_is_error: bool = False
        self._display_renderable: _DisplayRenderable | None = None
        self._progress_bar: dict[str, _ProgressTask] = {}

        self._init_progress()

    @property
    def console(self) -> rich.console.Console:
        """Console インスタンスを取得"""
        return self._console

    @property
    def is_terminal(self) -> bool:
        """TTY 環境かどうか"""
        return self._console.is_terminal

    def _init_progress(self) -> None:
        """Progress と Live を初期化"""
        # 非TTY環境では Live を使用しない
        if not self._console.is_terminal:
            return

        self._progress = rich.progress.Progress(
            rich.progress.TextColumn("[bold]{task.description:<31}"),
            rich.progress.BarColumn(bar_width=None),
            rich.progress.TaskProgressColumn(),
            rich.progress.TextColumn("{task.completed:>5} / {task.total:<5}"),
            rich.progress.TextColumn("経過:"),
            rich.progress.TimeElapsedColumn(),
            rich.progress.TextColumn("残り:"),
            rich.progress.TimeRemainingColumn(),
            console=self._console,
            expand=True,
        )
        self._start_time = time.time()
        self._display_renderable = _DisplayRenderable(self)
        self._live = rich.live.Live(
            self._display_renderable,
            console=self._console,
            refresh_per_second=4,
        )

    def start(self) -> None:
        """Live 表示を開始"""
        self._live.start()

    def stop(self) -> None:
        """Live 表示を停止"""
        self._live.stop()

    def _create_status_bar(self) -> rich.table.Table:
        """ステータスバーを作成（左: タイトル、中央: 進捗、右: 時間）"""
        style = _STATUS_STYLE_ERROR if self._status_is_error else _STATUS_STYLE_NORMAL
        elapsed = time.time() - self._start_time
        elapsed_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"

        # ターミナル幅を取得し、明示的に幅を制限
        # NOTE: tmux 環境では幅計算が実際と異なることがあるため、余裕を持たせる
        terminal_width = self._console.width
        if os.environ.get("TMUX"):
            terminal_width -= 2

        table = rich.table.Table(
            show_header=False,
            show_edge=False,
            box=None,
            padding=0,
            expand=False,
            width=terminal_width,
            style=style,
        )
        table.add_column("title", justify="left", ratio=1, no_wrap=True, overflow="ellipsis", style=style)
        table.add_column("status", justify="center", ratio=3, no_wrap=True, overflow="ellipsis", style=style)
        table.add_column("time", justify="right", ratio=1, no_wrap=True, overflow="ellipsis", style=style)

        table.add_row(
            rich.text.Text(" 🐍 py-project ", style=style),
            rich.text.Text(self._status_text, style=style),
            rich.text.Text(f" {elapsed_str} ", style=style),
        )

        return table

    def _create_display(self) -> Any:
        """表示内容を作成"""
        status_bar = self._create_status_bar()
        # NullProgress の場合 tasks は常に空なのでこの条件で十分
        if len(self._progress.tasks) > 0:
            return rich.console.Group(status_bar, self._progress)
        return status_bar

    def _refresh_display(self) -> None:
        """表示を強制的に再描画"""
        self._live.refresh()

    def set_progress_bar(self, desc: str, total: int) -> None:
        """プログレスバーを作成"""
        task_id = self._progress.add_task(desc, total=total)
        self._progress_bar[desc] = _ProgressTask(self, task_id, total)
        self._refresh_display()

    def update_progress_bar(self, desc: str, advance: int = 1) -> None:
        """プログレスバーを進める（存在しない場合は何もしない）"""
        if desc in self._progress_bar:
            self._progress_bar[desc].update(advance)

    def remove_progress_bar(self, desc: str) -> None:
        """プログレスバーを削除"""
        if desc in self._progress_bar:
            task = self._progress_bar.pop(desc)
            self._progress.remove_task(task.task_id)
            self._refresh_display()

    def set_status(self, status: str, *, is_error: bool = False) -> None:
        """ステータスを更新"""
        self._status_text = status
        self._status_is_error = is_error
        self._refresh_display()

    def print(self, *args: Any, **kwargs: Any) -> None:
        """コンソールに出力（非TTY環境でのみ使用）"""
        if not self._console.is_terminal:
            self._console.print(*args, **kwargs)
