#!/usr/bin/env python3
# ruff: noqa: S101
"""
handlers/dockerfile.py のテスト
"""

import pytest

import py_project.config as config_module
import py_project.handlers.base as handlers_base
import py_project.handlers.dockerfile as handlers_dockerfile

TEMPLATE_DOCKER_STANDARD = """\
FROM {{ vars.ubuntu_image }}
WORKDIR /opt/{{ project.get_app_name() }}
{%- if project.docker.chrome %}
RUN install-chrome
{%- endif %}
CMD {{ project.docker.cmd | tojson }}
"""


@pytest.fixture
def docker_templates(tmp_templates):
    docker_dir = tmp_templates / "docker"
    docker_dir.mkdir()
    (docker_dir / "standard.j2").write_text(TEMPLATE_DOCKER_STANDARD)
    return tmp_templates


@pytest.fixture
def docker_config(tmp_project, docker_templates):
    return config_module.Config(
        defaults=config_module.Defaults(
            python_version="3.12",
            configs=["dockerfile"],
            vars={"ubuntu_image": "ubuntu:24.04@sha256:test"},
        ),
        template_dir=str(docker_templates),
        projects=[],
    )


def _make_context(docker_templates, docker_config):
    return handlers_base.ApplyContext(
        config=docker_config,
        template_dir=docker_templates,
        dry_run=False,
        backup=False,
    )


class TestDockerfileHandler:
    """DockerfileHandler のテスト"""

    def test_skipped_without_template(self, tmp_project, docker_templates, docker_config):
        """docker.template 未設定なら SKIPPED"""
        handler = handlers_dockerfile.DockerfileHandler()
        project = config_module.Project(name="test-project", path=str(tmp_project))

        result = handler.apply(project, _make_context(docker_templates, docker_config))

        assert result.status == handlers_base.ApplyStatus.SKIPPED
        assert not (tmp_project / "Dockerfile").exists()
        assert handler.diff(project, _make_context(docker_templates, docker_config)) is None

    def test_apply_standard(self, tmp_project, docker_templates, docker_config):
        """standard テンプレートの適用と変数展開"""
        handler = handlers_dockerfile.DockerfileHandler()
        project = config_module.Project(
            name="test-project",
            path=str(tmp_project),
            docker=config_module.DockerOptions(
                template="standard",
                app_name="myapp",
                chrome=True,
                cmd=["myapp", "-l"],
            ),
        )

        result = handler.apply(project, _make_context(docker_templates, docker_config))

        assert result.status == handlers_base.ApplyStatus.CREATED
        content = (tmp_project / "Dockerfile").read_text()
        assert "FROM ubuntu:24.04@sha256:test" in content
        assert "WORKDIR /opt/myapp" in content
        assert "RUN install-chrome" in content
        assert 'CMD ["myapp", "-l"]' in content

    def test_app_name_defaults_to_project_name(self, tmp_project, docker_templates, docker_config):
        """app_name 省略時はプロジェクト名が使われる"""
        handler = handlers_dockerfile.DockerfileHandler()
        project = config_module.Project(
            name="test-project",
            path=str(tmp_project),
            docker=config_module.DockerOptions(template="standard"),
        )

        handler.apply(project, _make_context(docker_templates, docker_config))

        content = (tmp_project / "Dockerfile").read_text()
        assert "WORKDIR /opt/test-project" in content
