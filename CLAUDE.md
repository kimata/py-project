# CLAUDE.md

このファイルは Claude Code がこのリポジトリで作業する際のガイダンスを提供します。

## プロジェクト概要

py-project は、複数の Python プロジェクトに標準的な設定ファイル（pre-commit, ruff, pyproject.toml 等）を一括適用するための CLI ツールです。

## 開発コマンド

```bash
# 依存関係のインストール
uv sync

# ヘルプ表示
uv run py-project -h

# ドライラン（デフォルト）
uv run py-project

# 実際に適用
uv run py-project --apply

# 特定プロジェクトのみ
uv run py-project -p プロジェクト名

# 差分表示
uv run py-project -d
```

## アーキテクチャ

```
src/
└── py_project/
    ├── __main__.py             # エントリポイント
    ├── cli.py                  # CLI（docopt）
    ├── applier.py              # 設定適用ロジック
    ├── differ.py               # 差分表示
    └── handlers/               # 設定タイプハンドラ
        ├── base.py             # 基底クラス
        ├── template_copy.py    # テンプレートコピー系
        ├── pyproject.py        # pyproject.toml マージ
        └── my_py_lib.py        # my-py-lib 更新
```

## コーディング規約

### インポートスタイル

```python
# NG: from xxx import yyy
# OK: import xxx として xxx.yyy でアクセス
import py_project.config
# 使用時: py_project.config.Project

# 例外: handlers.base は循環インポート回避のため as を使用
import py_project.handlers.base as handlers_base
# 使用時: handlers_base.ConfigHandler
```

- `from __future__ import annotations` は Python 3.11+ では不要なため使用しない

### CLI

- docopt を使用
- pyproject.toml の `[project.scripts]` で `py-project` コマンドを定義
- エントリポイントは `src/py_project/__main__.py` → `cli.py:main()`

### ハンドラ追加手順

1. `handlers/` に新クラス作成（`ConfigHandler` 継承）
2. `name`, `apply()`, `diff()` を実装
3. `handlers/__init__.py` の `HANDLERS` に登録

### 例外処理

- 広すぎる例外（`except Exception:`）は避け、具体的な例外クラスを指定する
- 外部ライブラリの例外は、そのライブラリ固有の例外クラスを使用
    - YAML: `yaml.YAMLError`
    - TOML: `tomlkit.exceptions.TOMLKitError`
    - JSON: `json.JSONDecodeError`

### 型定義

- 構造化データは dataclass を使用
- タプルよりも名前付きフィールドを持つ dataclass を優先
- Protocol は構造的部分型が必要な場合にのみ使用（通常は ABC で十分）
- 状態を表す文字列リテラルは Enum で定義する（例: `ApplyStatus`）
- `| None` は Python の標準的イディオムとして許容
- 外部ライブラリ（tomlkit 等）の不完全な型定義には `typing.cast()` で対応可
- `isinstance` は外部ライブラリとの連携で必要な場合のみ許容
- 関数の戻り値でタプルを使う場合、要素が2つ以下で意味が明確なら dataclass 化は不要
    - 例: `(bool, str | None)` は許容（成功/失敗とエラーメッセージ）

### 後方互換性

- 未使用の変数、関数、re-export は残さず削除する
- 削除したコードに関する `# removed` などのコメントは不要

### 出力処理

- console/progress への出力は `_create_printer()` パターンを使用
- progress 固有のメソッド（`set_progress_bar` 等）は個別に if 分岐

### コード重複の回避

- 同じ処理が複数箇所で必要な場合は共通関数/メソッドに抽出する
- ハンドラ間で共通の処理は基底クラス `ConfigHandler` に実装する

### ログ

- ハンドラ内は DEBUG レベル（コンソール出力と重複するため）

### 大きな関数の分割

- 関数の行数よりも「単一責任」を重視する
- 処理フローの可視性を維持するため、過度な分割は避ける
- 分割の目安: 異なる抽象度の処理が混在している場合

### ローカルインポート

- 原則としてモジュール先頭でインポートする
- 循環インポート回避のためのローカルインポートは許容
- `TYPE_CHECKING` ブロックを活用する

### コーディングスタイル

- リストのコピーは `.copy()` を使用し、意図を明確にする
    ```python
    # NG: list(existing_list) - コピーの意図が不明確
    # OK: existing_list.copy() - コピーの意図が明確
    configs = defaults.configs.copy()
    ```
- 外部ライブラリのプライベート属性（`_` 接頭辞）への直接アクセスは避ける

## 設定

- `config.yaml`: JSON Schema で検証（`schema/config.schema`）
- テンプレート: `templates/設定タイプ名/` に配置、Jinja2 対応

## 依存関係

- `my-lib`: 設定読み込み・ロギング
- `docopt`: CLI
- `tomlkit`: TOML パース（フォーマット保持）
- `jinja2`: テンプレート
- `rich`: コンソール出力

## 外部リソースの修正

### my-py-lib

`my_lib` のコードは `../my-py-lib` に存在します。リファクタリングで `my_lib` も修正した方がよい場合：

1. `../my-py-lib` を修正
2. commit & push
3. このリポジトリの `pyproject.toml` を更新（ハッシュ値）
4. `uv sync`

**重要**: `my_lib` を修正する際は、何を変更したいのかを説明し、確認を取ること。

### プロジェクト管理ファイル

`pyproject.toml` をはじめとする一般的なプロジェクト管理ファイルは、このツール自身（py-project）で管理しています。

**重要**: 本プロジェクトの `pyproject.toml` 等を直接編集しないこと。以下の手順で修正すること：

1. `templates/` 配下のテンプレートを更新
2. `uv run py-project -p py-project --apply` で適用
3. `uv sync` で依存関係を更新

**重要**: テンプレートを修正する際は、何を変更したいのかを説明し、確認を取ること。

## 注意

- pyproject.toml 更新後は自動で `uv sync` 実行（`--no-sync` でスキップ）
- tomlkit の空行差分対策で正規化処理あり
- コードを更新した際は、README.md や CLAUDE.md の更新が必要か検討すること
