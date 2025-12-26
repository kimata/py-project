"""テンプレートファイルをコピーするハンドラ"""

import difflib
import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from .base import ApplyContext, ApplyResult, ConfigHandler

logger = logging.getLogger(__name__)


class TemplateCopyHandler(ConfigHandler):
    """テンプレートファイルをコピーするハンドラの基底クラス"""

    # サブクラスでオーバーライド
    template_subdir: str = ""  # テンプレートのサブディレクトリ
    template_file: str = ""  # テンプレートファイル名
    output_file: str = ""  # 出力ファイル名

    @property
    def name(self) -> str:
        return self.template_subdir

    def get_template_path(self, project: dict[str, Any], context: ApplyContext) -> Path:
        """テンプレートファイルのパスを取得"""
        # template_overrides でオーバーライドされているかチェック
        overrides = project.get("template_overrides", {})
        if self.name in overrides:
            return Path(overrides[self.name]).expanduser()

        return context.template_dir / self.template_subdir / self.template_file

    def get_output_path(self, project: dict[str, Any]) -> Path:
        """出力ファイルのパスを取得"""
        return self.get_project_path(project) / self.output_file

    def render_template(self, project: dict[str, Any], context: ApplyContext) -> str:
        """テンプレートをレンダリング"""
        template_path = self.get_template_path(project, context)

        # Jinja2 環境を設定
        env = Environment(
            loader=FileSystemLoader(template_path.parent),
            keep_trailing_newline=True,
        )
        template = env.get_template(template_path.name)

        # テンプレート変数を構築
        defaults = context.config.get("defaults", {})
        vars_ = project.get("vars", {})

        return template.render(
            project=project,
            defaults=defaults,
            vars=vars_,
        )

    def diff(self, project: dict[str, Any], context: ApplyContext) -> str | None:
        """差分を取得"""
        template_path = self.get_template_path(project, context)
        output_path = self.get_output_path(project)

        if not template_path.exists():
            return f"テンプレートが見つかりません: {template_path}"

        new_content = self.render_template(project, context)

        if not output_path.exists():
            return f"新規作成: {output_path.name}"

        current_content = output_path.read_text()

        if current_content == new_content:
            return None

        # 差分を生成
        diff = difflib.unified_diff(
            current_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{output_path.name}",
            tofile=f"b/{output_path.name}",
        )
        return "".join(diff)

    def apply(self, project: dict[str, Any], context: ApplyContext) -> ApplyResult:
        """設定を適用"""
        template_path = self.get_template_path(project, context)
        output_path = self.get_output_path(project)

        if not template_path.exists():
            return ApplyResult(
                status="error",
                message=f"テンプレートが見つかりません: {template_path}",
            )

        new_content = self.render_template(project, context)
        is_new = not output_path.exists()

        if not is_new:
            current_content = output_path.read_text()
            if current_content == new_content:
                return ApplyResult(status="unchanged")

        if context.dry_run:
            return ApplyResult(status="created" if is_new else "updated")

        # バックアップ作成
        if context.backup and not is_new:
            self.create_backup(output_path)

        # ファイル書き込み
        output_path.write_text(new_content)
        logger.info("%s を%sしました: %s", self.name, "作成" if is_new else "更新", output_path)

        return ApplyResult(status="created" if is_new else "updated")


class PreCommitHandler(TemplateCopyHandler):
    """pre-commit 設定ハンドラ"""

    template_subdir = "pre-commit"
    template_file = ".pre-commit-config.yaml"
    output_file = ".pre-commit-config.yaml"


class RuffHandler(TemplateCopyHandler):
    """ruff 設定ハンドラ"""

    template_subdir = "ruff"
    template_file = "ruff.toml"
    output_file = "ruff.toml"


class YamllintHandler(TemplateCopyHandler):
    """yamllint 設定ハンドラ"""

    template_subdir = "yamllint"
    template_file = ".yamllint.yaml"
    output_file = ".yamllint.yaml"


class PrettierHandler(TemplateCopyHandler):
    """prettier 設定ハンドラ"""

    template_subdir = "prettier"
    template_file = ".prettierrc"
    output_file = ".prettierrc"


class PythonVersionHandler(TemplateCopyHandler):
    """python-version 設定ハンドラ"""

    template_subdir = "python-version"
    template_file = ".python-version"
    output_file = ".python-version"


class DockerignoreHandler(TemplateCopyHandler):
    """dockerignore 設定ハンドラ"""

    template_subdir = "dockerignore"
    template_file = ".dockerignore"
    output_file = ".dockerignore"


class GitignoreHandler(TemplateCopyHandler):
    """gitignore 設定ハンドラ"""

    template_subdir = "gitignore"
    template_file = ".gitignore"
    output_file = ".gitignore"
