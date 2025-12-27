# 🛠️ py-project

[![Test Status](https://github.com/kimata/py-project/actions/workflows/test.yml/badge.svg)](https://github.com/kimata/py-project/actions/workflows/test.yml)
[![Coverage Report](https://img.shields.io/badge/coverage-report-blue)](https://kimata.github.io/py-project/)

複数の Python プロジェクトに標準的な設定を一括適用するツール

## 📋 概要

複数のプロジェクトで共通の設定ファイル（pre-commit, ruff, pyproject.toml 等）を管理・適用します。

### 主な特徴

- 📦 **一括適用** - 複数プロジェクトへ一度に設定を適用
- 🔍 **ドライラン** - 適用前に変更内容を確認可能
- 📝 **差分表示** - 変更箇所をシンタックスハイライト付きで表示
- 🔄 **pyproject.toml マージ** - プロジェクト固有設定を保持しつつ共通設定を適用
- ⚡ **自動 uv sync** - pyproject.toml 更新後に自動で依存関係を同期
- 🎨 **テンプレート対応** - Jinja2 テンプレートで柔軟な設定生成

### 対応する設定タイプ

| タイプ | 説明 |
|--------|------|
| `pyproject` | pyproject.toml 共通セクション |
| `pre-commit` | .pre-commit-config.yaml |
| `ruff` | ruff.toml |
| `gitignore` | .gitignore |
| `dockerignore` | .dockerignore |
| `yamllint` | .yamllint.yaml |
| `prettier` | .prettierrc |
| `python-version` | .python-version |
| `renovate` | renovate.json |
| `my-py-lib` | my-py-lib 依存関係の更新 |

## 🚀 セットアップ

### 1. インストール

```bash
# uv のインストール（未インストールの場合）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 依存関係のインストール
uv sync
```

### 2. 設定ファイルの準備

`config.yaml` を作成して、管理対象のプロジェクトを設定：

```yaml
# デフォルト設定
defaults:
  python_version: "3.12"
  configs:
    - pyproject
    - pre-commit
    - ruff
    - gitignore

# テンプレートディレクトリ
template_dir: ./templates

# プロジェクト一覧
projects:
  - name: my-project
    path: ~/github/my-project

  - name: another-project
    path: ~/github/another-project
    configs:  # プロジェクト固有の設定
      - pyproject
      - pre-commit
```

## 💻 使い方

### 基本的な使い方

```bash
# ドライラン（デフォルト）- 変更内容を確認
uv run src/app.py

# 実際に変更を適用
uv run src/app.py --apply

# 差分を詳細表示
uv run src/app.py -d
```

### フィルタリング

```bash
# 特定のプロジェクトのみ
uv run src/app.py -p my-project

# 特定の設定タイプのみ
uv run src/app.py -t pyproject -t pre-commit

# 組み合わせ
uv run src/app.py -p my-project -t pyproject --apply
```

### その他のオプション

```bash
# 設定ファイルを指定
uv run src/app.py -c custom-config.yaml

# バックアップを作成して適用
uv run src/app.py --apply --backup

# pyproject.toml 更新後の uv sync をスキップ
uv run src/app.py --apply --no-sync

# 詳細ログ出力
uv run src/app.py -v

# 設定ファイルの検証のみ
uv run src/app.py --validate

# プロジェクト一覧を表示
uv run src/app.py --list-projects

# 設定タイプ一覧を表示
uv run src/app.py --list-configs
```

## 📁 テンプレート

`templates/` ディレクトリに設定タイプごとのテンプレートを配置：

```
templates/
├── pyproject/
│   └── sections.toml      # pyproject.toml の共通セクション
├── pre-commit/
│   └── .pre-commit-config.yaml
├── ruff/
│   └── ruff.toml
├── gitignore/
│   └── .gitignore
└── ...
```

### Jinja2 テンプレート

テンプレートでは以下の変数が使用可能：

```yaml
# .pre-commit-config.yaml の例
repos:
  - repo: local
    hooks:
      - id: ruff
        language: python
        language_version: "{{ vars.python_version | default(defaults.python_version) }}"
```

## ⚙️ 高度な設定

### プロジェクト固有のオプション

```yaml
projects:
  - name: special-project
    path: ~/github/special-project

    # テンプレート変数
    vars:
      python_version: "3.11"

    # テンプレートファイルのオーバーライド
    template_overrides:
      pre-commit: ~/my-templates/.pre-commit-config.yaml

    # pyproject.toml 固有オプション
    pyproject:
      # 追加で保持するセクション
      preserve_sections:
        - tool.custom
      # 追加の開発依存
      extra_dev_deps:
        - some-package>=1.0
```

## 📝 ライセンス

Apache License Version 2.0

---

<div align="center">

**⭐ このプロジェクトが役に立った場合は、Star をお願いします！**

[🐛 Issue 報告](https://github.com/kimata/py-project/issues)

</div>
