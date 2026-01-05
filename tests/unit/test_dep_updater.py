#!/usr/bin/env python3
# ruff: noqa: S101
"""dep_updater モジュールのテスト"""

import json
import urllib.error
import urllib.request
from unittest import mock

import pytest
import rich.console
import tomlkit

import py_project.dep_updater as dep_updater


class TestDepUpdate:
    """DepUpdate データクラスのテスト"""

    def test_create_dep_update(self):
        """DepUpdate の作成テスト"""
        update = dep_updater.DepUpdate(
            package="pytest",
            current="8.0.0",
            latest="8.1.0",
            updated=True,
        )
        assert update.package == "pytest"
        assert update.current == "8.0.0"
        assert update.latest == "8.1.0"
        assert update.updated is True

    def test_create_dep_update_default_updated(self):
        """DepUpdate のデフォルト値テスト"""
        update = dep_updater.DepUpdate(
            package="pytest",
            current="8.0.0",
            latest="8.0.0",
        )
        assert update.updated is False


class TestGetLatestVersion:
    """_get_latest_version 関数のテスト"""

    def test_get_latest_version_success(self, mocker):
        """PyPI から最新バージョンを正常に取得"""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps({"info": {"version": "8.1.0"}}).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        mocker.patch("urllib.request.urlopen", return_value=mock_response)

        result = dep_updater._get_latest_version("pytest")
        assert result == "8.1.0"

    def test_get_latest_version_network_error(self, mocker):
        """ネットワークエラー時は None を返す"""
        mocker.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        )

        result = dep_updater._get_latest_version("nonexistent-package")
        assert result is None

    def test_get_latest_version_timeout(self, mocker):
        """タイムアウト時は None を返す"""
        mocker.patch(
            "urllib.request.urlopen",
            side_effect=TimeoutError("Connection timed out"),
        )

        result = dep_updater._get_latest_version("pytest")
        assert result is None

    def test_get_latest_version_invalid_json(self, mocker):
        """不正な JSON 時は None を返す"""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = b"invalid json"
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        mocker.patch("urllib.request.urlopen", return_value=mock_response)

        result = dep_updater._get_latest_version("pytest")
        assert result is None

    def test_get_latest_version_missing_field(self, mocker):
        """必須フィールドがない場合は None を返す"""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "info": {}  # version フィールドがない
            }
        ).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        mocker.patch("urllib.request.urlopen", return_value=mock_response)

        result = dep_updater._get_latest_version("pytest")
        assert result is None


class TestParseDependency:
    """_parse_dependency 関数のテスト"""

    def test_parse_valid_dependency(self):
        """正常な依存関係文字列のパース"""
        result = dep_updater._parse_dependency("pytest>=8.3.0")
        assert result == ("pytest", "8.3.0")

    def test_parse_dependency_with_hyphen(self):
        """ハイフンを含むパッケージ名のパース"""
        result = dep_updater._parse_dependency("pytest-cov>=5.0.0")
        assert result == ("pytest-cov", "5.0.0")

    def test_parse_dependency_with_underscore(self):
        """アンダースコアを含むパッケージ名のパース"""
        result = dep_updater._parse_dependency("pytest_mock>=3.14.0")
        assert result == ("pytest_mock", "3.14.0")

    def test_parse_invalid_dependency_no_version(self):
        """バージョンがない依存関係"""
        result = dep_updater._parse_dependency("pytest")
        assert result is None

    def test_parse_invalid_dependency_wrong_operator(self):
        """異なる演算子の依存関係"""
        result = dep_updater._parse_dependency("pytest==8.3.0")
        assert result is None

    def test_parse_invalid_dependency_extra_constraint(self):
        """追加の制約がある依存関係"""
        result = dep_updater._parse_dependency("pytest>=8.3.0,<9.0.0")
        assert result is None


class TestFormatDependency:
    """_format_dependency 関数のテスト"""

    def test_format_dependency(self):
        """依存関係文字列の生成"""
        result = dep_updater._format_dependency("pytest", "8.3.0")
        assert result == "pytest>=8.3.0"


class TestNormalizeVersion:
    """_normalize_version 関数のテスト"""

    def test_normalize_version_standard(self):
        """標準的なバージョン文字列"""
        result = dep_updater._normalize_version("8.3.0")
        assert result == "8.3.0"

    def test_normalize_version_with_extra_parts(self):
        """追加パーツがあるバージョン"""
        result = dep_updater._normalize_version("2025.2.0.20251108")
        assert result == "2025.2.0"

    def test_normalize_version_short(self):
        """短いバージョン文字列"""
        result = dep_updater._normalize_version("1.0")
        assert result == "1.0"


class TestUpdateTemplateDeps:
    """update_template_deps 関数のテスト"""

    @pytest.fixture
    def template_file(self, tmp_path):
        """テスト用テンプレートファイルを作成"""
        template_path = tmp_path / "sections.toml"
        content = tomlkit.dumps(
            {
                "dependency-groups": {
                    "dev": [
                        "pytest>=8.0.0",
                        "pytest-cov>=5.0.0",
                    ]
                }
            }
        )
        template_path.write_text(content)
        return template_path

    def test_update_template_deps_all_up_to_date(self, template_file, mocker):
        """すべての依存関係が最新の場合"""
        mock_response = mock.MagicMock()

        def mock_urlopen(url, timeout=10):
            package = url.split("/")[-2]
            versions = {
                "pytest": "8.0.0",
                "pytest-cov": "5.0.0",
            }
            mock_response.read.return_value = json.dumps(
                {"info": {"version": versions.get(package, "1.0.0")}}
            ).encode()
            mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
            mock_response.__exit__ = mock.MagicMock(return_value=False)
            return mock_response

        mocker.patch("urllib.request.urlopen", side_effect=mock_urlopen)

        console = rich.console.Console(force_terminal=False)
        updates = dep_updater.update_template_deps(template_file, dry_run=True, console=console)

        assert len(updates) == 2
        assert all(not u.updated for u in updates)

    def test_update_template_deps_with_updates(self, template_file, mocker):
        """更新がある場合"""
        mock_response = mock.MagicMock()

        def mock_urlopen(url, timeout=10):
            package = url.split("/")[-2]
            versions = {
                "pytest": "8.1.0",  # 更新あり
                "pytest-cov": "5.0.0",  # 更新なし
            }
            mock_response.read.return_value = json.dumps(
                {"info": {"version": versions.get(package, "1.0.0")}}
            ).encode()
            mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
            mock_response.__exit__ = mock.MagicMock(return_value=False)
            return mock_response

        mocker.patch("urllib.request.urlopen", side_effect=mock_urlopen)

        console = rich.console.Console(force_terminal=False)
        updates = dep_updater.update_template_deps(template_file, dry_run=True, console=console)

        assert len(updates) == 2
        pytest_update = next(u for u in updates if u.package == "pytest")
        assert pytest_update.updated is True
        assert pytest_update.current == "8.0.0"
        assert pytest_update.latest == "8.1.0"

    def test_update_template_deps_apply_mode(self, template_file, mocker):
        """apply モードで実際に更新"""
        mock_response = mock.MagicMock()

        def mock_urlopen(url, timeout=10):
            package = url.split("/")[-2]
            versions = {
                "pytest": "8.1.0",
                "pytest-cov": "5.1.0",
            }
            mock_response.read.return_value = json.dumps(
                {"info": {"version": versions.get(package, "1.0.0")}}
            ).encode()
            mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
            mock_response.__exit__ = mock.MagicMock(return_value=False)
            return mock_response

        mocker.patch("urllib.request.urlopen", side_effect=mock_urlopen)

        console = rich.console.Console(force_terminal=False)
        updates = dep_updater.update_template_deps(template_file, dry_run=False, console=console)

        assert len(updates) == 2
        assert sum(1 for u in updates if u.updated) == 2

        # ファイルが更新されていることを確認
        content = template_file.read_text()
        assert "pytest>=8.1.0" in content
        assert "pytest-cov>=5.1.0" in content

    def test_update_template_deps_file_not_found(self, tmp_path):
        """テンプレートファイルが存在しない場合"""
        template_path = tmp_path / "nonexistent.toml"
        console = rich.console.Console(force_terminal=False)

        updates = dep_updater.update_template_deps(template_path, dry_run=True, console=console)

        assert updates == []

    def test_update_template_deps_no_dev_deps(self, tmp_path):
        """dependency-groups.dev がない場合"""
        template_path = tmp_path / "sections.toml"
        template_path.write_text(tomlkit.dumps({"dependency-groups": {}}))

        console = rich.console.Console(force_terminal=False)
        updates = dep_updater.update_template_deps(template_path, dry_run=True, console=console)

        assert updates == []

    def test_update_template_deps_version_fetch_failed(self, template_file, mocker):
        """バージョン取得に失敗した場合"""
        mocker.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        )

        console = rich.console.Console(force_terminal=False)
        updates = dep_updater.update_template_deps(template_file, dry_run=True, console=console)

        # 取得失敗でも空リストではなく、元の依存関係が維持される
        assert updates == []

    def test_update_template_deps_unparseable_dependency(self, tmp_path, mocker):
        """パースできない依存関係がある場合"""
        template_path = tmp_path / "sections.toml"
        content = tomlkit.dumps(
            {
                "dependency-groups": {
                    "dev": [
                        "pytest>=8.0.0",
                        "special-package",  # バージョン指定なし
                    ]
                }
            }
        )
        template_path.write_text(content)

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps({"info": {"version": "8.0.0"}}).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)
        mocker.patch("urllib.request.urlopen", return_value=mock_response)

        console = rich.console.Console(force_terminal=False)
        updates = dep_updater.update_template_deps(template_path, dry_run=True, console=console)

        # パース可能な依存関係のみが処理される
        assert len(updates) == 1
        assert updates[0].package == "pytest"

    def test_update_template_deps_with_long_version(self, tmp_path, mocker):
        """長いバージョン文字列が正規化される場合"""
        template_path = tmp_path / "sections.toml"
        content = tomlkit.dumps(
            {
                "dependency-groups": {
                    "dev": [
                        "pytest>=8.0.0",
                    ]
                }
            }
        )
        template_path.write_text(content)

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "info": {"version": "2025.2.0.20251108"}  # 長いバージョン
            }
        ).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)
        mocker.patch("urllib.request.urlopen", return_value=mock_response)

        console = rich.console.Console(force_terminal=False)
        updates = dep_updater.update_template_deps(template_path, dry_run=True, console=console)

        assert len(updates) == 1
        assert updates[0].latest == "2025.2.0"  # 正規化されている

    def test_update_template_deps_default_console(self, template_file, mocker):
        """console が None の場合のデフォルト動作"""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps({"info": {"version": "8.0.0"}}).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)
        mocker.patch("urllib.request.urlopen", return_value=mock_response)

        # console=None でも動作することを確認
        updates = dep_updater.update_template_deps(template_file, dry_run=True, console=None)
        assert len(updates) == 2
