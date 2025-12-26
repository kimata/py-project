"""設定適用ロジック"""

import dataclasses
import logging
import pathlib
import subprocess
import typing

import rich.console
import rich.table

import py_project.differ
import py_project.handlers

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ApplySummary:
    """適用結果サマリ"""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: int = 0
    projects_processed: int = 0
    error_messages: list[str] = dataclasses.field(default_factory=list)


def get_project_configs(project: dict[str, typing.Any], defaults: dict[str, typing.Any]) -> list[str]:
    """プロジェクトに適用する設定タイプのリストを取得"""
    if "configs" in project:
        return project["configs"]
    return defaults.get("configs", [])


def apply_configs(
    config: dict[str, typing.Any],
    projects: list[str] | None = None,
    config_types: list[str] | None = None,
    dry_run: bool = True,
    backup: bool = False,
    show_diff: bool = False,
    run_sync: bool = True,
    console: rich.console.Console | None = None,
) -> ApplySummary:
    """設定を適用

    Args:
        config: アプリケーション設定
        projects: 対象プロジェクト名のリスト（None の場合は全て）
        config_types: 対象設定タイプのリスト（None の場合は全て）
        dry_run: ドライランモード
        backup: バックアップ作成フラグ
        show_diff: 差分表示フラグ
        run_sync: pyproject.toml 更新後に uv sync を実行するかどうか
        console: Rich Console インスタンス

    Returns:
        適用結果サマリ
    """
    if console is None:
        console = rich.console.Console()

    summary = ApplySummary()

    # テンプレートディレクトリ
    template_dir = pathlib.Path(config.get("template_dir", "./templates")).expanduser()

    # デフォルト設定
    defaults = config.get("defaults", {})

    # コンテキスト作成
    context = py_project.handlers.base.ApplyContext(
        config=config,
        template_dir=template_dir,
        dry_run=dry_run,
        backup=backup,
    )

    # モード表示
    if dry_run:
        console.print("[yellow]🔍 Dry run mode[/yellow] (use --apply to apply changes)\n")
    else:
        console.print("[green]🚀 Applying configurations...[/green]\n")

    # 各プロジェクトを処理
    for project in config.get("projects", []):
        project_name = project["name"]

        # プロジェクトフィルタ
        if projects and project_name not in projects:
            continue

        project_path = pathlib.Path(project["path"]).expanduser()
        console.print(f"[bold blue]{project_name}[/bold blue] ({project_path})")

        # プロジェクトディレクトリの存在確認
        if not project_path.exists():
            console.print("  [red]! プロジェクトディレクトリが見つかりません[/red]")
            summary.errors += 1
            summary.error_messages.append(f"{project_name}: ディレクトリが見つかりません")
            continue

        summary.projects_processed += 1

        # 適用する設定タイプを取得
        project_configs = get_project_configs(project, defaults)

        # pyproject が更新されたかどうかを追跡
        pyproject_updated = False

        # 各設定タイプを処理
        for config_type in project_configs:
            # 設定タイプフィルタ
            if config_types and config_type not in config_types:
                continue

            handler_class = py_project.handlers.HANDLERS.get(config_type)
            if handler_class is None:
                console.print(f"  [red]! {config_type:15} : 未知の設定タイプ[/red]")
                summary.errors += 1
                continue

            handler = handler_class()

            # 差分表示
            if show_diff:
                diff_text = handler.diff(project, context)
                if diff_text:
                    console.print(f"  [cyan]~ {config_type:15}[/cyan]")
                    py_project.differ.print_diff(diff_text, console)
                else:
                    console.print(f"  [green]✓ {config_type:15} : up to date[/green]")
                continue

            # 適用
            result = handler.apply(project, context)
            _print_result(console, config_type, result, dry_run)
            _update_summary(summary, result, project_name, config_type)

            # pyproject または my-py-lib が更新されたかチェック
            if config_type in ("pyproject", "my-py-lib") and result.status == "updated":
                pyproject_updated = True

        # pyproject.toml が更新された場合は uv sync を実行
        if pyproject_updated and not dry_run and run_sync:
            _run_uv_sync(project_path, console)

        console.print()

    # サマリ表示
    _print_summary(console, summary, dry_run)

    return summary


def _print_result(
    console: rich.console.Console,
    config_type: str,
    result: py_project.handlers.base.ApplyResult,
    dry_run: bool,
) -> None:
    """適用結果を表示"""
    status_display = {
        "created": ("[green]+[/green]", "will be created" if dry_run else "created"),
        "updated": ("[cyan]~[/cyan]", "will be updated" if dry_run else "updated"),
        "unchanged": ("[green]✓[/green]", "up to date"),
        "skipped": ("[yellow]-[/yellow]", "skipped"),
        "error": ("[red]![/red]", "error"),
    }

    symbol, text = status_display.get(result.status, ("[white]?[/white]", result.status))

    if result.message:
        console.print(f"  {symbol} {config_type:15} : {text} ({result.message})")
    else:
        console.print(f"  {symbol} {config_type:15} : {text}")


def _update_summary(
    summary: ApplySummary,
    result: py_project.handlers.base.ApplyResult,
    project_name: str,
    config_type: str,
) -> None:
    """サマリを更新"""
    if result.status == "created":
        summary.created += 1
    elif result.status == "updated":
        summary.updated += 1
    elif result.status == "unchanged":
        summary.unchanged += 1
    elif result.status == "skipped":
        summary.skipped += 1
    elif result.status == "error":
        summary.errors += 1
        if result.message:
            summary.error_messages.append(f"{project_name}/{config_type}: {result.message}")


def _run_uv_sync(project_path: pathlib.Path, console: rich.console.Console) -> None:
    """uv sync を実行"""
    console.print("  [dim]Running uv sync...[/dim]")
    try:
        result = subprocess.run(
            ["uv", "sync"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            console.print("  [green]✓ uv sync completed[/green]")
        else:
            console.print("  [red]! uv sync failed[/red]")
            if result.stderr:
                for line in result.stderr.strip().split("\n")[:5]:
                    console.print(f"    {line}")
    except subprocess.TimeoutExpired:
        console.print("  [red]! uv sync timed out[/red]")
    except FileNotFoundError:
        console.print("  [yellow]! uv command not found[/yellow]")


def _print_summary(console: rich.console.Console, summary: ApplySummary, dry_run: bool) -> None:
    """サマリを表示"""
    table = rich.table.Table(show_header=False, box=None)
    table.add_column("Key", style="dim")
    table.add_column("Value")

    table.add_row("Projects", str(summary.projects_processed))
    table.add_row("Created", f"[green]{summary.created}[/green]")
    table.add_row("Updated", f"[cyan]{summary.updated}[/cyan]")
    table.add_row("Unchanged", str(summary.unchanged))

    if summary.skipped > 0:
        table.add_row("Skipped", f"[yellow]{summary.skipped}[/yellow]")

    if summary.errors > 0:
        table.add_row("Errors", f"[red]{summary.errors}[/red]")

    console.print("[bold]Summary[/bold]")
    console.print(table)

    if summary.error_messages:
        console.print("\n[red bold]Errors:[/red bold]")
        for msg in summary.error_messages:
            console.print(f"  - {msg}")

    if dry_run and (summary.created > 0 or summary.updated > 0):
        console.print("\n[yellow]Run with --apply to apply these changes[/yellow]")
    elif not dry_run and summary.errors == 0:
        console.print("\n[green]✨ Done![/green]")
