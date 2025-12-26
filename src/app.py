#!/usr/bin/env python3
"""
複数の Python プロジェクトに標準的な設定を一括適用します。

Usage:
  app.py [-c CONFIG] [-a] [-p PROJECT]... [-t CONFIG_TYPE]... [-d] [-b] [-v] [--no-sync]
  app.py [-c CONFIG] --validate
  app.py [-c CONFIG] --list-projects
  app.py --list-configs

Options:
  -c CONFIG, --config CONFIG    CONFIG を設定ファイルとして読み込みます。[default: config.yaml]
  -a, --apply                   実際に変更を適用します。(指定しないとドライラン)
  -p PROJECT, --project PROJECT 対象プロジェクトを限定します。(複数指定可)
  -t TYPE, --type TYPE          対象設定タイプを限定します。(複数指定可)
  -d, --diff                    差分を詳細表示します。
  -b, --backup                  適用前にバックアップを作成します。
  -v, --verbose                 詳細ログを出力します。
  --no-sync                     pyproject.toml 更新後に uv sync を実行しません。
  --validate                    設定ファイルの検証のみ行います。
  --list-projects               プロジェクト一覧を表示します。
  --list-configs                設定タイプ一覧を表示します。
"""

from __future__ import annotations

import logging
import pathlib
import sys
import typing

import my_lib.config
import my_lib.logger
import rich.console
import rich.table

import py_project.applier
import py_project.handlers

SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "schema" / "config.schema.json"


def execute(
    config: dict[str, typing.Any],
    projects: list[str] | None = None,
    config_types: list[str] | None = None,
    dry_run: bool = True,
    backup: bool = False,
    show_diff: bool = False,
    run_sync: bool = True,
) -> int:
    console = rich.console.Console()

    summary = py_project.applier.apply_configs(
        config=config,
        projects=projects,
        config_types=config_types,
        dry_run=dry_run,
        backup=backup,
        show_diff=show_diff,
        run_sync=run_sync,
        console=console,
    )

    return summary.errors


def show_config_types() -> None:
    """設定タイプ一覧を表示"""
    console = rich.console.Console()
    table = rich.table.Table(title="Available Config Types")
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

    for name in py_project.handlers.HANDLERS:
        table.add_row(name, descriptions.get(name, ""))

    console.print(table)


def show_projects(config: dict[str, typing.Any]) -> None:
    """プロジェクト一覧を表示"""
    console = rich.console.Console()
    table = rich.table.Table(title="Configured Projects")
    table.add_column("Name", style="cyan")
    table.add_column("Path")
    table.add_column("Configs")

    defaults = config.get("defaults", {})
    default_configs = defaults.get("configs", [])

    for proj in config.get("projects", []):
        name = proj["name"]
        path = proj["path"]
        configs = proj.get("configs", default_configs)
        configs_str = ", ".join(configs) if configs else "(defaults)"

        table.add_row(name, path, configs_str)

    console.print(table)


######################################################################
if __name__ == "__main__":
    import docopt

    args = docopt.docopt(__doc__)

    config_file: str = args["--config"]
    apply_mode: bool = args["--apply"]
    projects: list[str] | None = args["--project"] if args["--project"] else None
    config_types: list[str] | None = args["--type"] if args["--type"] else None
    show_diff: bool = args["--diff"]
    backup: bool = args["--backup"]
    verbose: bool = args["--verbose"]
    no_sync: bool = args["--no-sync"]
    validate_only: bool = args["--validate"]
    list_projects_flag: bool = args["--list-projects"]
    list_configs_flag: bool = args["--list-configs"]

    log_level = logging.DEBUG if verbose else logging.INFO
    my_lib.logger.init("py-project", level=log_level)

    console = rich.console.Console()

    # 設定タイプ一覧表示
    if list_configs_flag:
        show_config_types()
        sys.exit(0)

    # 設定ファイル読み込み
    try:
        config = my_lib.config.load(config_file, str(SCHEMA_PATH))
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

    # プロジェクト一覧表示
    if list_projects_flag:
        show_projects(config)
        sys.exit(0)

    # 設定適用
    ret_code = execute(
        config=config,
        projects=projects,
        config_types=config_types,
        dry_run=not apply_mode,
        backup=backup,
        show_diff=show_diff,
        run_sync=not no_sync,
    )

    sys.exit(ret_code)
