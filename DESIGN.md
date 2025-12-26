# py-project 設計ドキュメント

## 概要

複数の Python プロジェクトに対して、標準的な設定ファイルを一括で適用・更新するための CLI ツール。

---

## 設計方針

### 1. シンプルさと拡張性の両立

- 基本操作は `uv run src/app.py` の一発で完了
- 新しい設定タイプの追加が容易なプラグイン的構造
- 設定ファイルは YAML で人間が読み書きしやすく

### 2. 安全性重視

- デフォルトでドライランモード（`--apply` で実行）
- 変更前に差分を表示
- バックアップ機能を内蔵

### 3. 柔軟なテンプレート

- Jinja2 によるテンプレート変数展開
- プロジェクト固有の値を埋め込み可能

### 4. my-py-lib の最大活用

- `my_lib.config`: YAML 読み込み + JSON Schema バリデーション
- `my_lib.logger`: 統一されたログ出力（coloredlogs + ローテーション）

---

## ディレクトリ構成

```
py-project/
├── src/
│   ├── app.py                 # エントリーポイント
│   ├── cli.py                 # CLI 定義
│   ├── applier.py             # 設定適用ロジック
│   ├── differ.py              # 差分表示
│   └── handlers/              # 設定タイプ別ハンドラ
│       ├── __init__.py
│       ├── base.py            # 基底クラス
│       ├── template_copy.py   # テンプレートコピー系
│       ├── pyproject.py       # pyproject.toml 共通設定
│       └── my_py_lib.py       # my-py-lib 更新用
├── templates/                 # テンプレートファイル
│   ├── pre-commit/
│   │   └── .pre-commit-config.yaml
│   ├── ruff/
│   │   └── ruff.toml
│   ├── yamllint/
│   │   └── .yamllint.yaml
│   ├── prettier/
│   │   └── .prettierrc
│   ├── python-version/
│   │   └── .python-version
│   ├── dockerignore/
│   │   └── .dockerignore
│   ├── gitignore/
│   │   └── .gitignore
│   └── pyproject/
│       └── sections.toml      # pyproject.toml 共通セクション
├── schema/
│   └── config.schema.json     # 設定ファイルの JSON Schema
├── config.yaml                # プロジェクト設定
├── pyproject.toml
└── DESIGN.md
```

---

## JSON Schema (schema/config.schema.json)

設定ファイルのバリデーションに使用する JSON Schema。`my_lib.config.load()` で自動検証される。

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "py-project Configuration",
  "description": "複数Pythonプロジェクトへの設定適用ツールの設定ファイル",
  "type": "object",
  "required": ["projects"],
  "properties": {
    "defaults": {
      "type": "object",
      "description": "全プロジェクト共通のデフォルト設定",
      "properties": {
        "python_version": {
          "type": "string",
          "description": "デフォルトの Python バージョン",
          "pattern": "^3\\.[0-9]+$",
          "default": "3.12"
        },
        "configs": {
          "type": "array",
          "description": "デフォルトで適用する設定タイプ",
          "items": {
            "$ref": "#/$defs/configType"
          },
          "default": []
        }
      },
      "additionalProperties": false
    },
    "template_dir": {
      "type": "string",
      "description": "テンプレートディレクトリのパス",
      "default": "./templates"
    },
    "projects": {
      "type": "array",
      "description": "管理対象プロジェクト一覧",
      "minItems": 1,
      "items": {
        "$ref": "#/$defs/project"
      }
    }
  },
  "additionalProperties": false,
  "$defs": {
    "configType": {
      "type": "string",
      "enum": [
        "pre-commit",
        "ruff",
        "yamllint",
        "prettier",
        "python-version",
        "dockerignore",
        "gitignore",
        "pyproject",
        "my-py-lib"
      ],
      "description": "設定タイプ"
    },
    "project": {
      "type": "object",
      "required": ["name", "path"],
      "properties": {
        "name": {
          "type": "string",
          "description": "プロジェクト名（識別用）",
          "minLength": 1
        },
        "path": {
          "type": "string",
          "description": "プロジェクトのパス（絶対パスまたは ~/ 形式）",
          "minLength": 1
        },
        "configs": {
          "type": "array",
          "description": "適用する設定タイプ（省略時は defaults.configs を使用）",
          "items": {
            "$ref": "#/$defs/configType"
          }
        },
        "vars": {
          "type": "object",
          "description": "テンプレート変数",
          "properties": {
            "python_version": {
              "type": "string",
              "pattern": "^3\\.[0-9]+$"
            }
          },
          "additionalProperties": {
            "type": "string"
          }
        },
        "template_overrides": {
          "type": "object",
          "description": "設定タイプ別のテンプレート上書き",
          "additionalProperties": {
            "type": "string"
          }
        },
        "pyproject": {
          "type": "object",
          "description": "pyproject.toml 設定タイプのオプション",
          "properties": {
            "preserve_sections": {
              "type": "array",
              "description": "追加で保持するセクション",
              "items": { "type": "string" }
            },
            "extra_dev_deps": {
              "type": "array",
              "description": "追加の開発依存",
              "items": { "type": "string" }
            }
          },
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    }
  }
}
```

---

## 設定ファイル (config.yaml)

```yaml
# グローバル設定（全プロジェクト共通のデフォルト）
defaults:
  python_version: "3.12"
  configs:
    - pre-commit
    - ruff
    - gitignore

# テンプレートディレクトリ（デフォルト: ./templates）
template_dir: ./templates

# プロジェクト一覧
projects:
  - name: my-web-app
    path: ~/github/my-web-app
    # 適用する設定（defaults を上書き）
    configs:
      - pre-commit
      - ruff
      - yamllint
      - prettier
      - gitignore
      - dockerignore
      - my-py-lib
    # プロジェクト固有の変数（テンプレートで使用）
    vars:
      python_version: "3.11"

  - name: my-cli-tool
    path: ~/github/my-cli-tool
    # configs を省略すると defaults.configs を使用
    vars:
      python_version: "3.12"

  - name: my-library
    path: ~/github/my-library
    configs:
      - pre-commit
      - ruff
      - python-version
      - gitignore
    # 特定の設定だけテンプレートを上書き
    template_overrides:
      gitignore: ./custom-templates/library.gitignore
```

---

## CLI インターフェース

```bash
# 基本使用（ドライラン - 変更内容を表示するのみ）
uv run src/app.py

# 実際に適用
uv run src/app.py --apply

# 特定プロジェクトのみ
uv run src/app.py --project my-web-app --apply

# 特定の設定タイプのみ
uv run src/app.py --config ruff --apply

# 複数の設定タイプ
uv run src/app.py --config ruff --config pre-commit --apply

# 差分を詳細表示
uv run src/app.py --diff

# バックアップを作成して適用
uv run src/app.py --backup --apply

# 設定ファイルを指定
uv run src/app.py -c /path/to/config.yaml --apply

# 詳細ログ
uv run src/app.py --verbose

# 設定の検証のみ
uv run src/app.py --validate
```

### CLI オプション一覧

| オプション | 短縮形 | 説明 |
|-----------|--------|------|
| `--apply` | `-a` | 実際に変更を適用（指定しないとドライラン） |
| `--project` | `-p` | 対象プロジェクトを限定（複数指定可） |
| `--config` | `-t` | 対象設定タイプを限定（複数指定可） |
| `--diff` | `-d` | 差分を詳細表示 |
| `--backup` | `-b` | 適用前にバックアップを作成 |
| `--config-file` | `-c` | 設定ファイルパス（デフォルト: ./config.yaml） |
| `--verbose` | `-v` | 詳細ログ出力 |
| `--validate` | | 設定ファイルの検証のみ |
| `--list-projects` | | プロジェクト一覧を表示 |
| `--list-configs` | | 設定タイプ一覧を表示 |

---

## 設定タイプ

### テンプレートコピー系

単純にテンプレートファイルを対象プロジェクトにコピーする設定タイプ。

| 設定タイプ | テンプレート | 出力先 |
|-----------|-------------|--------|
| `pre-commit` | `templates/pre-commit/.pre-commit-config.yaml` | `.pre-commit-config.yaml` |
| `ruff` | `templates/ruff/ruff.toml` | `ruff.toml` |
| `yamllint` | `templates/yamllint/.yamllint.yaml` | `.yamllint.yaml` |
| `prettier` | `templates/prettier/.prettierrc` | `.prettierrc` |
| `python-version` | `templates/python-version/.python-version` | `.python-version` |
| `dockerignore` | `templates/dockerignore/.dockerignore` | `.dockerignore` |
| `gitignore` | `templates/gitignore/.gitignore` | `.gitignore` |

### 特殊処理系

| 設定タイプ | 説明 |
|-----------|------|
| `my-py-lib` | pyproject.toml の my-py-lib 依存関係を最新化 |
| `pyproject` | pyproject.toml の共通セクションを更新 |

---

## pyproject.toml 共通設定管理

### 概要

pyproject.toml には**プロジェクト固有**の設定と**共通化可能**な設定があります。
このツールは共通化可能な設定セクションのみを更新し、プロジェクト固有の設定は保持します。

### 設定の分類

| 分類 | セクション | 説明 |
|------|-----------|------|
| **固有** | `project.name` | プロジェクト名 |
| **固有** | `project.version` | バージョン |
| **固有** | `project.description` | 説明 |
| **固有** | `project.dependencies` | 依存ライブラリ |
| **固有** | `tool.hatch.build.targets.wheel.packages` | パッケージパス |
| **固有** | `tool.mypy.packages` | mypy 対象パッケージ |
| **固有** | `tool.mypy.overrides` | mypy 無視モジュール |
| **共通** | `project.authors` | 著者情報 |
| **共通** | `project.readme` | README ファイル |
| **共通** | `project.requires-python` | Python バージョン要件 |
| **共通** | `dependency-groups.dev` | 開発依存 |
| **共通** | `tool.uv` | uv 設定 |
| **共通** | `build-system` | ビルドシステム |
| **共通** | `tool.hatch.metadata` | Hatch メタデータ |
| **共通** | `tool.pytest.ini_options` | pytest 設定 |
| **共通** | `tool.coverage` | coverage 設定 |
| **共通** | `tool.mypy` (基本設定) | mypy 基本設定 |
| **共通** | `tool.pyright` | pyright 設定 |
| **共通** | `tool.ruff` | ruff 設定（pyproject 内） |

### テンプレート構造

```
templates/
└── pyproject/
    └── sections.toml    # 共通セクションのテンプレート
```

### sections.toml の例

```toml
# 共通化する pyproject.toml のセクション
# プロジェクト固有の設定（name, version, description, dependencies）は
# 各プロジェクトの pyproject.toml の値を維持します

[project]
authors = [
    { name = "KIMATA Tetsuya", email = "kimata@green-rabbit.net" }
]
readme = "README.md"
requires-python = ">= 3.10"

[dependency-groups]
dev = [
    "pre-commit>=4.0.0",
    "flaky>=3.8.1",
    "playwright>=1.49.0",
    "pytest>=8.3.0",
    "pytest-cov>=6.0.0",
    "pytest-html>=4.1.1",
    "pytest-mock>=3.14.0",
    "pytest-playwright>=0.6.0",
    "pytest-xdist>=3.6.1",
    "pytest-timeout>=2.3.0",
    "time-machine>=2.16.0",
    "mypy>=1.14.0",
]

[tool.uv]
default-groups = ["dev"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.metadata]
allow-direct-references = true

[tool.pytest.ini_options]
minversion = "6.0"
addopts = """
--verbose
--timeout=300
--durations=10
--log-file-level=DEBUG
--log-format="%(asctime)s %(levelname)s [%(filename)s:%(lineno)s %(funcName)s] %(message)s"
--capture=sys
--html=tests/evidence/index.htm
--self-contained-html
--cov=src
--cov-report=html
"""
testpaths = ["tests"]
filterwarnings = [
    "ignore:datetime\\.datetime\\.utcfromtimestamp\\(\\) is deprecated:DeprecationWarning",
    "ignore::DeprecationWarning:multiprocessing\\.popen_fork",
    "ignore:unclosed database.*:ResourceWarning:rich.*",
    "ignore:unclosed database.*:ResourceWarning:influxdb_client.*",
    "ignore:unclosed database.*:ResourceWarning:coverage.*",
    "ignore:unclosed database.*:ResourceWarning:time_machine.*",
    "ignore::ResourceWarning:_pytest.unraisableexception",
    "ignore::ResourceWarning:coverage.sqldata",
]

[tool.coverage.run]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
]

[tool.coverage.html]
directory = "tests/evidence/coverage"

[tool.mypy]
warn_return_any = false
warn_unused_configs = true
ignore_missing_imports = true

[tool.pyright]
venvPath = "."
venv = ".venv"

[tool.ruff]
line-length = 110

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP"]
```

### マージ動作

`pyproject` 設定タイプは以下のルールでマージします：

1. **完全上書き**: テンプレートにあるセクションは完全に上書き
2. **保持**: テンプレートにないセクションは既存値を保持
3. **プロジェクト固有フィールドの保持**: 以下のフィールドは常に保持
   - `project.name`
   - `project.version`
   - `project.description`
   - `project.dependencies`
   - `tool.hatch.build.targets.wheel.packages`
   - `tool.mypy.packages`
   - `tool.mypy.overrides`

### プロジェクト設定での制御

```yaml
projects:
  - name: my-web-app
    path: ~/github/my-web-app
    configs:
      - pyproject
    # pyproject 固有のオプション
    pyproject:
      # 追加で保持したいセクション
      preserve_sections:
        - tool.mypy.plugins
      # 追加の開発依存（テンプレートにマージ）
      extra_dev_deps:
        - types-pillow>=10.2.0
```

---

## テンプレート変数

テンプレートファイル内で Jinja2 構文を使用可能。

### 使用可能な変数

```jinja2
{{ project.name }}          # プロジェクト名
{{ project.path }}          # プロジェクトパス
{{ vars.python_version }}   # プロジェクト固有変数
{{ defaults.python_version }} # デフォルト変数
```

### 使用例 (.python-version テンプレート)

```jinja2
{{ vars.python_version | default(defaults.python_version) }}
```

---

## my-py-lib の活用

### 設定ファイル読み込み (my_lib.config)

```python
import my_lib.config as config

# 設定ファイルの読み込みと JSON Schema バリデーション
# スキーマは config.yaml と同じディレクトリの schema/config.schema.json を自動検索
app_config = config.load(
    config_file="config.yaml",
    schema_file="schema/config.schema.json"
)

# パス指定でのデータ取得
template_dir = config.get_path(app_config, "template_dir", default="./templates")
python_version = config.get_data(app_config, "defaults.python_version", default="3.12")

# プロジェクト一覧の取得
projects = config.get_data(app_config, "projects")
```

### 例外処理

```python
from my_lib.config import (
    ConfigError,
    ConfigValidationError,
    ConfigParseError,
    ConfigFileNotFoundError,
)

try:
    app_config = config.load("config.yaml", "schema/config.schema.json")
except ConfigFileNotFoundError as e:
    # 設定ファイルが見つからない
    logger.error(f"設定ファイルが見つかりません: {e}")
except ConfigParseError as e:
    # YAML パースエラー（日本語で詳細表示）
    logger.error(f"設定ファイルの形式が不正です:\n{e.details}")
except ConfigValidationError as e:
    # スキーマ検証エラー（日本語で詳細表示）
    logger.error(f"設定ファイルの検証に失敗しました:\n{e.details}")
```

### ロギング (my_lib.logger)

```python
import logging
import my_lib.logger

# ロガーの初期化（coloredlogs 有効化 + ファイル出力）
my_lib.logger.init(
    name="py-project",
    level=logging.INFO,  # --verbose 時は logging.DEBUG
    log_dir="./logs"     # オプション: ログファイル出力先
)

logger = logging.getLogger("py-project")

# 使用例
logger.info("設定ファイルを読み込みました")
logger.debug("プロジェクト: %s", project_name)
logger.warning("ファイルが既に存在します: %s", file_path)
logger.error("適用に失敗しました: %s", error_message)
```

---

## ハンドラ設計

### 基底クラス

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from dataclasses import dataclass

@dataclass
class ApplyContext:
    """適用時のコンテキスト情報"""
    config: dict[str, Any]      # アプリ設定全体
    template_dir: Path          # テンプレートディレクトリ
    dry_run: bool               # ドライランモード
    backup: bool                # バックアップ作成フラグ

@dataclass
class ApplyResult:
    """適用結果"""
    status: str                 # "created" | "updated" | "unchanged" | "error"
    message: str | None = None  # エラーメッセージ等

class ConfigHandler(ABC):
    """設定タイプのハンドラ基底クラス"""

    @property
    @abstractmethod
    def name(self) -> str:
        """設定タイプ名"""
        pass

    @abstractmethod
    def apply(self, project: dict[str, Any], context: ApplyContext) -> ApplyResult:
        """設定を適用"""
        pass

    @abstractmethod
    def diff(self, project: dict[str, Any], context: ApplyContext) -> str | None:
        """差分を取得（変更がない場合は None）"""
        pass
```

### ハンドラ登録

```python
# handlers/__init__.py
from .template_copy import (
    PreCommitHandler,
    RuffHandler,
    YamllintHandler,
    PrettierHandler,
    PythonVersionHandler,
    DockerignoreHandler,
    GitignoreHandler,
)
from .pyproject import PyprojectHandler
from .my_py_lib import MyPyLibHandler

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
```

---

## 処理フロー

```
1. CLI 引数パース (typer)
2. ロガー初期化 (my_lib.logger.init)
3. config.yaml 読み込み・バリデーション (my_lib.config.load)
   - JSON Schema による検証
   - エラー時は日本語で詳細表示
4. 対象プロジェクト/設定タイプのフィルタリング
5. 各プロジェクトに対して:
   a. 各設定タイプのハンドラを取得
   b. 差分を計算
   c. ドライランなら差分表示のみ
   d. --apply なら:
      - バックアップ作成（--backup 指定時）
      - 設定ファイルを適用
6. 結果サマリを表示
```

---

## 出力例

### ドライラン時

```
🔍 Dry run mode (use --apply to apply changes)

📁 my-web-app (~/github/my-web-app)
   ✓ pre-commit    : up to date
   ~ ruff          : will be updated
   + yamllint      : will be created
   + prettier      : will be created

📁 my-cli-tool (~/github/my-cli-tool)
   ✓ pre-commit    : up to date
   ✓ ruff          : up to date
   ✓ gitignore     : up to date

Summary: 2 projects, 1 update, 2 creates, 4 unchanged
```

### 適用時

```
🚀 Applying configurations...

📁 my-web-app (~/github/my-web-app)
   ✓ pre-commit    : unchanged
   ✓ ruff          : updated
   ✓ yamllint      : created
   ✓ prettier      : created

📁 my-cli-tool (~/github/my-cli-tool)
   ✓ pre-commit    : unchanged
   ✓ ruff          : unchanged
   ✓ gitignore     : unchanged

✅ Done! 2 projects processed, 1 updated, 2 created
```

### バリデーションエラー時

```
❌ 設定ファイルの検証に失敗しました:

エラー箇所: projects[0].configs[2]
  値: "invalid-type"
  問題: 値が許可されていません
  許可される値: pre-commit, ruff, yamllint, prettier, python-version, dockerignore, gitignore, my-py-lib
```

---

## 依存ライブラリ

```toml
[project]
dependencies = [
    "my-py-lib @ git+https://github.com/kimata/my-py-lib",  # 設定・ログ
    "jinja2>=3.0",        # テンプレートエンジン
    "typer>=0.9",         # CLI フレームワーク
    "rich>=13.0",         # リッチな出力
    "tomlkit>=0.12",      # TOML 読み書き（コメント保持）
]
```

※ `my-py-lib` が依存している `pyyaml`, `jsonschema`, `coloredlogs` 等は自動的にインストールされる

---

## 拡張ポイント

### 新しい設定タイプの追加

1. `handlers/` に新しいハンドラクラスを作成
2. `ConfigHandler` を継承
3. `handlers/__init__.py` の `HANDLERS` に登録
4. 必要に応じて `templates/` にテンプレートを追加
5. `schema/config.schema.json` の `configType` enum に追加

### カスタムハンドラの例

```python
# handlers/mypy.py
class MypyHandler(TemplateCopyHandler):
    name = "mypy"
    template_path = "mypy/mypy.ini"
    output_path = "mypy.ini"
```

---

## 今後の拡張案

- **フック機能**: 適用前後にカスタムスクリプトを実行
- **リモートテンプレート**: Git リポジトリからテンプレートを取得
- **設定のマージ**: 既存ファイルとテンプレートをマージ
- **GUI**: TUI (Textual) による対話的操作
- **Watch モード**: テンプレート変更時に自動適用
