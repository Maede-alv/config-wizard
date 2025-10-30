import os
from pathlib import Path
from typing import Dict, List

import yaml

from core.models import Project, Container

DEFAULT_TEMPLATE = {
    "services": {
        "nginx": {
            "image": "nginx:latest",
            "ports": ["8080:80"],
            "restart": "unless-stopped",
        }
    },
}


class FileRepository:
    @staticmethod
    def scan_directories(root_path: Path):
        return [p for p in root_path.iterdir() if p.is_dir()]

    @staticmethod
    def validate_root_path(root_path: Path) -> bool:
        """Validate if root_path exists, is writable, and create if missing."""
        if root_path.exists():
            if not os.access(root_path, os.W_OK):
                return False
        else:
            try:
                root_path.mkdir(parents=True, exist_ok=True)
            except OSError:
                return False
        return True

    @staticmethod
    def load_project(path: Path) -> Project:
        compose_path = path / "docker-compose.yaml"
        if not compose_path.exists():
            return Project(path.name, path, containers=[])
        with open(compose_path) as f:
            yaml_data = yaml.safe_load(f)
        containers = []
        extra_hosts = {}
        for name, conf in yaml_data.get("services", {}).items():

            ports: Dict[str, str] = {}
            ports_list = conf.get("ports", [])
            for port_str in ports_list:
                if ":" in port_str:
                    host_port, cont_port = port_str.split(":", 1)
                    ports[host_port] = cont_port

            volumes: Dict[str, str] = {}
            volumes_list = conf.get("volumes", [])
            for vol_str in volumes_list:
                if ":" in vol_str:
                    host_vol, cont_vol = vol_str.split(":", 1)
                    volumes[host_vol] = cont_vol

            env: Dict[str, str] = conf.get("environment", {}) or {}

            depends_on: List[str] = conf.get("depends_on", [])

            containers.append(
                Container(
                    name=name,
                    image=conf.get("image", ""),
                    ports=ports,
                    volumes=volumes,
                    env=env,
                    depends_on=depends_on,
                    restart_policy=conf.get("restart", "unless-stopped"),
                )
            )
        project = Project(path.name, path, containers)
        project.extra_hosts = list(extra_hosts.items()) if extra_hosts else []
        return project

    @staticmethod
    def save_project(project: Project):
        services = {}
        for c in project.containers:
            service_conf = {
                "image": c.image,
                "ports": [f"{h}:{c}" for h, c in c.ports.items()],
                "volumes": [f"{h}:{c}" for h, c in c.volumes.items()],
                "depends_on": c.depends_on,
                "restart": c.restart_policy,
            }
            if c.env:
                service_conf["environment"] = c.env
            services[c.name] = service_conf
        yaml_data = {"services": services}
        with open(project.path / "docker-compose.yaml", "w") as f:
            yaml.safe_dump(yaml_data, f)

    @staticmethod
    def create_compose(path: Path, containers: List[Container] = None):
        path.mkdir(parents=True, exist_ok=True)
        compose_file = path / "docker-compose.yaml"

        services = {}
        for c in (containers or []):
            service_conf = {
                "image": c.image,
                "ports": [f"{h}:{c}" for h, c in c.ports.items()],
                "volumes": [f"{h}:{c}" for h, c in c.volumes.items()],
                "depends_on": c.depends_on,
                "restart": c.restart_policy,
            }
            if c.env:
                service_conf["environment"] = c.env
            services[c.name] = service_conf
        if not services:
            yaml.safe_dump(DEFAULT_TEMPLATE, open(compose_file, "w"))
        else:
            yaml_data = {"services": services}
            with open(compose_file, "w") as f:
                yaml.safe_dump(yaml_data, f)

    def create_default_compose(self, path: Path):
        self.create_compose(path, [])

    @staticmethod
    def delete_project(path: Path):
        if path.exists():
            for item in path.iterdir():
                if item.is_file():
                    item.unlink()
            path.rmdir()
