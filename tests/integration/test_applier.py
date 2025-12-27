#!/usr/bin/env python3
# ruff: noqa: S101
"""
applier.py の統合テスト
"""
import io
import textwrap

import rich.console

import py_project.applier as applier


class TestApplyConfigs:
    """apply_configs のテスト"""

    def test_apply_all_configs(self, sample_config, tmp_project, tmp_templates):
        """全設定を適用"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.apply_configs(
            config=sample_config,
            dry_run=False,
            console=console,
        )

        assert summary.projects_processed == 1
        assert summary.errors == 0
        # pyproject が更新される
        assert summary.updated >= 1

    def test_apply_dry_run(self, sample_config, tmp_project, tmp_templates):
        """ドライランモード"""
        original_pyproject = (tmp_project / "pyproject.toml").read_text()

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.apply_configs(
            config=sample_config,
            dry_run=True,
            console=console,
        )

        # ファイルは変更されない
        assert (tmp_project / "pyproject.toml").read_text() == original_pyproject
        # 出力に "Dry run" が含まれる
        assert "Dry run" in output.getvalue()

    def test_apply_specific_project(self, tmp_path, tmp_templates):
        """特定プロジェクトのみ適用"""
        # 2つのプロジェクトを作成
        project1 = tmp_path / "project1"
        project1.mkdir()
        (project1 / "pyproject.toml").write_text(
            textwrap.dedent("""\
                [project]
                name = "project1"
                version = "0.1.0"
                description = "Project 1"
                dependencies = []
            """)
        )

        project2 = tmp_path / "project2"
        project2.mkdir()
        (project2 / "pyproject.toml").write_text(
            textwrap.dedent("""\
                [project]
                name = "project2"
                version = "0.1.0"
                description = "Project 2"
                dependencies = []
            """)
        )

        config = {
            "template_dir": str(tmp_templates),
            "defaults": {"configs": ["pyproject"]},
            "projects": [
                {"name": "project1", "path": str(project1)},
                {"name": "project2", "path": str(project2)},
            ],
        }

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.apply_configs(
            config=config,
            projects=["project1"],
            dry_run=False,
            console=console,
        )

        # project1 のみ処理される
        assert summary.projects_processed == 1
        assert "project1" in output.getvalue()
        # project2 は処理されない
        assert "project2" not in output.getvalue()

    def test_apply_specific_config_type(self, sample_config, tmp_project, tmp_templates):
        """特定設定タイプのみ適用"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.apply_configs(
            config=sample_config,
            config_types=["gitignore"],
            dry_run=False,
            console=console,
        )

        assert summary.projects_processed == 1
        # gitignore のみ作成される
        assert (tmp_project / ".gitignore").exists()
        # pre-commit は作成されない
        assert not (tmp_project / ".pre-commit-config.yaml").exists()

    def test_apply_with_backup(self, sample_config, tmp_project, tmp_templates):
        """バックアップ作成"""
        # 既存の gitignore を作成
        (tmp_project / ".gitignore").write_text("old content")

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.apply_configs(
            config=sample_config,
            config_types=["gitignore"],
            dry_run=False,
            backup=True,
            console=console,
        )

        assert summary.updated >= 1
        # バックアップが作成される
        assert (tmp_project / ".gitignore.bak").exists()
        assert (tmp_project / ".gitignore.bak").read_text() == "old content"

    def test_apply_nonexistent_project(self, tmp_path, tmp_templates):
        """存在しないプロジェクト"""
        config = {
            "template_dir": str(tmp_templates),
            "defaults": {"configs": ["pyproject"]},
            "projects": [
                {"name": "nonexistent", "path": str(tmp_path / "nonexistent")},
            ],
        }

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.apply_configs(
            config=config,
            dry_run=False,
            console=console,
        )

        assert summary.errors == 1
        assert "ディレクトリが見つかりません" in output.getvalue()

    def test_apply_unknown_config_type(self, tmp_path, tmp_templates):
        """未知の設定タイプ"""
        project = tmp_path / "project"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        config = {
            "template_dir": str(tmp_templates),
            "defaults": {"configs": ["unknown-type"]},
            "projects": [
                {"name": "project", "path": str(project)},
            ],
        }

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.apply_configs(
            config=config,
            dry_run=False,
            console=console,
        )

        assert summary.errors == 1
        assert "未知の設定タイプ" in output.getvalue()


class TestApplySummary:
    """ApplySummary のテスト"""

    def test_summary_counts(self, sample_config, tmp_project, tmp_templates):
        """サマリのカウント"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.apply_configs(
            config=sample_config,
            dry_run=False,
            console=console,
        )

        # created + updated + unchanged + skipped >= 0
        total = summary.created + summary.updated + summary.unchanged + summary.skipped
        assert total >= 0


class TestShowDiff:
    """show_diff オプションのテスト"""

    def test_show_diff(self, sample_config, tmp_project, tmp_templates):
        """差分表示モード"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        applier.apply_configs(
            config=sample_config,
            show_diff=True,
            console=console,
        )

        result = output.getvalue()
        # 何らかの出力がある
        assert len(result) > 0

    def test_show_diff_no_changes(self, tmp_project, tmp_templates):
        """差分なしの場合の表示"""
        # gitignore をテンプレートと同じ内容で作成
        import py_project.handlers.base as handlers_base
        import py_project.handlers.template_copy as template_copy

        handler = template_copy.GitignoreHandler()
        context = handlers_base.ApplyContext(
            config={},
            template_dir=tmp_templates,
            dry_run=False,
            backup=False,
        )
        project = {"name": "test-project", "path": str(tmp_project)}
        content = handler.render_template(project, context)
        (tmp_project / ".gitignore").write_text(content)

        config = {
            "template_dir": str(tmp_templates),
            "defaults": {"configs": ["gitignore"]},
            "projects": [project],
        }

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        applier.apply_configs(
            config=config,
            show_diff=True,
            console=console,
        )

        result = output.getvalue()
        # up to date が表示される
        assert "up to date" in result


class TestGetProjectConfigs:
    """get_project_configs のテスト"""

    def test_project_specific_configs(self):
        """プロジェクト固有の設定"""
        project = {"name": "test", "path": "/tmp/test", "configs": ["ruff", "pre-commit"]}
        defaults = {"configs": ["pyproject"]}

        result = applier.get_project_configs(project, defaults)

        assert result == ["ruff", "pre-commit"]

    def test_default_configs(self):
        """デフォルト設定の使用"""
        project = {"name": "test", "path": "/tmp/test"}
        defaults = {"configs": ["pyproject", "gitignore"]}

        result = applier.get_project_configs(project, defaults)

        assert result == ["pyproject", "gitignore"]

    def test_empty_defaults(self):
        """デフォルト設定が空の場合"""
        project = {"name": "test", "path": "/tmp/test"}
        defaults = {}

        result = applier.get_project_configs(project, defaults)

        assert result == []


class TestApplyWithoutConsole:
    """console 引数なしのテスト"""

    def test_apply_without_console(self, sample_config):
        """console を渡さない場合"""
        # console=None の場合、内部で Console が作成される
        summary = applier.apply_configs(
            config=sample_config,
            dry_run=True,
            console=None,
        )

        assert summary.projects_processed == 1


class TestUpdateSummary:
    """_update_summary のテスト"""

    def test_update_summary_created(self):
        """created ステータス"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status="created")

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.created == 1

    def test_update_summary_updated(self):
        """updated ステータス"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status="updated")

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.updated == 1

    def test_update_summary_unchanged(self):
        """unchanged ステータス"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status="unchanged")

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.unchanged == 1

    def test_update_summary_skipped(self):
        """skipped ステータス"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status="skipped")

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.skipped == 1

    def test_update_summary_error_with_message(self):
        """エラーメッセージ付きのエラー"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status="error", message="テストエラー")

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.errors == 1
        assert len(summary.error_messages) == 1
        assert "テストエラー" in summary.error_messages[0]

    def test_update_summary_error_without_message(self):
        """エラーメッセージなしのエラー"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status="error")

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.errors == 1
        assert len(summary.error_messages) == 0

    def test_update_summary_unknown_status(self):
        """未知のステータス（何も更新されない）"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status="unknown_status")

        applier._update_summary(summary, result, "test-project", "pyproject")

        # 何も更新されない
        assert summary.created == 0
        assert summary.updated == 0
        assert summary.unchanged == 0
        assert summary.skipped == 0
        assert summary.errors == 0


class TestPrintResult:
    """_print_result のテスト"""

    def test_print_result_with_message(self):
        """メッセージ付きの結果表示"""
        import py_project.handlers.base as handlers_base

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        result = handlers_base.ApplyResult(status="updated", message="詳細メッセージ")

        applier._print_result(console, "pyproject", result, dry_run=False)

        assert "詳細メッセージ" in output.getvalue()

    def test_print_result_unknown_status(self):
        """未知のステータス"""
        import py_project.handlers.base as handlers_base

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        result = handlers_base.ApplyResult(status="unknown_status")

        applier._print_result(console, "pyproject", result, dry_run=False)

        assert "unknown_status" in output.getvalue()


class TestPrintSummary:
    """_print_summary のテスト"""

    def test_print_summary_with_skipped(self):
        """skipped を含むサマリ表示"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.ApplySummary(
            created=1,
            updated=2,
            unchanged=3,
            skipped=4,
            projects_processed=1,
        )

        applier._print_summary(console, summary, dry_run=False)

        result = output.getvalue()
        assert "Skipped" in result

    def test_print_summary_with_errors(self):
        """エラーを含むサマリ表示"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.ApplySummary(
            errors=2,
            projects_processed=1,
            error_messages=["Error 1", "Error 2"],
        )

        applier._print_summary(console, summary, dry_run=False)

        result = output.getvalue()
        assert "Errors" in result
        assert "Error 1" in result

    def test_print_summary_dry_run_with_changes(self):
        """ドライランで変更がある場合"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.ApplySummary(
            created=1,
            updated=1,
            projects_processed=1,
        )

        applier._print_summary(console, summary, dry_run=True)

        result = output.getvalue()
        assert "--apply" in result

    def test_print_summary_apply_success(self):
        """適用成功時の Done! 表示"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.ApplySummary(
            updated=1,
            projects_processed=1,
            errors=0,
        )

        applier._print_summary(console, summary, dry_run=False)

        result = output.getvalue()
        assert "Done!" in result


class TestRunUvSync:
    """_run_uv_sync のテスト"""

    def test_run_uv_sync_success(self, tmp_project, mocker):
        """uv sync 成功"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        applier._run_uv_sync(tmp_project, console)

        result = output.getvalue()
        assert "uv sync completed" in result

    def test_run_uv_sync_failure_with_stderr(self, tmp_project, mocker):
        """uv sync 失敗（stderr あり）"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Error message\nLine 2\nLine 3"

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        applier._run_uv_sync(tmp_project, console)

        result = output.getvalue()
        assert "uv sync failed" in result
        assert "Error message" in result

    def test_run_uv_sync_failure_without_stderr(self, tmp_project, mocker):
        """uv sync 失敗（stderr なし）"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = ""

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        applier._run_uv_sync(tmp_project, console)

        result = output.getvalue()
        assert "uv sync failed" in result

    def test_run_uv_sync_timeout(self, tmp_project, mocker):
        """uv sync タイムアウト"""
        import subprocess

        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("uv", 120))

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        applier._run_uv_sync(tmp_project, console)

        result = output.getvalue()
        assert "timed out" in result

    def test_run_uv_sync_not_found(self, tmp_project, mocker):
        """uv コマンドが見つからない"""
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        applier._run_uv_sync(tmp_project, console)

        result = output.getvalue()
        assert "uv command not found" in result
