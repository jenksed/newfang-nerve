from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

class FileCategory(str, Enum):
    DOCUMENTATION = "documentation"
    CODE = "code"
    SYSTEM = "system"  # .newfang/
    CONFIG = "config"
    OTHER = "other"

class FileEntry(BaseModel):
    path: str
    category: FileCategory
    extension: str
    size: int
    last_modified: datetime
    summary: Optional[str] = None

class ProjectState(BaseModel):
    name: str
    root: str
    scanned_at: datetime = Field(default_factory=datetime.now)
    docs_files: List[FileEntry] = []
    code_files: List[FileEntry] = []
    system_files: List[FileEntry] = []
    stats: Dict[str, int] = {}

class DriftType(str, Enum):
    STALE_DOCS = "stale_docs"
    UNDOCUMENTED_CODE = "undocumented_code"
    MISSING_IMPLEMENTATION = "missing_implementation"

class DriftItem(BaseModel):
    title: str
    description: str
    severity: str  # High, Medium, Low
    type: DriftType
    related_files: List[str] = []

class DriftReport(BaseModel):
    project_name: str
    generated_at: datetime = Field(default_factory=datetime.now)
    items: List[DriftItem] = []
    score: int = 100  # 0-100 health score
