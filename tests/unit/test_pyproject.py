#!/usr/bin/env python3
# ruff: noqa: S101, ARG002, SLF001, D200, D403
"""
handlers/pyproject.py のテスト
"""

import textwrap

import tomlkit

import py_project.config
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
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

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
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

        current = tomlkit.parse((tmp_project / "pyproject.toml").read_text())
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        # テンプレートの設定が適用されている
        assert result["project"]["requires-python"] == ">=3.11"
        assert result["tool"]["ruff"]["line-length"] == 110

    def test_merge_preserves_dependencies(self, tmp_templates, tmp_project, apply_context):
        """dependencies が保持されることを確認"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

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
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

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
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

        diff = handler.diff(project, apply_context)

        # 初期状態ではテンプレートとの差分がある
        assert diff is not None

    def test_apply_updates_file(self, tmp_templates, tmp_project, apply_context):
        """ファイル更新"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

        result = handler.apply(project, apply_context)

        assert result.status == "updated"

        # 更新後の内容を確認
        content = (tmp_project / "pyproject.toml").read_text()
        assert "requires-python" in content
        assert ">=3.11" in content

    def test_apply_unchanged(self, tmp_templates, tmp_project, apply_context):
        """変更なし"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

        # 一度適用
        handler.apply(project, apply_context)

        # 再度適用
        result = handler.apply(project, apply_context)

        assert result.status == "unchanged"

    def test_apply_dry_run(self, tmp_templates, tmp_project):
        """ドライランモード"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

        original_content = (tmp_project / "pyproject.toml").read_text()

        config = py_project.config.Config(
            defaults=py_project.config.Defaults(configs=[]),
            projects=[],
        )
        context = handlers_base.ApplyContext(
            config=config,
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
        project = py_project.config.Project(name="empty-project", path=str(empty_project))

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

    def test_set_deeply_nested_key(self):
        """深くネストされたキーを設定"""
        handler = pyproject_handler.PyprojectHandler()
        doc = tomlkit.parse("")

        handler.set_nested_value(doc, "a.b.c.d", "value")

        assert doc["a"]["b"]["c"]["d"] == "value"

    def test_set_key_in_existing_path(self):
        """既存のパスにキーを設定"""
        handler = pyproject_handler.PyprojectHandler()
        doc = tomlkit.parse("[tool]\n[tool.ruff]\nline-length = 80")

        handler.set_nested_value(doc, "tool.ruff.select", ["E", "F"])

        assert doc["tool"]["ruff"]["line-length"] == 80
        assert doc["tool"]["ruff"]["select"] == ["E", "F"]

    def test_set_key_partial_existing_path(self):
        """一部が既存のパスにキーを設定"""
        handler = pyproject_handler.PyprojectHandler()
        doc = tomlkit.parse("[tool]\nexisting = 'value'")

        handler.set_nested_value(doc, "tool.new.nested", "new_value")

        assert doc["tool"]["existing"] == "value"
        assert doc["tool"]["new"]["nested"] == "new_value"


class TestHandlerName:
    """name プロパティのテスト"""

    def test_name(self):
        """name プロパティ"""
        handler = pyproject_handler.PyprojectHandler()
        assert handler.name == "pyproject"


class TestMergePyprojectAdvanced:
    """merge_pyproject の高度なテスト"""

    def test_merge_without_tool_section_in_template(self, tmp_path):
        """テンプレートに tool セクションがない場合"""
        handler = pyproject_handler.PyprojectHandler()

        # tool セクションがないテンプレート
        template_content = textwrap.dedent("""\
            [project]
            authors = []
            requires-python = ">=3.11"

            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"
        """)
        template_dir = tmp_path / "templates" / "pyproject"
        template_dir.mkdir(parents=True)
        (template_dir / "sections.toml").write_text(template_content)

        project_content = textwrap.dedent("""\
            [project]
            name = "test"
            version = "1.0"
            description = "Test"
            dependencies = []

            [tool.ruff]
            line-length = 100
        """)
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(project_content)

        current = tomlkit.parse(project_content)
        template = tomlkit.parse(template_content)
        project = py_project.config.Project(name="test", path=str(project_dir))

        result = handler.merge_pyproject(current, template, project)

        # プロジェクトの tool セクションは保持される
        assert "tool" in result
        assert result["tool"]["ruff"]["line-length"] == 100

    def test_merge_without_extra_dev_deps(self, tmp_templates, tmp_project):
        """extra_dev_deps がない場合（デフォルトケース）"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(
            name="test-project",
            path=str(tmp_project),
            # pyproject オプションなし
        )

        current = tomlkit.parse((tmp_project / "pyproject.toml").read_text())
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        # テンプレートの dev_deps がそのまま適用される
        assert "dependency-groups" in result
        assert "dev" in result["dependency-groups"]

    def test_merge_extra_dev_deps_without_existing_dev_group(self, tmp_path):
        """extra_dev_deps があるが、dependency-groups.dev が存在しない場合"""
        handler = pyproject_handler.PyprojectHandler()

        # dependency-groups がないテンプレート
        template_content = textwrap.dedent("""\
            [project]
            authors = []
            requires-python = ">=3.11"
        """)
        template_dir = tmp_path / "templates" / "pyproject"
        template_dir.mkdir(parents=True)
        (template_dir / "sections.toml").write_text(template_content)

        project_content = textwrap.dedent("""\
            [project]
            name = "test"
            version = "1.0"
            description = "Test"
            dependencies = []
        """)
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(project_content)

        current = tomlkit.parse(project_content)
        template = tomlkit.parse(template_content)
        project = py_project.config.Project(
            name="test",
            path=str(project_dir),
            pyproject=py_project.config.PyprojectOptions(
                extra_dev_deps=["some-package>=1.0"],
            ),
        )

        result = handler.merge_pyproject(current, template, project)

        # dependency-groups がないので extra_dev_deps は追加されない（エラーなし）
        assert "dependency-groups" not in result

    def test_merge_preserves_hatch_build(self, tmp_templates, tmp_project):
        """tool.hatch.build が保持されることを確認"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

        pyproject_content = textwrap.dedent("""\
            [project]
            name = "test-project"
            version = "0.1.0"
            description = "Test project"
            dependencies = []

            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [tool.hatch.build.targets.wheel]
            packages = ["src/my_package"]
        """)
        (tmp_project / "pyproject.toml").write_text(pyproject_content)

        current = tomlkit.parse(pyproject_content)
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        # tool.hatch.build が保持されている
        assert "hatch" in result["tool"]
        assert "build" in result["tool"]["hatch"]

    def test_merge_preserves_mypy_overrides(self, tmp_templates, tmp_project):
        """tool.mypy.overrides が保持されることを確認"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

        pyproject_content = textwrap.dedent("""\
            [project]
            name = "test-project"
            version = "0.1.0"
            description = "Test"
            dependencies = []

            [tool.mypy]
            warn_return_any = false

            [[tool.mypy.overrides]]
            module = "some_module.*"
            ignore_missing_imports = true
        """)
        (tmp_project / "pyproject.toml").write_text(pyproject_content)

        current = tomlkit.parse(pyproject_content)
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        # overrides が保持されている
        assert "overrides" in result["tool"]["mypy"]

    def test_merge_with_extra_dev_deps(self, tmp_templates, tmp_project):
        """extra_dev_deps が追加されることを確認"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(
            name="test-project",
            path=str(tmp_project),
            pyproject=py_project.config.PyprojectOptions(
                extra_dev_deps=["custom-package>=1.0"],
            ),
        )

        current = tomlkit.parse((tmp_project / "pyproject.toml").read_text())
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        # extra_dev_deps が追加されている
        dev_deps = result["dependency-groups"]["dev"]
        assert "custom-package>=1.0" in dev_deps

    def test_merge_with_extra_dev_deps_already_exists(self, tmp_templates, tmp_project):
        """extra_dev_deps が既に存在する場合は重複しない（完全一致）"""
        handler = pyproject_handler.PyprojectHandler()

        # テンプレートの dev_deps を確認し、同じ文字列を使用
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())
        existing_dep = str(template["dependency-groups"]["dev"][0])  # 最初の依存関係

        project = py_project.config.Project(
            name="test-project",
            path=str(tmp_project),
            pyproject=py_project.config.PyprojectOptions(
                extra_dev_deps=[existing_dep],  # 完全に同じ文字列
            ),
        )

        current = tomlkit.parse((tmp_project / "pyproject.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        # 重複して追加されていない
        dev_deps = result["dependency-groups"]["dev"]
        count = sum(1 for dep in dev_deps if str(dep) == existing_dep)
        assert count == 1

    def test_merge_with_multiple_extra_dev_deps(self, tmp_templates, tmp_project):
        """複数の extra_dev_deps が追加される"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(
            name="test-project",
            path=str(tmp_project),
            pyproject=py_project.config.PyprojectOptions(
                extra_dev_deps=["new-package>=1.0", "another-package>=2.0"],
            ),
        )

        current = tomlkit.parse((tmp_project / "pyproject.toml").read_text())
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        dev_deps = result["dependency-groups"]["dev"]
        assert "new-package>=1.0" in dev_deps
        assert "another-package>=2.0" in dev_deps

    def test_merge_with_extra_preserve_sections(self, tmp_templates, tmp_project):
        """preserve_sections で追加のセクションを保持"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(
            name="test-project",
            path=str(tmp_project),
            pyproject=py_project.config.PyprojectOptions(
                preserve_sections=["tool.custom"],
            ),
        )

        pyproject_content = textwrap.dedent("""\
            [project]
            name = "test-project"
            version = "0.1.0"
            description = "Test"
            dependencies = []

            [tool.custom]
            setting = "value"
        """)
        (tmp_project / "pyproject.toml").write_text(pyproject_content)

        current = tomlkit.parse(pyproject_content)
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        # tool.custom が保持されている
        assert "custom" in result["tool"]
        assert result["tool"]["custom"]["setting"] == "value"

    def test_merge_adds_new_tool_section(self, tmp_templates, tmp_project):
        """テンプレートの新しい tool セクションが追加される"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

        # tool セクションがない pyproject.toml
        pyproject_content = textwrap.dedent("""\
            [project]
            name = "test-project"
            version = "0.1.0"
            description = "Test"
            dependencies = []
        """)
        (tmp_project / "pyproject.toml").write_text(pyproject_content)

        current = tomlkit.parse(pyproject_content)
        template = tomlkit.parse((tmp_templates / "pyproject" / "sections.toml").read_text())

        result = handler.merge_pyproject(current, template, project)

        # テンプレートの tool.ruff が追加されている
        assert "tool" in result
        assert "ruff" in result["tool"]


class TestMergeSectionAdvanced:
    """_merge_section の高度なテスト"""

    def test_merge_section_not_in_template(self, tmp_templates, tmp_project):
        """テンプレートにないセクションは変更されない"""
        handler = pyproject_handler.PyprojectHandler()

        result = tomlkit.parse("[existing]\nkey = 'value'")
        template = tomlkit.parse("[other]\nkey = 'other'")

        handler._merge_section(result, template, "existing", [])

        # existing セクションは変更されない
        assert result["existing"]["key"] == "value"

    def test_merge_section_not_in_result(self, tmp_templates):
        """結果にないセクションは追加される"""
        handler = pyproject_handler.PyprojectHandler()

        result = tomlkit.parse("")
        template = tomlkit.parse("[new_section]\nkey = 'value'")

        handler._merge_section(result, template, "new_section", [])

        assert "new_section" in result
        assert result["new_section"]["key"] == "value"

    def test_merge_section_with_preserve_fields(self, tmp_templates):
        """preserve_fields が正しく保持される"""
        handler = pyproject_handler.PyprojectHandler()

        result = tomlkit.parse("[section]\npreserve_me = 'original'\nupdate_me = 'old'")
        template = tomlkit.parse("[section]\npreserve_me = 'new'\nupdate_me = 'new'\nnew_key = 'added'")

        handler._merge_section(result, template, "section", ["preserve_me"])

        assert result["section"]["preserve_me"] == "original"  # 保持
        assert result["section"]["update_me"] == "new"  # 更新
        assert result["section"]["new_key"] == "added"  # 追加

    def test_merge_section_with_nonexistent_preserve_fields(self, tmp_templates):
        """preserve_fields に存在しないフィールドが含まれる場合"""
        handler = pyproject_handler.PyprojectHandler()

        result = tomlkit.parse("[section]\nexisting = 'value'")
        template = tomlkit.parse("[section]\nexisting = 'new'\ntemplate_key = 'added'")

        # 存在しないフィールドを preserve_fields に指定
        handler._merge_section(result, template, "section", ["nonexistent_field"])

        # テンプレートの内容が適用される
        assert result["section"]["existing"] == "new"
        assert result["section"]["template_key"] == "added"

    def test_merge_section_empty_preserve_fields(self, tmp_templates):
        """preserve_fields が空の場合"""
        handler = pyproject_handler.PyprojectHandler()

        result = tomlkit.parse("[section]\nold_key = 'old'")
        template = tomlkit.parse("[section]\nold_key = 'new'\nnew_key = 'added'")

        handler._merge_section(result, template, "section", [])

        # 全てテンプレートの値で上書きされる
        assert result["section"]["old_key"] == "new"
        assert result["section"]["new_key"] == "added"


class TestToolSectionMerge:
    """tool セクションのマージテスト"""

    def test_merge_skips_exact_preserved_tool_section(self, tmp_path):
        """preserve_sections に完全一致する tool セクションはスキップされる"""
        handler = pyproject_handler.PyprojectHandler()

        template_content = textwrap.dedent("""\
            [project]
            authors = []

            [tool.custom]
            template_value = "from_template"
        """)
        template_dir = tmp_path / "templates" / "pyproject"
        template_dir.mkdir(parents=True)
        (template_dir / "sections.toml").write_text(template_content)

        project_content = textwrap.dedent("""\
            [project]
            name = "test"
            version = "1.0"
            description = "Test"
            dependencies = []

            [tool.custom]
            project_value = "from_project"
        """)
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(project_content)

        current = tomlkit.parse(project_content)
        template = tomlkit.parse(template_content)
        project = py_project.config.Project(
            name="test",
            path=str(project_dir),
            pyproject=py_project.config.PyprojectOptions(
                preserve_sections=["tool.custom"],  # tool.custom を保持
            ),
        )

        result = handler.merge_pyproject(current, template, project)

        # tool.custom はプロジェクトの値が保持され、テンプレートの値は適用されない
        assert result["tool"]["custom"]["project_value"] == "from_project"
        assert "template_value" not in result["tool"]["custom"]

    def test_merge_skips_preserved_tool_section(self, tmp_path):
        """preserve_sections にある tool セクションはスキップされる"""
        handler = pyproject_handler.PyprojectHandler()

        # テンプレートに tool.hatch.build.targets.wheel がある場合
        template_content = textwrap.dedent("""\
            [project]
            authors = []

            [tool.hatch.build.targets.wheel]
            packages = ["template_package"]
        """)
        template_dir = tmp_path / "templates" / "pyproject"
        template_dir.mkdir(parents=True)
        (template_dir / "sections.toml").write_text(template_content)

        # プロジェクトの pyproject.toml
        project_content = textwrap.dedent("""\
            [project]
            name = "test"
            version = "1.0"
            description = "Test"
            dependencies = []

            [tool.hatch.build.targets.wheel]
            packages = ["my_package"]
        """)
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(project_content)

        current = tomlkit.parse(project_content)
        template = tomlkit.parse(template_content)
        project = py_project.config.Project(name="test", path=str(project_dir))

        result = handler.merge_pyproject(current, template, project)

        # tool.hatch.build.targets.wheel は保持される（テンプレートで上書きされない）
        assert result["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["my_package"]

    def test_merge_with_existing_hatch_section(self, tmp_path):
        """既存の hatch セクションがある場合のマージ"""
        handler = pyproject_handler.PyprojectHandler()

        template_content = textwrap.dedent("""\
            [project]
            authors = []

            [tool.hatch.metadata]
            allow-direct-references = true
        """)
        template_dir = tmp_path / "templates" / "pyproject"
        template_dir.mkdir(parents=True)
        (template_dir / "sections.toml").write_text(template_content)

        project_content = textwrap.dedent("""\
            [project]
            name = "test"
            version = "1.0"
            description = "Test"
            dependencies = []

            [tool.hatch.build.targets.wheel]
            packages = ["my_package"]
        """)
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(project_content)

        current = tomlkit.parse(project_content)
        template = tomlkit.parse(template_content)
        project = py_project.config.Project(name="test", path=str(project_dir))

        result = handler.merge_pyproject(current, template, project)

        # tool.hatch.build は保持される
        assert "build" in result["tool"]["hatch"]
        # tool.hatch.metadata は追加される
        assert "metadata" in result["tool"]["hatch"]

    def test_merge_with_existing_mypy_section(self, tmp_path):
        """既存の mypy セクションがある場合のマージ"""
        handler = pyproject_handler.PyprojectHandler()

        template_content = textwrap.dedent("""\
            [project]
            authors = []

            [tool.mypy]
            warn_return_any = true
            warn_unused_configs = true
        """)
        template_dir = tmp_path / "templates" / "pyproject"
        template_dir.mkdir(parents=True)
        (template_dir / "sections.toml").write_text(template_content)

        project_content = textwrap.dedent("""\
            [project]
            name = "test"
            version = "1.0"
            description = "Test"
            dependencies = []

            [tool.mypy]
            warn_return_any = false

            [tool.mypy.packages]
            my_package = "strict"

            [[tool.mypy.overrides]]
            module = "test.*"
            ignore_missing_imports = true
        """)
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(project_content)

        current = tomlkit.parse(project_content)
        template = tomlkit.parse(template_content)
        project = py_project.config.Project(name="test", path=str(project_dir))

        result = handler.merge_pyproject(current, template, project)

        # packages と overrides は保持される
        assert "packages" in result["tool"]["mypy"]
        assert "overrides" in result["tool"]["mypy"]
        # テンプレートの設定は適用される
        assert result["tool"]["mypy"]["warn_unused_configs"] is True


class TestDiffErrors:
    """diff のエラーケースのテスト"""

    def test_diff_missing_template(self, tmp_path, tmp_project):
        """テンプレートが存在しない場合"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

        config = py_project.config.Config(
            defaults=py_project.config.Defaults(configs=[]),
            projects=[],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "nonexistent",
            dry_run=False,
            backup=False,
        )

        diff = handler.diff(project, context)

        assert "テンプレートが見つかりません" in diff

    def test_diff_missing_pyproject(self, tmp_templates, tmp_path):
        """pyproject.toml が存在しない場合"""
        handler = pyproject_handler.PyprojectHandler()
        empty_project = tmp_path / "empty"
        empty_project.mkdir()
        project = py_project.config.Project(name="empty", path=str(empty_project))

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

        diff = handler.diff(project, context)

        assert "pyproject.toml が見つかりません" in diff


class TestApplyErrors:
    """apply のエラーケースのテスト"""

    def test_apply_missing_template(self, tmp_path, tmp_project):
        """テンプレートが存在しない場合"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

        config = py_project.config.Config(
            defaults=py_project.config.Defaults(configs=[]),
            projects=[],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "nonexistent",
            dry_run=False,
            backup=False,
        )

        result = handler.apply(project, context)

        assert result.status == "error"
        assert "テンプレートが見つかりません" in result.message

    def test_apply_with_backup(self, tmp_templates, tmp_project):
        """バックアップ付き適用"""
        handler = pyproject_handler.PyprojectHandler()
        project = py_project.config.Project(name="test-project", path=str(tmp_project))

        original_content = (tmp_project / "pyproject.toml").read_text()

        config = py_project.config.Config(
            defaults=py_project.config.Defaults(configs=[]),
            projects=[],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_templates,
            dry_run=False,
            backup=True,
        )

        result = handler.apply(project, context)

        assert result.status == "updated"
        # バックアップが作成されている
        assert (tmp_project / "pyproject.toml.bak").exists()
        assert (tmp_project / "pyproject.toml.bak").read_text() == original_content


class TestFormatType:
    """format_type のテスト"""

    def test_pyproject_format_type(self):
        """PyprojectHandler の format_type"""
        from py_project.handlers.base import FormatType

        handler = pyproject_handler.PyprojectHandler()
        assert handler.format_type == FormatType.TOML
