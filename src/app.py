#!/usr/bin/env python3
"""
複数の Python プロジェクトに標準的な設定を一括適用します。

Usage:
  app.py [-c CONFIG] [-a] [-p PROJECT]... [-t CONFIG_TYPE]... [-d] [-b] [-v] [--no-sync] [--git-commit]
  app.py [-c CONFIG] --validate
  app.py [-c CONFIG] --list-projects
  app.py --list-configs
  app.py [-c CONFIG] --update-deps [-a]

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
  --validate                    設定ファイルの検証のみ行います。
  --list-projects               プロジェクト一覧を表示します。
  --list-configs                設定タイプ一覧を表示します。
  --update-deps                 テンプレートの依存関係を最新バージョンに更新します。
"""

from __future__ import annotations

import logging
import pathlib
import sys

import my_lib.config
import my_lib.cui_progress
import my_lib.logger
import rich.console
import rich.table

import py_project.applier
import py_project.config
import py_project.dep_updater
import py_project.handlers

_SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "schema" / "config.schema"


def execute(
    config: py_project.config.Config,
    options: py_project.config.ApplyOptions,
    projects: list[str] | None = None,
    config_types: list[str] | None = None,
) -> int:
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

    default_configs = config.defaults.configs

    for proj in config.projects:
        configs = proj.configs if proj.configs is not None else default_configs
        configs_str = ", ".join(configs) if configs else "(デフォルト)"

        table.add_row(proj.name, proj.path, configs_str)

    console.print(table)


######################################################################
if __name__ == "__main__":  # pragma: no cover
    import docopt

    args = docopt.docopt(__doc__)  # type: ignore[arg-type]

    config_file: str = args["--config"]
    apply_mode: bool = args["--apply"]
    projects: list[str] | None = args["--project"] if args["--project"] else None
    config_types: list[str] | None = args["--type"] if args["--type"] else None
    show_diff: bool = args["--diff"]
    backup: bool = args["--backup"]
    verbose: bool = args["--verbose"]
    no_sync: bool = args["--no-sync"]
    git_commit_flag: bool = args["--git-commit"]
    validate_only: bool = args["--validate"]
    list_projects_flag: bool = args["--list-projects"]
    list_configs_flag: bool = args["--list-configs"]
    update_deps_flag: bool = args["--update-deps"]

    log_level = logging.DEBUG if verbose else logging.INFO
    my_lib.logger.init("py-project", level=log_level)

    console = rich.console.Console()

    # 設定タイプ一覧表示
    if list_configs_flag:
        show_config_types()
        sys.exit(0)

    # 設定ファイル読み込み
    try:
        config_dict = my_lib.config.load(config_file, str(_SCHEMA_PATH))
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
        template_dir = config.get_template_dir()
        template_path = template_dir / "pyproject" / "sections.toml"
        py_project.dep_updater.update_template_deps(
            template_path=template_path,
            dry_run=not apply_mode,
            console=console,
        )
        sys.exit(0)

    # 設定適用
    options = py_project.config.ApplyOptions(
        dry_run=not apply_mode,
        backup=backup,
        show_diff=show_diff,
        run_sync=not no_sync,
        git_commit=git_commit_flag,
    )
    ret_code = execute(
        config=config,
        options=options,
        projects=projects,
        config_types=config_types,
    )

    sys.exit(ret_code)
