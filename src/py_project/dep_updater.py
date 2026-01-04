"""依存関係バージョン更新ロジック"""

import dataclasses
import json
import pathlib
import re
import urllib.request

import rich.console
import rich.table
import tomlkit


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
