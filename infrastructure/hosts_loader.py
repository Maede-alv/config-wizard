import re
from pathlib import Path
from typing import List, Tuple


class HostsLoader:
    @staticmethod
    def load_system_hosts() -> List[Tuple[str, str]]:
        """Parse /etc/hosts and return list of (ip, host) tuples."""
        hosts: List[Tuple[str, str]] = []
        hosts_file = Path("/etc/hosts")
        if not hosts_file.exists():
            return hosts
        try:
            with open(hosts_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = re.split(r"\s+", line, maxsplit=1)
                        if len(parts) >= 2:
                            ip, host_entry = parts
                            hosts_list = host_entry.split()
                            for host in hosts_list:
                                hosts.append((ip, host))
        except Exception:
            pass
        return hosts

    @staticmethod
    def parse_custom_hosts(input_str: str) -> List[Tuple[str, str]]:
        """Parse comma-separated 'ip:host' from string."""
        hosts: List[Tuple[str, str]] = []
        if not input_str:
            return hosts
        entries = [e.strip() for e in input_str.split(",") if e.strip()]
        for entry in entries:
            if ":" in entry:
                ip, host = entry.split(":", 1)
                hosts.append((ip.strip(), host.strip()))
        return hosts