"""設定適用ロジック"""

import dataclasses
import difflib
import logging
import pathlib
import re
import subprocess
import typing

import my_lib.cui_progress
import rich.box
import rich.console
import rich.panel
import rich.table

import py_project.config
import py_project.differ
import py_project.handlers
import py_project.handlers.base as handlers_base

logger = logging.getLogger(__name__)

# 型エイリアス: ProgressManager または NullProgressManager
ProgressType: typing.TypeAlias = my_lib.cui_progress.ProgressManager | my_lib.cui_progress.NullProgressManager

# 型エイリアス: 対象リスト（プロジェクト名または設定タイプのリスト）
TargetList: typing.TypeAlias = list[str] | None


def _create_printer(
    progress: ProgressType,
) -> typing.Callable[[str], None]:
    """progress の print 関数を返す"""

    def printer(msg: str) -> None:
        progress.print(msg)

    return printer


def _to_relative_path(path: pathlib.Path, base: pathlib.Path) -> pathlib.Path:
    """パスを base からの相対パスに変換

    変換できない場合（パスが base 配下にない場合）は元のパスを返す。
    """
    try:
        return path.relative_to(base)
    except ValueError:
        return path


@dataclasses.dataclass
class GitCommitFile:
    """Git commit 対象ファイルの情報"""

    path: pathlib.Path
    config_type: str
    message: str


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

    context: handlers_base.ApplyContext
    options: py_project.config.ApplyOptions
    config_types: TargetList
    summary: ApplySummary
    console: rich.console.Console
    progress: ProgressType


def _get_project_configs(
    project: py_project.config.Project, defaults: py_project.config.Defaults
) -> list[str]:
    """プロジェクトに適用する設定タイプのリストを取得

    defaults.configs をベースに、project.configs を追加し、
    project.exclude_configs を除外した結果を返す。
    """
    # defaults.configs をベースにする
    configs = defaults.configs.copy()

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
    projects: TargetList = None,
    config_types: TargetList = None,
    console: rich.console.Console | None = None,
    progress: ProgressType | None = None,
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
    if progress is None:
        progress = my_lib.cui_progress.NullProgressManager(console=console)

    summary = ApplySummary()

    # テンプレートディレクトリ
    template_dir = config.get_template_dir()

    # 利用可能なプロジェクト名のリストを取得
    available_projects = config.get_project_names()

    # 指定されたプロジェクトの検証
    if projects:
        _validate_projects(projects, available_projects)

    # コンテキスト作成
    context = handlers_base.ApplyContext(
        config=config,
        template_dir=template_dir,
        dry_run=options.dry_run,
        backup=options.backup,
    )

    # モード表示（非TTY環境でのみ表示）
    _print = _create_printer(progress)
    _print(
        "[yellow]🔍 確認モード[/yellow]（--apply で実際に適用）\n"
        if options.dry_run
        else "[green]🚀 設定を適用中...[/green]\n"
    )

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
    progress.set_progress_bar("プロジェクト", len(target_projects))

    # 各プロジェクトを処理
    for project in target_projects:
        progress.set_status(f"処理中: {project.name}")
        _process_project(project, proc_ctx)
        progress.update_progress_bar("プロジェクト")

    # プログレスバーを削除
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

    # 共通の print 関数を作成
    _print = _create_printer(progress)

    project_name = project.name
    project_path = project.get_path()

    # プロジェクト名を表示（TTY/非TTY 両方で表示）
    console.print(f"[bold blue]{project_name}[/bold blue] ({project_path})")

    # プロジェクトディレクトリの存在確認
    if not project_path.exists():
        _print("  [red]! プロジェクトディレクトリが見つかりません[/red]")
        summary.errors += 1
        summary.error_messages.append(f"{project_name}: ディレクトリが見つかりません")
        return

    summary.projects_processed += 1

    # 適用する設定タイプを取得
    project_configs = _get_project_configs(project, defaults)

    # 対象設定タイプをフィルタ
    target_configs = [c for c in project_configs if config_types is None or c in config_types]

    # pyproject が更新されたかどうかを追跡
    pyproject_updated = False

    # git commit 対象のファイル情報リスト
    files_to_commit: list[GitCommitFile] = []

    # git 操作が有効かどうか（git_push は git_commit を含む）
    do_git_commit = options.git_commit or options.git_push

    # git commit オプションが有効な場合、処理前に既存の変更を stash
    stashed = False
    if (
        do_git_commit
        and not options.dry_run
        and _is_git_repo(project_path)
        and _has_uncommitted_changes(project_path)
    ):
        stashed = _run_git_stash(project_path, console, progress)

    # 設定タイプ用プログレスバーを設定
    config_bar_name = f"  {project_name}"
    progress.set_progress_bar(config_bar_name, len(target_configs))

    # 各設定タイプを処理
    for config_type in target_configs:
        handler_class = py_project.handlers.HANDLERS.get(config_type)
        if handler_class is None:
            _print(f"  [red]! {config_type:15} : 未知の設定タイプ[/red]")
            summary.errors += 1
            progress.update_progress_bar(config_bar_name)
            continue

        handler = handler_class()

        # 差分表示
        if options.show_diff:
            diff_text = handler.diff(project, context)
            if diff_text:
                _print(f"  [cyan]~ {config_type:15}[/cyan]")
                py_project.differ.print_diff(diff_text, console)
            else:
                _print(f"  [green]✓ {config_type:15} : up to date[/green]")
            # --diff のみで --apply なしの場合はスキップ
            if options.dry_run:
                progress.update_progress_bar(config_bar_name)
                continue

        # 適用
        result = handler.apply(project, context)
        _print_result(console, config_type, result, dry_run=options.dry_run, progress=progress)
        _update_summary(summary, result, project_name, config_type)

        # pyproject または my-py-lib が更新されたかチェック
        if config_type in ("pyproject", "my-py-lib") and result.status == handlers_base.ApplyStatus.UPDATED:
            pyproject_updated = True

        # git commit 対象のファイルを追加
        if (
            do_git_commit
            and result.status in (handlers_base.ApplyStatus.CREATED, handlers_base.ApplyStatus.UPDATED)
            and not options.dry_run
        ):
            output_path = handler.get_output_path(project)
            files_to_commit.append(
                GitCommitFile(path=output_path, config_type=config_type, message=result.message or "")
            )

        progress.update_progress_bar(config_bar_name)

    # 設定タイプ用プログレスバーを削除
    progress.remove_progress_bar(config_bar_name)

    # pyproject.toml が更新された場合は uv sync を実行
    uv_sync_success = False
    if pyproject_updated and not options.dry_run and options.run_sync:
        uv_sync_success = _run_uv_sync(project_path, console, progress)

        # uv sync が成功した場合は uv.lock も commit 対象に追加
        if uv_sync_success and do_git_commit:
            uv_lock_path = project_path / "uv.lock"
            if uv_lock_path.exists():
                uv_lock_message = _get_uv_lock_changes(project_path)
                files_to_commit.append(
                    GitCommitFile(path=uv_lock_path, config_type="uv.lock", message=uv_lock_message)
                )

    # git commit を実行
    if files_to_commit:
        commit_success = _run_git_commit(
            project_path, files_to_commit, console, progress, will_push=options.git_push
        )

        # push が有効で commit が成功した場合は push も実行
        if options.git_push and commit_success:
            _run_git_push(project_path, files_to_commit, console, progress)

    # stash した場合は復元
    if stashed:
        _run_git_stash_pop(project_path, console, progress)

    _print("")


def _print_result(
    console: rich.console.Console,
    config_type: str,
    result: handlers_base.ApplyResult,
    *,
    dry_run: bool,
    progress: ProgressType,
) -> None:
    """適用結果を表示"""
    _print = _create_printer(progress)

    ApplyStatus = handlers_base.ApplyStatus
    status_display = {
        ApplyStatus.CREATED: ("[green]+[/green]", "作成予定" if dry_run else "作成"),
        ApplyStatus.UPDATED: ("[cyan]~[/cyan]", "更新予定" if dry_run else "更新"),
        ApplyStatus.UNCHANGED: ("[green]✓[/green]", "変更なし"),
        ApplyStatus.SKIPPED: ("[yellow]-[/yellow]", "スキップ"),
        ApplyStatus.ERROR: ("[red]![/red]", "エラー"),
    }

    symbol, text = status_display[result.status]

    if result.message:
        msg = f"  {symbol} {config_type:15} : {text} ({result.message})"
    else:
        msg = f"  {symbol} {config_type:15} : {text}"

    _print(msg)


def _update_summary(
    summary: ApplySummary,
    result: handlers_base.ApplyResult,
    project_name: str,
    config_type: str,
) -> None:
    """サマリを更新"""
    ApplyStatus = handlers_base.ApplyStatus
    match result.status:
        case ApplyStatus.CREATED:
            summary.created += 1
            summary.changes.append(ChangeDetail(project_name, config_type, "created", result.message or ""))
        case ApplyStatus.UPDATED:
            summary.updated += 1
            summary.changes.append(ChangeDetail(project_name, config_type, "updated", result.message or ""))
        case ApplyStatus.UNCHANGED:
            summary.unchanged += 1
        case ApplyStatus.SKIPPED:
            summary.skipped += 1
        case ApplyStatus.ERROR:
            summary.errors += 1
            summary.changes.append(ChangeDetail(project_name, config_type, "error", result.message or ""))
            if result.message:
                summary.error_messages.append(f"{project_name}/{config_type}: {result.message}")


def _run_uv_sync(
    project_path: pathlib.Path,
    console: rich.console.Console,
    progress: ProgressType,
) -> bool:
    """Uv sync を実行

    Returns:
        sync が成功したかどうか

    """
    _print = _create_printer(progress)

    _print("  [dim]Running uv sync...[/dim]")
    try:
        result = subprocess.run(
            ["uv", "sync"],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            _print("  [green]✓ uv sync completed[/green]")
            return True
        _print("  [red]! uv sync failed[/red]")
        if result.stderr:
            for line in result.stderr.strip().split("\n")[:5]:
                _print(f"    {line}")
        return False
    except subprocess.TimeoutExpired:
        _print("  [red]! uv sync timed out[/red]")
        return False
    except FileNotFoundError:
        _print("  [yellow]! uv command not found[/yellow]")
        return False


def _is_git_repo(project_path: pathlib.Path) -> bool:
    """プロジェクトが Git リポジトリかどうかを確認"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            timeout=5,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _has_uncommitted_changes(project_path: pathlib.Path) -> bool:
    """未コミットの変更があるか確認"""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _run_git_stash(
    project_path: pathlib.Path,
    console: rich.console.Console,
    progress: ProgressType,
) -> bool:
    """Git stash を実行

    Returns:
        stash が成功したかどうか

    """
    _print = _create_printer(progress)

    try:
        result = subprocess.run(
            ["git", "stash", "push", "-m", "py-project: temporary stash"],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            _print("  [dim]git stash: 既存の変更を一時退避[/dim]")
            return True
        _print(f"  [red]! git stash failed: {result.stderr.strip()}[/red]")
        return False
    except subprocess.TimeoutExpired:
        _print("  [red]! git stash timed out[/red]")
        return False
    except FileNotFoundError:
        return False


def _run_git_stash_pop(
    project_path: pathlib.Path,
    console: rich.console.Console,
    progress: ProgressType,
) -> None:
    """Git stash pop を実行

    コンフリクトが発生した場合は、状態をクリーンアップして stash を削除する。
    """
    _print = _create_printer(progress)

    try:
        result = subprocess.run(
            ["git", "stash", "pop"],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            _print("  [dim]git stash pop: 退避した変更を復元[/dim]")
        else:
            # コンフリクトが発生した場合はクリーンアップ
            combined_output = result.stdout + result.stderr
            if "CONFLICT" in combined_output or "overwritten by merge" in combined_output:
                _print("  [yellow]! stash pop でコンフリクト発生、クリーンアップ中...[/yellow]")
                # コンフリクトを解消（コミット済みの状態に戻す）
                subprocess.run(
                    ["git", "checkout", "--theirs", "."],  # noqa: S607
                    cwd=project_path,
                    capture_output=True,
                    timeout=30,
                    check=False,
                    stdin=subprocess.DEVNULL,
                )
                subprocess.run(
                    ["git", "reset", "HEAD"],  # noqa: S607
                    cwd=project_path,
                    capture_output=True,
                    timeout=30,
                    check=False,
                    stdin=subprocess.DEVNULL,
                )
                # stash を削除（pop は失敗しても stash は残る）
                subprocess.run(
                    ["git", "stash", "drop"],  # noqa: S607
                    cwd=project_path,
                    capture_output=True,
                    timeout=30,
                    check=False,
                    stdin=subprocess.DEVNULL,
                )
                _print("  [yellow]! 退避した変更は適用済みの内容と競合したため破棄されました[/yellow]")
            else:
                _print(f"  [yellow]! git stash pop failed: {result.stderr.strip()}[/yellow]")
    except subprocess.TimeoutExpired:
        _print("  [red]! git stash pop timed out[/red]")
    except FileNotFoundError:
        pass


def _parse_uv_lock_packages(content: str) -> dict[str, str]:
    """uv.lock からパッケージ名とバージョンの辞書を取得

    Args:
        content: uv.lock ファイルの内容

    Returns:
        {パッケージ名: バージョン} の辞書

    """
    packages: dict[str, str] = {}
    current_name: str | None = None

    for line in content.splitlines():
        # [[package]] セクションの name を検出
        name_match = re.match(r'^name\s*=\s*"([^"]+)"', line)
        if name_match:
            current_name = name_match.group(1)
            continue

        # version を検出
        version_match = re.match(r'^version\s*=\s*"([^"]+)"', line)
        if version_match and current_name:
            packages[current_name] = version_match.group(1)
            current_name = None

    return packages


def _get_uv_lock_changes(project_path: pathlib.Path) -> str:
    """uv.lock の変更内容を取得

    Args:
        project_path: プロジェクトのパス

    Returns:
        変更内容の文字列（例: "my-lib, selenium を更新"）

    """
    uv_lock_path = project_path / "uv.lock"
    if not uv_lock_path.exists():
        return ""

    # 現在の uv.lock を読み込み
    new_content = uv_lock_path.read_text()
    new_packages = _parse_uv_lock_packages(new_content)

    # git show で古い uv.lock を取得
    try:
        result = subprocess.run(
            ["git", "show", "HEAD:uv.lock"],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            # 新規ファイルの場合
            return ""
        old_content = result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""

    old_packages = _parse_uv_lock_packages(old_content)

    # 変更を検出
    added = [name for name, _ in new_packages.items() if name not in old_packages]
    updated = [
        name
        for name, version in new_packages.items()
        if name in old_packages and old_packages[name] != version
    ]
    removed = [name for name in old_packages if name not in new_packages]

    # メッセージを構築
    parts: list[str] = []
    if added:
        parts.append(f"{', '.join(sorted(added))} を追加")
    if updated:
        parts.append(f"{', '.join(sorted(updated))} を更新")
    if removed:
        parts.append(f"{', '.join(sorted(removed))} を削除")

    return "; ".join(parts) if parts else ""


def _generate_commit_message(files_info: list[GitCommitFile]) -> str:
    """Commit メッセージを生成

    Args:
        files_info: GitCommitFile のリスト

    Returns:
        commit メッセージ

    """
    # 1行目: 概要
    lines = ["chore: 設定ファイルを更新", ""]

    # 詳細
    for file_info in files_info:
        filename = file_info.path.name
        config_type = file_info.config_type
        message = file_info.message
        if message:
            # config_type がファイル名と異なる場合は含める（例: pyproject.toml に対する my-py-lib）
            if config_type and config_type != "uv.lock" and not filename.endswith(config_type):
                lines.append(f"- {filename}: {config_type} {message}")
            else:
                lines.append(f"- {filename}: {message}")
        else:
            lines.append(f"- {filename}: {config_type} を同期")

    lines.append("")
    lines.append("🤖 Generated with [py-project](https://github.com/kimata/py-project)")

    return "\n".join(lines)


def _run_git_commit(
    project_path: pathlib.Path,
    files_info: list[GitCommitFile],
    console: rich.console.Console,
    progress: ProgressType,
    *,
    will_push: bool = False,
) -> bool:
    """Git add & commit を実行

    Args:
        project_path: プロジェクトのパス
        files_info: GitCommitFile のリスト
        console: Rich Console インスタンス
        progress: プログレスマネージャ（オプション）
        will_push: この後 push する予定かどうか（ログメッセージ制御用）

    Returns:
        commit が成功したかどうか

    """
    max_retries = 3  # pre-commit がファイルを修正した場合のリトライ回数
    _print = _create_printer(progress)

    # 相対パスに変換
    relative_files = [
        GitCommitFile(
            path=_to_relative_path(f.path, project_path),
            config_type=f.config_type,
            message=f.message,
        )
        for f in files_info
    ]
    file_paths = [str(f.path) for f in relative_files]

    try:
        for attempt in range(max_retries):
            # git add
            add_result = subprocess.run(  # noqa: S603
                ["git", "add", *file_paths],  # noqa: S607
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                stdin=subprocess.DEVNULL,
            )
            if add_result.returncode != 0:
                _print(f"  [red]! git add failed: {add_result.stderr.strip()}[/red]")
                return False

            # commit メッセージを生成
            commit_message = _generate_commit_message(relative_files)

            # git commit
            commit_result = subprocess.run(  # noqa: S603
                ["git", "commit", "-m", commit_message],  # noqa: S607
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                stdin=subprocess.DEVNULL,
            )
            if commit_result.returncode == 0:
                # push する場合は commit のログを抑制（push のログでまとめて表示）
                if not will_push:
                    _print(f"  [green]✓ git commit: {', '.join(file_paths)}[/green]")
                return True

            # pre-commit がファイルを修正した場合、リトライ
            # "files were modified by this hook" というメッセージを検出
            combined_output = commit_result.stdout + commit_result.stderr
            if "files were modified by this hook" in combined_output:
                if attempt < max_retries - 1:
                    _print("  [dim]pre-commit がファイルを修正、再コミット中...[/dim]")
                    # 全ての変更されたファイルを add（pre-commit が修正したファイルも含む）
                    # 注: git add -u は追跡されているファイルのみを対象とするため、
                    #     新規作成されたファイルを含む元のファイルリストも再度追加する
                    subprocess.run(
                        ["git", "add", "-u"],  # noqa: S607
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                        stdin=subprocess.DEVNULL,
                    )
                    subprocess.run(  # noqa: S603
                        ["git", "add", *file_paths],  # noqa: S607
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                        stdin=subprocess.DEVNULL,
                    )
                    continue
                _print("  [red]! pre-commit によるファイル修正後もコミットに失敗[/red]")
                return False

            _print(f"  [red]! git commit failed: {commit_result.stderr.strip()}[/red]")
            return False

        return False
    except subprocess.TimeoutExpired:
        _print("  [red]! git commit timed out[/red]")
        return False
    except FileNotFoundError:
        return False  # git not installed, silently skip


def _run_git_push(
    project_path: pathlib.Path,
    files_info: list[GitCommitFile],
    console: rich.console.Console,
    progress: ProgressType,
) -> bool:
    """Git push を実行

    Args:
        project_path: プロジェクトのパス
        files_info: GitCommitFile のリスト（ログ表示用）
        console: Rich Console インスタンス
        progress: プログレスマネージャ（オプション）

    Returns:
        push が成功したかどうか

    """
    _print = _create_printer(progress)

    # 相対パスに変換
    file_paths = [str(_to_relative_path(f.path, project_path)) for f in files_info]

    try:
        push_result = subprocess.run(
            ["git", "push"],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if push_result.returncode == 0:
            _print(f"  [green]✓ git commit & push: {', '.join(file_paths)}[/green]")
            return True
        _print(f"  [red]! git push failed: {push_result.stderr.strip()}[/red]")
        return False
    except subprocess.TimeoutExpired:
        _print("  [red]! git push timed out[/red]")
        return False
    except FileNotFoundError:
        return False  # git not installed, silently skip


def _print_summary(
    console: rich.console.Console,
    summary: ApplySummary,
    *,
    dry_run: bool,
    progress: ProgressType,
) -> None:
    """サマリを表示"""
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
    elapsed = progress.get_elapsed_time()
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

    panel_content = rich.console.Group(*content_parts)

    # Panel で囲む
    panel = rich.panel.Panel(
        panel_content,
        title="[bold]📊 サマリー[/bold]",
        border_style="blue",
        padding=(1, 2),
    )

    console.print()
    console.print(panel)
