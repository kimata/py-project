#!/usr/bin/env python3
# ruff: noqa: S101
"""config モジュールのテスト"""

import py_project.config


class TestGitlabCiEdit:
    """GitlabCiEdit のテスト"""

    def test_from_dict(self):
        """辞書から GitlabCiEdit を生成"""
        data = {"path": "/image", "value": "ubuntu:latest"}
        edit = py_project.config.GitlabCiEdit.from_dict(data)

        assert edit.path == "/image"
        assert edit.value == "ubuntu:latest"


class TestGitlabCiOptions:
    """GitlabCiOptions のテスト"""

    def test_from_dict_with_edits(self):
        """edits を持つ辞書から GitlabCiOptions を生成"""
        data = {
            "edits": [
                {"path": "/image", "value": "ubuntu:latest"},
                {"path": "/stages", "value": "test"},
            ]
        }
        options = py_project.config.GitlabCiOptions.from_dict(data)

        assert len(options.edits) == 2
        assert options.edits[0].path == "/image"

    def test_from_dict_empty(self):
        """空の辞書から GitlabCiOptions を生成"""
        data = {}
        options = py_project.config.GitlabCiOptions.from_dict(data)

        assert options.edits == []


class TestPyprojectOptions:
    """PyprojectOptions のテスト"""

    def test_from_dict_full(self):
        """すべてのフィールドを持つ辞書から生成"""
        data = {
            "preserve_sections": ["tool.custom"],
            "extra_dev_deps": ["pytest>=8.0.0"],
        }
        options = py_project.config.PyprojectOptions.from_dict(data)

        assert options.preserve_sections == ["tool.custom"]
        assert options.extra_dev_deps == ["pytest>=8.0.0"]

    def test_from_dict_empty(self):
        """空の辞書から生成"""
        data = {}
        options = py_project.config.PyprojectOptions.from_dict(data)

        assert options.preserve_sections == []
        assert options.extra_dev_deps == []


class TestGitignoreOptions:
    """GitignoreOptions のテスト"""

    def test_from_dict_with_extra_lines(self):
        """extra_lines を持つ辞書から生成"""
        data = {"extra_lines": ["!config.yaml", "*.log"]}
        options = py_project.config.GitignoreOptions.from_dict(data)

        assert options.extra_lines == ["!config.yaml", "*.log"]

    def test_from_dict_empty(self):
        """空の辞書から生成"""
        data = {}
        options = py_project.config.GitignoreOptions.from_dict(data)

        assert options.extra_lines == []


class TestDefaults:
    """Defaults のテスト"""

    def test_from_dict_full(self):
        """すべてのフィールドを持つ辞書から生成"""
        data = {
            "python_version": "3.11",
            "configs": ["pyproject", "pre-commit"],
            "vars": {"registry": "example.com"},
            "gitlab_ci": {"edits": [{"path": "/image", "value": "ubuntu:latest"}]},
        }
        defaults = py_project.config.Defaults.from_dict(data)

        assert defaults.python_version == "3.11"
        assert defaults.configs == ["pyproject", "pre-commit"]
        assert defaults.vars == {"registry": "example.com"}
        assert defaults.gitlab_ci is not None
        assert len(defaults.gitlab_ci.edits) == 1

    def test_from_dict_minimal(self):
        """最小限の辞書から生成"""
        data = {}
        defaults = py_project.config.Defaults.from_dict(data)

        assert defaults.python_version == "3.12"
        assert defaults.configs == []
        assert defaults.vars == {}
        assert defaults.gitlab_ci is None

    def test_from_dict_without_gitlab_ci(self):
        """gitlab_ci なしの辞書から生成"""
        data = {
            "python_version": "3.12",
            "configs": ["pyproject"],
        }
        defaults = py_project.config.Defaults.from_dict(data)

        assert defaults.gitlab_ci is None


class TestProject:
    """Project のテスト"""

    def test_get_path(self):
        """パスの展開テスト"""
        project = py_project.config.Project(name="test", path="~/project")
        path = project.get_path()

        assert not str(path).startswith("~")
        assert path.name == "project"

    def test_from_dict_full(self):
        """すべてのフィールドを持つ辞書から生成"""
        data = {
            "name": "test-project",
            "path": "/path/to/project",
            "configs": ["pyproject"],
            "exclude_configs": ["pre-commit"],
            "vars": {"key": "value"},
            "template_overrides": {"pyproject": "custom"},
            "pyproject": {
                "preserve_sections": ["tool.custom"],
                "extra_dev_deps": ["pytest>=8.0.0"],
            },
            "gitlab_ci": {"edits": [{"path": "/image", "value": "ubuntu:latest"}]},
            "gitignore": {"extra_lines": ["!keep.txt"]},
        }
        project = py_project.config.Project.from_dict(data)

        assert project.name == "test-project"
        assert project.path == "/path/to/project"
        assert project.configs == ["pyproject"]
        assert project.exclude_configs == ["pre-commit"]
        assert project.vars == {"key": "value"}
        assert project.template_overrides == {"pyproject": "custom"}
        assert project.pyproject is not None
        assert project.pyproject.preserve_sections == ["tool.custom"]
        assert project.gitlab_ci is not None
        assert len(project.gitlab_ci.edits) == 1
        assert project.gitignore is not None
        assert project.gitignore.extra_lines == ["!keep.txt"]

    def test_from_dict_minimal(self):
        """最小限の辞書から生成"""
        data = {"name": "test", "path": "/path"}
        project = py_project.config.Project.from_dict(data)

        assert project.name == "test"
        assert project.path == "/path"
        assert project.configs is None
        assert project.exclude_configs == []
        assert project.vars == {}
        assert project.template_overrides == {}
        assert project.pyproject is None
        assert project.gitlab_ci is None
        assert project.gitignore is None


class TestConfig:
    """Config のテスト"""

    def test_get_template_dir(self, tmp_path):
        """テンプレートディレクトリの展開テスト"""
        config = py_project.config.Config(
            projects=[],
            template_dir="~/templates",
        )
        path = config.get_template_dir()

        assert not str(path).startswith("~")
        assert path.name == "templates"

    def test_get_project_found(self):
        """プロジェクトの検索（見つかる場合）"""
        project1 = py_project.config.Project(name="project1", path="/path1")
        project2 = py_project.config.Project(name="project2", path="/path2")
        config = py_project.config.Config(
            projects=[project1, project2],
        )

        result = config.get_project("project2")
        assert result is not None
        assert result.name == "project2"

    def test_get_project_not_found(self):
        """プロジェクトの検索（見つからない場合）"""
        project1 = py_project.config.Project(name="project1", path="/path1")
        config = py_project.config.Config(
            projects=[project1],
        )

        result = config.get_project("nonexistent")
        assert result is None

    def test_get_project_names(self):
        """プロジェクト名のリスト取得"""
        project1 = py_project.config.Project(name="project1", path="/path1")
        project2 = py_project.config.Project(name="project2", path="/path2")
        config = py_project.config.Config(
            projects=[project1, project2],
        )

        names = config.get_project_names()
        assert names == ["project1", "project2"]

    def test_from_dict_full(self):
        """すべてのフィールドを持つ辞書から生成"""
        data = {
            "defaults": {
                "python_version": "3.11",
                "configs": ["pyproject"],
            },
            "template_dir": "/templates",
            "projects": [
                {"name": "project1", "path": "/path1"},
                {"name": "project2", "path": "/path2"},
            ],
        }
        config = py_project.config.Config.from_dict(data)

        assert config.defaults.python_version == "3.11"
        assert config.template_dir == "/templates"
        assert len(config.projects) == 2
        assert config.projects[0].name == "project1"

    def test_from_dict_minimal(self):
        """最小限の辞書から生成"""
        data = {}
        config = py_project.config.Config.from_dict(data)

        assert config.defaults.python_version == "3.12"
        assert config.template_dir == "./templates"
        assert config.projects == []

    def test_from_dict_without_defaults(self):
        """defaults なしの辞書から生成"""
        data = {
            "projects": [{"name": "test", "path": "/path"}],
        }
        config = py_project.config.Config.from_dict(data)

        assert config.defaults.python_version == "3.12"
        assert len(config.projects) == 1


class TestApplyOptions:
    """ApplyOptions のテスト"""

    def test_default_values(self):
        """デフォルト値のテスト"""
        options = py_project.config.ApplyOptions()

        assert options.dry_run is True
        assert options.backup is False
        assert options.show_diff is False
        assert options.run_sync is True
        assert options.git_commit is False

    def test_custom_values(self):
        """カスタム値のテスト"""
        options = py_project.config.ApplyOptions(
            dry_run=False,
            backup=True,
            show_diff=True,
            run_sync=False,
            git_commit=True,
        )

        assert options.dry_run is False
        assert options.backup is True
        assert options.show_diff is True
        assert options.run_sync is False
        assert options.git_commit is True
