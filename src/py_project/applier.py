"""設定適用ロジック"""

from __future__ import annotations

import dataclasses
import difflib
import logging
import pathlib
import subprocess
from typing import TYPE_CHECKING

import rich.box
import rich.console
import rich.panel
import rich.table

import py_project.config
import py_project.differ
import py_project.handlers

if TYPE_CHECKING:
    import py_project.progress

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ChangeDetail:
    """個別の変更詳細"""

    project: str
    config_type: str
    status: str
    message: str = ""


@dataclasses.dataclass
class ApplySummary:
    """適用結果サマリ

    Attributes:
        created: 新規作成された設定ファイル数
        updated: 更新された設定ファイル数
        unchanged: 変更なしの設定ファイル数
        skipped: スキップされた設定ファイル数
        errors: エラー数
        projects_processed: 設定を適用したプロジェクト数（ディレクトリが存在したもののみ）
        error_messages: エラーメッセージのリスト
        changes: 変更詳細のリスト（created, updated, error のみ記録）

    """

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: int = 0
    projects_processed: int = 0
    error_messages: list[str] = dataclasses.field(default_factory=list)
    changes: list[ChangeDetail] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ProcessContext:
    """プロジェクト処理用コンテキスト

    Attributes:
        context: ハンドラ用コンテキスト
        options: 適用オプション
        config_types: 対象設定タイプのリスト（None の場合は全て）
        summary: 適用結果サマリ（更新される）
        console: Rich Console インスタンス
        progress: プログレスマネージャ（オプション）

    """

    context: py_project.handlers.base.ApplyContext
    options: py_project.config.ApplyOptions
    config_types: list[str] | None
    summary: ApplySummary
    console: rich.console.Console
    progress: py_project.progress.ProgressManager | None = None


def get_project_configs(
    project: py_project.config.Project, defaults: py_project.config.Defaults
) -> list[str]:
    """プロジェクトに適用する設定タイプのリストを取得

    defaults.configs をベースに、project.configs を追加し、
    project.exclude_configs を除外した結果を返す。
    """
    # defaults.configs をベースにする
    configs = list(defaults.configs)

    # project.configs があれば追加（重複排除）
    if project.configs:
        for config in project.configs:
            if config not in configs:
                configs.append(config)

    # exclude_configs を除外
    for exclude in project.exclude_configs:
        if exclude in configs:
            configs.remove(exclude)

    return configs


def _validate_projects(
    requested_projects: list[str],
    available_projects: list[str],
) -> list[str]:
    """指定されたプロジェクトが設定に存在するか検証し、存在しないものを返す

    存在しないプロジェクトがあれば警告を出し、類似候補を表示する。

    Args:
        requested_projects: リクエストされたプロジェクト名のリスト
        available_projects: 設定ファイルに定義されているプロジェクト名のリスト

    Returns:
        存在しないプロジェクト名のリスト

    """
    missing = []
    for project in requested_projects:
        if project not in available_projects:
            missing.append(project)
            logger.warning("プロジェクト '%s' は設定に存在しません", project)

            # 類似候補を検索
            close_matches = difflib.get_close_matches(project, available_projects, n=3, cutoff=0.4)
            if close_matches:
                logger.info("  類似候補: %s", ", ".join(close_matches))

    return missing


def apply_configs(
    config: py_project.config.Config,
    options: py_project.config.ApplyOptions | None = None,
    projects: list[str] | None = None,
    config_types: list[str] | None = None,
    console: rich.console.Console | None = None,
    progress: py_project.progress.ProgressManager | None = None,
) -> ApplySummary:
    """設定を適用

    Args:
        config: アプリケーション設定
        options: 適用オプション（None の場合はデフォルト）
        projects: 対象プロジェクト名のリスト（None の場合は全て）
        config_types: 対象設定タイプのリスト（None の場合は全て）
        console: Rich Console インスタンス
        progress: プログレスマネージャ（オプション）

    Returns:
        適用結果サマリ

    """
    if options is None:
        options = py_project.config.ApplyOptions()
    if console is None:
        console = rich.console.Console()

    summary = ApplySummary()

    # テンプレートディレクトリ
    template_dir = config.get_template_dir()

    # 利用可能なプロジェクト名のリストを取得
    available_projects = config.get_project_names()

    # 指定されたプロジェクトの検証
    if projects:
        _validate_projects(projects, available_projects)

    # コンテキスト作成
    context = py_project.handlers.base.ApplyContext(
        config=config,
        template_dir=template_dir,
        dry_run=options.dry_run,
        backup=options.backup,
    )

    # モード表示（非TTY環境でのみ表示）
    if progress:
        progress.print(
            "[yellow]🔍 確認モード[/yellow]（--apply で実際に適用）\n"
            if options.dry_run
            else "[green]🚀 設定を適用中...[/green]\n"
        )
    else:
        if options.dry_run:
            console.print("[yellow]🔍 確認モード[/yellow]（--apply で実際に適用）\n")
        else:
            console.print("[green]🚀 設定を適用中...[/green]\n")

    # プロセスコンテキスト作成
    proc_ctx = ProcessContext(
        context=context,
        options=options,
        config_types=config_types,
        summary=summary,
        console=console,
        progress=progress,
    )

    # 対象プロジェクトのリストを作成
    target_projects = [p for p in config.projects if projects is None or p.name in projects]

    # プログレスバーを設定
    if progress:
        progress.set_progress_bar("プロジェクト", len(target_projects))

    # 各プロジェクトを処理
    for project in target_projects:
        if progress:
            progress.set_status(f"処理中: {project.name}")

        _process_project(project, proc_ctx)

        if progress:
            progress.update_progress_bar("プロジェクト")

    # プログレスバーを削除
    if progress:
        progress.remove_progress_bar("プロジェクト")
        progress.set_status("完了！")

    # サマリ表示
    _print_summary(console, summary, dry_run=options.dry_run, progress=progress)

    return summary


def _process_project(
    project: py_project.config.Project,
    proc_ctx: ProcessContext,
) -> None:
    """単一プロジェクトの設定を処理"""
    # コンテキストから必要な値を取得
    context = proc_ctx.context
    options = proc_ctx.options
    config_types = proc_ctx.config_types
    summary = proc_ctx.summary
    console = proc_ctx.console
    progress = proc_ctx.progress
    defaults = context.config.defaults

    project_name = project.name
    project_path = project.get_path()

    # TTY環境では詳細出力を抑制
    if progress:
        progress.print(f"[bold blue]{project_name}[/bold blue] ({project_path})")
    else:
        console.print(f"[bold blue]{project_name}[/bold blue] ({project_path})")

    # プロジェクトディレクトリの存在確認
    if not project_path.exists():
        if progress:
            progress.print("  [red]! プロジェクトディレクトリが見つかりません[/red]")
        else:
            console.print("  [red]! プロジェクトディレクトリが見つかりません[/red]")
        summary.errors += 1
        summary.error_messages.append(f"{project_name}: ディレクトリが見つかりません")
        return

    summary.projects_processed += 1

    # 適用する設定タイプを取得
    project_configs = get_project_configs(project, defaults)

    # 対象設定タイプをフィルタ
    target_configs = [c for c in project_configs if config_types is None or c in config_types]

    # pyproject が更新されたかどうかを追跡
    pyproject_updated = False

    # git add 対象のファイルリスト
    files_to_add: list[pathlib.Path] = []

    # 設定タイプ用プログレスバーを設定
    config_bar_name = f"  {project_name}"
    if progress:
        progress.set_progress_bar(config_bar_name, len(target_configs))

    # 各設定タイプを処理
    for config_type in target_configs:
        handler_class = py_project.handlers.HANDLERS.get(config_type)
        if handler_class is None:
            if progress:
                progress.print(f"  [red]! {config_type:15} : 未知の設定タイプ[/red]")
            else:
                console.print(f"  [red]! {config_type:15} : 未知の設定タイプ[/red]")
            summary.errors += 1
            if progress:
                progress.update_progress_bar(config_bar_name)
            continue

        handler = handler_class()

        # 差分表示
        if options.show_diff:
            diff_text = handler.diff(project, context)
            if diff_text:
                if progress:
                    progress.print(f"  [cyan]~ {config_type:15}[/cyan]")
                else:
                    console.print(f"  [cyan]~ {config_type:15}[/cyan]")
                py_project.differ.print_diff(diff_text, console)
            else:
                if progress:
                    progress.print(f"  [green]✓ {config_type:15} : up to date[/green]")
                else:
                    console.print(f"  [green]✓ {config_type:15} : up to date[/green]")
            # --diff のみで --apply なしの場合はスキップ
            if options.dry_run:
                if progress:
                    progress.update_progress_bar(config_bar_name)
                continue

        # 適用
        result = handler.apply(project, context)
        _print_result(console, config_type, result, dry_run=options.dry_run, progress=progress)
        _update_summary(summary, result, project_name, config_type)

        # pyproject または my-py-lib が更新されたかチェック
        if config_type in ("pyproject", "my-py-lib") and result.status == "updated":
            pyproject_updated = True

        # git add 対象のファイルを追加
        if options.git_add and result.status in ("created", "updated") and not options.dry_run:
            output_path = handler.get_output_path(project)
            files_to_add.append(output_path)

        if progress:
            progress.update_progress_bar(config_bar_name)

    # 設定タイプ用プログレスバーを削除
    if progress:
        progress.remove_progress_bar(config_bar_name)

    # pyproject.toml が更新された場合は uv sync を実行
    if pyproject_updated and not options.dry_run and options.run_sync:
        _run_uv_sync(project_path, console, progress)

    # git add を実行
    if files_to_add:
        _run_git_add(project_path, files_to_add, console, progress)

    if progress:
        progress.print()
    else:
        console.print()


def _print_result(
    console: rich.console.Console,
    config_type: str,
    result: py_project.handlers.base.ApplyResult,
    *,
    dry_run: bool,
    progress: py_project.progress.ProgressManager | None = None,
) -> None:
    """適用結果を表示"""
    status_display = {
        "created": ("[green]+[/green]", "作成予定" if dry_run else "作成"),
        "updated": ("[cyan]~[/cyan]", "更新予定" if dry_run else "更新"),
        "unchanged": ("[green]✓[/green]", "変更なし"),
        "skipped": ("[yellow]-[/yellow]", "スキップ"),
        "error": ("[red]![/red]", "エラー"),
    }

    symbol, text = status_display.get(result.status, ("[white]?[/white]", result.status))

    if result.message:
        msg = f"  {symbol} {config_type:15} : {text} ({result.message})"
    else:
        msg = f"  {symbol} {config_type:15} : {text}"

    if progress:
        progress.print(msg)
    else:
        console.print(msg)


def _update_summary(
    summary: ApplySummary,
    result: py_project.handlers.base.ApplyResult,
    project_name: str,
    config_type: str,
) -> None:
    """サマリを更新"""
    if result.status == "created":
        summary.created += 1
        summary.changes.append(ChangeDetail(project_name, config_type, "created", result.message or ""))
    elif result.status == "updated":
        summary.updated += 1
        summary.changes.append(ChangeDetail(project_name, config_type, "updated", result.message or ""))
    elif result.status == "unchanged":
        summary.unchanged += 1
    elif result.status == "skipped":
        summary.skipped += 1
    elif result.status == "error":
        summary.errors += 1
        summary.changes.append(ChangeDetail(project_name, config_type, "error", result.message or ""))
        if result.message:
            summary.error_messages.append(f"{project_name}/{config_type}: {result.message}")
    else:
        logger.warning("未知のステータス: %s (%s/%s)", result.status, project_name, config_type)


def _run_uv_sync(
    project_path: pathlib.Path,
    console: rich.console.Console,
    progress: py_project.progress.ProgressManager | None = None,
) -> None:
    """Uv sync を実行"""

    def _print(msg: str) -> None:
        if progress:
            progress.print(msg)
        else:
            console.print(msg)

    _print("  [dim]Running uv sync...[/dim]")
    try:
        result = subprocess.run(
            ["uv", "sync"],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode == 0:
            _print("  [green]✓ uv sync completed[/green]")
        else:
            _print("  [red]! uv sync failed[/red]")
            if result.stderr:
                for line in result.stderr.strip().split("\n")[:5]:
                    _print(f"    {line}")
    except subprocess.TimeoutExpired:
        _print("  [red]! uv sync timed out[/red]")
    except FileNotFoundError:
        _print("  [yellow]! uv command not found[/yellow]")


def _is_git_repo(project_path: pathlib.Path) -> bool:
    """プロジェクトが Git リポジトリかどうかを確認"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _run_git_add(
    project_path: pathlib.Path,
    files: list[pathlib.Path],
    console: rich.console.Console,
    progress: py_project.progress.ProgressManager | None = None,
) -> None:
    """Git add を実行"""
    if not _is_git_repo(project_path):
        return

    def _print(msg: str) -> None:
        if progress:
            progress.print(msg)
        else:
            console.print(msg)

    # 相対パスに変換
    relative_files = []
    for file_path in files:
        try:
            relative_files.append(str(file_path.relative_to(project_path)))
        except ValueError:
            relative_files.append(str(file_path))

    try:
        result = subprocess.run(  # noqa: S603
            ["git", "add", *relative_files],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            _print(f"  [dim]git add: {', '.join(relative_files)}[/dim]")
        else:
            _print(f"  [red]! git add failed: {result.stderr.strip()}[/red]")
    except subprocess.TimeoutExpired:
        _print("  [red]! git add timed out[/red]")
    except FileNotFoundError:
        pass  # git not installed, silently skip


def _print_summary(
    console: rich.console.Console,
    summary: ApplySummary,
    *,
    dry_run: bool,
    progress: py_project.progress.ProgressManager | None = None,
) -> None:
    """サマリを表示"""
    import time

    from rich.console import Group

    # 統計テーブル（横並び）
    stats_table = rich.table.Table(
        box=rich.box.ROUNDED,
        show_header=True,
        header_style="bold",
        padding=(0, 1),
    )
    stats_table.add_column("📁 プロジェクト", justify="center", style="bold")
    stats_table.add_column("✨ 作成", justify="center", style="green")
    stats_table.add_column("🔄 更新", justify="center", style="cyan")
    stats_table.add_column("✓ 変更なし", justify="center", style="dim")

    if summary.skipped > 0:
        stats_table.add_column("⏭️ スキップ", justify="center", style="yellow")
    if summary.errors > 0:
        stats_table.add_column("❌ エラー", justify="center", style="red bold")

    # 行を追加
    row = [
        str(summary.projects_processed),
        str(summary.created),
        str(summary.updated),
        str(summary.unchanged),
    ]
    if summary.skipped > 0:
        row.append(str(summary.skipped))
    if summary.errors > 0:
        row.append(str(summary.errors))

    stats_table.add_row(*row)

    # 経過時間
    elapsed_str = ""
    if progress:
        elapsed = time.time() - progress._start_time
        minutes, seconds = divmod(int(elapsed), 60)
        elapsed_str = f"⏱️  経過時間: {minutes:02d}:{seconds:02d}"

    # ステータスメッセージ
    if dry_run and (summary.created > 0 or summary.updated > 0):
        status_msg = "[yellow]📋 --apply で変更を適用[/yellow]"
    elif summary.errors > 0:
        status_msg = f"[red bold]❌ {summary.errors} 件のエラーで完了[/red bold]"
    else:
        status_msg = "[green]✨ 完了！[/green]"

    # パネル内のコンテンツを構築
    content_parts: list[rich.table.Table | str] = [stats_table]

    # 変更詳細テーブル（幅が十分ある場合のみ表示）
    min_width_for_changes = 80
    if summary.changes and console.width >= min_width_for_changes:
        content_parts.append("")
        content_parts.append("[bold]📝 変更内容:[/bold]")

        changes_table = rich.table.Table(
            box=rich.box.SIMPLE,
            show_header=True,
            header_style="bold dim",
            padding=(0, 1),
            expand=False,
        )
        changes_table.add_column("プロジェクト", style="cyan", no_wrap=True)
        changes_table.add_column("設定タイプ", style="white", no_wrap=True)
        changes_table.add_column("状態", justify="center", no_wrap=True)
        changes_table.add_column("詳細", style="dim")

        status_style = {
            "created": "[green]+ 作成[/green]",
            "updated": "[cyan]~ 更新[/cyan]",
            "error": "[red]! エラー[/red]",
        }

        for change in summary.changes:
            changes_table.add_row(
                change.project,
                change.config_type,
                status_style.get(change.status, change.status),
                change.message if change.message else "",
            )

        content_parts.append(changes_table)

    # エラーメッセージがある場合
    # 変更詳細テーブルが表示されていない場合、または changes に含まれないエラーがある場合は表示
    show_error_messages = summary.error_messages and (
        console.width < min_width_for_changes or not summary.changes
    )
    if show_error_messages:
        error_table = rich.table.Table(box=None, show_header=False, padding=(0, 0))
        error_table.add_column("Error", style="red")
        for msg in summary.error_messages:
            error_table.add_row(f"  • {msg}")
        content_parts.append("")
        content_parts.append("[red bold]エラー:[/red bold]")
        content_parts.append(error_table)

    # 経過時間とステータス
    footer_parts = []
    if elapsed_str:
        footer_parts.append(elapsed_str)
    footer_parts.append(status_msg)

    content_parts.append("")
    content_parts.append("  ".join(footer_parts))

    panel_content = Group(*content_parts)

    # Panel で囲む
    panel = rich.panel.Panel(
        panel_content,
        title="[bold]📊 サマリー[/bold]",
        border_style="blue",
        padding=(1, 2),
    )

    console.print()
    console.print(panel)
