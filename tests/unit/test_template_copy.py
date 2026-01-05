#!/usr/bin/env python3
# ruff: noqa: S101
"""
handlers/template_copy.py のテスト
"""

import py_project.config as config_module
import py_project.handlers.base as handlers_base
import py_project.handlers.template_copy as template_copy


class TestTemplateCopyHandler:
    """TemplateCopyHandler のテスト"""

    def test_render_template(self, tmp_templates, tmp_project, apply_context, sample_project):
        """テンプレートレンダリング"""
        handler = template_copy.PreCommitHandler()

        result = handler.render_template(sample_project, apply_context)

        assert "ruff-pre-commit" in result
        assert "v0.12.0" in result

    def test_diff_new_file(self, tmp_templates, tmp_project, apply_context, sample_project):
        """新規ファイルの差分"""
        handler = template_copy.PreCommitHandler()

        diff = handler.diff(sample_project, apply_context)

        assert diff is not None
        assert "新規作成" in diff

    def test_diff_unchanged(self, tmp_templates, tmp_project, apply_context, sample_project):
        """変更なしの場合"""
        handler = template_copy.PreCommitHandler()

        # テンプレートと同じ内容を書き込む
        content = handler.render_template(sample_project, apply_context)
        (tmp_project / ".pre-commit-config.yaml").write_text(content)

        diff = handler.diff(sample_project, apply_context)

        assert diff is None

    def test_diff_with_changes(self, tmp_templates, tmp_project, apply_context, sample_project):
        """変更がある場合"""
        handler = template_copy.PreCommitHandler()

        # 異なる内容を書き込む
        (tmp_project / ".pre-commit-config.yaml").write_text("old content")

        diff = handler.diff(sample_project, apply_context)

        assert diff is not None
        assert "---" in diff  # unified diff format

    def test_apply_creates_new_file(self, tmp_templates, tmp_project, apply_context, sample_project):
        """新規ファイル作成"""
        handler = template_copy.PreCommitHandler()

        result = handler.apply(sample_project, apply_context)

        assert result.status == "created"
        assert (tmp_project / ".pre-commit-config.yaml").exists()

    def test_apply_updates_file(self, tmp_templates, tmp_project, apply_context, sample_project):
        """ファイル更新"""
        handler = template_copy.PreCommitHandler()

        # 古い内容を書き込む
        (tmp_project / ".pre-commit-config.yaml").write_text("old content")

        result = handler.apply(sample_project, apply_context)

        assert result.status == "updated"

    def test_apply_unchanged(self, tmp_templates, tmp_project, apply_context, sample_project):
        """変更なし"""
        handler = template_copy.PreCommitHandler()

        # テンプレートと同じ内容を書き込む
        content = handler.render_template(sample_project, apply_context)
        (tmp_project / ".pre-commit-config.yaml").write_text(content)

        result = handler.apply(sample_project, apply_context)

        assert result.status == "unchanged"

    def test_apply_dry_run(self, tmp_templates, tmp_project, sample_config):
        """ドライランモード"""
        handler = template_copy.PreCommitHandler()
        project = config_module.Project(name="test-project", path=str(tmp_project))

        context = handlers_base.ApplyContext(
            config=sample_config,
            template_dir=tmp_templates,
            dry_run=True,
            backup=False,
        )

        result = handler.apply(project, context)

        assert result.status == "created"
        # ドライランなのでファイルは作成されない
        assert not (tmp_project / ".pre-commit-config.yaml").exists()

    def test_apply_with_backup(self, tmp_templates, tmp_project, sample_config):
        """バックアップ作成"""
        handler = template_copy.PreCommitHandler()
        project = config_module.Project(name="test-project", path=str(tmp_project))

        # 古い内容を書き込む
        (tmp_project / ".pre-commit-config.yaml").write_text("old content")

        context = handlers_base.ApplyContext(
            config=sample_config,
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

    def test_apply(self, tmp_templates, tmp_project, apply_context, sample_project):
        """gitignore 適用"""
        handler = template_copy.GitignoreHandler()

        result = handler.apply(sample_project, apply_context)

        assert result.status == "created"
        content = (tmp_project / ".gitignore").read_text()
        assert "__pycache__/" in content

    def test_apply_with_extra_lines(self, tmp_templates, tmp_project, sample_config):
        """gitignore に extra_lines を追加"""
        handler = template_copy.GitignoreHandler()
        project = config_module.Project(
            name="test-project",
            path=str(tmp_project),
            gitignore=config_module.GitignoreOptions(extra_lines=["!config.yaml", "*.secret"]),
        )

        context = handlers_base.ApplyContext(
            config=sample_config,
            template_dir=tmp_templates,
            dry_run=False,
            backup=False,
        )

        result = handler.apply(project, context)

        assert result.status == "created"
        content = (tmp_project / ".gitignore").read_text()
        assert "__pycache__/" in content
        assert "!config.yaml" in content
        assert "*.secret" in content

    def test_render_template_with_extra_lines(self, tmp_templates, sample_config):
        """extra_lines 付きでテンプレートをレンダリング"""
        handler = template_copy.GitignoreHandler()
        project = config_module.Project(
            name="test-project",
            path="/tmp/test",  # noqa: S108
            gitignore=config_module.GitignoreOptions(extra_lines=["!keep.txt", "custom-pattern/*"]),
        )

        context = handlers_base.ApplyContext(
            config=sample_config,
            template_dir=tmp_templates,
            dry_run=False,
            backup=False,
        )

        content = handler.render_template(project, context)

        assert "__pycache__/" in content
        assert "!keep.txt" in content
        assert "custom-pattern/*" in content


class TestTemplateOverrides:
    """template_overrides のテスト"""

    def test_template_override(self, tmp_path, tmp_project, sample_config):
        """テンプレートオーバーライド"""
        # カスタムテンプレートを作成
        custom_template = tmp_path / "custom" / ".pre-commit-config.yaml"
        custom_template.parent.mkdir(parents=True)
        custom_template.write_text("custom: template\n")

        handler = template_copy.PreCommitHandler()
        project = config_module.Project(
            name="test-project",
            path=str(tmp_project),
            template_overrides={
                "pre-commit": str(custom_template),
            },
        )

        context = handlers_base.ApplyContext(
            config=sample_config,
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

    def test_diff_missing_template(self, tmp_path, tmp_project, sample_config):
        """テンプレートが存在しない場合の diff"""
        handler = template_copy.PreCommitHandler()
        project = config_module.Project(name="test-project", path=str(tmp_project))

        context = handlers_base.ApplyContext(
            config=sample_config,
            template_dir=tmp_path / "nonexistent",
            dry_run=False,
            backup=False,
        )

        diff = handler.diff(project, context)

        assert "テンプレートが見つかりません" in diff

    def test_apply_missing_template(self, tmp_path, tmp_project, sample_config):
        """テンプレートが存在しない場合の apply"""
        handler = template_copy.PreCommitHandler()
        project = config_module.Project(name="test-project", path=str(tmp_project))

        context = handlers_base.ApplyContext(
            config=sample_config,
            template_dir=tmp_path / "nonexistent",
            dry_run=False,
            backup=False,
        )

        result = handler.apply(project, context)

        assert result.status == "error"
        assert "テンプレートが見つかりません" in result.message

    def test_apply_validation_failure(self, tmp_path):
        """バリデーション失敗時の apply"""
        # テスト用のプロジェクトディレクトリを作成
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        handler = template_copy.PreCommitHandler()
        project = config_module.Project(name="test-project", path=str(project_dir))

        # 無効な YAML を含むテンプレートを作成
        template_dir = tmp_path / "invalid_templates" / "pre-commit"
        template_dir.mkdir(parents=True)
        (template_dir / ".pre-commit-config.yaml").write_text("invalid: [unclosed")

        # 最小限の Config を作成
        config = config_module.Config(projects=[project])

        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "invalid_templates",
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


class TestJSONValidation:
    """JSON フォーマットのバリデーションテスト"""

    def test_validate_valid_json(self):
        """有効な JSON のバリデーション"""
        handler = template_copy.PrettierHandler()
        is_valid, error = handler.validate('{"key": "value"}')

        assert is_valid is True
        assert error is None

    def test_validate_invalid_json(self):
        """無効な JSON のバリデーション"""
        handler = template_copy.PrettierHandler()
        is_valid, error = handler.validate('{"key": "value"')  # 閉じ括弧なし

        assert is_valid is False
        assert error is not None

    def test_apply_invalid_json_template(self, tmp_path):
        """無効な JSON テンプレートを適用した場合"""
        handler = template_copy.PrettierHandler()
        project_dir = tmp_path / "json-test-project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        project = config_module.Project(name="json-test-project", path=str(project_dir))

        # 無効な JSON を含むテンプレートを作成
        template_dir = tmp_path / "invalid_json_templates" / "prettier"
        template_dir.mkdir(parents=True)
        (template_dir / ".prettierrc").write_text('{"invalid: json')

        # 最小限の Config を作成
        config = config_module.Config(projects=[project])

        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "invalid_json_templates",
            dry_run=False,
            backup=False,
        )

        result = handler.apply(project, context)

        assert result.status == "error"
        assert "バリデーション失敗" in result.message
