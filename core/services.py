from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
from core.models import Project, Container, Status
from infrastructure.filesystem import FileRepository
from infrastructure.docker_runner import DockerRunner
from infrastructure.hosts_loader import HostsLoader


TEMPLATE_VARS_SCHEMA = {
    "required": {
        "frontend_image": "str (e.g., 'nginx:latest')",
        "backend_image": "str (e.g., 'python:3.11')",
        "selected_host": "str (e.g., 'myapp.local')",
    },
    "optional": {
        "use_reverse_proxy": "bool (default: False)",
        "frontend_ports": "str (e.g., '8080:80', if not use_reverse_proxy)",
        "backend_ports": "str (e.g., '5000:5000', if not use_reverse_proxy)",
        "uses_redis": "bool (default: False)",
        "db_enabled": "bool (default: False, enables DB section)",
        "db_service": "str (e.g., 'postgres-db', if db_enabled)",
        "db_type": "str (one of 'postgres', 'mysql', 'mongo', if db_enabled)",
        "db_image": "str (e.g., 'postgres:15', if db_enabled)",
        "db_user": "str (if db_enabled)",
        "db_password": "str (if db_enabled)",
        "db_name": "str (if db_enabled)",
        "db_port": "str (e.g., '5432', if db_enabled)",
    },
}


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
        hosts: List[Tuple[str, str]] = None,
        template_vars: Optional[Dict[str, Any]] = None,
    ) -> Project:
        """
        Create a new project. Supports two modes:
        - Free-form: Provide containers and hosts (template_vars=None).
        - Template: Provide template_vars dict; ignores containers/hosts.
        
        Template vars must conform to TEMPLATE_VARS_SCHEMA for valid rendering.
        Required: frontend_image (str), backend_image (str), selected_host (str).
        Optional: use_reverse_proxy (bool), uses_redis (bool), db_enabled (bool), etc.
        Hosts: Template does not use extra_hosts; provide via free-form if needed.
        """
        path = root_path / name
        if template_vars is not None:
            # Template mode
            self.file_repo.create_compose(path, template_vars=template_vars)
        else:
            self.file_repo.create_compose(path, containers or [], hosts or [])
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