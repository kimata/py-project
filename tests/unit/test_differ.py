#!/usr/bin/env python3
# ruff: noqa: S101
"""
differ.py のテスト
"""

import io

import rich.console

import py_project.differ as differ


class TestPrintDiff:
    """print_diff のテスト"""

    def test_print_diff_with_content(self):
        """差分がある場合"""
        diff_text = """\
--- a/test.txt
+++ b/test.txt
@@ -1 +1 @@
-old line
+new line
"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)

        differ.print_diff(diff_text, console)

        result = output.getvalue()
        # 何らかの出力があることを確認（ANSI エスケープコード含む）
        assert len(result) > 0

    def test_print_diff_empty(self):
        """差分が空の場合"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)

        differ.print_diff("", console)

        result = output.getvalue()
        assert result == ""

    def test_print_diff_none_like(self):
        """空文字列の場合"""
        output = io.StringIO()
        console = rich.console.Console(file=output, force_terminal=True)

        differ.print_diff("", console)

        # 例外が発生しないことを確認
        assert True
