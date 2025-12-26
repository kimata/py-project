"""CLI 定義"""

import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

import my_lib.config as config
import my_lib.logger

from .applier import apply_configs
from .handlers import HANDLERS

app = typer.Typer(
    name="py-project",
    help="複数の Python プロジェクトに標準的な設定を一括適用するツール",
    no_args_is_help=False,
)

console = Console()

# スキーマファイルのパス
SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "config.schema.json"


def init_logger(verbose: bool) -> None:
    """ロガーを初期化"""
    level = logging.DEBUG if verbose else logging.INFO
    my_lib.logger.init(name="py-project", level=level)


def load_config(config_file: Path) -> dict | None:
    """設定ファイルを読み込み"""
    try:
        return config.load(str(config_file), str(SCHEMA_PATH))
    except config.ConfigFileNotFoundError as e:
        console.print(f"[red]設定ファイルが見つかりません: {e}[/red]")
        return None
    except config.ConfigParseError as e:
        console.print(f"[red]設定ファイルの形式が不正です:[/red]\n{e.details}")
        return None
    except config.ConfigValidationError as e:
        console.print(f"[red]設定ファイルの検証に失敗しました:[/red]\n{e.details}")
        return None


@app.command()
def main(
    config_file: Annotated[
        Path,
        typer.Option(
            "-c",
            "--config-file",
            help="設定ファイルのパス",
            exists=False,
        ),
    ] = Path("config.yaml"),
    apply: Annotated[
        bool,
        typer.Option(
            "-a",
            "--apply",
            help="実際に変更を適用（指定しないとドライラン）",
        ),
    ] = False,
    project: Annotated[
        Optional[list[str]],
        typer.Option(
            "-p",
            "--project",
            help="対象プロジェクトを限定（複数指定可）",
        ),
    ] = None,
    config_type: Annotated[
        Optional[list[str]],
        typer.Option(
            "-t",
            "--config",
            help="対象設定タイプを限定（複数指定可）",
        ),
    ] = None,
    diff: Annotated[
        bool,
        typer.Option(
            "-d",
            "--diff",
            help="差分を詳細表示",
        ),
    ] = False,
    backup: Annotated[
        bool,
        typer.Option(
            "-b",
            "--backup",
            help="適用前にバックアップを作成",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "-v",
            "--verbose",
            help="詳細ログ出力",
        ),
    ] = False,
    validate: Annotated[
        bool,
        typer.Option(
            "--validate",
            help="設定ファイルの検証のみ",
        ),
    ] = False,
    list_projects: Annotated[
        bool,
        typer.Option(
            "--list-projects",
            help="プロジェクト一覧を表示",
        ),
    ] = False,
    list_configs: Annotated[
        bool,
        typer.Option(
            "--list-configs",
            help="設定タイプ一覧を表示",
        ),
    ] = False,
) -> None:
    """複数の Python プロジェクトに標準的な設定を一括適用"""
    init_logger(verbose)

    # 設定タイプ一覧表示
    if list_configs:
        _show_config_types()
        return

    # 設定ファイル読み込み
    app_config = load_config(config_file)
    if app_config is None:
        raise typer.Exit(1)

    # 検証のみ
    if validate:
        console.print("[green]設定ファイルは正常です[/green]")
        return

    # プロジェクト一覧表示
    if list_projects:
        _show_projects(app_config)
        return

    # 設定適用
    dry_run = not apply
    summary = apply_configs(
        config=app_config,
        projects=project,
        config_types=config_type,
        dry_run=dry_run,
        backup=backup,
        show_diff=diff,
        console=console,
    )

    # エラーがあった場合は終了コード 1
    if summary.errors > 0:
        raise typer.Exit(1)


def _show_config_types() -> None:
    """設定タイプ一覧を表示"""
    table = Table(title="Available Config Types")
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    descriptions = {
        "pre-commit": "pre-commit 設定ファイル",
        "ruff": "ruff 設定ファイル",
        "yamllint": "yamllint 設定ファイル",
        "prettier": "prettier 設定ファイル",
        "python-version": ".python-version ファイル",
        "dockerignore": ".dockerignore ファイル",
        "gitignore": ".gitignore ファイル",
        "pyproject": "pyproject.toml 共通セクション",
        "my-py-lib": "my-py-lib 依存関係の更新",
    }

    for name in HANDLERS:
        table.add_row(name, descriptions.get(name, ""))

    console.print(table)


def _show_projects(app_config: dict) -> None:
    """プロジェクト一覧を表示"""
    table = Table(title="Configured Projects")
    table.add_column("Name", style="cyan")
    table.add_column("Path")
    table.add_column("Configs")

    defaults = app_config.get("defaults", {})
    default_configs = defaults.get("configs", [])

    for project in app_config.get("projects", []):
        name = project["name"]
        path = project["path"]
        configs = project.get("configs", default_configs)
        configs_str = ", ".join(configs) if configs else "(defaults)"

        table.add_row(name, path, configs_str)

    console.print(table)


if __name__ == "__main__":
    app()
