import json
import subprocess
from pathlib import Path
from core.models import Status
from typing import Dict


class DockerRunner:
    def get_container_statuses(self, path: Path) -> Dict[str, Status]:
        statuses: Dict[str, Status] = {}
        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return statuses

            if not result.stdout.strip():
                return statuses

            containers_data = json.loads(result.stdout)
            if isinstance(containers_data, dict):
                containers_data = [containers_data]
            if not isinstance(containers_data, list):
                return statuses

            for cont in containers_data:
                service_name = cont.get("Service", "")
                if not service_name:
                    name = cont.get("Name", "")
                    service_name = name.split("_")[-2] if "_" in name and len(name.split("_")) > 2 else name
                state = cont.get("State", "").lower()
                if "running" in state or "up" in state:
                    statuses[service_name] = Status.RUNNING
                elif "exited" in state or "stopped" in state:
                    statuses[service_name] = Status.STOPPED
                else:
                    statuses[service_name] = Status.NOT_CREATED
        except (json.JSONDecodeError, subprocess.TimeoutExpired, Exception):
            pass
        return statuses

    def get_status(self, path: Path) -> Status:
        statuses = self.get_container_statuses(path)
        if not statuses:
            return Status.NOT_CREATED
        if any(s == Status.RUNNING for s in statuses.values()):
            return Status.RUNNING
        return Status.STOPPED

    def compose_up(self, path: Path):
        try:
            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, ["docker", "compose", "up", "-d"], result.stdout, result.stderr)
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise Exception("Docker up timed out—check if paused or heavy volumes.")
        except Exception as e:
            raise Exception(f"Docker up failed: {e}")

    def compose_down(self, path: Path):
        try:
            result = subprocess.run(
                ["docker", "compose", "down"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, ["docker", "compose", "down"], result.stdout, result.stderr)
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise Exception("Docker down timed out—check if paused or heavy volumes.")
        except Exception as e:
            raise Exception(f"Docker down failed: {e}")