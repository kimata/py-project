"""依存関係バージョン更新ロジック"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import re
import urllib.request

import rich.console
import rich.table
import ruamel.yaml
import tomlkit

import py_project.config


@dataclasses.dataclass
class DepUpdate:
    """依存関係の更新情報"""

    package: str
    current: str
    latest: str
    updated: bool = False


def _get_latest_version(package: str) -> str | None:
    """PyPI から最新バージョンを取得"""
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310
            data = json.loads(response.read().decode())
            return data["info"]["version"]
    except Exception:
        return None


def _parse_dependency(dep: str) -> tuple[str, str] | None:
    """依存関係文字列からパッケージ名とバージョンを抽出

    例: "pytest>=8.3.0" -> ("pytest", "8.3.0")
    """
    match = re.match(r"^([a-zA-Z0-9_-]+)>=([0-9.]+)$", dep)
    if match:
        return match.group(1), match.group(2)
    return None


def _format_dependency(package: str, version: str) -> str:
    """依存関係文字列を生成"""
    return f"{package}>={version}"


def _normalize_version(version: str) -> str:
    """バージョン文字列を正規化（メジャー.マイナー.パッチ形式に）

    例: "2025.2.0.20251108" -> "2025.2.0"
    """
    parts = version.split(".")
    if len(parts) >= 3:
        return ".".join(parts[:3])
    return version


def update_template_deps(
    template_path: pathlib.Path,
    *,
    dry_run: bool = True,
    console: rich.console.Console | None = None,
) -> list[DepUpdate]:
    """テンプレートファイルの依存関係を更新

    Args:
        template_path: テンプレートファイルのパス
        dry_run: ドライランモード
        console: Rich Console インスタンス

    Returns:
        更新情報のリスト

    """
    if console is None:
        console = rich.console.Console()

    if not template_path.exists():
        console.print(f"[red]テンプレートファイルが見つかりません: {template_path}[/red]")
        return []

    # TOML ファイルを読み込み
    content = template_path.read_text()
    doc = tomlkit.parse(content)

    updates: list[DepUpdate] = []

    # dependency-groups.dev を処理
    dep_groups = doc.get("dependency-groups", {})
    dev_deps = dep_groups.get("dev", [])

    if not dev_deps:
        console.print("[yellow]dependency-groups.dev が見つかりません[/yellow]")
        return []

    console.print("[bold]📦 依存関係のバージョンをチェック中...[/bold]\n")

    new_deps = []
    for dep in dev_deps:
        parsed = _parse_dependency(str(dep))
        if parsed is None:
            new_deps.append(dep)
            continue

        package, current_version = parsed
        console.print(f"  🔍 {package}...", end="")

        latest = _get_latest_version(package)
        if latest is None:
            console.print(" [yellow]取得失敗[/yellow]")
            new_deps.append(dep)
            continue

        # バージョンを正規化
        normalized_latest = _normalize_version(latest)

        if normalized_latest != current_version:
            console.print(f" [cyan]⬆️  {current_version} → {normalized_latest}[/cyan]")
            new_dep = _format_dependency(package, normalized_latest)
            new_deps.append(new_dep)
            updates.append(
                DepUpdate(
                    package=package,
                    current=current_version,
                    latest=normalized_latest,
                    updated=True,
                )
            )
        else:
            console.print(" [green]✅ 最新[/green]")
            new_deps.append(dep)
            updates.append(
                DepUpdate(
                    package=package,
                    current=current_version,
                    latest=normalized_latest,
                    updated=False,
                )
            )

    console.print()

    # 更新があった場合
    updated_count = sum(1 for u in updates if u.updated)
    if updated_count == 0:
        console.print("[green]✨ すべての依存関係が最新です[/green]")
        return updates

    # ドライランの場合
    if dry_run:
        console.print(f"[yellow]🔍 {updated_count} 個の依存関係が更新可能です[/yellow]")
        console.print("[dim]--apply を指定すると実際に更新されます[/dim]")
        return updates

    # 実際に更新（フォーマットを保持するため、tomlkit の配列を使用）
    new_array = tomlkit.array()
    new_array.multiline(True)
    for dep in new_deps:
        new_array.append(str(dep))
    doc["dependency-groups"]["dev"] = new_array  # type: ignore[index]
    template_path.write_text(tomlkit.dumps(doc))

    console.print(f"[green]✨ {updated_count} 個の依存関係を更新しました[/green]")

    return updates


@dataclasses.dataclass
class FileUpdateResult:
    """ファイル更新結果"""

    file_path: pathlib.Path
    section: str
    updates: list[DepUpdate]
    original_content: str
    new_content: str


def _check_and_update_deps(
    deps: list[str],
    console: rich.console.Console,
    *,
    silent: bool = False,
) -> tuple[list[str], list[DepUpdate]]:
    """依存関係リストをチェックして更新

    Args:
        deps: 依存関係文字列のリスト
        console: Rich Console インスタンス
        silent: 進捗表示を抑制

    Returns:
        (更新後の依存関係リスト, 更新情報リスト)

    """
    updates: list[DepUpdate] = []
    new_deps: list[str] = []

    for dep in deps:
        parsed = _parse_dependency(str(dep))
        if parsed is None:
            new_deps.append(str(dep))
            continue

        package, current_version = parsed
        if not silent:
            console.print(f"  🔍 {package}...", end="")

        latest = _get_latest_version(package)
        if latest is None:
            if not silent:
                console.print(" [yellow]取得失敗[/yellow]")
            new_deps.append(str(dep))
            continue

        normalized_latest = _normalize_version(latest)

        if normalized_latest != current_version:
            if not silent:
                console.print(f" [cyan]⬆️  {current_version} → {normalized_latest}[/cyan]")
            new_dep = _format_dependency(package, normalized_latest)
            new_deps.append(new_dep)
            updates.append(
                DepUpdate(
                    package=package,
                    current=current_version,
                    latest=normalized_latest,
                    updated=True,
                )
            )
        else:
            if not silent:
                console.print(" [green]✅ 最新[/green]")
            new_deps.append(str(dep))
            updates.append(
                DepUpdate(
                    package=package,
                    current=current_version,
                    latest=normalized_latest,
                    updated=False,
                )
            )

    return new_deps, updates


def update_project_deps(
    project: py_project.config.Project,
    *,
    dry_run: bool = True,
    console: rich.console.Console | None = None,
) -> FileUpdateResult | None:
    """プロジェクトの pyproject.toml の dependencies を更新

    Args:
        project: プロジェクト設定
        dry_run: ドライランモード
        console: Rich Console インスタンス

    Returns:
        更新結果（更新なしの場合は None）

    """
    if console is None:
        console = rich.console.Console()

    pyproject_path = pathlib.Path(project.path).expanduser() / "pyproject.toml"

    if not pyproject_path.exists():
        console.print(f"[yellow]pyproject.toml が見つかりません: {pyproject_path}[/yellow]")
        return None

    original_content = pyproject_path.read_text()
    doc = tomlkit.parse(original_content)

    project_section = doc.get("project", {})
    deps = project_section.get("dependencies", [])

    if not deps:
        return None

    console.print(f"\n[bold]📦 {project.name} の dependencies をチェック中...[/bold]\n")

    new_deps, updates = _check_and_update_deps(list(deps), console)

    updated_count = sum(1 for u in updates if u.updated)
    if updated_count == 0:
        return None

    # 新しい配列を作成
    new_array = tomlkit.array()
    new_array.multiline(True)
    for dep in new_deps:
        new_array.append(dep)
    doc["project"]["dependencies"] = new_array  # type: ignore[index]
    new_content = tomlkit.dumps(doc)

    result = FileUpdateResult(
        file_path=pyproject_path,
        section="project.dependencies",
        updates=updates,
        original_content=original_content,
        new_content=new_content,
    )

    if not dry_run:
        pyproject_path.write_text(new_content)
        console.print(f"[green]✨ {updated_count} 個の依存関係を更新しました[/green]")

    return result


def update_config_deps(
    config_path: pathlib.Path,
    projects: list[str] | None = None,
    *,
    dry_run: bool = True,
    console: rich.console.Console | None = None,
) -> FileUpdateResult | None:
    """config.yaml の extra_dev_deps を更新

    Args:
        config_path: config.yaml のパス
        projects: 対象プロジェクト名のリスト（None の場合は全て）
        dry_run: ドライランモード
        console: Rich Console インスタンス

    Returns:
        更新結果（更新なしの場合は None）

    """
    if console is None:
        console = rich.console.Console()

    if not config_path.exists():
        console.print(f"[red]設定ファイルが見つかりません: {config_path}[/red]")
        return None

    original_content = config_path.read_text()

    yaml = ruamel.yaml.YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=4, sequence=4, offset=4)

    doc = yaml.load(original_content)

    all_updates: list[DepUpdate] = []
    updated_projects: list[str] = []

    console.print("\n[bold]📦 config.yaml の extra_dev_deps をチェック中...[/bold]")

    for proj_data in doc.get("projects", []):
        proj_name = proj_data.get("name", "")

        if projects is not None and proj_name not in projects:
            continue

        pyproject_opts = proj_data.get("pyproject", {})
        if pyproject_opts is None:
            continue

        extra_deps = pyproject_opts.get("extra_dev_deps", [])
        if not extra_deps:
            continue

        console.print(f"\n[bold]  📁 {proj_name}[/bold]")

        new_deps, updates = _check_and_update_deps(list(extra_deps), console)

        updated_count = sum(1 for u in updates if u.updated)
        if updated_count > 0:
            # 更新を適用
            proj_data["pyproject"]["extra_dev_deps"] = new_deps
            all_updates.extend(updates)
            updated_projects.append(proj_name)

    if not all_updates or not any(u.updated for u in all_updates):
        console.print("\n[green]✨ すべての extra_dev_deps が最新です[/green]")
        return None

    # 新しいコンテンツを生成
    import io

    stream = io.StringIO()
    yaml.dump(doc, stream)
    new_content = stream.getvalue()

    result = FileUpdateResult(
        file_path=config_path,
        section="projects[*].pyproject.extra_dev_deps",
        updates=all_updates,
        original_content=original_content,
        new_content=new_content,
    )

    if not dry_run:
        config_path.write_text(new_content)
        total_updated = sum(1 for u in all_updates if u.updated)
        console.print(f"\n[green]✨ {total_updated} 個の依存関係を更新しました[/green]")
        console.print(f"[dim]更新対象: {', '.join(updated_projects)}[/dim]")

    return result


def format_diff(result: FileUpdateResult) -> str:
    """更新結果を差分形式でフォーマット

    Args:
        result: ファイル更新結果

    Returns:
        差分文字列

    """
    lines: list[str] = []
    lines.append(f"--- {result.file_path}")
    lines.append(f"+++ {result.file_path} (updated)")
    lines.append(f"@@ {result.section} @@")

    for update in result.updates:
        if update.updated:
            lines.append(f'-    "{update.package}>={update.current}",')
            lines.append(f'+    "{update.package}>={update.latest}",')

    return "\n".join(lines)
