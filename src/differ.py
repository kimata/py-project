"""差分表示モジュール"""

from rich.console import Console
from rich.syntax import Syntax


def print_diff(diff_text: str, console: Console) -> None:
    """差分をシンタックスハイライト付きで表示"""
    if not diff_text:
        return

    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
    console.print(syntax)
