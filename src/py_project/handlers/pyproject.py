"""pyproject.toml 共通設定ハンドラ"""

import difflib
import logging
import pathlib
import typing

import tomlkit

import py_project.handlers.base as handlers_base

logger = logging.getLogger(__name__)

# プロジェクト固有のフィールド（常に保持）
PRESERVE_FIELDS = {
    "project": ["name", "version", "description", "dependencies"],
}

# プロジェクト固有のセクション（常に保持）
PRESERVE_SECTIONS = [
    "tool.hatch.build.targets.wheel",
    "tool.mypy.packages",
    "tool.mypy.overrides",
]


def _normalize_toml(content: str) -> str:
    """TOML 内容を正規化（空行の重複を除去）"""
    import re

    # 3つ以上の連続した空行を2つに正規化
    content = re.sub(r"\n{3,}", "\n\n", content)
    # 末尾の空白を除去
    content = content.rstrip() + "\n"
    return content


class PyprojectHandler(handlers_base.ConfigHandler):
    """pyproject.toml 共通設定ハンドラ"""

    @property
    def name(self) -> str:
        return "pyproject"

    def get_template_path(self, context: handlers_base.ApplyContext) -> pathlib.Path:
        """テンプレートファイルのパスを取得"""
        return context.template_dir / "pyproject" / "sections.toml"

    def get_output_path(self, project: dict[str, typing.Any]) -> pathlib.Path:
        """出力ファイルのパスを取得"""
        return self.get_project_path(project) / "pyproject.toml"

    def load_toml(self, path: pathlib.Path) -> tomlkit.TOMLDocument:
        """TOML ファイルを読み込み"""
        return tomlkit.parse(path.read_text())

    def get_nested_value(self, doc: tomlkit.TOMLDocument, key_path: str) -> typing.Any:
        """ドット区切りのキーパスで値を取得"""
        keys = key_path.split(".")
        current = doc
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def set_nested_value(
        self, doc: tomlkit.TOMLDocument, key_path: str, value: typing.Any
    ) -> None:
        """ドット区切りのキーパスで値を設定"""
        keys = key_path.split(".")
        current = doc
        for key in keys[:-1]:
            if key not in current:
                current[key] = tomlkit.table()
            current = current[key]
        current[keys[-1]] = value

    def delete_nested_key(self, doc: tomlkit.TOMLDocument, key_path: str) -> bool:
        """ドット区切りのキーパスでキーを削除"""
        keys = key_path.split(".")
        current = doc
        for key in keys[:-1]:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return False
        if keys[-1] in current:
            del current[keys[-1]]
            return True
        return False

    def merge_pyproject(
        self,
        current: tomlkit.TOMLDocument,
        template: tomlkit.TOMLDocument,
        project: dict[str, typing.Any],
    ) -> tomlkit.TOMLDocument:
        """pyproject.toml をマージ

        元のファイルをベースにして、テンプレートの内容で共通セクションを上書きする。
        プロジェクト固有のフィールドは保持される。
        """
        # プロジェクト設定からオプションを取得
        pyproject_opts = project.get("pyproject", {})
        extra_preserve = pyproject_opts.get("preserve_sections", [])
        extra_dev_deps = pyproject_opts.get("extra_dev_deps", [])

        # 保持するセクションのリスト
        preserve_sections = PRESERVE_SECTIONS + extra_preserve

        # 元のファイルをベースにコピー
        result = tomlkit.parse(tomlkit.dumps(current))

        # テンプレートの各セクションを処理
        self._merge_section(result, template, "project", PRESERVE_FIELDS.get("project", []))
        self._merge_section(result, template, "dependency-groups", [])
        self._merge_section(result, template, "build-system", [])

        # tool セクションの各サブセクションを処理
        if "tool" in template:
            if "tool" not in result:
                result["tool"] = tomlkit.table()
            for tool_key in template["tool"]:
                tool_path = f"tool.{tool_key}"
                # 保持するセクションはスキップ
                if any(tool_path == ps or tool_path.startswith(ps + ".") for ps in preserve_sections):
                    continue
                # サブセクションをマージ
                if tool_key in result["tool"]:
                    # 既存のサブセクションを更新
                    preserve_sub = []
                    if tool_key == "hatch":
                        preserve_sub = ["build"]  # tool.hatch.build は保持
                    elif tool_key == "mypy":
                        preserve_sub = ["packages", "overrides"]
                    self._merge_section(result["tool"], template["tool"], tool_key, preserve_sub)
                else:
                    result["tool"][tool_key] = template["tool"][tool_key]

        # 追加の開発依存をマージ
        if extra_dev_deps:
            dev_deps = self.get_nested_value(result, "dependency-groups.dev")
            if dev_deps is not None:
                for dep in extra_dev_deps:
                    if dep not in dev_deps:
                        dev_deps.append(dep)

        return result

    def _merge_section(
        self,
        result: tomlkit.TOMLDocument | dict,
        template: tomlkit.TOMLDocument | dict,
        section: str,
        preserve_fields: list[str],
    ) -> None:
        """セクションをマージ"""
        if section not in template:
            return

        if section not in result:
            result[section] = template[section]
            return

        # 保持するフィールドを保存
        preserved = {}
        for field in preserve_fields:
            if field in result[section]:
                preserved[field] = result[section][field]

        # テンプレートの内容で更新
        for key in template[section]:
            if key not in preserve_fields:
                result[section][key] = template[section][key]

        # 保持したフィールドを復元
        for field, value in preserved.items():
            result[section][field] = value

    def generate_merged_content(
        self, project: dict[str, typing.Any], context: handlers_base.ApplyContext
    ) -> str | None:
        """マージされた内容を生成"""
        template_path = self.get_template_path(context)
        output_path = self.get_output_path(project)

        if not template_path.exists():
            return None

        if not output_path.exists():
            return None

        template = self.load_toml(template_path)
        current = self.load_toml(output_path)

        merged = self.merge_pyproject(current, template, project)
        return tomlkit.dumps(merged)

    def diff(
        self, project: dict[str, typing.Any], context: handlers_base.ApplyContext
    ) -> str | None:
        """差分を取得"""
        template_path = self.get_template_path(context)
        output_path = self.get_output_path(project)

        if not template_path.exists():
            return f"テンプレートが見つかりません: {template_path}"

        if not output_path.exists():
            return f"pyproject.toml が見つかりません: {output_path}"

        new_content = self.generate_merged_content(project, context)
        if new_content is None:
            return "マージに失敗しました"

        # 正規化して比較
        new_content = _normalize_toml(new_content)
        current_content = output_path.read_text()

        if current_content == new_content:
            return None

        # 差分を生成
        diff = difflib.unified_diff(
            current_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile="a/pyproject.toml",
            tofile="b/pyproject.toml",
        )
        return "".join(diff)

    def apply(
        self, project: dict[str, typing.Any], context: handlers_base.ApplyContext
    ) -> handlers_base.ApplyResult:
        """設定を適用"""
        template_path = self.get_template_path(context)
        output_path = self.get_output_path(project)

        if not template_path.exists():
            return handlers_base.ApplyResult(
                status="error",
                message=f"テンプレートが見つかりません: {template_path}",
            )

        if not output_path.exists():
            return handlers_base.ApplyResult(
                status="skipped",
                message=f"pyproject.toml が見つかりません: {output_path}",
            )

        new_content = self.generate_merged_content(project, context)
        if new_content is None:
            return handlers_base.ApplyResult(status="error", message="マージに失敗しました")

        # 正規化して比較
        new_content = _normalize_toml(new_content)
        current_content = output_path.read_text()

        if current_content == new_content:
            return handlers_base.ApplyResult(status="unchanged")

        if context.dry_run:
            return handlers_base.ApplyResult(status="updated")

        # バックアップ作成
        if context.backup:
            self.create_backup(output_path)

        # ファイル書き込み
        output_path.write_text(new_content)
        logger.debug("pyproject.toml を更新しました: %s", output_path)

        return handlers_base.ApplyResult(status="updated")
