"""設定タイプハンドラの基底クラス"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import tomlkit
import yaml

import py_project.config


class FormatType(Enum):
    """テンプレートの書式タイプ"""

    YAML = "yaml"
    TOML = "toml"
    JSON = "json"
    TEXT = "text"


@dataclass
class ApplyContext:
    """適用時のコンテキスト情報

    Attributes:
        config: アプリ設定全体
        template_dir: テンプレートディレクトリ
        dry_run: ドライランモード
        backup: バックアップ作成フラグ

    """

    config: py_project.config.Config
    template_dir: Path
    dry_run: bool
    backup: bool


@dataclass
class ApplyResult:
    """適用結果"""

    status: str  # "created" | "updated" | "unchanged" | "error" | "skipped"
    message: str | None = None  # エラーメッセージ等


class ConfigHandler(ABC):
    """設定タイプのハンドラ基底クラス"""

    format_type: FormatType = FormatType.TEXT  # デフォルトはプレーンテキスト

    @property
    @abstractmethod
    def name(self) -> str:
        """設定タイプ名"""
        ...  # pragma: no cover

    @abstractmethod
    def apply(self, project: py_project.config.Project, context: ApplyContext) -> ApplyResult:
        """設定を適用"""
        ...  # pragma: no cover

    @abstractmethod
    def diff(self, project: py_project.config.Project, context: ApplyContext) -> str | None:
        """差分を取得（変更がない場合は None）"""
        ...  # pragma: no cover

    @abstractmethod
    def get_output_path(self, project: py_project.config.Project) -> Path:
        """出力ファイルのパスを取得"""
        ...  # pragma: no cover

    def get_project_path(self, project: py_project.config.Project) -> Path:
        """プロジェクトのパスを取得（~を展開）"""
        return project.get_path()

    def create_backup(self, file_path: Path) -> Path | None:
        """バックアップを作成"""
        if not file_path.exists():
            return None

        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        backup_path.write_text(file_path.read_text())
        return backup_path

    def validate(self, content: str) -> tuple[bool, str | None]:
        """コンテンツのシンタックスを検証

        Args:
            content: 検証するコンテンツ

        Returns:
            (True, None) - 有効
            (False, error_message) - 無効

        """
        if self.format_type == FormatType.TEXT:
            return (True, None)

        try:
            if self.format_type == FormatType.YAML:
                yaml.safe_load(content)
            elif self.format_type == FormatType.TOML:
                tomlkit.parse(content)
            elif self.format_type == FormatType.JSON:
                json.loads(content)
            return (True, None)
        except Exception as e:
            return (False, str(e))
