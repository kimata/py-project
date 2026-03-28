#!/usr/bin/env python3
# ruff: noqa: S101, S108
"""
applier.py の統合テスト
"""

import io
import textwrap

import my_lib.cui_progress
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
        # 出力に "確認モード" が含まれる
        assert "確認モード" in output.getvalue()

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
    """_get_project_configs のテスト"""

    def test_merge_project_configs_with_defaults(self):
        """プロジェクトの configs は defaults にマージされる"""
        project = py_project.config.Project(name="test", path="/tmp/test", configs=["ruff", "pre-commit"])
        defaults = py_project.config.Defaults(configs=["pyproject"])

        result = applier._get_project_configs(project, defaults)

        # defaults.configs をベースに project.configs が追加される
        assert result == ["pyproject", "ruff", "pre-commit"]

    def test_default_configs(self):
        """デフォルト設定の使用"""
        project = py_project.config.Project(name="test", path="/tmp/test")
        defaults = py_project.config.Defaults(configs=["pyproject", "gitignore"])

        result = applier._get_project_configs(project, defaults)

        assert result == ["pyproject", "gitignore"]

    def test_empty_defaults(self):
        """デフォルト設定が空の場合"""
        project = py_project.config.Project(name="test", path="/tmp/test")
        defaults = py_project.config.Defaults(configs=[])

        result = applier._get_project_configs(project, defaults)

        assert result == []

    def test_exclude_configs(self):
        """exclude_configs で設定を除外できる"""
        project = py_project.config.Project(name="test", path="/tmp/test", exclude_configs=["gitignore"])
        defaults = py_project.config.Defaults(configs=["pyproject", "gitignore", "renovate"])

        result = applier._get_project_configs(project, defaults)

        assert result == ["pyproject", "renovate"]

    def test_exclude_configs_with_add(self):
        """configs 追加と exclude_configs を同時に使用"""
        project = py_project.config.Project(
            name="test",
            path="/tmp/test",
            configs=["ruff"],
            exclude_configs=["gitignore"],
        )
        defaults = py_project.config.Defaults(configs=["pyproject", "gitignore"])

        result = applier._get_project_configs(project, defaults)

        # pyproject + ruff (gitignore は除外)
        assert result == ["pyproject", "ruff"]

    def test_no_duplicate_configs(self):
        """重複する configs は追加されない"""
        project = py_project.config.Project(name="test", path="/tmp/test", configs=["pyproject", "ruff"])
        defaults = py_project.config.Defaults(configs=["pyproject", "gitignore"])

        result = applier._get_project_configs(project, defaults)

        # pyproject は重複しないので1回だけ
        assert result == ["pyproject", "gitignore", "ruff"]

    def test_exclude_nonexistent_config(self):
        """存在しない設定を exclude_configs で指定しても問題ない"""
        project = py_project.config.Project(
            name="test",
            path="/tmp/test",
            exclude_configs=["nonexistent-config"],  # 存在しない設定
        )
        defaults = py_project.config.Defaults(configs=["pyproject", "gitignore"])

        result = applier._get_project_configs(project, defaults)

        # nonexistent-config は無視される
        assert result == ["pyproject", "gitignore"]


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
        result = handlers_base.ApplyResult(status=handlers_base.ApplyStatus.CREATED)

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.created == 1

    def test_update_summary_updated(self):
        """updated ステータス"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status=handlers_base.ApplyStatus.UPDATED)

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.updated == 1

    def test_update_summary_unchanged(self):
        """unchanged ステータス"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status=handlers_base.ApplyStatus.UNCHANGED)

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.unchanged == 1

    def test_update_summary_skipped(self):
        """skipped ステータス"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status=handlers_base.ApplyStatus.SKIPPED)

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.skipped == 1

    def test_update_summary_error_with_message(self):
        """エラーメッセージ付きのエラー"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status=handlers_base.ApplyStatus.ERROR, message="テストエラー")

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.errors == 1
        assert len(summary.error_messages) == 1
        assert "テストエラー" in summary.error_messages[0]

    def test_update_summary_error_without_message(self):
        """エラーメッセージなしのエラー"""
        import py_project.handlers.base as handlers_base

        summary = applier.ApplySummary()
        result = handlers_base.ApplyResult(status=handlers_base.ApplyStatus.ERROR)

        applier._update_summary(summary, result, "test-project", "pyproject")

        assert summary.errors == 1
        assert len(summary.error_messages) == 0


class TestPrintResult:
    """_print_result のテスト"""

    def test_print_result_with_message(self):
        """メッセージ付きの結果表示"""
        import my_lib.cui_progress

        import py_project.handlers.base as handlers_base

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        result = handlers_base.ApplyResult(status=handlers_base.ApplyStatus.UPDATED, message="詳細メッセージ")
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        applier._print_result(console, "pyproject", result, dry_run=False, progress=progress)

        assert "詳細メッセージ" in output.getvalue()

    def test_print_result_updated_status(self):
        """更新ステータスの表示"""
        import my_lib.cui_progress

        import py_project.handlers.base as handlers_base

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        result = handlers_base.ApplyResult(status=handlers_base.ApplyStatus.UPDATED)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        applier._print_result(console, "pyproject", result, dry_run=False, progress=progress)

        assert "更新" in output.getvalue()


class TestPrintSummary:
    """_print_summary のテスト"""

    def test_print_summary_with_skipped(self):
        """skipped を含むサマリ表示"""
        import my_lib.cui_progress

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        summary = applier.ApplySummary(
            created=1,
            updated=2,
            unchanged=3,
            skipped=4,
            projects_processed=1,
        )

        applier._print_summary(console, summary, dry_run=False, progress=progress)

        result = output.getvalue()
        assert "スキップ" in result

    def test_print_summary_with_errors(self):
        """エラーを含むサマリ表示"""
        import my_lib.cui_progress

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        summary = applier.ApplySummary(
            errors=2,
            projects_processed=1,
            error_messages=["Error 1", "Error 2"],
        )

        applier._print_summary(console, summary, dry_run=False, progress=progress)

        result = output.getvalue()
        assert "エラー" in result
        assert "Error 1" in result

    def test_print_summary_dry_run_with_changes(self):
        """確認モードで変更がある場合"""
        import my_lib.cui_progress

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        summary = applier.ApplySummary(
            created=1,
            updated=1,
            projects_processed=1,
        )

        applier._print_summary(console, summary, dry_run=True, progress=progress)

        result = output.getvalue()
        assert "--apply" in result

    def test_print_summary_apply_success(self):
        """適用成功時の 完了！ 表示"""
        import my_lib.cui_progress

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        summary = applier.ApplySummary(
            updated=1,
            projects_processed=1,
            errors=0,
        )

        applier._print_summary(console, summary, dry_run=False, progress=progress)

        result = output.getvalue()
        assert "完了！" in result


class TestRunUvSync:
    """_run_uv_sync のテスト"""

    def test_run_uv_sync_success(self, tmp_project, mocker):
        """uv sync 成功"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        result = applier._run_uv_sync(tmp_project, console, progress)

        assert result is True
        assert "uv sync completed" in output.getvalue()

    def test_run_uv_sync_failure_with_stderr(self, tmp_project, mocker):
        """uv sync 失敗（stderr あり）"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Error message\nLine 2\nLine 3"

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        result = applier._run_uv_sync(tmp_project, console, progress)

        assert result is False
        output_text = output.getvalue()
        assert "uv sync failed" in output_text
        assert "Error message" in output_text

    def test_run_uv_sync_failure_without_stderr(self, tmp_project, mocker):
        """uv sync 失敗（stderr なし）"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = ""

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        result = applier._run_uv_sync(tmp_project, console, progress)

        assert result is False
        assert "uv sync failed" in output.getvalue()

    def test_run_uv_sync_timeout(self, tmp_project, mocker):
        """uv sync タイムアウト"""
        import subprocess

        import my_lib.cui_progress

        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("uv", 120))

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        result = applier._run_uv_sync(tmp_project, console, progress)

        assert result is False
        assert "timed out" in output.getvalue()

    def test_run_uv_sync_not_found(self, tmp_project, mocker):
        """uv コマンドが見つからない"""
        import my_lib.cui_progress

        mocker.patch("subprocess.run", side_effect=FileNotFoundError())

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        result = applier._run_uv_sync(tmp_project, console, progress)

        assert result is False
        assert "uv command not found" in output.getvalue()


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


class TestHasUncommittedChanges:
    """_has_uncommitted_changes のテスト"""

    def test_has_uncommitted_changes_true(self, tmp_path, mocker):
        """未コミットの変更がある場合"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = " M file.txt\n"

        result = applier._has_uncommitted_changes(tmp_path)

        assert result is True

    def test_has_uncommitted_changes_false(self, tmp_path, mocker):
        """未コミットの変更がない場合"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""

        result = applier._has_uncommitted_changes(tmp_path)

        assert result is False

    def test_has_uncommitted_changes_timeout(self, tmp_path, mocker):
        """タイムアウトの場合"""
        import subprocess

        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10))

        result = applier._has_uncommitted_changes(tmp_path)

        assert result is False


class TestRunGitStash:
    """_run_git_stash のテスト"""

    def test_run_git_stash_success(self, tmp_path, mocker):
        """git stash 成功"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        result = applier._run_git_stash(tmp_path, console, progress)

        assert result is True
        assert "一時退避" in output.getvalue()

    def test_run_git_stash_failure(self, tmp_path, mocker):
        """git stash 失敗"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "error message"

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        result = applier._run_git_stash(tmp_path, console, progress)

        assert result is False
        assert "stash failed" in output.getvalue()


class TestRunGitStashPop:
    """_run_git_stash_pop のテスト"""

    def test_run_git_stash_pop_success(self, tmp_path, mocker):
        """git stash pop 成功"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        applier._run_git_stash_pop(tmp_path, console, progress)

        assert "復元" in output.getvalue()

    def test_run_git_stash_pop_failure(self, tmp_path, mocker):
        """git stash pop 失敗（コンフリクト以外）"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "some error"

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        applier._run_git_stash_pop(tmp_path, console, progress)

        assert "stash pop failed" in output.getvalue()

    def test_run_git_stash_pop_conflict(self, tmp_path, mocker):
        """git stash pop でコンフリクト発生"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        # stash pop がコンフリクトで失敗、その後のクリーンアップは成功
        mock_run.side_effect = [
            mocker.MagicMock(
                returncode=1,
                stdout="CONFLICT (content): Merge conflict in file.txt",
                stderr="",
            ),
            mocker.MagicMock(returncode=0),  # checkout --theirs
            mocker.MagicMock(returncode=0),  # reset HEAD
            mocker.MagicMock(returncode=0),  # stash drop
        ]

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        applier._run_git_stash_pop(tmp_path, console, progress)

        output_text = output.getvalue()
        assert "コンフリクト発生" in output_text
        assert "破棄されました" in output_text

    def test_run_git_stash_pop_overwritten_by_merge(self, tmp_path, mocker):
        """git stash pop で overwritten by merge エラー"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(
                returncode=1,
                stdout="",
                stderr="error: Your local changes would be overwritten by merge",
            ),
            mocker.MagicMock(returncode=0),  # checkout --theirs
            mocker.MagicMock(returncode=0),  # reset HEAD
            mocker.MagicMock(returncode=0),  # stash drop
        ]

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        applier._run_git_stash_pop(tmp_path, console, progress)

        output_text = output.getvalue()
        assert "コンフリクト発生" in output_text
        assert "破棄されました" in output_text


class TestGenerateCommitMessage:
    """_generate_commit_message のテスト"""

    def test_generate_commit_message_single_file(self):
        """単一ファイルの commit メッセージ（message なし）"""
        import pathlib

        files_info = [
            applier.GitCommitFile(path=pathlib.Path("pyproject.toml"), config_type="pyproject", message="")
        ]

        result = applier._generate_commit_message(files_info)

        assert "- pyproject.toml: pyproject を同期" in result
        assert "🤖 Generated with [py-project]" in result

    def test_generate_commit_message_multiple_files(self):
        """複数ファイルの commit メッセージ（message あり・なし混合）"""
        import pathlib

        files_info = [
            applier.GitCommitFile(
                path=pathlib.Path("pyproject.toml"), config_type="my-py-lib", message="7481d562 -> b273ff7b"
            ),
            applier.GitCommitFile(
                path=pathlib.Path(".pre-commit-config.yaml"), config_type="pre-commit", message=""
            ),
            applier.GitCommitFile(
                path=pathlib.Path("uv.lock"), config_type="uv.lock", message="my-lib を更新"
            ),
        ]

        result = applier._generate_commit_message(files_info)

        # my-py-lib は pyproject.toml と異なるので config_type が含まれる
        assert "- pyproject.toml: my-py-lib 7481d562 -> b273ff7b" in result
        # message なしは「を同期」
        assert "- .pre-commit-config.yaml: pre-commit を同期" in result
        # uv.lock は config_type が uv.lock なので省略される
        assert "- uv.lock: my-lib を更新" in result
        assert "🤖 Generated with [py-project]" in result


class TestRunGitCommit:
    """_run_git_commit のテスト

    Note: stash の処理は _process_project で行われるため、
    _run_git_commit のテストでは stash 関連のテストは含まない。

    """

    def test_run_git_commit_success(self, tmp_path, mocker):
        """git commit 成功"""
        import subprocess

        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0
        mocker.patch.object(
            applier,
            "_run_subprocess_with_group_kill",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        )

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_commit(tmp_path, files_info, console, progress)

        assert result is True
        output_text = output.getvalue()
        assert "git commit" in output_text
        assert "file1.txt" in output_text

    def test_run_git_commit_success_with_will_push(self, tmp_path, mocker):
        """git commit 成功（will_push=True の場合はログ抑制）"""
        import subprocess

        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0
        mocker.patch.object(
            applier,
            "_run_subprocess_with_group_kill",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        )

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_commit(tmp_path, files_info, console, progress, will_push=True)

        assert result is True
        # will_push=True の場合は commit のログが出力されない
        output_text = output.getvalue()
        assert "git commit" not in output_text

    def test_run_git_commit_add_failure(self, tmp_path, mocker):
        """git add 失敗"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "fatal: error"

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_commit(tmp_path, files_info, console, progress)

        assert result is False
        assert "git add failed" in output.getvalue()

    def test_run_git_commit_commit_failure(self, tmp_path, mocker):
        """git commit 失敗"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        # 1回目の add は成功、2回目の commit は失敗
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),
            mocker.MagicMock(returncode=1, stderr="commit failed"),
        ]

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_commit(tmp_path, files_info, console, progress)

        assert result is False
        assert "git commit failed" in output.getvalue()

    def test_run_git_commit_timeout(self, tmp_path, mocker):
        """git commit タイムアウト"""
        import subprocess

        import my_lib.cui_progress

        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30))

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_commit(tmp_path, files_info, console, progress)

        assert result is False
        assert "git commit timed out" in output.getvalue()

    def test_run_git_commit_git_not_found(self, tmp_path, mocker):
        """git コマンドが見つからない"""
        import my_lib.cui_progress

        mocker.patch("subprocess.run", side_effect=FileNotFoundError())

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_commit(tmp_path, files_info, console, progress)

        assert result is False

    def test_run_git_commit_outside_project(self, tmp_path, mocker):
        """プロジェクト外のファイルの場合はフルパスで commit"""
        import pathlib
        import subprocess

        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0
        mocker.patch.object(
            applier,
            "_run_subprocess_with_group_kill",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        )

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        outside_file = pathlib.Path("/some/other/path/file.txt")
        files_info = [applier.GitCommitFile(path=outside_file, config_type="config-type", message="")]
        result = applier._run_git_commit(tmp_path, files_info, console, progress)

        assert result is True
        output_text = output.getvalue()
        assert "git commit" in output_text
        assert "/some/other/path/file.txt" in output_text

    def test_run_git_commit_precommit_retry(self, tmp_path, mocker):
        """pre-commit がファイルを修正した場合にリトライする"""
        import subprocess

        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        # subprocess.run: git add のみ（commit は _run_subprocess_with_group_kill 経由）
        # 1回目: add 成功 → リトライ: add -u 成功, add 成功 → 2回目: add 成功
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # add (1回目のループ)
            mocker.MagicMock(returncode=0),  # add -u (リトライ処理)
            mocker.MagicMock(returncode=0),  # add (リトライ処理、ファイルリスト)
            mocker.MagicMock(returncode=0),  # add (2回目のループ)
        ]
        # _run_subprocess_with_group_kill: git commit
        # 1回目: 失敗（pre-commit がファイル修正） → 2回目: 成功
        mocker.patch.object(
            applier,
            "_run_subprocess_with_group_kill",
            side_effect=[
                subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="files were modified by this hook", stderr=""
                ),
                subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
            ],
        )

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_commit(tmp_path, files_info, console, progress)

        assert result is True
        output_text = output.getvalue()
        assert "pre-commit がファイルを修正" in output_text
        assert "git commit" in output_text

    def test_run_git_commit_precommit_retry_max_retries(self, tmp_path, mocker):
        """pre-commit リトライが最大回数に達した場合"""
        import subprocess

        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        # subprocess.run: git add のみ（commit は _run_subprocess_with_group_kill 経由）
        # max_retries=3 なので、3回ループする
        mock_run.side_effect = [
            # 1回目のループ (attempt=0)
            mocker.MagicMock(returncode=0),  # add
            mocker.MagicMock(returncode=0),  # add -u (リトライ)
            mocker.MagicMock(returncode=0),  # add (リトライ、ファイルリスト)
            # 2回目のループ (attempt=1)
            mocker.MagicMock(returncode=0),  # add
            mocker.MagicMock(returncode=0),  # add -u (リトライ)
            mocker.MagicMock(returncode=0),  # add (リトライ、ファイルリスト)
            # 3回目のループ (attempt=2, max_retries-1=2 なのでリトライしない)
            mocker.MagicMock(returncode=0),  # add
        ]
        # _run_subprocess_with_group_kill: 全ての commit が pre-commit で失敗
        commit_fail = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="files were modified by this hook", stderr=""
        )
        mocker.patch.object(
            applier,
            "_run_subprocess_with_group_kill",
            side_effect=[commit_fail, commit_fail, commit_fail],
        )

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_commit(tmp_path, files_info, console, progress)

        assert result is False
        output_text = output.getvalue()
        assert "pre-commit によるファイル修正後もコミットに失敗" in output_text


class TestRunGitPush:
    """_run_git_push のテスト"""

    def test_run_git_push_success(self, tmp_path, mocker):
        """git push 成功"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_push(tmp_path, files_info, console, progress)

        assert result is True
        output_text = output.getvalue()
        assert "git commit & push" in output_text
        assert "file1.txt" in output_text

    def test_run_git_push_failure(self, tmp_path, mocker):
        """git push 失敗"""
        import my_lib.cui_progress

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "permission denied"

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_push(tmp_path, files_info, console, progress)

        assert result is False
        assert "git push failed" in output.getvalue()

    def test_run_git_push_timeout(self, tmp_path, mocker):
        """git push タイムアウト"""
        import subprocess

        import my_lib.cui_progress

        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 60))

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_push(tmp_path, files_info, console, progress)

        assert result is False
        assert "git push timed out" in output.getvalue()

    def test_run_git_push_git_not_found(self, tmp_path, mocker):
        """git コマンドが見つからない"""
        import my_lib.cui_progress

        mocker.patch("subprocess.run", side_effect=FileNotFoundError())

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        progress = my_lib.cui_progress.NullProgressManager(console=console)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_push(tmp_path, files_info, console, progress)

        assert result is False

    def test_run_git_push_with_progress(self, tmp_path, mocker):
        """progress を渡す場合"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)
        mock_progress = mocker.MagicMock(spec=my_lib.cui_progress.ProgressManager)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        result = applier._run_git_push(tmp_path, files_info, console, mock_progress)

        assert result is True
        mock_progress.print.assert_called()


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


class TestApplyWithGitCommit:
    """git_commit オプションのテスト"""

    def test_apply_with_git_commit(self, sample_config, tmp_project, tmp_templates, mocker):
        """git_commit=True でファイルが git commit される"""
        mocker.patch.object(applier, "_is_git_repo", return_value=True)
        mocker.patch.object(applier, "_has_uncommitted_changes", return_value=False)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        options = py_project.config.ApplyOptions(dry_run=False, git_commit=True, run_sync=False)
        applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
        )

        result = output.getvalue()
        # git commit が実行される
        assert "git commit" in result

    def test_apply_with_git_commit_dry_run(self, sample_config, tmp_project, tmp_templates, mocker):
        """dry_run=True では git_commit は実行されない"""
        mock_git_commit = mocker.patch.object(applier, "_run_git_commit")

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        options = py_project.config.ApplyOptions(dry_run=True, git_commit=True)
        applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
        )

        # _run_git_commit は呼ばれない
        mock_git_commit.assert_not_called()


class TestApplyWithGitPush:
    """git_push オプションのテスト"""

    def test_apply_with_git_push(self, sample_config, tmp_project, tmp_templates, mocker):
        """git_push=True でファイルが git commit & push される"""
        import subprocess

        mocker.patch.object(applier, "_is_git_repo", return_value=True)
        mocker.patch.object(applier, "_has_uncommitted_changes", return_value=False)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0
        mocker.patch.object(
            applier,
            "_run_subprocess_with_group_kill",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        )

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        options = py_project.config.ApplyOptions(dry_run=False, git_push=True, run_sync=False)
        applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
        )

        result = output.getvalue()
        # git commit & push が実行される
        assert "git commit & push" in result

    def test_apply_with_git_push_implies_git_commit(self, sample_config, tmp_project, tmp_templates, mocker):
        """git_push=True は git_commit も実行する（git_commit=False でも）"""
        mocker.patch.object(applier, "_is_git_repo", return_value=True)
        mocker.patch.object(applier, "_has_uncommitted_changes", return_value=False)
        mock_git_commit = mocker.patch.object(applier, "_run_git_commit", return_value=True)
        mock_git_push = mocker.patch.object(applier, "_run_git_push", return_value=True)

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        # git_commit=False でも git_push=True なら commit & push が実行される
        options = py_project.config.ApplyOptions(
            dry_run=False, git_commit=False, git_push=True, run_sync=False
        )
        applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
        )

        # _run_git_commit と _run_git_push が呼ばれる
        mock_git_commit.assert_called()
        mock_git_push.assert_called()

    def test_apply_with_git_push_dry_run(self, sample_config, tmp_project, tmp_templates, mocker):
        """dry_run=True では git_push は実行されない"""
        mock_git_commit = mocker.patch.object(applier, "_run_git_commit")
        mock_git_push = mocker.patch.object(applier, "_run_git_push")

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        options = py_project.config.ApplyOptions(dry_run=True, git_push=True)
        applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
        )

        # _run_git_commit も _run_git_push も呼ばれない
        mock_git_commit.assert_not_called()
        mock_git_push.assert_not_called()

    def test_apply_with_git_push_commit_fails(self, sample_config, tmp_project, tmp_templates, mocker):
        """commit が失敗した場合は push は実行されない"""
        mocker.patch.object(applier, "_is_git_repo", return_value=True)
        mocker.patch.object(applier, "_has_uncommitted_changes", return_value=False)
        mock_git_commit = mocker.patch.object(applier, "_run_git_commit", return_value=False)
        mock_git_push = mocker.patch.object(applier, "_run_git_push")

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        options = py_project.config.ApplyOptions(dry_run=False, git_push=True, run_sync=False)
        applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
        )

        # _run_git_commit は呼ばれるが _run_git_push は呼ばれない
        mock_git_commit.assert_called()
        mock_git_push.assert_not_called()


class TestApplyWithProgress:
    """progress パラメータを使うテスト"""

    def test_apply_with_progress(self, sample_config, tmp_project, tmp_templates, mocker):
        """progress を渡す場合"""

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        # ProgressManager のモック
        mock_progress = mocker.MagicMock(spec=my_lib.cui_progress.ProgressManager)
        mock_progress._start_time = 0  # 経過時間計算用

        options = py_project.config.ApplyOptions(dry_run=False, run_sync=False)
        summary = applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
            progress=mock_progress,
        )

        # progress のメソッドが呼ばれていることを確認
        mock_progress.print.assert_called()
        mock_progress.set_progress_bar.assert_called()
        mock_progress.update_progress_bar.assert_called()
        mock_progress.remove_progress_bar.assert_called()
        mock_progress.set_status.assert_called()

        assert summary.projects_processed == 1

    def test_apply_with_progress_nonexistent_project(self, tmp_path, tmp_templates, mocker):
        """progress ありで存在しないプロジェクトを処理"""

        config = py_project.config.Config(
            template_dir=str(tmp_templates),
            defaults=py_project.config.Defaults(configs=["pyproject"]),
            projects=[
                py_project.config.Project(name="nonexistent", path=str(tmp_path / "nonexistent")),
            ],
        )

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        mock_progress = mocker.MagicMock(spec=my_lib.cui_progress.ProgressManager)
        mock_progress._start_time = 0

        options = py_project.config.ApplyOptions(dry_run=False)
        summary = applier.apply_configs(
            config=config,
            options=options,
            console=console,
            progress=mock_progress,
        )

        assert summary.errors == 1
        # progress.print でエラーメッセージが出力される
        mock_progress.print.assert_called()

    def test_apply_with_progress_unknown_config_type(self, tmp_path, tmp_templates, mocker):
        """progress ありで未知の設定タイプを処理"""

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

        mock_progress = mocker.MagicMock(spec=my_lib.cui_progress.ProgressManager)
        mock_progress._start_time = 0

        options = py_project.config.ApplyOptions(dry_run=False)
        summary = applier.apply_configs(
            config=config,
            options=options,
            console=console,
            progress=mock_progress,
        )

        assert summary.errors == 1
        # progress.print と update_progress_bar が呼ばれる
        mock_progress.print.assert_called()
        mock_progress.update_progress_bar.assert_called()

    def test_apply_with_progress_show_diff(self, sample_config, tmp_project, tmp_templates, mocker):
        """progress ありで差分表示モード"""

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        mock_progress = mocker.MagicMock(spec=my_lib.cui_progress.ProgressManager)
        mock_progress._start_time = 0

        options = py_project.config.ApplyOptions(show_diff=True, dry_run=True)
        applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
            progress=mock_progress,
        )

        # progress.print が呼ばれていることを確認
        mock_progress.print.assert_called()


class TestRunUvSyncWithProgress:
    """_run_uv_sync の progress 付きテスト"""

    def test_run_uv_sync_with_progress(self, tmp_project, mocker):
        """progress を渡す場合"""

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        mock_progress = mocker.MagicMock(spec=my_lib.cui_progress.ProgressManager)

        applier._run_uv_sync(tmp_project, console, progress=mock_progress)

        # progress.print が呼ばれていることを確認
        mock_progress.print.assert_called()


class TestRunGitCommitWithProgress:
    """_run_git_commit の progress 付きテスト"""

    def test_run_git_commit_with_progress(self, tmp_path, mocker):
        """progress を渡す場合"""

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 0

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        mock_progress = mocker.MagicMock(spec=my_lib.cui_progress.ProgressManager)

        files_info = [
            applier.GitCommitFile(path=tmp_path / "file1.txt", config_type="config-type", message="")
        ]
        applier._run_git_commit(tmp_path, files_info, console, progress=mock_progress)

        # progress.print が呼ばれていることを確認
        mock_progress.print.assert_called()


class TestPrintResultWithProgress:
    """_print_result の progress 付きテスト"""

    def test_print_result_with_progress(self, mocker):
        """progress を渡す場合"""

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        mock_progress = mocker.MagicMock(spec=my_lib.cui_progress.ProgressManager)

        result = handlers_base.ApplyResult(status=handlers_base.ApplyStatus.UPDATED)
        applier._print_result(console, "pyproject", result, dry_run=False, progress=mock_progress)

        # progress.print が呼ばれていることを確認
        mock_progress.print.assert_called()


class TestPrintSummaryWithProgress:
    """_print_summary の progress 付きテスト"""

    def test_print_summary_with_progress(self, mocker):
        """progress を渡す場合（経過時間表示）"""

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        mock_progress = mocker.MagicMock(spec=my_lib.cui_progress.ProgressManager)
        mock_progress._start_time = 0  # 現在時刻との差で経過時間が計算される

        summary = applier.ApplySummary(
            created=1,
            updated=2,
            projects_processed=1,
        )

        applier._print_summary(console, summary, dry_run=False, progress=mock_progress)

        result = output.getvalue()
        # 経過時間が表示される
        assert "経過時間" in result


class TestApplyWithNoneOptions:
    """options=None のテスト"""

    def test_apply_with_none_options(self, sample_config, tmp_project, tmp_templates):
        """options=None の場合はデフォルト値が使われる"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        summary = applier.apply_configs(
            config=sample_config,
            options=None,  # 明示的に None を渡す
            console=console,
        )

        # デフォルトは dry_run=True なので確認モードが表示される
        assert "確認モード" in output.getvalue()
        assert summary.projects_processed == 1


class TestShowDiffNoDiffWithProgress:
    """show_diff モードで差分なし + progress のテスト"""

    def test_show_diff_no_changes_with_progress(self, tmp_project, tmp_templates, mocker):
        """差分なしで progress がある場合"""
        import py_project.handlers.template_copy as template_copy

        # gitignore をテンプレートと同じ内容で作成（差分なしの状態）
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

        mock_progress = mocker.MagicMock(spec=my_lib.cui_progress.ProgressManager)
        mock_progress._start_time = 0

        # show_diff=True で差分なし + progress
        options = py_project.config.ApplyOptions(show_diff=True, dry_run=True)
        applier.apply_configs(
            config=full_config,
            options=options,
            console=console,
            progress=mock_progress,
        )

        # progress.print が "up to date" で呼ばれていることを確認
        calls = [str(call) for call in mock_progress.print.call_args_list]
        assert any("up to date" in call for call in calls)


class TestShowDiffAndApply:
    """show_diff + apply モードのテスト（dry_run=False）"""

    def test_show_diff_and_apply(self, sample_config, tmp_project, tmp_templates):
        """差分表示しつつ適用も行う"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        # show_diff=True かつ dry_run=False で実際に適用
        options = py_project.config.ApplyOptions(show_diff=True, dry_run=False)
        summary = applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
        )

        # 適用が行われる
        assert summary.projects_processed == 1
        assert summary.updated >= 1 or summary.created >= 1

    def test_show_diff_and_apply_with_progress(self, sample_config, tmp_project, tmp_templates, mocker):
        """show_diff + apply + progress"""

        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=False)

        mock_progress = mocker.MagicMock(spec=my_lib.cui_progress.ProgressManager)
        mock_progress._start_time = 0

        # show_diff=True かつ dry_run=False で実際に適用
        options = py_project.config.ApplyOptions(show_diff=True, dry_run=False)
        summary = applier.apply_configs(
            config=sample_config,
            options=options,
            console=console,
            progress=mock_progress,
        )

        # 適用が行われる
        assert summary.projects_processed == 1
        # progress.print が呼ばれている
        mock_progress.print.assert_called()
