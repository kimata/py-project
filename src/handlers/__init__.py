"""設定タイプハンドラ"""

from .base import ApplyContext, ApplyResult, ConfigHandler
from .my_py_lib import MyPyLibHandler
from .pyproject import PyprojectHandler
from .template_copy import (
    DockerignoreHandler,
    GitignoreHandler,
    PreCommitHandler,
    PrettierHandler,
    PythonVersionHandler,
    RuffHandler,
    YamllintHandler,
)

HANDLERS: dict[str, type[ConfigHandler]] = {
    "pre-commit": PreCommitHandler,
    "ruff": RuffHandler,
    "yamllint": YamllintHandler,
    "prettier": PrettierHandler,
    "python-version": PythonVersionHandler,
    "dockerignore": DockerignoreHandler,
    "gitignore": GitignoreHandler,
    "pyproject": PyprojectHandler,
    "my-py-lib": MyPyLibHandler,
}

__all__ = [
    "ApplyContext",
    "ApplyResult",
    "ConfigHandler",
    "HANDLERS",
]
