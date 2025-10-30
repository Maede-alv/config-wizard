from pathlib import Path
from typing import List, Optional

from core.models import Project, Container, Status
from infrastructure.docker_runner import DockerRunner
from infrastructure.filesystem import FileRepository


class ProjectService:
    def __init__(self, file_repo: FileRepository, docker_runner: DockerRunner):
        self.file_repo = file_repo
        self.docker_runner = docker_runner

    def list_projects(self, root_path: Path) -> List[Project]:
        dirs = self.file_repo.scan_directories(root_path)
        projects = []
        for d in dirs:
            project = self.file_repo.load_project(d)
            self._update_project_statuses(project)
            projects.append(project)
        return projects

    def _update_project_statuses(self, project: Project):
        project.container_statuses = self.docker_runner.get_container_statuses(project.path)
        if not project.container_statuses:
            project.status = Status.NOT_CREATED
        elif any(s == Status.RUNNING for s in project.container_statuses.values()):
            project.status = Status.RUNNING
        else:
            project.status = Status.STOPPED

    def refresh_all_statuses(self, projects: List[Project]):
        for project in projects:
            self._update_project_statuses(project)

    def create_project(
        self,
        name: str,
        root_path: Path,
        containers: List[Container] = None,
    ) -> Project:

        path = root_path / name
        self.file_repo.create_compose(path, containers or [])
        project = self.file_repo.load_project(path)
        self._update_project_statuses(project)
        return project

    def get_project(self, root_path: Path, name: str) -> Optional[Project]:
        if not name or ".." in name:
            return None
        project_path = root_path / name
        if not project_path.exists():
            return None
        project = self.file_repo.load_project(project_path)
        self._update_project_statuses(project)
        return project

    def update_project(self, project: Project):
        self.file_repo.save_project(project)

    def delete_project(self, project: Project):
        self.file_repo.delete_project(project.path)

    def start_project(self, project: Project):
        self.docker_runner.compose_up(project.path)

    def stop_project(self, project: Project):
        self.docker_runner.compose_down(project.path)