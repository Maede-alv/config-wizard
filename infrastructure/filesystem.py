import yaml
import os
import re
from pathlib import Path
from core.models import Project, Container
from typing import Dict, List, Tuple, Optional, Any
from jinja2 import Template, TemplateError


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
    def scan_directories(self, root_path: Path):
        return [p for p in root_path.iterdir() if p.is_dir()]

    def validate_root_path(self, root_path: Path) -> bool:
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

    def render_template(self, template_name: str, vars_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Render a Jinja2 template to YAML dict. Includes basic validation."""

        full_template_path = Path(__file__).parent.parent / "templates" / template_name
        if not full_template_path.exists():
            raise FileNotFoundError(f"Template not found: {full_template_path}. Create templates/{template_name} with your Jinja2 content.")

        required_vars = {
            'frontend_image': str,
            'backend_image': str,
            'selected_host': str,
        }
        optional_bools = ['use_reverse_proxy', 'uses_redis']
        optional_db = ['db_service', 'db_type', 'db_image', 'db_user', 'db_password', 'db_name', 'db_port']
        
        for var_name, var_type in required_vars.items():
            if var_name not in vars_dict or not isinstance(vars_dict[var_name], var_type):
                raise ValueError(f"Missing or invalid required var: {var_name} (type: {var_type})")
        
        if 'use_reverse_proxy' in vars_dict and isinstance(vars_dict['use_reverse_proxy'], bool) and vars_dict['use_reverse_proxy']:
            if not re.match(r'^[a-zA-Z0-9.-]+$', vars_dict['selected_host']):
                raise ValueError("Invalid selected_host format for reverse proxy (must be valid domain).")
        
        port_regex = r'^[0-9]+:[0-9]+$'
        if 'frontend_ports' in vars_dict and not re.match(port_regex, vars_dict['frontend_ports']):
            raise ValueError("Invalid frontend_ports format (e.g., '8080:80').")
        if 'backend_ports' in vars_dict and not re.match(port_regex, vars_dict['backend_ports']):
            raise ValueError("Invalid backend_ports format (e.g., '5000:5000').")

        image_regex = r'^[a-z0-9.-]+(?:/[a-z0-9.-]+)?(:[a-z0-9.-]+)?$'
        if 'frontend_image' in vars_dict and not re.match(image_regex, vars_dict['frontend_image']):
            raise ValueError("Invalid frontend_image format (e.g., 'nginx:latest').")
        if 'backend_image' in vars_dict and not re.match(image_regex, vars_dict['backend_image']):
            raise ValueError("Invalid backend_image format (e.g., 'python:3.11').")

        try:
            with open(full_template_path, 'r') as f:
                template = Template(f.read())
            rendered_str = template.render(**vars_dict)
            yaml_data = yaml.safe_load(rendered_str)
            if not isinstance(yaml_data, dict):
                raise ValueError("Rendered template is not valid YAML dict.")
            return yaml_data
        except TemplateError as e:
            raise ValueError(f"Jinja2 rendering failed: {str(e)}")
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parsing failed after rendering: {str(e)}")

    def load_project(self, path: Path) -> Project:
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

            service_hosts = conf.get("extra_hosts", {})
            if service_hosts and not extra_hosts:
                extra_hosts = {host: ip for ip, host in service_hosts.items()}

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

    def save_project(self, project: Project):
        services = {}
        extra_hosts = {host: ip for ip, host in project.extra_hosts}
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
            if extra_hosts:
                service_conf["extra_hosts"] = extra_hosts
            services[c.name] = service_conf
        yaml_data = {"version": "3", "services": services}
        with open(project.path / "docker-compose.yaml", "w") as f:
            yaml.safe_dump(yaml_data, f)

    def create_compose(self, path: Path, containers: List[Container] = None, hosts: List[Tuple[str, str]] = None, template_vars: Optional[Dict[str, Any]] = None):
        path.mkdir(parents=True, exist_ok=True)
        compose_file = path / "docker-compose.yaml"
        
        if template_vars is not None:
            # Template mode
            yaml_data = self.render_template("fullstack.j2", template_vars)
            with open(compose_file, "w") as f:
                yaml.safe_dump(yaml_data, f)
        else:
            services = {}
            extra_hosts_dict = {host: ip for ip, host in (hosts or [])}  # {host: ip}
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
                if extra_hosts_dict:
                    service_conf["extra_hosts"] = extra_hosts_dict
                services[c.name] = service_conf
            if not services:
                yaml.safe_dump(DEFAULT_TEMPLATE, open(compose_file, "w"))
            else:
                yaml_data = {"version": "3", "services": services}
                with open(compose_file, "w") as f:
                    yaml.safe_dump(yaml_data, f)

    def create_default_compose(self, path: Path):
        self.create_compose(path, [], [])

    def delete_project(self, path: Path):
        if path.exists():
            for item in path.iterdir():
                if item.is_file():
                    item.unlink()
            path.rmdir()
