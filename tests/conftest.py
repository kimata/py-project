#!/usr/bin/env python3
# ruff: noqa: S101
"""
共通テストフィクスチャ

テスト全体で使用する共通のフィクスチャとヘルパーを定義します。
"""
import pathlib
import textwrap

import pytest

import py_project.config
import py_project.handlers.base as handlers_base


# === テスト用テンプレート ===
TEMPLATE_PYPROJECT_SECTIONS = """\
[project]
authors = [
    { name = "Test Author", email = "test@example.com" }
]
readme = "README.md"
requires-python = ">=3.11"

[dependency-groups]
dev = [
    "pytest>=8.0.0",
]

[tool.ruff]
line-length = 110
"""

TEMPLATE_PRE_COMMIT = """\
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.12.0
    hooks:
      - id: ruff
"""

TEMPLATE_GITIGNORE = """\
__pycache__/
*.py[cod]
.venv/
"""


# === プロジェクト用サンプル ===
SAMPLE_PYPROJECT = """\
[project]
name = "test-project"
version = "0.1.0"
description = "Test project"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""

SAMPLE_PYPROJECT_WITH_MY_LIB = """\
[project]
name = "test-project"
version = "0.1.0"
description = "Test project"
dependencies = [
    "my-lib @ git+https://github.com/kimata/my-py-lib@abcd1234567890abcdef1234567890abcdef1234",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""


@pytest.fixture
def tmp_templates(tmp_path):
    """テスト用テンプレートディレクトリを作成"""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()

    # pyproject テンプレート
    pyproject_dir = template_dir / "pyproject"
    pyproject_dir.mkdir()
    (pyproject_dir / "sections.toml").write_text(TEMPLATE_PYPROJECT_SECTIONS)

    # pre-commit テンプレート
    pre_commit_dir = template_dir / "pre-commit"
    pre_commit_dir.mkdir()
    (pre_commit_dir / ".pre-commit-config.yaml").write_text(TEMPLATE_PRE_COMMIT)

    # gitignore テンプレート
    gitignore_dir = template_dir / "gitignore"
    gitignore_dir.mkdir()
    (gitignore_dir / ".gitignore").write_text(TEMPLATE_GITIGNORE)

    return template_dir


@pytest.fixture
def tmp_project(tmp_path):
    """テスト用プロジェクトディレクトリを作成"""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()

    # pyproject.toml
    (project_dir / "pyproject.toml").write_text(SAMPLE_PYPROJECT)

    return project_dir


@pytest.fixture
def tmp_project_with_my_lib(tmp_path):
    """my-py-lib 依存関係を持つテスト用プロジェクトを作成"""
    project_dir = tmp_path / "test-project-my-lib"
    project_dir.mkdir()

    # pyproject.toml with my-lib
    (project_dir / "pyproject.toml").write_text(SAMPLE_PYPROJECT_WITH_MY_LIB)

    return project_dir


@pytest.fixture
def tmp_config(tmp_path, tmp_project, tmp_templates):
    """テスト用 config.yaml を作成"""
    config_content = textwrap.dedent(f"""\
        defaults:
          python_version: "3.12"
          configs:
            - pyproject
            - pre-commit
            - gitignore

        template_dir: {tmp_templates}

        projects:
          - name: test-project
            path: {tmp_project}
    """)

    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)

    return config_file


@pytest.fixture
def sample_config(tmp_project, tmp_templates):
    """テスト用の Config オブジェクトを作成"""
    return py_project.config.Config(
        defaults=py_project.config.Defaults(
            python_version="3.12",
            configs=["pyproject", "pre-commit", "gitignore"],
        ),
        template_dir=str(tmp_templates),
        projects=[
            py_project.config.Project(
                name="test-project",
                path=str(tmp_project),
            )
        ],
    )


@pytest.fixture
def sample_config_dict(tmp_project, tmp_templates):
    """テスト用の設定辞書を作成（dict 形式）"""
    return {
        "defaults": {
            "python_version": "3.12",
            "configs": ["pyproject", "pre-commit", "gitignore"],
        },
        "template_dir": str(tmp_templates),
        "projects": [
            {
                "name": "test-project",
                "path": str(tmp_project),
            }
        ],
    }


@pytest.fixture
def sample_project(tmp_project):
    """テスト用の Project オブジェクトを作成"""
    return py_project.config.Project(
        name="test-project",
        path=str(tmp_project),
    )


@pytest.fixture
def apply_context(tmp_templates, sample_config):
    """テスト用の ApplyContext を作成"""
    return handlers_base.ApplyContext(
        config=sample_config,
        template_dir=tmp_templates,
        dry_run=False,
        backup=False,
    )


@pytest.fixture
def mock_git_ls_remote(mocker):
    """git ls-remote のモック"""
    mock_result = mocker.MagicMock()
    mock_result.stdout = "1234567890abcdef1234567890abcdef12345678\tHEAD\n"
    mock_result.returncode = 0

    mocker.patch(
        "subprocess.run",
        return_value=mock_result,
    )

    return mock_result
