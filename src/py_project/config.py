"""設定データクラス定義"""

import dataclasses
import pathlib
import typing

import dacite


def expand_user_path(path: str | pathlib.Path) -> pathlib.Path:
    """ユーザー指定パスを展開・絶対化

    ~/ を展開し、相対パスを絶対パスに変換する。
    ユーザー入力や設定ファイルのパス指定に使用。

    Args:
        path: 展開対象のパス（文字列または Path）

    Returns:
        展開された絶対パス

    """
    return pathlib.Path(path).expanduser().resolve()


@dataclasses.dataclass
class ApplyOptions:
    """設定適用時のオプション

    Attributes:
        dry_run: ドライランモード（実際には変更しない）
        backup: 適用前にバックアップを作成
        show_diff: 差分を詳細表示
        run_sync: pyproject.toml 更新後に uv sync を実行
        git_commit: 更新したファイルを git add & commit
        git_push: 更新したファイルを git add & commit & push

    """

    dry_run: bool = True
    backup: bool = False
    show_diff: bool = False
    run_sync: bool = True
    git_commit: bool = False
    git_push: bool = False


@dataclasses.dataclass
class GitlabCiEdit:
    """GitLab CI の編集項目

    Attributes:
        path: yamlpath 形式のパス（例: /image, /renovate/image/name）
        value: 設定する値

    """

    path: str
    value: str


@dataclasses.dataclass
class GitlabCiOptions:
    """GitLab CI 設定タイプのオプション

    Attributes:
        edits: yamlpath 形式で値を編集するリスト

    """

    edits: list[GitlabCiEdit] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class PyprojectOptions:
    """pyproject.toml 設定タイプのオプション

    Attributes:
        preserve_sections: 追加で保持するセクション
        preserve_fields: [project] セクション内で追加で保持するフィールド
            （例: requires-python — テンプレートより新しい Python を要求するプロジェクト用）
        extra_dev_deps: 追加の開発依存

    """

    preserve_sections: list[str] = dataclasses.field(default_factory=list)
    preserve_fields: list[str] = dataclasses.field(default_factory=list)
    extra_dev_deps: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class GitignoreOptions:
    """gitignore 設定タイプのオプション

    Attributes:
        extra_lines: テンプレートの末尾に追加する行

    """

    extra_lines: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class DockerignoreOptions:
    """dockerignore 設定タイプのオプション

    Attributes:
        extra_lines: テンプレートの末尾に追加する行

    """

    extra_lines: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class DockerOptions:
    """dockerfile 設定タイプのオプション

    Attributes:
        template: Dockerfile テンプレート名（standard / supervisor / hardware）。
            空の場合、dockerfile 設定タイプは SKIPPED になる
        app_name: WORKDIR (/opt/<app_name>) に使う名前。省略時はプロジェクト名
        chrome: Google Chrome をインストールするか（Selenium 利用プロジェクト）
        chrome_version: Chrome のバージョンを固定する場合に指定
            （例: "142.0.7444.175-1"。新しい Chrome の不具合回避用）
        fonts: リポジトリの font/ をイメージへコピーするか
        cjk_fonts: fonts-noto-cjk を apt でインストールするか
        extra_apt: 追加でインストールする apt パッケージ
        extra_mkdir: 追加で作成するディレクトリ（named volume の所有権対策等）
        expose: EXPOSE するポート
        cmd: CMD に設定するコマンド
        install_project: COPY 後にプロジェクト自身を uv sync でインストールするか
            （./src/xxx.py 直接実行のプロジェクトは False で可）
        compile_bytecode: uv sync に --compile-bytecode を付けるか

    """

    template: str = ""
    app_name: str | None = None
    chrome: bool = False
    chrome_version: str | None = None
    fonts: bool = False
    cjk_fonts: bool = True
    extra_apt: list[str] = dataclasses.field(default_factory=list)
    extra_mkdir: list[str] = dataclasses.field(default_factory=list)
    expose: list[int] = dataclasses.field(default_factory=list)
    cmd: list[str] = dataclasses.field(default_factory=list)
    install_project: bool = True
    compile_bytecode: bool = False
    # hardware テンプレート用
    python_version: str = "3.13"
    lgpio: bool = False
    dev_deps: bool = False
    extra_env: dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class CiOptions:
    """gitlab-ci-gen 設定タイプのオプション

    Attributes:
        template: .gitlab-ci.yml テンプレート名（例: fleama, library）。
            空の場合、gitlab-ci-gen 設定タイプは SKIPPED になる。
            系統固有の値は project.vars（ci_ プレフィクス推奨）でも注入できる
        ty: typecheck ジョブに ty check を含めるか
        pyright_target: pyright の対象引数（空なら引数なし）
        pytest_args: pytest の追加引数（対象テストの限定等）
        pytest_pre: pytest 前に実行する追加コマンド（apt install 等）
        pytest_env_ja: pytest 前に日本語ロケールの環境変数を export するか
        extra_artifacts: test-pytest の追加 artifact パス（data/debug/** 等）
        smoke_config: test-smoke ジョブで bot-config から取得する設定ファイル名
            （smoke_command と両方指定で smoke ジョブが有効になる）
        smoke_command: test-smoke ジョブで実行するコマンド名
        lint: ruff の test-lint ジョブを含めるか
        update_cache: update-cache ジョブを含めるか

    """

    template: str = ""
    ty: bool = True
    pyright_target: str = "src/"
    pytest_args: str = ""
    pytest_pre: list[str] = dataclasses.field(default_factory=list)
    pytest_env_ja: bool = False
    extra_artifacts: list[str] = dataclasses.field(default_factory=list)
    smoke_config: str = ""
    smoke_command: str = ""
    lint: bool = False
    update_cache: bool = False


@dataclasses.dataclass
class RuffOptions:
    """ruff 設定タイプのオプション

    Attributes:
        extra_lines: テンプレートの末尾に追加する行（プロジェクト固有の TOML セクション等）

    """

    extra_lines: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class LicenseOptions:
    """license 設定タイプのオプション

    Attributes:
        type: ライセンスタイプ（テンプレートファイル名と一致）

    """

    type: str = "Apache-2.0"


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
    gitlab_ci: GitlabCiOptions = dataclasses.field(default_factory=GitlabCiOptions)


@dataclasses.dataclass
class Project:
    """管理対象プロジェクト

    Attributes:
        name: プロジェクト名（識別用）
        path: プロジェクトのパス（絶対パスまたは ~/ 形式）
        configs: 追加で適用する設定タイプ（defaults.configs にマージ）
        exclude_configs: 除外する設定タイプ（defaults.configs から除外）
        vars: テンプレート変数
        template_overrides: 設定タイプ別のテンプレート上書き
        pyproject: pyproject.toml 設定タイプのオプション
        gitlab_ci: gitlab-ci 設定タイプのオプション
        gitignore: gitignore 設定タイプのオプション
        dockerignore: dockerignore 設定タイプのオプション
        ruff: ruff 設定タイプのオプション
        license: license 設定タイプのオプション

    """

    name: str
    path: str
    configs: list[str] | None = None
    exclude_configs: list[str] = dataclasses.field(default_factory=list)
    vars: dict[str, str] = dataclasses.field(default_factory=dict)
    template_overrides: dict[str, str] = dataclasses.field(default_factory=dict)
    pyproject: PyprojectOptions = dataclasses.field(default_factory=PyprojectOptions)
    gitlab_ci: GitlabCiOptions = dataclasses.field(default_factory=GitlabCiOptions)
    gitignore: GitignoreOptions = dataclasses.field(default_factory=GitignoreOptions)
    dockerignore: DockerignoreOptions = dataclasses.field(default_factory=DockerignoreOptions)
    ruff: RuffOptions = dataclasses.field(default_factory=RuffOptions)
    license: LicenseOptions = dataclasses.field(default_factory=LicenseOptions)
    docker: DockerOptions = dataclasses.field(default_factory=DockerOptions)
    ci: CiOptions = dataclasses.field(default_factory=CiOptions)

    def get_path(self) -> pathlib.Path:
        """展開されたパスを取得（絶対パス）"""
        return expand_user_path(self.path)

    def get_app_name(self) -> str:
        """Dockerfile 等で使うアプリ名を取得（デフォルトはプロジェクト名）"""
        return self.docker.app_name or self.name


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
        """展開されたテンプレートディレクトリを取得（絶対パス）"""
        return expand_user_path(self.template_dir)

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
    def from_dict(cls, data: dict[str, typing.Any]) -> "Config":
        """辞書から Config を生成

        JSON Schema で検証済みの辞書を受け取り、dacite を使って
        ネストした dataclass を含めて自動的に変換する。
        """
        return dacite.from_dict(data_class=cls, data=data)
