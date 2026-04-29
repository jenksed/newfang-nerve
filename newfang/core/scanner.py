import os
from pathlib import Path
from datetime import datetime
from typing import List, Set, Optional
from newfang.models.project import ProjectState, FileEntry, FileCategory

class Scanner:
    def __init__(self, root_path: str):
        self.root = Path(root_path).resolve()
        self.ignore_dirs = {
            ".git", "node_modules", "venv", ".venv", "__pycache__", 
            ".pytest_cache", ".DS_Store", "dist", "build"
        }
        self.doc_extensions = {".md", ".txt", ".pdf", ".adoc", ".rst"}
        self.code_extensions = {
            ".py", ".js", ".ts", ".tsx", ".go", ".rs", ".c", ".cpp", 
            ".h", ".java", ".rb", ".php", ".sh", ".yaml", ".yml", ".json"
        }

    def scan(self) -> ProjectState:
        state = ProjectState(
            name=self.root.name,
            root=str(self.root)
        )

        for current_root, dirs, files in os.walk(self.root):
            # Prune ignore directories
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            
            relative_root = Path(current_root).relative_to(self.root)
            
            # Skip if we are deep inside .newfang except for specific folders
            if ".newfang" in relative_root.parts:
                category_default = FileCategory.SYSTEM
            else:
                category_default = None

            for file in files:
                file_path = Path(current_root) / file
                rel_path = file_path.relative_to(self.root)
                
                category = self._categorize(rel_path, category_default)
                entry = self._create_file_entry(file_path, rel_path, category)

                if category == FileCategory.DOCUMENTATION:
                    state.docs_files.append(entry)
                elif category == FileCategory.CODE:
                    state.code_files.append(entry)
                elif category == FileCategory.SYSTEM:
                    state.system_files.append(entry)

        state.stats = {
            "docs_count": len(state.docs_files),
            "code_count": len(state.code_files),
            "system_count": len(state.system_files),
            "total_files": len(state.docs_files) + len(state.code_files) + len(state.system_files)
        }
        return state

    def _categorize(self, rel_path: Path, default: Optional[FileCategory]) -> FileCategory:
        if default:
            return default
        
        parts = rel_path.parts
        ext = rel_path.suffix.lower()

        if ".newfang" in parts:
            return FileCategory.SYSTEM
        
        # Heuristic: If it's in a 'docs' or 'documentation' or 'specs' folder
        if any(p.lower() in {"docs", "documentation", "specs", "notes"} for p in parts):
            if ext in self.doc_extensions:
                return FileCategory.DOCUMENTATION
        
        # Root level READMEs are always docs
        if len(parts) == 1 and rel_path.stem.upper() == "README":
            return FileCategory.DOCUMENTATION

        if ext in self.code_extensions:
            # Check if it might be a config file in code extensions (e.g. yaml)
            if ext in {".yaml", ".yml", ".json", ".toml"} and any(p.lower() == "config" for p in parts):
                 return FileCategory.CODE # Still code for now, maybe refined later
            return FileCategory.CODE
            
        return FileCategory.OTHER

    def _create_file_entry(self, full_path: Path, rel_path: Path, category: FileCategory) -> FileEntry:
        stat = full_path.stat()
        return FileEntry(
            path=str(rel_path),
            category=category,
            extension=full_path.suffix,
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime)
        )
