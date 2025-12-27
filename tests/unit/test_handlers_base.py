#!/usr/bin/env python3
# ruff: noqa: S101
"""
handlers/base.py のテスト
"""
import pathlib

import pytest

import py_project.handlers.base as handlers_base


class TestApplyResult:
    """ApplyResult のテスト"""

    def test_status_created(self):
        """status が created の場合"""
        result = handlers_base.ApplyResult(status="created")

        assert result.status == "created"
        assert result.message is None

    def test_status_with_message(self):
        """message がある場合"""
        result = handlers_base.ApplyResult(status="error", message="Something went wrong")

        assert result.status == "error"
        assert result.message == "Something went wrong"

    def test_all_status_values(self):
        """全ステータス値をテスト"""
        for status in ["created", "updated", "unchanged", "error", "skipped"]:
            result = handlers_base.ApplyResult(status=status)
            assert result.status == status


class TestApplyContext:
    """ApplyContext のテスト"""

    def test_context_creation(self, tmp_path):
        """コンテキスト作成"""
        context = handlers_base.ApplyContext(
            config={"key": "value"},
            template_dir=tmp_path,
            dry_run=True,
            backup=False,
        )

        assert context.config == {"key": "value"}
        assert context.template_dir == tmp_path
        assert context.dry_run is True
        assert context.backup is False


class TestConfigHandler:
    """ConfigHandler のテスト"""

    def test_get_project_path_expands_tilde(self, tmp_path):
        """~ が展開されることを確認"""
        # 具象クラスを作成してテスト
        class DummyHandler(handlers_base.ConfigHandler):
            @property
            def name(self):
                return "dummy"

            def apply(self, project, context):
                return handlers_base.ApplyResult(status="unchanged")

            def diff(self, project, context):
                return None

        handler = DummyHandler()
        project = {"path": "~/test-project"}

        result = handler.get_project_path(project)

        assert "~" not in str(result)
        assert result == pathlib.Path.home() / "test-project"

    def test_create_backup(self, tmp_path):
        """バックアップ作成"""

        class DummyHandler(handlers_base.ConfigHandler):
            @property
            def name(self):
                return "dummy"

            def apply(self, project, context):
                return handlers_base.ApplyResult(status="unchanged")

            def diff(self, project, context):
                return None

        handler = DummyHandler()

        # テストファイル作成
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")

        # バックアップ作成
        backup_path = handler.create_backup(test_file)

        assert backup_path is not None
        assert backup_path == tmp_path / "test.txt.bak"
        assert backup_path.read_text() == "original content"

    def test_create_backup_nonexistent_file(self, tmp_path):
        """存在しないファイルのバックアップ"""

        class DummyHandler(handlers_base.ConfigHandler):
            @property
            def name(self):
                return "dummy"

            def apply(self, project, context):
                return handlers_base.ApplyResult(status="unchanged")

            def diff(self, project, context):
                return None

        handler = DummyHandler()
        nonexistent_file = tmp_path / "nonexistent.txt"

        result = handler.create_backup(nonexistent_file)

        assert result is None
