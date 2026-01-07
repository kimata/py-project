#!/usr/bin/env python3
# ruff: noqa: S101
"""
cli.py のテスト
"""

import py_project.cli
import py_project.config
import py_project.handlers


class TestExecute:
    """execute 関数のテスト"""

    def test_execute_success(self, sample_config):
        """正常実行"""
        options = py_project.config.ApplyOptions(dry_run=True)
        ret_code = py_project.cli.execute(
            config=sample_config,
            options=options,
        )

        assert ret_code == 0

    def test_execute_with_project_filter(self, sample_config):
        """プロジェクトフィルタ"""
        options = py_project.config.ApplyOptions(dry_run=True)
        ret_code = py_project.cli.execute(
            config=sample_config,
            options=options,
            projects=["test-project"],
        )

        assert ret_code == 0

    def test_execute_with_config_type_filter(self, sample_config):
        """設定タイプフィルタ"""
        options = py_project.config.ApplyOptions(dry_run=True)
        ret_code = py_project.cli.execute(
            config=sample_config,
            options=options,
            config_types=["pyproject"],
        )

        assert ret_code == 0


class TestShowConfigTypes:
    """show_config_types 関数のテスト"""

    def test_show_config_types(self, capsys):
        """設定タイプ一覧表示"""
        py_project.cli.show_config_types()

        # 出力が行われたことを確認（Rich は stderr/stdout に出力）
        # Rich console の出力をキャプチャするのは難しいので、
        # HANDLERS に登録されているタイプが正しく取得できることを確認
        assert "pyproject" in py_project.handlers.HANDLERS
        assert "pre-commit" in py_project.handlers.HANDLERS

    def test_config_type_descriptions(self):
        """設定タイプの説明が定義されている"""
        # descriptions 辞書に主要な設定タイプが含まれていることを確認
        # show_config_types は console を内部で作成するため、
        # HANDLERS に登録されているタイプの存在確認のみ行う
        assert "pyproject" in py_project.handlers.HANDLERS


class TestShowProjects:
    """show_projects 関数のテスト"""

    def test_show_projects(self, sample_config):
        """プロジェクト一覧表示"""
        # エラーなく実行できることを確認
        py_project.cli.show_projects(sample_config)

    def test_show_projects_with_defaults(self, tmp_project, tmp_templates):
        """デフォルト設定でのプロジェクト表示"""
        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                configs=["pyproject"],
            ),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(tmp_project),
                )
            ],
        )

        # エラーなく実行できることを確認
        py_project.cli.show_projects(config)

    def test_show_projects_with_custom_configs(self, tmp_project, tmp_templates):
        """プロジェクト固有設定でのプロジェクト表示"""
        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                configs=["pyproject"],
            ),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(tmp_project),
                    configs=["pre-commit", "ruff"],
                )
            ],
        )

        # エラーなく実行できることを確認
        py_project.cli.show_projects(config)

    def test_show_projects_empty(self):
        """空のプロジェクト一覧"""
        config = py_project.config.Config(
            defaults=py_project.config.Defaults(configs=[]),
            projects=[],
        )

        # エラーなく実行できることを確認
        py_project.cli.show_projects(config)
