"""設定タイプハンドラ"""

import py_project.handlers.base as handlers_base
import py_project.handlers.my_py_lib as handlers_my_py_lib
import py_project.handlers.pyproject as handlers_pyproject
import py_project.handlers.template_copy as handlers_template_copy

HANDLERS: dict[str, type[handlers_base.ConfigHandler]] = {
    "pre-commit": handlers_template_copy.PreCommitHandler,
    "ruff": handlers_template_copy.RuffHandler,
    "yamllint": handlers_template_copy.YamllintHandler,
    "prettier": handlers_template_copy.PrettierHandler,
    "python-version": handlers_template_copy.PythonVersionHandler,
    "dockerignore": handlers_template_copy.DockerignoreHandler,
    "gitignore": handlers_template_copy.GitignoreHandler,
    "pyproject": handlers_pyproject.PyprojectHandler,
    "my-py-lib": handlers_my_py_lib.MyPyLibHandler,
}

# サブモジュールを公開
base = handlers_base
