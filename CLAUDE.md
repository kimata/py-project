# CLAUDE.md

このファイルは Claude Code がこのリポジトリで作業する際のガイダンスを提供します。

## プロジェクト概要

py-project は、複数の Python プロジェクトに標準的な設定ファイル（pre-commit, ruff, pyproject.toml 等）を一括適用するための CLI ツールです。

## 開発コマンド

```bash
# 依存関係のインストール
uv sync

# ヘルプ表示
uv run src/app.py -h

# ドライラン（デフォルト）
uv run src/app.py

# 実際に適用
uv run src/app.py --apply

# 特定プロジェクトのみ
uv run src/app.py -p プロジェクト名

# 差分表示
uv run src/app.py -d
```

## アーキテクチャ

```
src/
├── app.py                      # エントリポイント（docopt CLI）
└── py_project/
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
import py_project.handlers.base as handlers_base
```

### CLI
- docopt を使用
- エントリポイントは `src/app.py`
- `if __name__ == "__main__":` で引数解析

### ハンドラ追加手順
1. `handlers/` に新クラス作成（`ConfigHandler` 継承）
2. `name`, `apply()`, `diff()` を実装
3. `handlers/__init__.py` の `HANDLERS` に登録

### ログ
- ハンドラ内は DEBUG レベル（コンソール出力と重複するため）

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

`pyproject.toml` をはじめとする一般的なプロジェクト管理ファイルは、このツール自身（py-project）で管理しています。修正したい場合は `templates/` 配下のテンプレートを更新し、ツールを実行して適用してください。

**重要**: テンプレートを修正する際は、何を変更したいのかを説明し、確認を取ること。

## 注意

- pyproject.toml 更新後は自動で `uv sync` 実行（`--no-sync` でスキップ）
- tomlkit の空行差分対策で正規化処理あり
