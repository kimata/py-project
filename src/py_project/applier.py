"""設定適用ロジック"""

import dataclasses
import difflib
import logging
import pathlib
import subprocess

import rich.console
import rich.table

import py_project.config
import py_project.differ
import py_project.handlers

logger = logging.getLogger(__name__)


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

    """

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: int = 0
    projects_processed: int = 0
    error_messages: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ProcessContext:
    """プロジェクト処理用コンテキスト

    Attributes:
        context: ハンドラ用コンテキスト
        options: 適用オプション
        config_types: 対象設定タイプのリスト（None の場合は全て）
        summary: 適用結果サマリ（更新される）
        console: Rich Console インスタンス

    """

    context: py_project.handlers.base.ApplyContext
    options: py_project.config.ApplyOptions
    config_types: list[str] | None
    summary: ApplySummary
    console: rich.console.Console


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
) -> ApplySummary:
    """設定を適用

    Args:
        config: アプリケーション設定
        options: 適用オプション（None の場合はデフォルト）
        projects: 対象プロジェクト名のリスト（None の場合は全て）
        config_types: 対象設定タイプのリスト（None の場合は全て）
        console: Rich Console インスタンス

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

    # モード表示
    if options.dry_run:
        console.print("[yellow]🔍 Dry run mode[/yellow] (use --apply to apply changes)\n")
    else:
        console.print("[green]🚀 Applying configurations...[/green]\n")

    # プロセスコンテキスト作成
    proc_ctx = ProcessContext(
        context=context,
        options=options,
        config_types=config_types,
        summary=summary,
        console=console,
    )

    # 各プロジェクトを処理
    for project in config.projects:
        # プロジェクトフィルタ
        if projects and project.name not in projects:
            continue

        _process_project(project, proc_ctx)

    # サマリ表示
    _print_summary(console, summary, dry_run=options.dry_run)

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
    defaults = context.config.defaults

    project_name = project.name
    project_path = project.get_path()
    console.print(f"[bold blue]{project_name}[/bold blue] ({project_path})")

    # プロジェクトディレクトリの存在確認
    if not project_path.exists():
        console.print("  [red]! プロジェクトディレクトリが見つかりません[/red]")
        summary.errors += 1
        summary.error_messages.append(f"{project_name}: ディレクトリが見つかりません")
        return

    summary.projects_processed += 1

    # 適用する設定タイプを取得
    project_configs = get_project_configs(project, defaults)

    # pyproject が更新されたかどうかを追跡
    pyproject_updated = False

    # git add 対象のファイルリスト
    files_to_add: list[pathlib.Path] = []

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
        if options.show_diff:
            diff_text = handler.diff(project, context)
            if diff_text:
                console.print(f"  [cyan]~ {config_type:15}[/cyan]")
                py_project.differ.print_diff(diff_text, console)
            else:
                console.print(f"  [green]✓ {config_type:15} : up to date[/green]")
            # --diff のみで --apply なしの場合はスキップ
            if options.dry_run:
                continue

        # 適用
        result = handler.apply(project, context)
        _print_result(console, config_type, result, dry_run=options.dry_run)
        _update_summary(summary, result, project_name, config_type)

        # pyproject または my-py-lib が更新されたかチェック
        if config_type in ("pyproject", "my-py-lib") and result.status == "updated":
            pyproject_updated = True

        # git add 対象のファイルを追加
        if options.git_add and result.status in ("created", "updated") and not options.dry_run:
            output_path = handler.get_output_path(project)
            files_to_add.append(output_path)

    # pyproject.toml が更新された場合は uv sync を実行
    if pyproject_updated and not options.dry_run and options.run_sync:
        _run_uv_sync(project_path, console)

    # git add を実行
    if files_to_add:
        _run_git_add(project_path, files_to_add, console)

    console.print()


def _print_result(
    console: rich.console.Console,
    config_type: str,
    result: py_project.handlers.base.ApplyResult,
    *,
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
    else:
        logger.warning("未知のステータス: %s (%s/%s)", result.status, project_name, config_type)


def _run_uv_sync(project_path: pathlib.Path, console: rich.console.Console) -> None:
    """Uv sync を実行"""
    console.print("  [dim]Running uv sync...[/dim]")
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
) -> None:
    """Git add を実行"""
    if not _is_git_repo(project_path):
        return

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
            console.print(f"  [dim]git add: {', '.join(relative_files)}[/dim]")
        else:
            console.print(f"  [red]! git add failed: {result.stderr.strip()}[/red]")
    except subprocess.TimeoutExpired:
        console.print("  [red]! git add timed out[/red]")
    except FileNotFoundError:
        pass  # git not installed, silently skip


def _print_summary(console: rich.console.Console, summary: ApplySummary, *, dry_run: bool) -> None:
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
