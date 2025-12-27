# 型ヒントにおける `|` 演算子の使用箇所

本プロジェクトで使用されている `X | None` 形式の型ヒントについてまとめます。

## 背景

`X | None` 構文は Python 3.10 で導入された Union 型の新しい記法です。従来は `typing.Optional[X]` または `typing.Union[X, None]` と書いていたものを、より簡潔に記述できます。

本プロジェクトは `requires-python = ">=3.11"` であるため、この構文はネイティブにサポートされています。

## 使用箇所一覧

### 1. 戻り値の型（19箇所）

| ファイル | 行 | コード | 目的 |
|----------|------|--------|------|
| `handlers/base.py` | 42 | `def diff(...) -> str \| None` | 差分がない場合 None を返す |
| `handlers/base.py` | 50 | `def create_backup(...) -> Path \| None` | ファイルが存在しない場合 None |
| `handlers/my_py_lib.py` | 31 | `def get_latest_commit_hash(self) -> str \| None` | 取得失敗時 None |
| `handlers/my_py_lib.py` | 66 | `def diff(...) -> str \| None` | 差分がない場合 None |
| `handlers/template_copy.py` | 67 | `def diff(...) -> str \| None` | 差分がない場合 None |
| `handlers/pyproject.py` | 184 | `def generate_merged_content(...) -> str \| None` | 生成失敗時 None |
| `handlers/pyproject.py` | 203 | `def diff(...) -> str \| None` | 差分がない場合 None |

### 2. 関数引数の型（6箇所）

| ファイル | 行 | コード | 目的 |
|----------|------|--------|------|
| `app.py` | 45-46 | `projects: list[str] \| None = None` | オプション引数（未指定時は全プロジェクト） |
| `app.py` | 46 | `config_types: list[str] \| None = None` | オプション引数（未指定時は全タイプ） |
| `applier.py` | 40-41 | `projects: list[str] \| None = None` | 同上 |
| `applier.py` | 46 | `console: rich.console.Console \| None = None` | コンソール未指定時は自動作成 |

### 3. タプル要素の型（1箇所）

| ファイル | 行 | コード | 目的 |
|----------|------|--------|------|
| `handlers/my_py_lib.py` | 47 | `tuple[str \| None, int \| None, int \| None]` | 依存関係が見つからない場合の各要素 |

### 4. データクラスフィールド（1箇所）

| ファイル | 行 | コード | 目的 |
|----------|------|--------|------|
| `handlers/base.py` | 24 | `message: str \| None = None` | 任意のメッセージ（エラー詳細など） |

### 5. Union 型（非 None）（1箇所）

| ファイル | 行 | コード | 目的 |
|----------|------|--------|------|
| `handlers/pyproject.py` | 154-155 | `tomlkit.TOMLDocument \| dict` | tomlkit のドキュメントと辞書の両方を受け付ける |

## 代替手法

### Optional を使う場合

```python
from typing import Optional

# 変更前
def diff(...) -> str | None:

# 変更後
def diff(...) -> Optional[str]:
```

### Union を使う場合

```python
from typing import Union

# 変更前
result: tomlkit.TOMLDocument | dict

# 変更後
result: Union[tomlkit.TOMLDocument, dict]
```

## 排除の可否

### 1. `X | None` 形式（大部分）

**排除可能**: `Optional[X]` に置き換え可能です。

ただし、以下の点に注意が必要です：
- `typing` モジュールからのインポートが必要
- コードが若干冗長になる
- Python 3.10+ では `|` が推奨スタイル

### 2. `tomlkit.TOMLDocument | dict` 形式

**排除可能**: `Union[tomlkit.TOMLDocument, dict]` に置き換え可能です。

または、設計を見直して：
- 常に `tomlkit.TOMLDocument` を使用する
- 共通のプロトコル/基底クラスを定義する

### 3. タプルの各要素

**排除可能だが非推奨**: `Tuple[Optional[str], Optional[int], Optional[int]]` に置き換え可能ですが、可読性が低下します。

## 推奨

`|` 構文は Python 3.10+ の標準的な記法であり、PEP 604 で正式に導入されました。本プロジェクトが Python 3.11+ をターゲットにしている以上、`|` を使用することは適切です。

ただし、以下のいずれかの理由で `Optional` / `Union` に戻す場合は、全ファイルで統一することを推奨します：

1. **Python 3.9 以前との互換性が必要な場合**（本プロジェクトでは不要）
2. **コードスタイルガイドで `Optional` を優先する場合**
3. **IDE/エディタの補完機能との互換性問題がある場合**

## 置き換えスクリプト例

すべての `X | None` を `Optional[X]` に置き換える場合：

```bash
# 確認用
grep -rn "| None" src/

# 置き換え（手動での確認を推奨）
# 各ファイルの先頭に from typing import Optional を追加し、
# X | None を Optional[X] に変更
```
