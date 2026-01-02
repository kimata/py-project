#!/usr/bin/env python3
# ruff: noqa: S101, ARG002, D200, D403
"""
handlers/base.py のテスト
"""

import pathlib

import py_project.config
import py_project.handlers.base as handlers_base


class DummyHandler(handlers_base.ConfigHandler):
    """テスト用のダミーハンドラ"""

    @property
    def name(self):
        return "dummy"

    def apply(self, project, context):
        return handlers_base.ApplyResult(status="unchanged")

    def diff(self, project, context):
        return None

    def get_output_path(self, project):
        return self.get_project_path(project) / "dummy.txt"


class TestFormatType:
    """FormatType のテスト"""

    def test_format_type_values(self):
        """FormatType の値"""
        assert handlers_base.FormatType.YAML.value == "yaml"
        assert handlers_base.FormatType.TOML.value == "toml"
        assert handlers_base.FormatType.JSON.value == "json"
        assert handlers_base.FormatType.TEXT.value == "text"


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
        config = py_project.config.Config(
            defaults=py_project.config.Defaults(configs=[]),
            projects=[],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path,
            dry_run=True,
            backup=False,
        )

        assert context.config == config
        assert context.template_dir == tmp_path
        assert context.dry_run is True
        assert context.backup is False


class TestConfigHandler:
    """ConfigHandler のテスト"""

    def test_get_project_path_expands_tilde(self, tmp_path):
        """~ が展開されることを確認"""
        handler = DummyHandler()
        project = py_project.config.Project(name="test", path="~/test-project")

        result = handler.get_project_path(project)

        assert "~" not in str(result)
        assert result == pathlib.Path.home() / "test-project"

    def test_create_backup(self, tmp_path):
        """バックアップ作成"""
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
        handler = DummyHandler()
        nonexistent_file = tmp_path / "nonexistent.txt"

        result = handler.create_backup(nonexistent_file)

        assert result is None


class TestValidate:
    """validate のテスト"""

    def test_validate_text_always_valid(self):
        """TEXT 形式は常に有効"""
        handler = DummyHandler()
        handler.format_type = handlers_base.FormatType.TEXT

        is_valid, error = handler.validate("any content")

        assert is_valid is True
        assert error is None

    def test_validate_yaml_valid(self):
        """有効な YAML"""
        handler = DummyHandler()
        handler.format_type = handlers_base.FormatType.YAML

        is_valid, error = handler.validate("key: value\nlist:\n  - item1\n  - item2\n")

        assert is_valid is True
        assert error is None

    def test_validate_yaml_invalid(self):
        """無効な YAML"""
        handler = DummyHandler()
        handler.format_type = handlers_base.FormatType.YAML

        is_valid, error = handler.validate("key: [unclosed bracket")

        assert is_valid is False
        assert error is not None

    def test_validate_toml_valid(self):
        """有効な TOML"""
        handler = DummyHandler()
        handler.format_type = handlers_base.FormatType.TOML

        is_valid, error = handler.validate('[section]\nkey = "value"\n')

        assert is_valid is True
        assert error is None

    def test_validate_toml_invalid(self):
        """無効な TOML"""
        handler = DummyHandler()
        handler.format_type = handlers_base.FormatType.TOML

        is_valid, error = handler.validate('[section\nkey = "value"')

        assert is_valid is False
        assert error is not None

    def test_validate_json_valid(self):
        """有効な JSON"""
        handler = DummyHandler()
        handler.format_type = handlers_base.FormatType.JSON

        is_valid, error = handler.validate('{"key": "value", "list": [1, 2, 3]}')

        assert is_valid is True
        assert error is None

    def test_validate_json_invalid(self):
        """無効な JSON"""
        handler = DummyHandler()
        handler.format_type = handlers_base.FormatType.JSON

        is_valid, error = handler.validate('{"key": "value",}')  # trailing comma

        assert is_valid is False
        assert error is not None
