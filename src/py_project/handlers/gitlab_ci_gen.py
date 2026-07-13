""".gitlab-ci.yml を系統テンプレートから生成するハンドラ"""

import pathlib

import py_project.config
import py_project.handlers.base as handlers_base
import py_project.handlers.template_copy as template_copy


class GitLabCIGenHandler(template_copy.TemplateCopyHandler):
    """.gitlab-ci.yml 生成ハンドラ

    project.ci.template で系統テンプレート（例: fleama）を選択する。
    従来の gitlab-ci ハンドラ（image タグの部分編集）とは異なり、
    ファイル全体をテンプレートから生成する。このハンドラを使う
    プロジェクトは exclude_configs で gitlab-ci を除外すること。

    template が未設定のプロジェクトは SKIPPED になる。
    """

    template_subdir = "gitlab-ci"
    template_file = "fleama.yml.j2"  # デフォルト（get_template_path でオーバーライド）
    output_file = ".gitlab-ci.yml"
    format_type = handlers_base.FormatType.YAML

    @property
    def name(self) -> str:
        return "gitlab-ci-gen"

    def get_template_path(
        self, project: py_project.config.Project, context: handlers_base.ApplyContext
    ) -> pathlib.Path:
        """テンプレートファイルのパスを取得（ci.template で選択）"""
        if self.name in project.template_overrides:
            return py_project.config.expand_user_path(project.template_overrides[self.name])

        return context.template_dir / self.template_subdir / f"{project.ci.template}.yml.j2"

    def apply(
        self, project: py_project.config.Project, context: handlers_base.ApplyContext
    ) -> handlers_base.ApplyResult:
        if not project.ci.template:
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.SKIPPED,
                message="ci.template が未設定",
            )
        return super().apply(project, context)

    def diff(self, project: py_project.config.Project, context: handlers_base.ApplyContext) -> str | None:
        if not project.ci.template:
            return None
        return super().diff(project, context)
