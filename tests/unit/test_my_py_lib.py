#!/usr/bin/env python3
# ruff: noqa: S101
"""
handlers/my_py_lib.py のテスト
"""
import textwrap

import py_project.handlers.base as handlers_base
import py_project.handlers.my_py_lib as my_py_lib_handler


class TestMyPyLibPattern:
    """MY_PY_LIB_PATTERN のテスト"""

    def test_match_with_hash(self):
        """ハッシュ付きの依存関係にマッチ"""
        content = 'my-lib @ git+https://github.com/kimata/my-py-lib@abcd1234'

        match = my_py_lib_handler.MY_PY_LIB_PATTERN.search(content)

        assert match is not None
        assert match.group(1) == "abcd1234"

    def test_match_without_hash(self):
        """ハッシュなしの依存関係にマッチ"""
        content = 'my-lib @ git+https://github.com/kimata/my-py-lib'

        match = my_py_lib_handler.MY_PY_LIB_PATTERN.search(content)

        assert match is not None
        assert match.group(1) is None

    def test_match_full_hash(self):
        """フルハッシュにマッチ"""
        content = 'my-lib @ git+https://github.com/kimata/my-py-lib@abcd1234567890abcdef1234567890abcdef1234'

        match = my_py_lib_handler.MY_PY_LIB_PATTERN.search(content)

        assert match is not None
        assert match.group(1) == "abcd1234567890abcdef1234567890abcdef1234"

    def test_no_match(self):
        """マッチしない場合"""
        content = 'requests @ https://example.com/requests'

        match = my_py_lib_handler.MY_PY_LIB_PATTERN.search(content)

        assert match is None


class TestMyPyLibHandler:
    """MyPyLibHandler のテスト"""

    def test_find_my_py_lib_dependency(self, tmp_project_with_my_lib):
        """依存関係を検索"""
        handler = my_py_lib_handler.MyPyLibHandler()
        content = (tmp_project_with_my_lib / "pyproject.toml").read_text()

        current_hash, start, end = handler.find_my_py_lib_dependency(content)

        assert current_hash == "abcd1234567890abcdef1234567890abcdef1234"
        assert start is not None
        assert end is not None

    def test_find_my_py_lib_dependency_not_found(self, tmp_project):
        """依存関係が見つからない場合"""
        handler = my_py_lib_handler.MyPyLibHandler()
        content = (tmp_project / "pyproject.toml").read_text()

        current_hash, start, end = handler.find_my_py_lib_dependency(content)

        assert current_hash is None
        assert start is None
        assert end is None

    def test_update_dependency(self):
        """依存関係を更新"""
        handler = my_py_lib_handler.MyPyLibHandler()
        content = textwrap.dedent("""\
            [project]
            dependencies = [
                "my-lib @ git+https://github.com/kimata/my-py-lib@abcd1234",
            ]
        """)
        new_hash = "ef567890"

        result = handler.update_dependency(content, new_hash)

        assert "ef567890" in result
        assert "abcd1234" not in result

    def test_get_latest_commit_hash_success(self, mocker):
        """最新コミットハッシュ取得成功"""
        handler = my_py_lib_handler.MyPyLibHandler()

        mock_result = mocker.MagicMock()
        mock_result.stdout = "1234567890abcdef1234567890abcdef12345678\tHEAD\n"
        mocker.patch("subprocess.run", return_value=mock_result)

        result = handler.get_latest_commit_hash()

        assert result == "1234567890abcdef1234567890abcdef12345678"

    def test_get_latest_commit_hash_failure(self, mocker):
        """最新コミットハッシュ取得失敗"""
        handler = my_py_lib_handler.MyPyLibHandler()

        import subprocess

        mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git"))

        result = handler.get_latest_commit_hash()

        assert result is None

    def test_diff_no_my_lib(self, tmp_project, apply_context):
        """my-lib 依存関係がない場合"""
        handler = my_py_lib_handler.MyPyLibHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        diff = handler.diff(project, apply_context)

        assert diff is not None
        assert "依存関係が見つかりません" in diff

    def test_diff_same_hash(self, tmp_project_with_my_lib, apply_context, mocker):
        """ハッシュが同じ場合"""
        handler = my_py_lib_handler.MyPyLibHandler()
        project = {"name": "test-project", "path": str(tmp_project_with_my_lib)}

        # 同じハッシュを返すモック
        mock_result = mocker.MagicMock()
        mock_result.stdout = "abcd1234567890abcdef1234567890abcdef1234\tHEAD\n"
        mocker.patch("subprocess.run", return_value=mock_result)

        diff = handler.diff(project, apply_context)

        assert diff is None

    def test_diff_different_hash(self, tmp_project_with_my_lib, apply_context, mocker):
        """ハッシュが異なる場合"""
        handler = my_py_lib_handler.MyPyLibHandler()
        project = {"name": "test-project", "path": str(tmp_project_with_my_lib)}

        # 異なるハッシュを返すモック
        mock_result = mocker.MagicMock()
        mock_result.stdout = "newhash567890abcdef1234567890abcdef12345678\tHEAD\n"
        mocker.patch("subprocess.run", return_value=mock_result)

        diff = handler.diff(project, apply_context)

        assert diff is not None
        assert "---" in diff  # unified diff

    def test_apply_no_my_lib(self, tmp_project, apply_context):
        """my-lib 依存関係がない場合"""
        handler = my_py_lib_handler.MyPyLibHandler()
        project = {"name": "test-project", "path": str(tmp_project)}

        result = handler.apply(project, apply_context)

        assert result.status == "skipped"

    def test_apply_same_hash(self, tmp_project_with_my_lib, apply_context, mocker):
        """ハッシュが同じ場合"""
        handler = my_py_lib_handler.MyPyLibHandler()
        project = {"name": "test-project", "path": str(tmp_project_with_my_lib)}

        mock_result = mocker.MagicMock()
        mock_result.stdout = "abcd1234567890abcdef1234567890abcdef1234\tHEAD\n"
        mocker.patch("subprocess.run", return_value=mock_result)

        result = handler.apply(project, apply_context)

        assert result.status == "unchanged"

    def test_apply_updates_hash(self, tmp_project_with_my_lib, apply_context, mocker):
        """ハッシュを更新"""
        handler = my_py_lib_handler.MyPyLibHandler()
        project = {"name": "test-project", "path": str(tmp_project_with_my_lib)}

        new_hash = "newhash567890abcdef1234567890abcdef12345678"
        mock_result = mocker.MagicMock()
        mock_result.stdout = f"{new_hash}\tHEAD\n"
        mocker.patch("subprocess.run", return_value=mock_result)

        result = handler.apply(project, apply_context)

        assert result.status == "updated"
        assert "abcd1234" in result.message  # old hash
        assert "newhash5" in result.message  # new hash (truncated)

        # ファイルが更新されていることを確認
        content = (tmp_project_with_my_lib / "pyproject.toml").read_text()
        assert new_hash in content

    def test_apply_dry_run(self, tmp_project_with_my_lib, mocker):
        """ドライランモード"""
        handler = my_py_lib_handler.MyPyLibHandler()
        project = {"name": "test-project", "path": str(tmp_project_with_my_lib)}

        original_content = (tmp_project_with_my_lib / "pyproject.toml").read_text()

        new_hash = "newhash567890abcdef1234567890abcdef12345678"
        mock_result = mocker.MagicMock()
        mock_result.stdout = f"{new_hash}\tHEAD\n"
        mocker.patch("subprocess.run", return_value=mock_result)

        context = handlers_base.ApplyContext(
            config={},
            template_dir=tmp_project_with_my_lib.parent,
            dry_run=True,
            backup=False,
        )

        result = handler.apply(project, context)

        assert result.status == "updated"
        # ドライランなのでファイルは変更されない
        assert (tmp_project_with_my_lib / "pyproject.toml").read_text() == original_content
