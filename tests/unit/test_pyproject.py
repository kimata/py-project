#!/usr/bin/env python3
# ruff: noqa: S101
"""
handlers/pyproject.py のテスト
"""
import textwrap

import tomlkit

import py_project.handlers.base as handlers_base
import py_project.handlers.pyproject as pyproject_handler


class TestNormalizeToml:
    """_normalize_toml のテスト"""

    def test_normalize_multiple_blank_lines(self):
        """複数の空行を正規化"""
        content = "line1\n\n\n\nline2\n"

        result = pyproject_handler._normalize_toml(content)

        assert result == "line1\n\nline2\n"

    def test_normalize_trailing_whitespace(self):
        """末尾の空白を除去"""
        content = "line1\nline2\n\n\n"

        result = pyproject_handler._normalize_toml(content)

        assert result == "line1\nline2\n"


class TestPyprojectHandler:
    """PyprojectHandler のテスト"""

    def test_merge_preserves_project_name(self, tmp_templates, tmp_project, apply_context):
        """プロジェクト名が保持されることを確認"""
        handler = pyproject_handler.PyprojectHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        # 元のファイルを読み込む
        current = tomlkit.parse((tmp_project / "pyproject.toml").read_text())
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        # プロジェクト固有フィールドが保持されている
        assert result["project"]["name"] == "test-project"
        assert result["project"]["version"] == "0.1.0"
        assert result["project"]["description"] == "Test project"

    def test_merge_applies_template_settings(self, tmp_templates, tmp_project, apply_context):
        """テンプレート設定が適用されることを確認"""
        handler = pyproject_handler.PyprojectHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        current = tomlkit.parse((tmp_project / "pyproject.toml").read_text())
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        # テンプレートの設定が適用されている
        assert result["project"]["requires-python"] == ">=3.11"
        assert result["tool"]["ruff"]["line-length"] == 110

    def test_merge_preserves_dependencies(self, tmp_templates, tmp_project, apply_context):
        """dependencies が保持されることを確認"""
        handler = pyproject_handler.PyprojectHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        # dependencies を追加
        pyproject_content = textwrap.dedent("""\
            [project]
            name = "test-project"
            version = "0.1.0"
            description = "Test project"
            dependencies = ["requests>=2.0"]

            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"
        """)
        (tmp_project / "pyproject.toml").write_text(pyproject_content)

        current = tomlkit.parse(pyproject_content)
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        # dependencies が保持されている
        assert "requests>=2.0" in result["project"]["dependencies"]

    def test_diff_no_changes(self, tmp_templates, tmp_project, apply_context):
        """変更なしの場合"""
        handler = pyproject_handler.PyprojectHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        # マージ結果と同じ内容を書き込む
        merged = handler.generate_merged_content(project, apply_context)
        if merged:
            normalized = pyproject_handler._normalize_toml(merged)
            (tmp_project / "pyproject.toml").write_text(normalized)

        diff = handler.diff(project, apply_context)

        assert diff is None

    def test_diff_with_changes(self, tmp_templates, tmp_project, apply_context):
        """変更がある場合"""
        handler = pyproject_handler.PyprojectHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        diff = handler.diff(project, apply_context)

        # 初期状態ではテンプレートとの差分がある
        assert diff is not None

    def test_apply_updates_file(self, tmp_templates, tmp_project, apply_context):
        """ファイル更新"""
        handler = pyproject_handler.PyprojectHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        result = handler.apply(project, apply_context)

        assert result.status == "updated"

        # 更新後の内容を確認
        content = (tmp_project / "pyproject.toml").read_text()
        assert "requires-python" in content
        assert ">=3.11" in content

    def test_apply_unchanged(self, tmp_templates, tmp_project, apply_context):
        """変更なし"""
        handler = pyproject_handler.PyprojectHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        # 一度適用
        handler.apply(project, apply_context)

        # 再度適用
        result = handler.apply(project, apply_context)

        assert result.status == "unchanged"

    def test_apply_dry_run(self, tmp_templates, tmp_project):
        """ドライランモード"""
        handler = pyproject_handler.PyprojectHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        original_content = (tmp_project / "pyproject.toml").read_text()

        context = handlers_base.ApplyContext(
            config={},
            template_dir=tmp_templates,
            dry_run=True,
            backup=False,
        )

        result = handler.apply(project, context)

        assert result.status == "updated"
        # ドライランなのでファイルは変更されない
        assert (tmp_project / "pyproject.toml").read_text() == original_content

    def test_apply_missing_pyproject(self, tmp_templates, tmp_path, apply_context):
        """pyproject.toml が存在しない場合"""
        handler = pyproject_handler.PyprojectHandler()
        empty_project = tmp_path / "empty-project"
        empty_project.mkdir()
        project = {"name": "empty-project", "path": str(empty_project)}

        result = handler.apply(project, apply_context)

        assert result.status == "skipped"
        assert "pyproject.toml が見つかりません" in result.message


class TestGetNestedValue:
    """get_nested_value のテスト"""

    def test_get_simple_key(self):
        """単純なキー"""
        handler = pyproject_handler.PyprojectHandler()
        doc = tomlkit.parse("[project]\nname = 'test'")

        result = handler.get_nested_value(doc, "project.name")

        assert result == "test"

    def test_get_nonexistent_key(self):
        """存在しないキー"""
        handler = pyproject_handler.PyprojectHandler()
        doc = tomlkit.parse("[project]\nname = 'test'")

        result = handler.get_nested_value(doc, "project.nonexistent")

        assert result is None


class TestSetNestedValue:
    """set_nested_value のテスト"""

    def test_set_new_key(self):
        """新しいキーを設定"""
        handler = pyproject_handler.PyprojectHandler()
        doc = tomlkit.parse("[project]\nname = 'test'")

        handler.set_nested_value(doc, "tool.ruff.line-length", 100)

        assert doc["tool"]["ruff"]["line-length"] == 100
