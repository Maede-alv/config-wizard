from enum import Enum
from pathlib import Path
from typing import List, Dict, Tuple


class Status(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    NOT_CREATED = "not_created"


class Container:
    def __init__(
        self,
        name: str,
        image: str,
        ports: Dict[str, str] = None,
        volumes: Dict[str, str] = None,
        env: Dict[str, str] = None,
        depends_on: List[str] = None,
        restart_policy: str = "unless-stopped",
    ):
        self.name = name
        self.image = image
        self.ports = ports or {}
        self.volumes = volumes or {}
        self.env = env or {}
        self.depends_on = depends_on or []
        self.restart_policy = restart_policy


class Project:
    def __init__(self, name: str, path: Path, containers: List[Container] = None):
        self.name = name
        self.path = path
        self.containers = containers or []
        self.status = Status.NOT_CREATED
        self.container_statuses: Dict[str, Status] = {}
        self.extra_hosts: List[Tuple[str, str]] = []  # New: (ip, host) list