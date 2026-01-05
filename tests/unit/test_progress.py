#!/usr/bin/env python3
# ruff: noqa: S101 S108
"""
progress.py のテスト
"""

import io
import time

import rich.console
import rich.live
import rich.progress
import rich.text

import py_project.progress as progress


class TestNullProgress:
    """_NullProgress のテスト"""

    def test_init(self):
        """初期化"""
        null_progress = progress._NullProgress()
        assert null_progress.tasks == []

    def test_add_task(self):
        """タスク追加（常に TaskID(0) を返す）"""
        null_progress = progress._NullProgress()
        task_id = null_progress.add_task("test", total=100)
        assert task_id == rich.progress.TaskID(0)

    def test_update(self):
        """更新（何もしない）"""
        null_progress = progress._NullProgress()
        task_id = null_progress.add_task("test", total=100)
        # 例外が発生しないことを確認
        null_progress.update(task_id, advance=10)

    def test_remove_task(self):
        """タスク削除（何もしない）"""
        null_progress = progress._NullProgress()
        task_id = null_progress.add_task("test", total=100)
        # 例外が発生しないことを確認
        null_progress.remove_task(task_id)

    def test_rich_protocol(self):
        """Rich プロトコル対応"""
        null_progress = progress._NullProgress()
        result = null_progress.__rich__()
        assert isinstance(result, rich.text.Text)
        assert str(result) == ""


class TestNullLive:
    """_NullLive のテスト"""

    def test_start(self):
        """開始（何もしない）"""
        null_live = progress._NullLive()
        # 例外が発生しないことを確認
        null_live.start()

    def test_stop(self):
        """停止（何もしない）"""
        null_live = progress._NullLive()
        # 例外が発生しないことを確認
        null_live.stop()

    def test_refresh(self):
        """リフレッシュ（何もしない）"""
        null_live = progress._NullLive()
        # 例外が発生しないことを確認
        null_live.refresh()


class TestProgressTask:
    """_ProgressTask のテスト"""

    def test_properties(self):
        """プロパティ"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        task = progress._ProgressTask(manager, rich.progress.TaskID(1), total=10)

        assert task.total == 10
        assert task.count == 0
        assert task.task_id == rich.progress.TaskID(1)

    def test_update(self):
        """更新"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        task = progress._ProgressTask(manager, rich.progress.TaskID(1), total=10)
        task.update(advance=3)

        assert task.count == 3

    def test_update_multiple(self):
        """複数回更新"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        task = progress._ProgressTask(manager, rich.progress.TaskID(1), total=10)
        task.update(advance=2)
        task.update(advance=3)

        assert task.count == 5


class TestDisplayRenderable:
    """_DisplayRenderable のテスト"""

    def test_rich_protocol(self):
        """Rich プロトコル対応"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        renderable = progress._DisplayRenderable(manager)
        result = renderable.__rich__()

        # ステータスバー（Table）が返される
        assert result is not None


class TestProgressManagerNonTTY:
    """ProgressManager のテスト（非TTY環境）"""

    def test_init_non_tty(self):
        """非TTY環境での初期化"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        assert manager.console == console
        assert manager.is_terminal is False
        assert isinstance(manager._progress, progress._NullProgress)
        assert isinstance(manager._live, progress._NullLive)

    def test_init_default_console(self):
        """デフォルトコンソールでの初期化"""
        manager = progress.ProgressManager()
        assert manager.console is not None

    def test_start_stop(self):
        """開始・停止（非TTY）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        # 例外が発生しないことを確認
        manager.start()
        manager.stop()

    def test_set_progress_bar(self):
        """プログレスバー作成（非TTY）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        manager.set_progress_bar("test", total=10)

        assert "test" in manager._progress_bar
        assert manager._progress_bar["test"].total == 10

    def test_update_progress_bar(self):
        """プログレスバー更新（非TTY）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        manager.set_progress_bar("test", total=10)
        manager.update_progress_bar("test", advance=3)

        assert manager._progress_bar["test"].count == 3

    def test_update_progress_bar_nonexistent(self):
        """存在しないプログレスバーの更新（何もしない）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        # 例外が発生しないことを確認
        manager.update_progress_bar("nonexistent", advance=1)

    def test_remove_progress_bar(self):
        """プログレスバー削除（非TTY）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        manager.set_progress_bar("test", total=10)
        manager.remove_progress_bar("test")

        assert "test" not in manager._progress_bar

    def test_remove_progress_bar_nonexistent(self):
        """存在しないプログレスバーの削除（何もしない）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        # 例外が発生しないことを確認
        manager.remove_progress_bar("nonexistent")

    def test_set_status(self):
        """ステータス設定"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        manager.set_status("処理中...")

        assert manager._status_text == "処理中..."
        assert manager._status_is_error is False

    def test_set_status_error(self):
        """エラーステータス設定"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        manager.set_status("エラー発生", is_error=True)

        assert manager._status_text == "エラー発生"
        assert manager._status_is_error is True

    def test_print_non_tty(self):
        """print メソッド（非TTY環境では出力される）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        manager.print("テスト出力")

        result = output.getvalue()
        assert "テスト出力" in result

    def test_create_display_no_tasks(self):
        """表示内容作成（タスクなし）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        manager = progress.ProgressManager(console)

        result = manager._create_display()

        # ステータスバーのみ（Table）
        assert result is not None


class TestProgressManagerTTY:
    """ProgressManager のテスト（TTY環境）"""

    def test_init_tty(self):
        """TTY環境での初期化"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)
        manager = progress.ProgressManager(console)

        assert manager.console == console
        assert manager.is_terminal is True
        assert isinstance(manager._progress, rich.progress.Progress)
        assert isinstance(manager._live, rich.live.Live)

    def test_start_stop(self):
        """開始・停止（TTY）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)
        manager = progress.ProgressManager(console)

        # 例外が発生しないことを確認
        manager.start()
        manager.stop()

    def test_set_progress_bar_tty(self):
        """プログレスバー作成（TTY）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)
        manager = progress.ProgressManager(console)

        manager.set_progress_bar("test", total=10)

        assert "test" in manager._progress_bar
        assert len(manager._progress.tasks) == 1

    def test_remove_progress_bar_tty(self):
        """プログレスバー削除（TTY）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)
        manager = progress.ProgressManager(console)

        manager.set_progress_bar("test", total=10)
        manager.remove_progress_bar("test")

        assert "test" not in manager._progress_bar

    def test_print_tty(self):
        """print メソッド（TTY環境では出力されない）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)
        manager = progress.ProgressManager(console)

        manager.print("テスト出力")

        result = output.getvalue()
        assert result == ""

    def test_create_display_with_tasks(self):
        """表示内容作成（タスクあり）"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)
        manager = progress.ProgressManager(console)

        manager.set_progress_bar("test", total=10)
        result = manager._create_display()

        # Group（ステータスバー + プログレス）
        assert isinstance(result, rich.console.Group)


class TestStatusBar:
    """ステータスバーのテスト"""

    def test_create_status_bar_normal(self):
        """通常のステータスバー"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True, width=80)
        manager = progress.ProgressManager(console)

        manager.set_status("処理中...")
        table = manager._create_status_bar()

        assert table is not None

    def test_create_status_bar_error(self):
        """エラー時のステータスバー"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True, width=80)
        manager = progress.ProgressManager(console)

        manager.set_status("エラー発生", is_error=True)
        table = manager._create_status_bar()

        assert table is not None

    def test_elapsed_time_format(self, mocker):
        """経過時間のフォーマット"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True, width=80)
        manager = progress.ProgressManager(console)

        # 開始時刻を固定
        manager._start_time = time.time() - 65  # 1分5秒前

        table = manager._create_status_bar()
        assert table is not None

    def test_tmux_width_adjustment(self, mocker, monkeypatch):
        """TMUX 環境での幅調整"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True, width=100)
        manager = progress.ProgressManager(console)

        monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,12345,0")

        table = manager._create_status_bar()

        # TMUX 環境では幅が調整される（100 - 2 = 98）
        assert table.width == 98


class TestMultipleProgressBars:
    """複数プログレスバーのテスト"""

    def test_multiple_bars(self):
        """複数のプログレスバーを管理"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)
        manager = progress.ProgressManager(console)

        manager.set_progress_bar("bar1", total=10)
        manager.set_progress_bar("bar2", total=20)

        assert "bar1" in manager._progress_bar
        assert "bar2" in manager._progress_bar
        assert manager._progress_bar["bar1"].total == 10
        assert manager._progress_bar["bar2"].total == 20

    def test_update_specific_bar(self):
        """特定のプログレスバーを更新"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)
        manager = progress.ProgressManager(console)

        manager.set_progress_bar("bar1", total=10)
        manager.set_progress_bar("bar2", total=20)

        manager.update_progress_bar("bar1", advance=5)
        manager.update_progress_bar("bar2", advance=10)

        assert manager._progress_bar["bar1"].count == 5
        assert manager._progress_bar["bar2"].count == 10

    def test_remove_one_bar(self):
        """1つのプログレスバーを削除"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)
        manager = progress.ProgressManager(console)

        manager.set_progress_bar("bar1", total=10)
        manager.set_progress_bar("bar2", total=20)

        manager.remove_progress_bar("bar1")

        assert "bar1" not in manager._progress_bar
        assert "bar2" in manager._progress_bar
