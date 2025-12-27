"""設定タイプハンドラの基底クラス"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ApplyContext:
    """適用時のコンテキスト情報"""

    config: dict[str, Any]  # アプリ設定全体
    template_dir: Path  # テンプレートディレクトリ
    dry_run: bool  # ドライランモード
    backup: bool  # バックアップ作成フラグ


@dataclass
class ApplyResult:
    """適用結果"""

    status: str  # "created" | "updated" | "unchanged" | "error" | "skipped"
    message: str | None = None  # エラーメッセージ等


class ConfigHandler(ABC):
    """設定タイプのハンドラ基底クラス"""

    @property
    @abstractmethod
    def name(self) -> str:
        """設定タイプ名"""
        pass  # pragma: no cover

    @abstractmethod
    def apply(self, project: dict[str, Any], context: ApplyContext) -> ApplyResult:
        """設定を適用"""
        pass  # pragma: no cover

    @abstractmethod
    def diff(self, project: dict[str, Any], context: ApplyContext) -> str | None:
        """差分を取得（変更がない場合は None）"""
        pass  # pragma: no cover

    def get_project_path(self, project: dict[str, Any]) -> Path:
        """プロジェクトのパスを取得（~を展開）"""
        return Path(project["path"]).expanduser()

    def create_backup(self, file_path: Path) -> Path | None:
        """バックアップを作成"""
        if not file_path.exists():
            return None

        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        backup_path.write_text(file_path.read_text())
        return backup_path
