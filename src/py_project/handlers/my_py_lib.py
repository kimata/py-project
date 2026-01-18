"""my-py-lib 依存関係更新ハンドラ"""

import dataclasses
import logging
import pathlib
import re
import subprocess

import py_project.config
import py_project.handlers.base as handlers_base


@dataclasses.dataclass
class MyPyLibDependencyMatch:
    """my-py-lib 依存関係の検索結果"""

    hash: str | None
    start: int | None
    end: int | None


logger = logging.getLogger(__name__)

_MY_PY_LIB_REPO = "https://github.com/kimata/my-py-lib"
_MY_PY_LIB_PATTERN = re.compile(r"my-lib\s*@\s*git\+https://github\.com/kimata/my-py-lib(?:@([a-f0-9]+))?")


class MyPyLibHandler(handlers_base.ConfigHandler):
    """my-py-lib 依存関係更新ハンドラ"""

    @property
    def name(self) -> str:
        return "my-py-lib"

    def get_output_path(self, project: py_project.config.Project) -> pathlib.Path:
        """出力ファイルのパスを取得"""
        return self.get_project_path(project) / "pyproject.toml"

    def get_latest_commit_hash(self) -> str | None:
        """my-py-lib の最新コミットハッシュを取得"""
        try:
            result = subprocess.run(  # noqa: S603
                ["git", "ls-remote", _MY_PY_LIB_REPO, "HEAD"],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            # 出力形式: "hash\tHEAD"
            parts = result.stdout.split()
            if not parts:
                logger.warning("my-py-lib の最新コミットハッシュ取得に失敗: 出力が空です")
                return None
            commit_hash = parts[0]
            # ハッシュの形式を検証（40文字の16進数）
            if not commit_hash or len(commit_hash) != 40:
                logger.warning("my-py-lib ハッシュ取得失敗: 不正な形式: %s", commit_hash)
                return None
            return commit_hash
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, IndexError) as e:
            logger.warning("my-py-lib の最新コミットハッシュ取得に失敗: %s", e)
            return None

    def find_my_py_lib_dependency(self, content: str) -> MyPyLibDependencyMatch:
        """my-py-lib の依存関係を検索"""
        match = _MY_PY_LIB_PATTERN.search(content)
        if match:
            return MyPyLibDependencyMatch(
                hash=match.group(1),
                start=match.start(),
                end=match.end(),
            )
        return MyPyLibDependencyMatch(hash=None, start=None, end=None)

    def update_dependency(self, content: str, new_hash: str) -> str:
        """依存関係を更新した内容を返す"""
        new_dep = f"my-lib @ git+https://github.com/kimata/my-py-lib@{new_hash}"
        return _MY_PY_LIB_PATTERN.sub(new_dep, content)

    def diff(self, project: py_project.config.Project, context: handlers_base.ApplyContext) -> str | None:
        """差分を取得"""
        output_path = self.get_output_path(project)

        if not output_path.exists():
            return f"pyproject.toml が見つかりません: {output_path}"

        content = output_path.read_text()
        dep_match = self.find_my_py_lib_dependency(content)

        if dep_match.hash is None:
            return "my-py-lib の依存関係が見つかりません"

        latest_hash = self.get_latest_commit_hash()
        if latest_hash is None:
            return "最新コミットハッシュの取得に失敗"

        if dep_match.hash == latest_hash:
            return None

        new_content = self.update_dependency(content, latest_hash)

        return self.generate_diff(content, new_content, "pyproject.toml")

    def apply(
        self, project: py_project.config.Project, context: handlers_base.ApplyContext
    ) -> handlers_base.ApplyResult:
        """設定を適用"""
        output_path = self.get_output_path(project)

        if not output_path.exists():
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.SKIPPED,
                message=f"pyproject.toml が見つかりません: {output_path}",
            )

        content = output_path.read_text()
        dep_match = self.find_my_py_lib_dependency(content)

        if dep_match.hash is None:
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.SKIPPED,
                message="my-py-lib の依存関係が見つかりません",
            )

        latest_hash = self.get_latest_commit_hash()
        if latest_hash is None:
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.ERROR,
                message="最新コミットハッシュの取得に失敗",
            )

        if dep_match.hash == latest_hash:
            return handlers_base.ApplyResult(status=handlers_base.ApplyStatus.UNCHANGED)

        if context.dry_run:
            return handlers_base.ApplyResult(
                status=handlers_base.ApplyStatus.UPDATED,
                message=f"{dep_match.hash[:8]} -> {latest_hash[:8]}",
            )

        # バックアップ作成
        if context.backup:
            self.create_backup(output_path)

        # ファイル更新
        new_content = self.update_dependency(content, latest_hash)
        output_path.write_text(new_content)
        logger.debug(
            "my-py-lib を更新しました: %s (%s -> %s)",
            output_path,
            dep_match.hash[:8],
            latest_hash[:8],
        )

        return handlers_base.ApplyResult(
            status=handlers_base.ApplyStatus.UPDATED,
            message=f"{dep_match.hash[:8]} -> {latest_hash[:8]}",
        )
