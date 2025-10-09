from core.services import ProjectService
from infrastructure.filesystem import FileRepository
from infrastructure.docker_runner import DockerRunner
from infrastructure.config import ConfigManager
from ui.flet_app import launch_ui


def main():
    root_path = ConfigManager.load_root_path()
    file_repo = FileRepository()
    docker_runner = DockerRunner()
    service = ProjectService(file_repo, docker_runner)

    launch_ui(service, root_path)


if __name__ == "__main__":
    main()