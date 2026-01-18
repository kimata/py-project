#!/usr/bin/env python3
# ruff: noqa: S101
"""gitlab_ci ハンドラのテスト"""

import textwrap

import pytest

import py_project.config
import py_project.handlers.base as handlers_base
import py_project.handlers.gitlab_ci as gitlab_ci


class TestGitLabCIHandler:
    """GitLabCIHandler のテスト"""

    @pytest.fixture
    def handler(self):
        """ハンドラインスタンスを作成"""
        return gitlab_ci.GitLabCIHandler()

    @pytest.fixture
    def sample_gitlab_ci_content(self):
        """サンプルの .gitlab-ci.yml 内容"""
        return textwrap.dedent("""\
            image: ubuntu:22.04

            stages:
              - test
              - deploy

            test:
              stage: test
              script:
                - echo "Running tests"

            renovate:
              image:
                name: renovate/renovate:latest
                entrypoint: [""]
              script:
                - renovate
        """)

    @pytest.fixture
    def project_with_gitlab_ci(self, tmp_path, sample_gitlab_ci_content):
        """GitLab CI ファイルを持つプロジェクトを作成"""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".gitlab-ci.yml").write_text(sample_gitlab_ci_content)
        return project_dir

    @pytest.fixture
    def config_with_edits(self, project_with_gitlab_ci, tmp_path):
        """編集設定を持つ Config を作成"""
        return py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={"registry": "registry.example.com", "tag": "v1.0.0"},
                gitlab_ci=py_project.config.GitlabCiOptions(
                    edits=[
                        py_project.config.GitlabCiEdit(
                            path="/image",
                            value="{{ vars.registry }}/ubuntu:{{ vars.tag }}",
                        ),
                    ]
                ),
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_with_gitlab_ci),
                )
            ],
        )

    @pytest.fixture
    def apply_context_with_edits(self, config_with_edits, tmp_path):
        """編集設定を持つ ApplyContext を作成"""
        return handlers_base.ApplyContext(
            config=config_with_edits,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )

    def test_handler_name(self, handler):
        """ハンドラ名のテスト"""
        assert handler.name == "gitlab-ci"

    def test_format_type(self, handler):
        """フォーマットタイプのテスト"""
        assert handler.format_type == handlers_base.FormatType.YAML

    def test_get_output_path(self, handler, project_with_gitlab_ci):
        """出力パスの取得テスト"""
        project = py_project.config.Project(
            name="test-project",
            path=str(project_with_gitlab_ci),
        )
        output_path = handler.get_output_path(project)
        assert output_path == project_with_gitlab_ci / ".gitlab-ci.yml"

    def test_get_line_number(self, handler, sample_gitlab_ci_content):
        """YAML パスから行番号を取得"""
        line_num = handler._get_line_number(sample_gitlab_ci_content, "/image")
        assert line_num == 0  # 最初の行

    def test_get_line_number_nested(self, handler, sample_gitlab_ci_content):
        """ネストされた YAML パスから行番号を取得"""
        line_num = handler._get_line_number(sample_gitlab_ci_content, "/renovate/image/name")
        assert line_num is not None

    def test_get_line_number_not_found(self, handler, sample_gitlab_ci_content):
        """存在しないパスの場合は None を返す"""
        line_num = handler._get_line_number(sample_gitlab_ci_content, "/nonexistent")
        assert line_num is None

    def test_replace_value_in_line(self, handler):
        """行内の値を置換"""
        original = "image: ubuntu:22.04"
        result = handler._replace_value_in_line(original, "new-image:latest")
        assert result == "image: new-image:latest"

    def test_replace_value_in_line_with_indent(self, handler):
        """インデントがある行の値を置換"""
        original = "    name: renovate/renovate:latest"
        result = handler._replace_value_in_line(original, "custom/renovate:v1")
        assert result == "    name: custom/renovate:v1"

    def test_replace_value_in_line_no_match(self, handler):
        """キー: 値形式でない行は変更なし"""
        original = "  - echo 'hello'"
        result = handler._replace_value_in_line(original, "new-value")
        assert result == original

    def test_apply_edits(self, handler, sample_gitlab_ci_content):
        """編集を適用"""
        edits = [py_project.config.GitlabCiEdit(path="/image", value="new-ubuntu:24.04")]
        result = handler._apply_edits(sample_gitlab_ci_content, edits)

        lines = result.splitlines()
        assert lines[0] == "image: new-ubuntu:24.04"

    def test_apply_edits_path_not_found(self, handler, sample_gitlab_ci_content, caplog):
        """存在しないパスへの編集は警告を出す"""
        edits = [py_project.config.GitlabCiEdit(path="/nonexistent", value="new-value")]
        handler._apply_edits(sample_gitlab_ci_content, edits)

        # 警告が出力されていることを確認
        assert "パス /nonexistent が見つかりません" in caplog.text

    def test_render_value_with_template(self, handler):
        """Jinja2 テンプレートをレンダリング"""
        vars_dict = {"registry": "registry.example.com", "tag": "v1.0.0"}
        result = handler._render_value("{{ vars.registry }}/image:{{ vars.tag }}", vars_dict)
        assert result == "registry.example.com/image:v1.0.0"

    def test_render_value_without_template(self, handler):
        """テンプレートでない値はそのまま返す"""
        vars_dict = {"registry": "registry.example.com"}
        result = handler._render_value("plain-value", vars_dict)
        assert result == "plain-value"

    def test_get_edits_with_defaults(self, handler, config_with_edits, apply_context_with_edits):
        """デフォルト設定から編集を取得"""
        project = config_with_edits.projects[0]
        edits = handler._get_edits(project, apply_context_with_edits)

        assert len(edits) == 1
        assert edits[0].path == "/image"
        assert edits[0].value == "registry.example.com/ubuntu:v1.0.0"

    def test_get_edits_with_project_override(self, handler, project_with_gitlab_ci, tmp_path):
        """プロジェクト固有の設定がデフォルトを上書き"""
        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={"registry": "default.registry.com"},
                gitlab_ci=py_project.config.GitlabCiOptions(
                    edits=[
                        py_project.config.GitlabCiEdit(path="/image", value="default:latest"),
                    ]
                ),
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_with_gitlab_ci),
                    gitlab_ci=py_project.config.GitlabCiOptions(
                        edits=[
                            py_project.config.GitlabCiEdit(path="/image", value="override:v2"),
                        ]
                    ),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        edits = handler._get_edits(project, context)

        assert len(edits) == 1
        assert edits[0].value == "override:v2"

    def test_get_edits_no_gitlab_ci_options(self, handler, project_with_gitlab_ci, tmp_path):
        """gitlab_ci オプションがない場合は空リスト"""
        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={},
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_with_gitlab_ci),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        edits = handler._get_edits(project, context)

        assert edits == []

    def test_generate_edited_content(self, handler, config_with_edits, apply_context_with_edits):
        """編集後の内容を生成"""
        project = config_with_edits.projects[0]
        result = handler._generate_edited_content(project, apply_context_with_edits)

        assert result is not None
        assert "registry.example.com/ubuntu:v1.0.0" in result

    def test_generate_edited_content_no_edits(self, handler, project_with_gitlab_ci, tmp_path):
        """編集がない場合は None を返す"""
        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={},
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_with_gitlab_ci),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        result = handler._generate_edited_content(project, context)

        assert result is None

    def test_diff_with_changes(self, handler, config_with_edits, apply_context_with_edits):
        """変更がある場合の差分"""
        project = config_with_edits.projects[0]
        diff = handler.diff(project, apply_context_with_edits)

        assert diff is not None
        assert "-image: ubuntu:22.04" in diff
        assert "+image: registry.example.com/ubuntu:v1.0.0" in diff

    def test_diff_no_changes(self, handler, project_with_gitlab_ci, tmp_path):
        """変更がない場合は None"""
        # 既に期待値と同じ内容に設定
        gitlab_ci_path = project_with_gitlab_ci / ".gitlab-ci.yml"
        gitlab_ci_path.write_text("image: expected:value\n")

        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={},
                gitlab_ci=py_project.config.GitlabCiOptions(
                    edits=[
                        py_project.config.GitlabCiEdit(path="/image", value="expected:value"),
                    ]
                ),
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_with_gitlab_ci),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        diff = handler.diff(project, context)

        assert diff is None

    def test_diff_file_not_found(self, handler, tmp_path):
        """ファイルが存在しない場合"""
        project_dir = tmp_path / "no-gitlab-ci"
        project_dir.mkdir()

        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={},
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_dir),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        diff = handler.diff(project, context)

        assert ".gitlab-ci.yml が見つかりません" in diff

    def test_diff_no_edits(self, handler, project_with_gitlab_ci, tmp_path):
        """編集がない場合は None"""
        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={},
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_with_gitlab_ci),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        diff = handler.diff(project, context)

        assert diff is None

    def test_apply_success(self, handler, config_with_edits, apply_context_with_edits):
        """正常な適用"""
        project = config_with_edits.projects[0]
        result = handler.apply(project, apply_context_with_edits)

        assert result.status == handlers_base.ApplyStatus.UPDATED

        # ファイルが更新されていることを確認
        output_path = handler.get_output_path(project)
        content = output_path.read_text()
        assert "registry.example.com/ubuntu:v1.0.0" in content

    def test_apply_file_not_found(self, handler, tmp_path):
        """ファイルが存在しない場合はスキップ"""
        project_dir = tmp_path / "no-gitlab-ci"
        project_dir.mkdir()

        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={},
                gitlab_ci=py_project.config.GitlabCiOptions(
                    edits=[
                        py_project.config.GitlabCiEdit(path="/image", value="new:value"),
                    ]
                ),
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_dir),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        result = handler.apply(project, context)

        assert result.status == handlers_base.ApplyStatus.SKIPPED
        assert ".gitlab-ci.yml が見つかりません" in result.message

    def test_apply_no_edits(self, handler, project_with_gitlab_ci, tmp_path):
        """編集がない場合はスキップ"""
        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={},
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_with_gitlab_ci),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        result = handler.apply(project, context)

        assert result.status == handlers_base.ApplyStatus.SKIPPED
        assert "edits が指定されていません" in result.message

    def test_apply_no_changes(self, handler, project_with_gitlab_ci, tmp_path):
        """変更がない場合は unchanged"""
        # 既に期待値と同じ内容に設定
        gitlab_ci_path = project_with_gitlab_ci / ".gitlab-ci.yml"
        gitlab_ci_path.write_text("image: expected:value\n")

        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={},
                gitlab_ci=py_project.config.GitlabCiOptions(
                    edits=[
                        py_project.config.GitlabCiEdit(path="/image", value="expected:value"),
                    ]
                ),
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_with_gitlab_ci),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        result = handler.apply(project, context)

        assert result.status == handlers_base.ApplyStatus.UNCHANGED

    def test_apply_dry_run(self, handler, config_with_edits, project_with_gitlab_ci, tmp_path):
        """dry_run モードでは実際に変更しない"""
        context = handlers_base.ApplyContext(
            config=config_with_edits,
            template_dir=tmp_path / "templates",
            dry_run=True,  # dry_run モード
            backup=False,
        )
        project = config_with_edits.projects[0]

        # 元の内容を保存
        output_path = handler.get_output_path(project)
        original_content = output_path.read_text()

        result = handler.apply(project, context)

        assert result.status == handlers_base.ApplyStatus.UPDATED
        # ファイルは変更されていない
        assert output_path.read_text() == original_content

    def test_apply_with_backup(self, handler, config_with_edits, project_with_gitlab_ci, tmp_path):
        """backup モードではバックアップを作成"""
        context = handlers_base.ApplyContext(
            config=config_with_edits,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=True,  # backup モード
        )
        project = config_with_edits.projects[0]

        result = handler.apply(project, context)

        assert result.status == handlers_base.ApplyStatus.UPDATED
        # バックアップファイルが作成されている
        backup_files = list(project_with_gitlab_ci.glob(".gitlab-ci.yml.bak*"))
        assert len(backup_files) >= 1

    def test_apply_validation_failure(self, handler, project_with_gitlab_ci, tmp_path, mocker):
        """バリデーション失敗時はエラー"""
        # validate メソッドをモックして失敗させる
        mocker.patch.object(
            handler,
            "validate",
            return_value=handlers_base.ValidationResult(
                is_valid=False, error_message="Invalid YAML structure"
            ),
        )

        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={},
                gitlab_ci=py_project.config.GitlabCiOptions(
                    edits=[
                        py_project.config.GitlabCiEdit(path="/image", value="new:value"),
                    ]
                ),
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_with_gitlab_ci),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        result = handler.apply(project, context)

        assert result.status == handlers_base.ApplyStatus.ERROR
        assert "バリデーション失敗" in result.message

    def test_diff_generate_edited_content_returns_none(
        self, handler, project_with_gitlab_ci, tmp_path, mocker
    ):
        """_generate_edited_content が None を返す場合の diff"""
        # _generate_edited_content をモックして None を返す
        mocker.patch.object(handler, "_generate_edited_content", return_value=None)

        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={},
                gitlab_ci=py_project.config.GitlabCiOptions(
                    edits=[
                        py_project.config.GitlabCiEdit(path="/image", value="new:value"),
                    ]
                ),
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_with_gitlab_ci),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        diff = handler.diff(project, context)

        # _generate_edited_content が None を返すので diff も None
        assert diff is None

    def test_apply_generate_edited_content_returns_none(
        self, handler, project_with_gitlab_ci, tmp_path, mocker
    ):
        """_generate_edited_content が None を返す場合の apply"""
        # _generate_edited_content をモックして None を返す
        mocker.patch.object(handler, "_generate_edited_content", return_value=None)

        config = py_project.config.Config(
            defaults=py_project.config.Defaults(
                python_version="3.12",
                configs=["gitlab-ci"],
                vars={},
                gitlab_ci=py_project.config.GitlabCiOptions(
                    edits=[
                        py_project.config.GitlabCiEdit(path="/image", value="new:value"),
                    ]
                ),
            ),
            template_dir=str(tmp_path / "templates"),
            projects=[
                py_project.config.Project(
                    name="test-project",
                    path=str(project_with_gitlab_ci),
                )
            ],
        )
        context = handlers_base.ApplyContext(
            config=config,
            template_dir=tmp_path / "templates",
            dry_run=False,
            backup=False,
        )
        project = config.projects[0]
        result = handler.apply(project, context)

        # _generate_edited_content が None を返すので unchanged
        assert result.status == handlers_base.ApplyStatus.UNCHANGED
