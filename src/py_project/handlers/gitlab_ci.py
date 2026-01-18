"""GitLab CI 設定ハンドラ（yamlpath + 文字列置換方式）"""

import argparse
import logging
import pathlib
import re

import jinja2
import ruamel.yaml
import yamlpath.processor
import yamlpath.wrappers

import py_project.config
import py_project.handlers.base as handlers_base

logger = logging.getLogger(__name__)


class GitLabCIHandler(handlers_base.ConfigHandler):
    """GitLab CI 設定ハンドラ

    既存の .gitlab-ci.yml を yamlpath 形式で指定した値に書き換える。
    yamlpath で行番号を特定し、文字列置換でフォーマットを完全保持。
    """

    format_type = handlers_base.FormatType.YAML

    @property
    def name(self) -> str:
        return "gitlab-ci"

    def get_output_path(self, project: py_project.config.Project) -> pathlib.Path:
        """出力ファイルのパスを取得"""
        return self.get_project_path(project) / ".gitlab-ci.yml"

    def _get_line_number(self, content: str, yaml_path: str) -> int | None:
        """指定された YAML パスの行番号を取得"""
        yaml = ruamel.yaml.YAML()
        data = yaml.load(content)

        args = argparse.Namespace(verbose=False, quiet=True, debug=False)
        log = yamlpath.wrappers.ConsolePrinter(args)
        proc = yamlpath.processor.Processor(log, data)

        for node in proc.get_nodes(yaml_path):
            # 親マッピングからキーの行番号を取得
            if hasattr(node, "parent") and hasattr(node.parent, "lc"):
                key = node.parentref
                if key is not None:
                    line, _ = node.parent.lc.key(key)
                    return line
            # トップレベルの場合
            if hasattr(data, "lc"):
                key = yaml_path.lstrip("/").split("/")[-1]
                if key in data:
                    line, _ = data.lc.key(key)
                    return line
        return None

    def _replace_value_in_line(self, line: str, new_value: str) -> str:
        """行内の値を置換（フォーマット保持）"""
        match = re.match(r"^(\s*\S+:\s*)", line)
        if match:
            return match.group(1) + new_value
        return line

    def _apply_edits(self, content: str, edits: list[py_project.config.GitlabCiEdit]) -> str:
        """編集を適用"""
        lines = content.splitlines(keepends=True)

        for edit in edits:
            line_num = self._get_line_number(content, edit.path)

            if line_num is not None:
                original_line = lines[line_num]
                newline = "\n" if original_line.endswith("\n") else ""
                new_line = self._replace_value_in_line(original_line.rstrip("\n\r"), edit.value)
                lines[line_num] = new_line + newline
            else:
                logger.warning("パス %s が見つかりません", edit.path)

        return "".join(lines)

    def _render_value(self, value: str, vars_dict: dict[str, str]) -> str:
        """Jinja2 テンプレートをレンダリング"""
        if "{{" not in value:
            return value
        template = jinja2.Template(value)
        return template.render(vars=vars_dict)

    def _get_edits(
        self, project: py_project.config.Project, context: handlers_base.ApplyContext
    ) -> list[py_project.config.GitlabCiEdit]:
        """編集リストを取得（defaults とプロジェクト設定をマージ、Jinja2 展開）"""
        defaults = context.config.defaults
        default_gitlab_ci = defaults.gitlab_ci
        project_gitlab_ci = project.gitlab_ci

        # デフォルトの edits をベースにプロジェクト固有の edits で上書き
        default_edits = {e.path: e.value for e in default_gitlab_ci.edits} if default_gitlab_ci else {}
        project_edits = {e.path: e.value for e in project_gitlab_ci.edits} if project_gitlab_ci else {}

        # マージ（プロジェクト設定が優先）
        merged = {**default_edits, **project_edits}

        # Jinja2 テンプレート展開
        vars_dict = defaults.vars
        return [
            py_project.config.GitlabCiEdit(path=k, value=self._render_value(v, vars_dict))
            for k, v in merged.items()
        ]

    def _generate_edited_content(
        self, project: py_project.config.Project, context: handlers_base.ApplyContext
    ) -> str | None:
        """編集後の内容を生成"""
        output_path = self.get_output_path(project)
        edits = self._get_edits(project, context)

        if not edits:
            return None

        content = output_path.read_text()
        return self._apply_edits(content, edits)

    def diff(self, project: py_project.config.Project, context: handlers_base.ApplyContext) -> str | None:
        """差分を取得"""
        output_path = self.get_output_path(project)

        if not output_path.exists():
            return f".gitlab-ci.yml が見つかりません: {output_path}"

        edits = self._get_edits(project, context)

        if not edits:
            return None

        new_content = self._generate_edited_content(project, context)
        if new_content is None:
            return None

        current_content = output_path.read_text()

        return self.generate_diff(current_content, new_content, ".gitlab-ci.yml")

    def apply(
        self, project: py_project.config.Project, context: handlers_base.ApplyContext
    ) -> handlers_base.ApplyResult:
        """設定を適用"""
        output_path = self.get_output_path(project)

        if not output_path.exists():
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.SKIPPED,
                message=f".gitlab-ci.yml が見つかりません: {output_path}",
            )

        edits = self._get_edits(project, context)

        if not edits:
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.SKIPPED,
                message="edits が指定されていません",
            )

        new_content = self._generate_edited_content(project, context)
        if new_content is None:
            return handlers_base.ApplyResult(status=handlers_base.ApplyStatus.UNCHANGED)

        validation = self.validate(new_content)
        if not validation.is_valid:
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.ERROR,
                message=f"バリデーション失敗: {validation.error_message}",
            )

        current_content = output_path.read_text()

        if current_content == new_content:
            return handlers_base.ApplyResult(status=handlers_base.ApplyStatus.UNCHANGED)

        if context.dry_run:
            return handlers_base.ApplyResult(status=handlers_base.ApplyStatus.UPDATED)

        if context.backup:
            self.create_backup(output_path)

        output_path.write_text(new_content)
        logger.debug(".gitlab-ci.yml を更新しました: %s", output_path)

        return handlers_base.ApplyResult(status=handlers_base.ApplyStatus.UPDATED)
