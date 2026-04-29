import json
from pathlib import Path
from typing import Dict, List
import os

class ProjectRegistry:
    def __init__(self, storage_path: str = None):
        if storage_path is None:
            # Global registry for the user, stored in a standard location
            home = Path.home()
            self.storage_dir = home / ".gemini" / "tmp" / "spine" / "registry"
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self.storage_file = self.storage_dir / "projects.json"
        else:
            self.storage_file = Path(storage_path)
        
        self.projects: Dict[str, str] = self._load()

    def _load(self) -> Dict[str, str]:
        if not self.storage_file.exists():
            return {}
        try:
            with open(self.storage_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self):
        with open(self.storage_file, "w") as f:
            json.dump(self.projects, f, indent=2)

    def add_project(self, name: str, root_path: str):
        # Use a slugified name as the ID
        project_id = name.lower().replace(" ", "-")
        self.projects[project_id] = str(Path(root_path).resolve())
        self._save()
        return project_id

    def remove_project(self, project_id: str):
        if project_id in self.projects:
            del self.projects[project_id]
            self._save()

    def list_projects(self) -> Dict[str, str]:
        return self.projects
