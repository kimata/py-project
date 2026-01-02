"""設定データクラス定義"""

from __future__ import annotations

import dataclasses
import pathlib
import typing


@dataclasses.dataclass
class ApplyOptions:
    """設定適用時のオプション

    Attributes:
        dry_run: ドライランモード（実際には変更しない）
        backup: 適用前にバックアップを作成
        show_diff: 差分を詳細表示
        run_sync: pyproject.toml 更新後に uv sync を実行
        git_add: 更新したファイルを git add

    """

    dry_run: bool = True
    backup: bool = False
    show_diff: bool = False
    run_sync: bool = True
    git_add: bool = False


@dataclasses.dataclass
class GitlabCiEdit:
    """GitLab CI の編集項目

    Attributes:
        path: yamlpath 形式のパス（例: /image, /renovate/image/name）
        value: 設定する値

    """

    path: str
    value: str

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> GitlabCiEdit:
        """辞書から GitlabCiEdit を生成"""
        return cls(path=data["path"], value=data["value"])


@dataclasses.dataclass
class GitlabCiOptions:
    """GitLab CI 設定タイプのオプション

    Attributes:
        edits: yamlpath 形式で値を編集するリスト

    """

    edits: list[GitlabCiEdit] = dataclasses.field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> GitlabCiOptions:
        """辞書から GitlabCiOptions を生成"""
        edits = [GitlabCiEdit.from_dict(e) for e in data.get("edits", [])]
        return cls(edits=edits)


@dataclasses.dataclass
class PyprojectOptions:
    """pyproject.toml 設定タイプのオプション

    Attributes:
        preserve_sections: 追加で保持するセクション
        extra_dev_deps: 追加の開発依存

    """

    preserve_sections: list[str] = dataclasses.field(default_factory=list)
    extra_dev_deps: list[str] = dataclasses.field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> PyprojectOptions:
        """辞書から PyprojectOptions を生成"""
        return cls(
            preserve_sections=data.get("preserve_sections", []),
            extra_dev_deps=data.get("extra_dev_deps", []),
        )


@dataclasses.dataclass
class Defaults:
    """全プロジェクト共通のデフォルト設定

    Attributes:
        python_version: デフォルトの Python バージョン
        configs: デフォルトで適用する設定タイプ
        vars: テンプレート変数（Jinja2 で展開）
        gitlab_ci: gitlab-ci 設定タイプのオプション

    """

    python_version: str = "3.12"
    configs: list[str] = dataclasses.field(default_factory=list)
    vars: dict[str, str] = dataclasses.field(default_factory=dict)
    gitlab_ci: GitlabCiOptions | None = None

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> Defaults:
        """辞書から Defaults を生成"""
        gitlab_ci = None
        if "gitlab_ci" in data:
            gitlab_ci = GitlabCiOptions.from_dict(data["gitlab_ci"])
        return cls(
            python_version=data.get("python_version", "3.12"),
            configs=data.get("configs", []),
            vars=data.get("vars", {}),
            gitlab_ci=gitlab_ci,
        )


@dataclasses.dataclass
class Project:
    """管理対象プロジェクト

    Attributes:
        name: プロジェクト名（識別用）
        path: プロジェクトのパス（絶対パスまたは ~/ 形式）
        configs: 適用する設定タイプ（省略時は defaults.configs を使用）
        vars: テンプレート変数
        template_overrides: 設定タイプ別のテンプレート上書き
        pyproject: pyproject.toml 設定タイプのオプション
        gitlab_ci: gitlab-ci 設定タイプのオプション

    """

    name: str
    path: str
    configs: list[str] | None = None
    vars: dict[str, str] = dataclasses.field(default_factory=dict)
    template_overrides: dict[str, str] = dataclasses.field(default_factory=dict)
    pyproject: PyprojectOptions | None = None
    gitlab_ci: GitlabCiOptions | None = None

    def get_path(self) -> pathlib.Path:
        """展開されたパスを取得"""
        return pathlib.Path(self.path).expanduser()

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> Project:
        """辞書から Project を生成"""
        pyproject = None
        if "pyproject" in data:
            pyproject = PyprojectOptions.from_dict(data["pyproject"])
        gitlab_ci = None
        if "gitlab_ci" in data:
            gitlab_ci = GitlabCiOptions.from_dict(data["gitlab_ci"])
        return cls(
            name=data["name"],
            path=data["path"],
            configs=data.get("configs"),
            vars=data.get("vars", {}),
            template_overrides=data.get("template_overrides", {}),
            pyproject=pyproject,
            gitlab_ci=gitlab_ci,
        )


@dataclasses.dataclass
class Config:
    """py-project 設定ファイル

    Attributes:
        defaults: 全プロジェクト共通のデフォルト設定
        template_dir: テンプレートディレクトリのパス
        projects: 管理対象プロジェクト一覧

    """

    projects: list[Project]
    defaults: Defaults = dataclasses.field(default_factory=Defaults)
    template_dir: str = "./templates"

    def get_template_dir(self) -> pathlib.Path:
        """展開されたテンプレートディレクトリを取得"""
        return pathlib.Path(self.template_dir).expanduser()

    def get_project(self, name: str) -> Project | None:
        """名前でプロジェクトを取得"""
        for project in self.projects:
            if project.name == name:
                return project
        return None

    def get_project_names(self) -> list[str]:
        """プロジェクト名のリストを取得"""
        return [p.name for p in self.projects]

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> Config:
        """辞書から Config を生成"""
        defaults = Defaults()
        if "defaults" in data:
            defaults = Defaults.from_dict(data["defaults"])
        projects = [Project.from_dict(p) for p in data.get("projects", [])]
        return cls(
            projects=projects,
            defaults=defaults,
            template_dir=data.get("template_dir", "./templates"),
        )
