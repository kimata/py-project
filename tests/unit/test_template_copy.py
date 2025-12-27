#!/usr/bin/env python3
# ruff: noqa: S101
"""
handlers/template_copy.py のテスト
"""
import py_project.handlers.base as handlers_base
import py_project.handlers.template_copy as template_copy


class TestTemplateCopyHandler:
    """TemplateCopyHandler のテスト"""

    def test_render_template(self, tmp_templates, tmp_project, apply_context):
        """テンプレートレンダリング"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        result = handler.render_template(project, apply_context)

        assert "ruff-pre-commit" in result
        assert "v0.12.0" in result

    def test_diff_new_file(self, tmp_templates, tmp_project, apply_context):
        """新規ファイルの差分"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        diff = handler.diff(project, apply_context)

        assert diff is not None
        assert "新規作成" in diff

    def test_diff_unchanged(self, tmp_templates, tmp_project, apply_context):
        """変更なしの場合"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        # テンプレートと同じ内容を書き込む
        content = handler.render_template(project, apply_context)
        (tmp_project / ".pre-commit-config.yaml").write_text(content)

        diff = handler.diff(project, apply_context)

        assert diff is None

    def test_diff_with_changes(self, tmp_templates, tmp_project, apply_context):
        """変更がある場合"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        # 異なる内容を書き込む
        (tmp_project / ".pre-commit-config.yaml").write_text("old content")

        diff = handler.diff(project, apply_context)

        assert diff is not None
        assert "---" in diff  # unified diff format

    def test_apply_creates_new_file(self, tmp_templates, tmp_project, apply_context):
        """新規ファイル作成"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        result = handler.apply(project, apply_context)

        assert result.status == "created"
        assert (tmp_project / ".pre-commit-config.yaml").exists()

    def test_apply_updates_file(self, tmp_templates, tmp_project, apply_context):
        """ファイル更新"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        # 古い内容を書き込む
        (tmp_project / ".pre-commit-config.yaml").write_text("old content")

        result = handler.apply(project, apply_context)

        assert result.status == "updated"

    def test_apply_unchanged(self, tmp_templates, tmp_project, apply_context):
        """変更なし"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        # テンプレートと同じ内容を書き込む
        content = handler.render_template(project, apply_context)
        (tmp_project / ".pre-commit-config.yaml").write_text(content)

        result = handler.apply(project, apply_context)

        assert result.status == "unchanged"

    def test_apply_dry_run(self, tmp_templates, tmp_project):
        """ドライランモード"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        context = handlers_base.ApplyContext(
            config={},
            template_dir=tmp_templates,
            dry_run=True,
            backup=False,
        )

        result = handler.apply(project, context)

        assert result.status == "created"
        # ドライランなのでファイルは作成されない
        assert not (tmp_project / ".pre-commit-config.yaml").exists()

    def test_apply_with_backup(self, tmp_templates, tmp_project):
        """バックアップ作成"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        # 古い内容を書き込む
        (tmp_project / ".pre-commit-config.yaml").write_text("old content")

        context = handlers_base.ApplyContext(
            config={},
            template_dir=tmp_templates,
            dry_run=False,
            backup=True,
        )

        result = handler.apply(project, context)

        assert result.status == "updated"
        assert (tmp_project / ".pre-commit-config.yaml.bak").exists()
        assert (tmp_project / ".pre-commit-config.yaml.bak").read_text() == "old content"


class TestGitignoreHandler:
    """GitignoreHandler のテスト"""

    def test_apply(self, tmp_templates, tmp_project, apply_context):
        """gitignore 適用"""
        handler = template_copy.GitignoreHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        result = handler.apply(project, apply_context)

        assert result.status == "created"
        content = (tmp_project / ".gitignore").read_text()
        assert "__pycache__/" in content


class TestTemplateOverrides:
    """template_overrides のテスト"""

    def test_template_override(self, tmp_path, tmp_project):
        """テンプレートオーバーライド"""
        # カスタムテンプレートを作成
        custom_template = tmp_path / "custom" / ".pre-commit-config.yaml"
        custom_template.parent.mkdir(parents=True)
        custom_template.write_text("custom: template\n")

        handler = template_copy.PreCommitHandler()
        project = {
            "name": "test-project",
            "path": str(tmp_project),
            "template_overrides": {
                "pre-commit": str(custom_template),
            },
        }

        context = handlers_base.ApplyContext(
            config={},
            template_dir=tmp_path / "templates",  # 存在しなくてもオーバーライドで上書き
            dry_run=False,
            backup=False,
        )

        result = handler.apply(project, context)

        assert result.status == "created"
        content = (tmp_project / ".pre-commit-config.yaml").read_text()
        assert "custom: template" in content


class TestTemplateCopyErrors:
    """エラーケースのテスト"""

    def test_diff_missing_template(self, tmp_path, tmp_project):
        """テンプレートが存在しない場合の diff"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        context = handlers_base.ApplyContext(
            config={},
            template_dir=tmp_path / "nonexistent",
            dry_run=False,
            backup=False,
        )

        diff = handler.diff(project, context)

        assert "テンプレートが見つかりません" in diff

    def test_apply_missing_template(self, tmp_path, tmp_project):
        """テンプレートが存在しない場合の apply"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        context = handlers_base.ApplyContext(
            config={},
            template_dir=tmp_path / "nonexistent",
            dry_run=False,
            backup=False,
        )

        result = handler.apply(project, context)

        assert result.status == "error"
        assert "テンプレートが見つかりません" in result.message

    def test_apply_validation_failure(self, tmp_path, tmp_project):
        """バリデーション失敗時の apply"""
        handler = template_copy.PreCommitHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        # 無効な YAML を含むテンプレートを作成
        template_dir = tmp_path / "templates" / "pre-commit"
        template_dir.mkdir(parents=True)
        (template_dir / ".pre-commit-config.yaml").write_text("invalid: [unclosed")

        context = handlers_base.ApplyContext(
            config={},
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )

        result = handler.apply(project, context)

        assert result.status == "error"
        assert "バリデーション失敗" in result.message


class TestAllHandlers:
    """全ハンドラのテスト"""

    def test_ruff_handler_name(self):
        """RuffHandler の name プロパティ"""
        handler = template_copy.RuffHandler()
        assert handler.name == "ruff"

    def test_yamllint_handler_name(self):
        """YamllintHandler の name プロパティ"""
        handler = template_copy.YamllintHandler()
        assert handler.name == "yamllint"

    def test_prettier_handler_name(self):
        """PrettierHandler の name プロパティ"""
        handler = template_copy.PrettierHandler()
        assert handler.name == "prettier"

    def test_python_version_handler_name(self):
        """PythonVersionHandler の name プロパティ"""
        handler = template_copy.PythonVersionHandler()
        assert handler.name == "python-version"

    def test_dockerignore_handler_name(self):
        """DockerignoreHandler の name プロパティ"""
        handler = template_copy.DockerignoreHandler()
        assert handler.name == "dockerignore"

    def test_gitignore_handler_name(self):
        """GitignoreHandler の name プロパティ"""
        handler = template_copy.GitignoreHandler()
        assert handler.name == "gitignore"

    def test_renovate_handler_name(self):
        """RenovateHandler の name プロパティ"""
        handler = template_copy.RenovateHandler()
        assert handler.name == "renovate"


class TestFormatTypes:
    """format_type のテスト"""

    def test_precommit_format_type(self):
        """PreCommitHandler の format_type"""
        from py_project.handlers.base import FormatType

        handler = template_copy.PreCommitHandler()
        assert handler.format_type == FormatType.YAML

    def test_ruff_format_type(self):
        """RuffHandler の format_type"""
        from py_project.handlers.base import FormatType

        handler = template_copy.RuffHandler()
        assert handler.format_type == FormatType.TOML

    def test_yamllint_format_type(self):
        """YamllintHandler の format_type"""
        from py_project.handlers.base import FormatType

        handler = template_copy.YamllintHandler()
        assert handler.format_type == FormatType.YAML

    def test_prettier_format_type(self):
        """PrettierHandler の format_type"""
        from py_project.handlers.base import FormatType

        handler = template_copy.PrettierHandler()
        assert handler.format_type == FormatType.JSON

    def test_python_version_format_type(self):
        """PythonVersionHandler の format_type"""
        from py_project.handlers.base import FormatType

        handler = template_copy.PythonVersionHandler()
        assert handler.format_type == FormatType.TEXT

    def test_gitignore_format_type(self):
        """GitignoreHandler の format_type"""
        from py_project.handlers.base import FormatType

        handler = template_copy.GitignoreHandler()
        assert handler.format_type == FormatType.TEXT

    def test_dockerignore_format_type(self):
        """DockerignoreHandler の format_type"""
        from py_project.handlers.base import FormatType

        handler = template_copy.DockerignoreHandler()
        assert handler.format_type == FormatType.TEXT

    def test_renovate_format_type(self):
        """RenovateHandler の format_type"""
        from py_project.handlers.base import FormatType

        handler = template_copy.RenovateHandler()
        assert handler.format_type == FormatType.JSON
