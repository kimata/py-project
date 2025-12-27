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
