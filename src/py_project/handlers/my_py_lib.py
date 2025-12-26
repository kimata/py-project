"""my-py-lib 依存関係更新ハンドラ"""

import difflib
import logging
import pathlib
import re
import subprocess
import typing

import py_project.handlers.base as handlers_base

logger = logging.getLogger(__name__)

MY_PY_LIB_REPO = "https://github.com/kimata/my-py-lib"
MY_PY_LIB_PATTERN = re.compile(
    r'my-lib\s*@\s*git\+https://github\.com/kimata/my-py-lib(?:@([a-f0-9]+))?'
)


class MyPyLibHandler(handlers_base.ConfigHandler):
    """my-py-lib 依存関係更新ハンドラ"""

    @property
    def name(self) -> str:
        return "my-py-lib"

    def get_output_path(self, project: dict[str, typing.Any]) -> pathlib.Path:
        """出力ファイルのパスを取得"""
        return self.get_project_path(project) / "pyproject.toml"

    def get_latest_commit_hash(self) -> str | None:
        """my-py-lib の最新コミットハッシュを取得"""
        try:
            result = subprocess.run(
                ["git", "ls-remote", MY_PY_LIB_REPO, "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            # 出力形式: "hash\tHEAD"
            return result.stdout.split()[0]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, IndexError) as e:
            logger.warning("my-py-lib の最新コミットハッシュ取得に失敗: %s", e)
            return None

    def find_my_py_lib_dependency(self, content: str) -> tuple[str | None, int | None, int | None]:
        """my-py-lib の依存関係を検索

        Returns:
            (現在のハッシュ or None, 開始位置, 終了位置)
        """
        match = MY_PY_LIB_PATTERN.search(content)
        if match:
            current_hash = match.group(1)
            return current_hash, match.start(), match.end()
        return None, None, None

    def update_dependency(self, content: str, new_hash: str) -> str:
        """依存関係を更新した内容を返す"""
        new_dep = f"my-lib @ git+https://github.com/kimata/my-py-lib@{new_hash}"
        return MY_PY_LIB_PATTERN.sub(new_dep, content)

    def diff(
        self, project: dict[str, typing.Any], context: handlers_base.ApplyContext
    ) -> str | None:
        """差分を取得"""
        output_path = self.get_output_path(project)

        if not output_path.exists():
            return f"pyproject.toml が見つかりません: {output_path}"

        content = output_path.read_text()
        current_hash, _, _ = self.find_my_py_lib_dependency(content)

        if current_hash is None:
            return "my-py-lib の依存関係が見つかりません"

        latest_hash = self.get_latest_commit_hash()
        if latest_hash is None:
            return "最新コミットハッシュの取得に失敗"

        if current_hash == latest_hash:
            return None

        new_content = self.update_dependency(content, latest_hash)

        # 差分を生成
        diff = difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile="a/pyproject.toml",
            tofile="b/pyproject.toml",
        )
        return "".join(diff)

    def apply(
        self, project: dict[str, typing.Any], context: handlers_base.ApplyContext
    ) -> handlers_base.ApplyResult:
        """設定を適用"""
        output_path = self.get_output_path(project)

        if not output_path.exists():
            return handlers_base.ApplyResult(
                status="skipped",
                message=f"pyproject.toml が見つかりません: {output_path}",
            )

        content = output_path.read_text()
        current_hash, _, _ = self.find_my_py_lib_dependency(content)

        if current_hash is None:
            return handlers_base.ApplyResult(
                status="skipped",
                message="my-py-lib の依存関係が見つかりません",
            )

        latest_hash = self.get_latest_commit_hash()
        if latest_hash is None:
            return handlers_base.ApplyResult(
                status="error",
                message="最新コミットハッシュの取得に失敗",
            )

        if current_hash == latest_hash:
            return handlers_base.ApplyResult(status="unchanged")

        if context.dry_run:
            return handlers_base.ApplyResult(
                status="updated",
                message=f"{current_hash[:8]} -> {latest_hash[:8]}",
            )

        # バックアップ作成
        if context.backup:
            self.create_backup(output_path)

        # ファイル更新
        new_content = self.update_dependency(content, latest_hash)
        output_path.write_text(new_content)
        logger.info(
            "my-py-lib を更新しました: %s (%s -> %s)",
            output_path,
            current_hash[:8],
            latest_hash[:8],
        )

        return handlers_base.ApplyResult(
            status="updated",
            message=f"{current_hash[:8]} -> {latest_hash[:8]}",
        )
