"""設定タイプハンドラの基底クラス"""

import abc
import dataclasses
import difflib
import enum
import json
import pathlib

import tomlkit
import tomlkit.exceptions
import yaml

import py_project.config


class FormatType(enum.Enum):
    """テンプレートの書式タイプ"""

    YAML = "yaml"
    TOML = "toml"
    JSON = "json"
    TEXT = "text"


class ApplyStatus(enum.Enum):
    """適用結果のステータス"""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclasses.dataclass
class ValidationResult:
    """コンテンツバリデーション結果

    Attributes:
        is_valid: バリデーションが成功したかどうか
        error_message: エラーメッセージ（is_valid=False の場合）

    """

    is_valid: bool
    error_message: str | None = None


@dataclasses.dataclass
class ApplyContext:
    """適用時のコンテキスト情報

    Attributes:
        config: アプリ設定全体
        template_dir: テンプレートディレクトリ
        dry_run: ドライランモード
        backup: バックアップ作成フラグ

    """

    config: py_project.config.Config
    template_dir: pathlib.Path
    dry_run: bool
    backup: bool


@dataclasses.dataclass
class ApplyResult:
    """適用結果"""

    status: ApplyStatus
    message: str | None = None  # エラーメッセージ等


class ConfigHandler(abc.ABC):
    """設定タイプのハンドラ基底クラス"""

    format_type: FormatType = FormatType.TEXT  # デフォルトはプレーンテキスト

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """設定タイプ名"""
        ...  # pragma: no cover

    @abc.abstractmethod
    def apply(self, project: py_project.config.Project, context: ApplyContext) -> ApplyResult:
        """設定を適用"""
        ...  # pragma: no cover

    @abc.abstractmethod
    def diff(self, project: py_project.config.Project, context: ApplyContext) -> str | None:
        """差分を取得（変更がない場合は None）"""
        ...  # pragma: no cover

    @abc.abstractmethod
    def get_output_path(self, project: py_project.config.Project) -> pathlib.Path:
        """出力ファイルのパスを取得"""
        ...  # pragma: no cover

    def get_project_path(self, project: py_project.config.Project) -> pathlib.Path:
        """プロジェクトのパスを取得（~を展開）"""
        return project.get_path()

    def create_backup(self, file_path: pathlib.Path) -> pathlib.Path | None:
        """バックアップを作成"""
        if not file_path.exists():
            return None

        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        backup_path.write_text(file_path.read_text())
        return backup_path

    def _read_file(self, path: pathlib.Path, encoding: str = "utf-8") -> str:
        """ファイル内容を読み込み

        Args:
            path: 読み込むファイルのパス
            encoding: 文字エンコーディング（デフォルト: utf-8）

        Returns:
            ファイルの内容

        """
        return path.read_text(encoding=encoding)

    def _write_file(
        self,
        path: pathlib.Path,
        content: str,
        *,
        encoding: str = "utf-8",
        create_backup: bool = False,
    ) -> None:
        """ファイル内容を書き込み

        Args:
            path: 書き込むファイルのパス
            content: 書き込む内容
            encoding: 文字エンコーディング（デフォルト: utf-8）
            create_backup: バックアップを作成するかどうか

        """
        if create_backup and path.exists():
            self.create_backup(path)
        path.write_text(content, encoding=encoding)

    def validate(self, content: str) -> ValidationResult:
        """コンテンツのシンタックスを検証

        Args:
            content: 検証するコンテンツ

        Returns:
            ValidationResult: バリデーション結果

        """
        if self.format_type == FormatType.TEXT:
            return ValidationResult(is_valid=True)

        try:
            if self.format_type == FormatType.YAML:
                yaml.safe_load(content)
            elif self.format_type == FormatType.TOML:
                tomlkit.parse(content)
            elif self.format_type == FormatType.JSON:
                json.loads(content)
            return ValidationResult(is_valid=True)
        except (yaml.YAMLError, tomlkit.exceptions.TOMLKitError, json.JSONDecodeError) as e:
            return ValidationResult(is_valid=False, error_message=str(e))

    def generate_diff(
        self,
        current_content: str,
        new_content: str,
        filename: str,
    ) -> str | None:
        """差分を生成（変更がない場合は None）"""
        if current_content == new_content:
            return None
        diff = difflib.unified_diff(
            current_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
        return "".join(diff)
