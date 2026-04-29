import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ProjectConfig(BaseModel):
    name: str = "New Project"
    root: str = "."
    docs_dir: str = "docs"
    code_dir: str = "src"

class ModelConfig(BaseModel):
    planner: str = "qwen2.5:14b"
    auditor: str = "llama3.1:8b"
    editor: str = "qwen2.5:7b"
    code_reader: str = "deepseek-coder:16b"
    embeddings: str = "nomic-embed-text"

class EndpointConfig(BaseModel):
    ollama: str = "http://localhost:11434"
    lm_studio: str = "http://localhost:1234/v1"

class AppConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    models: ModelConfig = Field(default_factory=ModelConfig)
    endpoints: EndpointConfig = Field(default_factory=EndpointConfig)

def load_config(root_path: str = ".") -> AppConfig:
    config_path = Path(root_path) / ".newfang" / "config.yaml"
    if not config_path.exists():
        return AppConfig()
    
    with open(config_path, "r") as f:
        data = yaml.safe_load(f) or {}
    
    # Map yaml keys to pydantic model if they differ slightly or just parse
    return AppConfig.model_validate(data)
