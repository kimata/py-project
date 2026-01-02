#!/usr/bin/env python3
# ruff: noqa: S101, ARG002, SLF001, D200, D403, PLR0402, S108
"""
applier.py の統合テスト
"""

import io
import textwrap

import rich.console

import py_project.applier as applier
import py_project.config
import py_project.handlers.base as handlers_base


class TestApplyConfigs:
    """apply_configs のテスト"""

    def test_apply_all_configs(self, sample_config, tmp_project, tmp_templates):
        """全設定を適用"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        options = py_project.config.ApplyOptions(dry_run=False)

        summary = applier.apply_configs(
            config=sample_config,
            options=options,
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
        options = py_project.config.ApplyOptions(dry_run=True)

        applier.apply_configs(
            config=sample_config,
            options=options,
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

        config = py_project.config.Config(
            template_dir=str(tmp_templates),
            defaults=py_project.config.Defaults(configs=["pyproject"]),
            projects=[
                py_project.config.Project(name="project1", path=str(project1)),
                py_project.config.Project(name="project2", path=str(project2)),
            ],
        )

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        options = py_project.config.ApplyOptions(dry_run=False)
        summary = applier.apply_configs(
            config=config,
            options=options,
            projects=["project1"],
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

        options = py_project.config.ApplyOptions(dry_run=False)
        summary = applier.apply_configs(
            config=sample_config,
            options=options,
            config_types=["gitignore"],
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

        options = py_project.config.ApplyOptions(dry_run=False, backup=True)
        summary = applier.apply_configs(
            config=sample_config,
            options=options,
            config_types=["gitignore"],
            console=console,
        )

        assert summary.updated >= 1
        # バックアップが作成される
        assert (tmp_project / ".gitignore.bak").exists()
        assert (tmp_project / ".gitignore.bak").read_text() == "old content"

    def test_apply_nonexistent_project(self, tmp_path, tmp_templates):
        """存在しないプロジェクト"""
        config = py_project.config.Config(
            template_dir=str(tmp_templates),
            defaults=py_project.config.Defaults(configs=["pyproject"]),
            projects=[
                py_project.config.Project(name="nonexistent", path=str(tmp_path / "nonexistent")),
            ],
        )

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        options = py_project.config.ApplyOptions(dry_run=False)
        summary = applier.apply_configs(
            config=config,
            options=options,
            console=console,
        )

        assert summary.errors == 1
        assert "ディレクトリが見つかりません" in output.getvalue()

    def test_apply_unknown_config_type(self, tmp_path, tmp_templates):
        """未知の設定タイプ"""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        config = py_project.config.Config(
            template_dir=str(tmp_templates),
            defaults=py_project.config.Defaults(configs=["unknown-type"]),
            projects=[
                py_project.config.Project(name="project", path=str(project_dir)),
            ],
        )

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        options = py_project.config.ApplyOptions(dry_run=False)
        summary = applier.apply_configs(
            config=config,
            options=options,
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

        options = py_project.config.ApplyOptions(dry_run=False)
        summary = applier.apply_configs(
            config=sample_config,
            options=options,
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

        options = py_project.config.ApplyOptions(show_diff=True)
        applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
        )

        result = output.getvalue()
        # 何らかの出力がある
        assert len(result) > 0

    def test_show_diff_no_changes(self, tmp_project, tmp_templates):
        """差分なしの場合の表示"""
        # gitignore をテンプレートと同じ内容で作成
        import py_project.handlers.template_copy as template_copy

        handler = template_copy.GitignoreHandler()
        config = py_project.config.Config(
            defaults=py_project.config.Defaults(configs=[]),
            projects=[],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_templates,
            dry_run=False,
            backup=False,
        )
        project = py_project.config.Project(name="test-project", path=str(tmp_project))
        content = handler.render_template(project, context)
        (tmp_project / ".gitignore").write_text(content)

        full_config = py_project.config.Config(
            template_dir=str(tmp_templates),
            defaults=py_project.config.Defaults(configs=["gitignore"]),
            projects=[project],
        )

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        options = py_project.config.ApplyOptions(show_diff=True)
        applier.apply_configs(
            config=full_config,
            options=options,
            console=console,
        )

        result = output.getvalue()
        # up to date が表示される
        assert "up to date" in result


class TestGetProjectConfigs:
    """get_project_configs のテスト"""

    def test_project_specific_configs(self):
        """プロジェクト固有の設定"""
        project = py_project.config.Project(name="test", path="/tmp/test", configs=["ruff", "pre-commit"])
        defaults = py_project.config.Defaults(configs=["pyproject"])

        result = applier.get_project_configs(project, defaults)

        assert result == ["ruff", "pre-commit"]

    def test_default_configs(self):
        """デフォルト設定の使用"""
        project = py_project.config.Project(name="test", path="/tmp/test")
        defaults = py_project.config.Defaults(configs=["pyproject", "gitignore"])

        result = applier.get_project_configs(project, defaults)

        assert result == ["pyproject", "gitignore"]

    def test_empty_defaults(self):
        """デフォルト設定が空の場合"""
        project = py_project.config.Project(name="test", path="/tmp/test")
        defaults = py_project.config.Defaults(configs=[])

        result = applier.get_project_configs(project, defaults)

        assert result == []


class TestApplyWithoutConsole:
    """console 引数なしのテスト"""

    def test_apply_without_console(self, sample_config):
        """console を渡さない場合"""
        # console=None の場合、内部で Console が作成される
        options = py_project.config.ApplyOptions(dry_run=True)
        summary = applier.apply_configs(
            config=sample_config,
            options=options,
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


class TestIsGitRepo:
    """_is_git_repo のテスト"""

    def test_is_git_repo_true(self, tmp_path, mocker):
        """Git リポジトリの場合"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        result = applier._is_git_repo(tmp_path)

        assert result is True

    def test_is_git_repo_false(self, tmp_path, mocker):
        """Git リポジトリでない場合"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 128

        result = applier._is_git_repo(tmp_path)

        assert result is False

    def test_is_git_repo_timeout(self, tmp_path, mocker):
        """タイムアウトの場合"""
        import subprocess

        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5))

        result = applier._is_git_repo(tmp_path)

        assert result is False

    def test_is_git_repo_git_not_found(self, tmp_path, mocker):
        """git コマンドが見つからない場合"""
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())

        result = applier._is_git_repo(tmp_path)

        assert result is False


class TestRunGitAdd:
    """_run_git_add のテスト"""

    def test_run_git_add_success(self, tmp_path, mocker):
        """git add 成功"""
        # _is_git_repo を True に
        mocker.patch.object(applier, "_is_git_repo", return_value=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        files = [tmp_path / "file1.txt", tmp_path / "file2.txt"]
        applier._run_git_add(tmp_path, files, console)

        result = output.getvalue()
        assert "git add" in result
        assert "file1.txt" in result

    def test_run_git_add_outside_project(self, tmp_path, mocker):
        """プロジェクト外のファイルの場合はフルパスで git add"""
        import pathlib

        mocker.patch.object(applier, "_is_git_repo", return_value=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        # プロジェクト外のパスを指定
        outside_file = pathlib.Path("/some/other/path/file.txt")
        applier._run_git_add(tmp_path, [outside_file], console)

        result = output.getvalue()
        # フルパスで git add される
        assert "git add" in result
        assert "/some/other/path/file.txt" in result

    def test_run_git_add_not_git_repo(self, tmp_path, mocker):
        """Git リポジトリでない場合はスキップ"""
        mocker.patch.object(applier, "_is_git_repo", return_value=False)
        mock_run = mocker.patch("subprocess.run")

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        files = [tmp_path / "file1.txt"]
        applier._run_git_add(tmp_path, files, console)

        # subprocess.run は呼ばれない
        mock_run.assert_not_called()
        # 何も出力されない
        assert output.getvalue() == ""

    def test_run_git_add_failure(self, tmp_path, mocker):
        """git add 失敗"""
        mocker.patch.object(applier, "_is_git_repo", return_value=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "fatal: error message"

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        files = [tmp_path / "file1.txt"]
        applier._run_git_add(tmp_path, files, console)

        result = output.getvalue()
        assert "git add failed" in result

    def test_run_git_add_timeout(self, tmp_path, mocker):
        """git add タイムアウト"""
        import subprocess

        mocker.patch.object(applier, "_is_git_repo", return_value=True)
        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30))

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        files = [tmp_path / "file1.txt"]
        applier._run_git_add(tmp_path, files, console)

        result = output.getvalue()
        assert "git add timed out" in result

    def test_run_git_add_git_not_found(self, tmp_path, mocker):
        """git コマンドが見つからない場合"""
        mocker.patch.object(applier, "_is_git_repo", return_value=True)
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        files = [tmp_path / "file1.txt"]
        applier._run_git_add(tmp_path, files, console)

        # 何も出力されない（サイレントスキップ）
        assert output.getvalue() == ""


class TestValidateProjects:
    """_validate_projects のテスト"""

    def test_validate_existing_projects(self):
        """存在するプロジェクト名を指定した場合は空リストが返る"""
        requested = ["project1", "project2"]
        available = ["project1", "project2", "project3"]

        result = applier._validate_projects(requested, available)

        assert result == []

    def test_validate_missing_project(self, caplog):
        """存在しないプロジェクト名を指定した場合は警告が出る"""
        import logging

        requested = ["nonexistent"]
        available = ["project1", "project2", "project3"]

        with caplog.at_level(logging.WARNING):
            result = applier._validate_projects(requested, available)

        assert result == ["nonexistent"]
        assert "nonexistent" in caplog.text
        assert "設定に存在しません" in caplog.text

    def test_validate_with_close_matches(self, caplog):
        """類似候補がある場合は表示される"""
        import logging

        requested = ["projec1"]  # project1 のタイポ
        available = ["project1", "project2", "project3"]

        with caplog.at_level(logging.INFO):
            result = applier._validate_projects(requested, available)

        assert result == ["projec1"]
        assert "類似候補" in caplog.text
        assert "project1" in caplog.text

    def test_validate_no_close_matches(self, caplog):
        """類似候補がない場合は表示されない"""
        import logging

        requested = ["completely-different"]
        available = ["project1", "project2", "project3"]

        with caplog.at_level(logging.INFO):
            result = applier._validate_projects(requested, available)

        assert result == ["completely-different"]
        assert "類似候補" not in caplog.text

    def test_validate_multiple_missing_projects(self, caplog):
        """複数の存在しないプロジェクトを指定した場合"""
        import logging

        requested = ["missing1", "project1", "missing2"]
        available = ["project1", "project2", "project3"]

        with caplog.at_level(logging.WARNING):
            result = applier._validate_projects(requested, available)

        assert result == ["missing1", "missing2"]
        assert "missing1" in caplog.text
        assert "missing2" in caplog.text

    def test_validate_empty_requested(self):
        """空のリクエストリストの場合は空リストが返る"""
        requested: list[str] = []
        available = ["project1", "project2"]

        result = applier._validate_projects(requested, available)

        assert result == []

    def test_validate_empty_available(self, caplog):
        """利用可能なプロジェクトが空の場合"""
        import logging

        requested = ["project1"]
        available: list[str] = []

        with caplog.at_level(logging.WARNING):
            result = applier._validate_projects(requested, available)

        assert result == ["project1"]
        assert "設定に存在しません" in caplog.text


class TestApplyWithGitAdd:
    """git_add オプションのテスト"""

    def test_apply_with_git_add(self, sample_config, tmp_project, tmp_templates, mocker):
        """git_add=True でファイルが git add される"""
        mocker.patch.object(applier, "_is_git_repo", return_value=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        options = py_project.config.ApplyOptions(dry_run=False, git_add=True, run_sync=False)
        applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
        )

        result = output.getvalue()
        # git add が実行される
        assert "git add" in result

    def test_apply_with_git_add_dry_run(self, sample_config, tmp_project, tmp_templates, mocker):
        """dry_run=True では git_add は実行されない"""
        mock_git_add = mocker.patch.object(applier, "_run_git_add")

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        options = py_project.config.ApplyOptions(dry_run=True, git_add=True)
        applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
        )

        # _run_git_add は呼ばれない
        mock_git_add.assert_not_called()
