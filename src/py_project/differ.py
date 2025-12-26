"""差分表示モジュール"""

import rich.console
import rich.syntax


def print_diff(diff_text: str, console: rich.console.Console) -> None:
    """差分をシンタックスハイライト付きで表示"""
    if not diff_text:
        return

    syntax = rich.syntax.Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
    console.print(syntax)
