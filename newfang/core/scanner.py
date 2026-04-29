import os
import ast
from typing import List, Dict, Any, Optional
from newfang.core.spine import ProjectSpine, CodeNode, DocNode, UoWNode, DecisionNode, SpineEdge, NodeType, EdgeType
from newfang.models.uow import UnitOfWork, UoWState

class Scanner:
    """
    Scans a repository, extracts information, and builds the Project Spine.
    """
    def __init__(self, project_id: str, repo_path: str, spine_storage_path: str = ".newfang/spine"):
        self.project_id = project_id
        self.repo_path = os.path.abspath(repo_path)
        self.spine = ProjectSpine(project_id=project_id, storage_path=spine_storage_path)
        self.file_parsers = {
            ".py": self._parse_python_file,
            ".md": self._parse_markdown_file,
            # Add more parsers for other file types (e.g., .js, .ts, .yaml, .json)
        }

    async def scan_repository(self) -> ProjectSpine:
        """
        Orchestrates the scanning process to build the Project Spine.
        """
        print(f"Scanning repository: {self.repo_path}")
        discovered_files = self._discover_files()

        for file_path in discovered_files:
            relative_path = os.path.relpath(file_path, self.repo_path)
            file_extension = os.path.splitext(file_path)[1]

            parser = self.file_parsers.get(file_extension)
            if parser:
                nodes, edges = await parser(file_path, relative_path)
                for node in nodes:
                    self.spine.add_node(node)
                for edge in edges:
                    self.spine.add_edge(edge)
            else:
                # Add as generic CodeNode if no specific parser, or skip
                self.spine.add_node(CodeNode(id=relative_path, properties={"file_path": relative_path}))

        # Placeholder for UoW ingestion (e.g., from a specific UoW tracking system or files)
        await self._extract_uows_from_source()

        self.spine.save_spine()
        print(f"Repository scan complete. Spine built with {len(self.spine.graph.nodes)} nodes and {len(self.spine.graph.edges)} edges.")
        return self.spine

    def _discover_files(self) -> List[str]:
        """
        Recursively discovers relevant files in the repository.
        """
        relevant_files = []
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                # Exclude common ignore patterns
                if any(ignore_dir in root for ignore_dir in ["/.git", "/node_modules", "/__pycache__", "/.newfang"]):
                    continue
                if file.startswith("."): # Ignore dotfiles
                    continue

                file_extension = os.path.splitext(file)[1]
                if file_extension in self.file_parsers:
                    relevant_files.append(os.path.join(root, file))
                elif file_extension == ".json" or file_extension == ".yaml": # Consider these for generic nodes
                     relevant_files.append(os.path.join(root, file))
        return relevant_files

    async def _parse_python_file(self, file_path: str, relative_path: str) -> (List[SpineNode], List[SpineEdge]):
        """
        Parses a Python file to extract AST information and dependencies.
        """
        nodes: List[SpineNode] = []
        edges: List[SpineEdge] = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = ast.parse(content)

            # Add the file itself as a CodeNode
            file_node = CodeNode(id=relative_path, properties={"file_path": relative_path, "language": "python"})
            nodes.append(file_node)

            # Extract imports (basic dependency mapping)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module_name = ""
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            module_name = node.module
                        else: # Relative import
                            # This is a simplified handling for relative imports
                            # A more robust solution would resolve against current file's path
                            module_name = "." * node.level + (node.module or "")

                    if module_name:
                        # Convert module name to a potential file path (heuristic)
                        # This is a very basic heuristic and needs significant improvement for real-world projects
                        dependency_id = module_name.replace('.', '/') + ".py"
                        edges.append(SpineEdge(source=relative_path, target=dependency_id, type=EdgeType.DEPENDS_ON))

                # Extract function/class definitions (can be added as sub-nodes or properties)
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    # For now, just add as properties to the file node or create sub-nodes
                    pass # Future: create sub-nodes for functions/classes

        except Exception as e:
            print(f"Error parsing Python file {relative_path}: {e}")
        
        return nodes, edges

    async def _parse_markdown_file(self, file_path: str, relative_path: str) -> (List[SpineNode], List[SpineEdge]):
        """
        Parses a Markdown file. For now, just adds it as a DocNode.
        Future: Extract headings, links, code blocks, etc.
        """
        nodes: List[SpineNode] = []
        edges: List[SpineEdge] = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            doc_node = DocNode(id=relative_path, properties={"file_path": relative_path, "format": "markdown", "content_preview": content[:200]})
            nodes.append(doc_node)
        except Exception as e:
            print(f"Error parsing Markdown file {relative_path}: {e}")
        return nodes, edges

    async def _extract_uows_from_source(self):
        """
        Placeholder for extracting Units of Work from a source (e.g., a specific file, API, or pattern).
        For this initial version, we'll simulate finding a UoW.
        """
        print("Simulating UoW extraction...")
        # In a real system, this would involve:
        # - Reading from a UoW tracking system API (Jira, Linear)
        # - Scanning specific files (e.g., .newfang/uows/*.yaml)
        # - Identifying UoW patterns in code comments or documentation

        # Simulate a UoW being found
        simulated_uow = UnitOfWork(
            id="UOW-SIM-001",
            objective="Implement user profile management",
            acceptance_criteria=["User can view profile", "User can edit profile"],
            state=UoWState.DEFINED,
            linked_code=["src/user_profile.py", "src/api/app.py"]
        )
        self.spine.update_uow_node(simulated_uow)
        print(f"Simulated UoW '{simulated_uow.id}' added to Spine.")

        # Simulate linking UoW to code
        self.spine.add_edge(SpineEdge(source=simulated_uow.id, target="src/user_profile.py", type=EdgeType.IMPLEMENTS))
        self.spine.add_edge(SpineEdge(source=simulated_uow.id, target="src/api/app.py", type=EdgeType.IMPLEMENTS))


# Example usage
if __name__ == "__main__":
    import asyncio
    
    # Create a dummy repository for testing
    test_repo_path = "test_repo"
    os.makedirs(os.path.join(test_repo_path, "src"), exist_ok=True)
    os.makedirs(os.path.join(test_repo_path, "docs"), exist_ok=True)
    os.makedirs(os.path.join(test_repo_path, "src/utils"), exist_ok=True)

    with open(os.path.join(test_repo_path, "src/main.py"), "w") as f:
        f.write("""
import os
from src.utils.helper import some_function

class MainApp:
    def __init__(self):
        pass

    def run(self):
        print("App running")
        some_function()
"""
)
    with open(os.path.join(test_repo_path, "src/utils/helper.py"), "w") as f:
        f.write("""
def some_function():
    print("Helper function called")
"""
)
    with open(os.path.join(test_repo_path, "docs/README.md"), "w") as f:
        f.write("# Test Project\nThis is a test project.")
    with open(os.path.join(test_repo_path, "config.yaml"), "w") as f:
        f.write("setting: value") # Will be added as generic CodeNode

    project_id = "test_scanner_project"
    spine_storage_path = ".newfang/spine_scanner_test"
    # Clean up previous test spine and repo if they exist
    if os.path.exists(os.path.join(spine_storage_path, f"{project_id}_spine.json")):
        os.remove(os.path.join(spine_storage_path, f"{project_id}_spine.json"))
    if os.path.exists(test_repo_path):
        import shutil
        shutil.rmtree(test_repo_path)
    
    # Recreate dummy repo
    os.makedirs(os.path.join(test_repo_path, "src"), exist_ok=True)
    os.makedirs(os.path.join(test_repo_path, "docs"), exist_ok=True)
    os.makedirs(os.path.join(test_repo_path, "src/utils"), exist_ok=True)
    with open(os.path.join(test_repo_path, "src/main.py"), "w") as f:
        f.write("""
import os
from src.utils.helper import some_function

class MainApp:
    def __init__(self):
        pass

    def run(self):
        print("App running")
        some_function()
"""
)
    with open(os.path.join(test_repo_path, "src/utils/helper.py"), "w") as f:
        f.write("""
def some_function():
    print("Helper function called")
"""
)
    with open(os.path.join(test_repo_path, "docs/README.md"), "w") as f:
        f.write("# Test Project\nThis is a test project.")
    with open(os.path.join(test_repo_path, "config.yaml"), "w") as f:
        f.write("setting: value")

    scanner = Scanner(project_id=project_id, repo_path=test_repo_path, spine_storage_path=spine_storage_path)

    async def run_scan():
        built_spine = await scanner.scan_repository()
        print(f"\nBuilt Spine has {len(built_spine.graph.nodes)} nodes and {len(built_spine.graph.edges)} edges.")

        # Verify nodes
        assert built_spine.get_node("src/main.py") is not None
        assert built_spine.get_node("docs/README.md") is not None
        assert built_spine.get_uow_node("UOW-SIM-001") is not None

        # Verify edges
        main_py_node = built_spine.get_node("src/main.py")
        assert main_py_node is not None
        
        # Check for dependency edge (simplified target name)
        dependency_edges = built_spine.get_edges("src/main.py", "src/utils/helper.py", EdgeType.DEPENDS_ON)
        assert len(dependency_edges) > 0

        # Check UoW implements edge
        uow_implements_edges = built_spine.get_edges("UOW-SIM-001", "src/user_profile.py", EdgeType.IMPLEMENTS)
        assert len(uow_implements_edges) > 0

        print("\nSpine verification successful!")

    asyncio.run(run_scan())

    # Clean up test repo and spine
    import shutil
    shutil.rmtree(test_repo_path)
    shutil.rmtree(spine_storage_path)