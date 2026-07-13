"""Dockerfile を世代テンプレートから生成するハンドラ"""

import pathlib

import py_project.config
import py_project.handlers.base as handlers_base
import py_project.handlers.template_copy as template_copy


class DockerfileHandler(template_copy.TemplateCopyHandler):
    """Dockerfile 生成ハンドラ

    project.docker.template（standard / supervisor / hardware）で
    テンプレートを選択する（LicenseHandler と同じタイプ別選択方式）。
    template が未設定のプロジェクトは SKIPPED になる。
    """

    template_subdir = "docker"
    template_file = "standard.j2"  # デフォルト（get_template_path でオーバーライド）
    output_file = "Dockerfile"
    format_type = handlers_base.FormatType.TEXT

    @property
    def name(self) -> str:
        return "dockerfile"

    def get_template_path(
        self, project: py_project.config.Project, context: handlers_base.ApplyContext
    ) -> pathlib.Path:
        """テンプレートファイルのパスを取得（docker.template で選択）"""
        if self.name in project.template_overrides:
            return py_project.config.expand_user_path(project.template_overrides[self.name])

        return context.template_dir / self.template_subdir / f"{project.docker.template}.j2"

    def apply(
        self, project: py_project.config.Project, context: handlers_base.ApplyContext
    ) -> handlers_base.ApplyResult:
        if not project.docker.template:
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.SKIPPED,
                message="docker.template が未設定",
            )
        return super().apply(project, context)

    def diff(self, project: py_project.config.Project, context: handlers_base.ApplyContext) -> str | None:
        if not project.docker.template:
            return None
        return super().diff(project, context)
