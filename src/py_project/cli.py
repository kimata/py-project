#!/usr/bin/env python3
"""
複数の Python プロジェクトに標準的な設定を一括適用します。

Usage:
  py-project [-c CONFIG] [-a] [-p PROJECT]... [-t TYPE]... [-d] [-b] [-v] [options]
  py-project [-c CONFIG] --validate
  py-project [-c CONFIG] --list-projects
  py-project --list-configs
  py-project [-c CONFIG] --update-deps [-a] [-d] [--include-projects] [--include-config] [-p PROJECT]...

Options:
  -c CONFIG, --config CONFIG    CONFIG を設定ファイルとして読み込みます。[default: config.yaml]
  -a, --apply                   実際に変更を適用します。(指定しないとドライラン)
  -p PROJECT, --project PROJECT 対象プロジェクトを限定します。(複数指定可)
  -t TYPE, --type TYPE          対象設定タイプを限定します。(複数指定可)
  -d, --diff                    差分を詳細表示します。
  -b, --backup                  適用前にバックアップを作成します。
  -v, --verbose                 詳細ログを出力します。
  --no-sync                     pyproject.toml 更新後に uv sync を実行しません。
  --git-commit                  更新したファイルを git add & commit します。
  --git-push                    更新したファイルを git add & commit & push します。
  --validate                    設定ファイルの検証のみ行います。
  --list-projects               プロジェクト一覧を表示します。
  --list-configs                設定タイプ一覧を表示します。
  --update-deps                 依存関係を最新バージョンに更新します。
  --include-projects            プロジェクトの dependencies も更新対象にします。
  --include-config              config.yaml の extra_dev_deps も更新対象にします。
"""

import logging
import pathlib
import sys

import docopt
import my_lib.config
import my_lib.cui_progress
import my_lib.logger
import rich.console
import rich.table

import py_project.applier
import py_project.config
import py_project.dep_updater
import py_project.handlers

_SCHEMA_CONFIG = "schema/config.schema"


def execute(
    config: py_project.config.Config,
    options: py_project.config.ApplyOptions,
    projects: py_project.applier.TargetList | None = None,
    config_types: py_project.applier.TargetList | None = None,
) -> int:
    """設定を適用する

    Args:
        config: アプリケーション設定
        options: 適用オプション
        projects: 対象プロジェクト名のリスト
        config_types: 対象設定タイプのリスト

    Returns:
        エラー数（0 なら成功）

    """
    console = rich.console.Console()
    progress = my_lib.cui_progress.ProgressManager(
        console=console,
        title=" 🐍 py-project ",
    )

    try:
        progress.start()

        summary = py_project.applier.apply_configs(
            config=config,
            options=options,
            projects=projects,
            config_types=config_types,
            console=console,
            progress=progress,
        )

        return summary.errors
    finally:
        progress.stop()


def show_config_types() -> None:
    """設定タイプ一覧を表示"""
    console = rich.console.Console()
    table = rich.table.Table(title="設定タイプ一覧")
    table.add_column("名前", style="cyan")
    table.add_column("説明")

    descriptions = {
        "pre-commit": "pre-commit 設定ファイル",
        "ruff": "ruff 設定ファイル",
        "yamllint": "yamllint 設定ファイル",
        "prettier": "prettier 設定ファイル",
        "python-version": ".python-version ファイル",
        "dockerignore": ".dockerignore ファイル",
        "gitignore": ".gitignore ファイル",
        "renovate": "renovate 設定ファイル",
        "pyproject": "pyproject.toml 共通セクション",
        "my-py-lib": "my-py-lib 依存関係の更新",
    }

    for name in py_project.handlers.HANDLERS:
        table.add_row(name, descriptions.get(name, ""))

    console.print(table)


def show_projects(config: py_project.config.Config) -> None:
    """プロジェクト一覧を表示"""
    console = rich.console.Console()
    table = rich.table.Table(title="プロジェクト一覧")
    table.add_column("名前", style="cyan")
    table.add_column("パス")
    table.add_column("設定タイプ")

    for proj in config.projects:
        # 適用ロジックと同じ解決方法（defaults + 追加 - 除外）で表示する
        configs = py_project.applier.get_project_configs(proj, config.defaults)
        configs_str = ", ".join(configs) if configs else "(なし)"

        table.add_row(proj.name, proj.path, configs_str)

    console.print(table)


def main() -> None:
    """CLI エントリポイント"""
    if __doc__ is None:
        raise RuntimeError("__doc__ is not set")

    args = docopt.docopt(__doc__)

    config_file: str = args["--config"]
    apply_mode: bool = args["--apply"]
    projects: list[str] | None = args["--project"] if args["--project"] else None
    config_types: list[str] | None = args["--type"] if args["--type"] else None
    show_diff: bool = args["--diff"]
    backup: bool = args["--backup"]
    verbose: bool = args["--verbose"]
    no_sync: bool = args["--no-sync"]
    git_commit_flag: bool = args["--git-commit"]
    git_push_flag: bool = args["--git-push"]
    validate_only: bool = args["--validate"]
    list_projects_flag: bool = args["--list-projects"]
    list_configs_flag: bool = args["--list-configs"]
    update_deps_flag: bool = args["--update-deps"]
    include_projects_flag: bool = args["--include-projects"]
    include_config_flag: bool = args["--include-config"]

    log_level = logging.DEBUG if verbose else logging.INFO
    my_lib.logger.init("py-project", level=log_level)

    console = rich.console.Console()

    # 設定タイプ一覧表示
    if list_configs_flag:
        show_config_types()
        sys.exit(0)

    # 設定ファイル読み込み
    try:
        config_dict = my_lib.config.load(config_file, pathlib.Path(_SCHEMA_CONFIG))
    except my_lib.config.ConfigFileNotFoundError as e:
        console.print(f"[red]設定ファイルが見つかりません: {e}[/red]")
        sys.exit(1)
    except my_lib.config.ConfigParseError as e:
        console.print(f"[red]設定ファイルの形式が不正です:[/red]\n{e.details}")
        sys.exit(1)
    except my_lib.config.ConfigValidationError as e:
        console.print(f"[red]設定ファイルの検証に失敗しました:[/red]\n{e.details}")
        sys.exit(1)

    # 検証のみ
    if validate_only:
        console.print("[green]設定ファイルは正常です[/green]")
        sys.exit(0)

    # dict を Config オブジェクトに変換
    config = py_project.config.Config.from_dict(config_dict)

    # プロジェクト一覧表示
    if list_projects_flag:
        show_projects(config)
        sys.exit(0)

    # 依存関係更新
    if update_deps_flag:
        results: list[py_project.dep_updater.FileUpdateResult] = []

        # -p が指定された場合はプロジェクトのみ（テンプレートは更新しない）
        update_template = projects is None

        # テンプレートの dependency-groups.dev を更新
        if update_template:
            template_dir = config.get_template_dir()
            template_path = template_dir / "pyproject" / "sections.toml"
            console.print("[bold]━━━ テンプレート (sections.toml) ━━━[/bold]")
            py_project.dep_updater.update_template_deps(
                template_path=template_path,
                dry_run=not apply_mode,
                console=console,
            )

        # プロジェクトの dependencies を更新
        if include_projects_flag or projects is not None:
            target_projects = [p for p in config.projects if projects is None or p.name in projects]

            for proj in target_projects:
                result = py_project.dep_updater.update_project_deps(
                    project=proj,
                    dry_run=not apply_mode,
                    console=console,
                )
                if result is not None:
                    results.append(result)

        # config.yaml の extra_dev_deps を更新
        if include_config_flag:
            console.print("\n[bold]━━━ 設定ファイル (config.yaml) ━━━[/bold]")
            result = py_project.dep_updater.update_config_deps(
                config_path=pathlib.Path(config_file),
                projects=projects,
                dry_run=not apply_mode,
                console=console,
            )
            if result is not None:
                results.append(result)

        # 差分表示
        if show_diff and results:
            console.print("\n[bold]━━━ 差分 ━━━[/bold]\n")
            for result in results:
                diff_text = py_project.dep_updater.format_diff(result)
                console.print(diff_text)
                console.print()

        # サマリー
        console.print()
        if not apply_mode:
            total_updates = sum(sum(1 for u in r.updates if u.updated) for r in results)
            if total_updates > 0:
                console.print(f"[yellow]🔍 合計 {total_updates} 個の依存関係が更新可能です[/yellow]")
                console.print("[dim]--apply を指定すると実際に更新されます[/dim]")

        sys.exit(0)

    # 設定適用
    options = py_project.config.ApplyOptions(
        dry_run=not apply_mode,
        backup=backup,
        show_diff=show_diff,
        run_sync=not no_sync,
        git_commit=git_commit_flag,
        git_push=git_push_flag,
    )
    ret_code = execute(
        config=config,
        options=options,
        projects=projects,
        config_types=config_types,
    )

    sys.exit(ret_code)


if __name__ == "__main__":
    main()
