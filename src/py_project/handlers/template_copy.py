"""テンプレートファイルをコピーするハンドラ"""

import logging
import pathlib

import jinja2

import py_project.config
import py_project.handlers.base as handlers_base

logger = logging.getLogger(__name__)


class TemplateCopyHandler(handlers_base.ConfigHandler):
    """テンプレートファイルをコピーするハンドラの基底クラス"""

    # サブクラスでオーバーライド
    template_subdir: str = ""  # テンプレートのサブディレクトリ
    template_file: str = ""  # テンプレートファイル名
    output_file: str = ""  # 出力ファイル名
    format_type: handlers_base.FormatType = handlers_base.FormatType.TEXT  # 書式タイプ

    @property
    def name(self) -> str:
        return self.template_subdir

    def get_template_path(
        self, project: py_project.config.Project, context: handlers_base.ApplyContext
    ) -> pathlib.Path:
        """テンプレートファイルのパスを取得"""
        # template_overrides でオーバーライドされているかチェック
        if self.name in project.template_overrides:
            return py_project.config.expand_user_path(project.template_overrides[self.name])

        return context.template_dir / self.template_subdir / self.template_file

    def get_output_path(self, project: py_project.config.Project) -> pathlib.Path:
        """出力ファイルのパスを取得"""
        return self.get_project_path(project) / self.output_file

    def render_template(self, project: py_project.config.Project, context: handlers_base.ApplyContext) -> str:
        """テンプレートをレンダリング"""
        template_path = self.get_template_path(project, context)

        # Jinja2 環境を設定（テキストファイル生成なので autoescape 不要）
        env = jinja2.Environment(  # noqa: S701
            loader=jinja2.FileSystemLoader(template_path.parent),
            keep_trailing_newline=True,
        )
        template = env.get_template(template_path.name)

        # テンプレート変数を構築
        defaults = context.config.defaults
        template_vars = project.vars

        return template.render(
            project=project,
            defaults=defaults,
            vars=template_vars,
        )

    def diff(self, project: py_project.config.Project, context: handlers_base.ApplyContext) -> str | None:
        """差分を取得"""
        template_path = self.get_template_path(project, context)
        output_path = self.get_output_path(project)

        if not template_path.exists():
            return f"テンプレートが見つかりません: {template_path}"

        new_content = self.render_template(project, context)

        if not output_path.exists():
            return f"新規作成: {output_path.name}"

        current_content = output_path.read_text()

        return self.generate_diff(current_content, new_content, output_path.name)

    def apply(
        self, project: py_project.config.Project, context: handlers_base.ApplyContext
    ) -> handlers_base.ApplyResult:
        """設定を適用"""
        template_path = self.get_template_path(project, context)
        output_path = self.get_output_path(project)

        if not template_path.exists():
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.ERROR,
                message=f"テンプレートが見つかりません: {template_path}",
            )

        new_content = self.render_template(project, context)

        # バリデーション
        validation = self.validate(new_content)
        if not validation.is_valid:
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.ERROR,
                message=f"バリデーション失敗: {validation.error_message}",
            )

        is_new = not output_path.exists()

        if not is_new:
            current_content = output_path.read_text()
            if current_content == new_content:
                return handlers_base.ApplyResult(status=handlers_base.ApplyStatus.UNCHANGED)

        if context.dry_run:
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.CREATED if is_new else handlers_base.ApplyStatus.UPDATED
            )

        # バックアップ作成
        if context.backup and not is_new:
            self.create_backup(output_path)

        # ファイル書き込み
        output_path.write_text(new_content)
        logger.debug("%s を%sしました: %s", self.name, "作成" if is_new else "更新", output_path)

        return handlers_base.ApplyResult(
            status=handlers_base.ApplyStatus.CREATED if is_new else handlers_base.ApplyStatus.UPDATED
        )


class PreCommitHandler(TemplateCopyHandler):
    """pre-commit 設定ハンドラ"""

    template_subdir = "pre-commit"
    template_file = ".pre-commit-config.yaml"
    output_file = ".pre-commit-config.yaml"
    format_type = handlers_base.FormatType.YAML


class RuffHandler(TemplateCopyHandler):
    """ruff 設定ハンドラ"""

    template_subdir = "ruff"
    template_file = ".ruff.toml"
    output_file = ".ruff.toml"
    format_type = handlers_base.FormatType.TOML


class YamllintHandler(TemplateCopyHandler):
    """yamllint 設定ハンドラ"""

    template_subdir = "yamllint"
    template_file = ".yamllint.yaml"
    output_file = ".yamllint.yaml"
    format_type = handlers_base.FormatType.YAML


class PrettierHandler(TemplateCopyHandler):
    """prettier 設定ハンドラ"""

    template_subdir = "prettier"
    template_file = ".prettierrc"
    output_file = ".prettierrc"
    format_type = handlers_base.FormatType.JSON


class PythonVersionHandler(TemplateCopyHandler):
    """python-version 設定ハンドラ"""

    template_subdir = "python-version"
    template_file = ".python-version"
    output_file = ".python-version"


class IgnoreFileHandler(TemplateCopyHandler):
    """ignore ファイル系ハンドラの基底クラス（extra_lines 機能付き）"""

    # サブクラスでオーバーライド：プロジェクトのオプション属性名
    options_attr: str = ""

    def render_template(self, project: py_project.config.Project, context: handlers_base.ApplyContext) -> str:
        """テンプレートをレンダリングし、extra_lines を追加"""
        content = super().render_template(project, context)

        # extra_lines がある場合は末尾に追加
        options = getattr(project, self.options_attr)
        if options.extra_lines:
            extra = "\n".join(options.extra_lines)
            content = content.rstrip("\n") + "\n" + extra + "\n"

        return content


class DockerignoreHandler(IgnoreFileHandler):
    """dockerignore 設定ハンドラ"""

    template_subdir = "dockerignore"
    template_file = ".dockerignore"
    output_file = ".dockerignore"
    options_attr = "dockerignore"


class GitignoreHandler(IgnoreFileHandler):
    """gitignore 設定ハンドラ"""

    template_subdir = "gitignore"
    template_file = ".gitignore"
    output_file = ".gitignore"
    options_attr = "gitignore"


class RenovateHandler(TemplateCopyHandler):
    """renovate 設定ハンドラ"""

    template_subdir = "renovate"
    template_file = "renovate.json"
    output_file = "renovate.json"
    format_type = handlers_base.FormatType.JSON


class LicenseHandler(TemplateCopyHandler):
    """license 設定ハンドラ

    プロジェクトごとに異なるライセンスタイプを選択可能。
    テンプレートファイル名はライセンスタイプ名（例: Apache-2.0, MIT）。
    """

    template_subdir = "license"
    template_file = "Apache-2.0"  # デフォルト（get_template_path でオーバーライド）
    output_file = "LICENSE"

    def get_template_path(
        self, project: py_project.config.Project, context: handlers_base.ApplyContext
    ) -> pathlib.Path:
        """テンプレートファイルのパスを取得

        プロジェクトの license.type オプションに応じてテンプレートを選択。
        """
        # template_overrides でオーバーライドされている場合はそちらを優先
        if self.name in project.template_overrides:
            return py_project.config.expand_user_path(project.template_overrides[self.name])

        license_type = project.license.type
        return context.template_dir / self.template_subdir / license_type
