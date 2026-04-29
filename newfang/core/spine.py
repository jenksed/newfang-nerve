from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Type, TypeVar
from enum import Enum
import networkx as nx
import json
import os

from newfang.models.uow import UnitOfWork, UoWState

# --- Node and Edge Models for the Project Spine ---

class NodeType(str, Enum):
    CODE = "Code"
    DOCUMENTATION = "Documentation"
    UOW = "UnitOfWork"
    DECISION = "Decision"
    TICKET = "Ticket" # Could be a specific type of UoW or a separate node

class EdgeType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    OWNS = "OWNS"
    ALIGNS_WITH = "ALIGNS_WITH"
    CHANGED_BY = "CHANGED_BY"
    BLOCKED_BY = "BLOCKED_BY"
    RELATED_TO = "RELATED_TO"
    IMPLEMENTS = "IMPLEMENTS"
    DOCUMENTS = "DOCUMENTS"
    REFERENCES = "REFERENCES"

class SpineNode(BaseModel):
    """
    Base model for any node in the Project Spine.
    """
    id: str = Field(..., description="Unique identifier for the node")
    type: NodeType = Field(..., description="Type of the node")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary properties of the node")

class CodeNode(SpineNode):
    type: NodeType = Field(NodeType.CODE, const=True)
    properties: Dict[str, Any] = Field(default_factory=dict, description="e.g., file_path, language, ast_hash, complexity_metrics")

class DocNode(SpineNode):
    type: NodeType = Field(NodeType.DOCUMENTATION, const=True)
    properties: Dict[str, Any] = Field(default_factory=dict, description="e.g., file_path, format, content_hash, semantic_summary")

class UoWNode(SpineNode):
    type: NodeType = Field(NodeType.UOW, const=True)
    # The properties of a UoWNode are directly derived from the UnitOfWork model
    properties: UnitOfWork = Field(..., description="The UnitOfWork model instance")

class DecisionNode(SpineNode):
    type: NodeType = Field(NodeType.DECISION, const=True)
    properties: Dict[str, Any] = Field(default_factory=dict, description="e.g., adr_id, decision_summary, rationale")

class SpineEdge(BaseModel):
    """
    Represents an edge (relationship) between two nodes in the Project Spine.
    """
    source: str = Field(..., description="ID of the source node")
    target: str = Field(..., description="ID of the target node")
    type: EdgeType = Field(..., description="Type of the relationship")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary properties of the edge (e.g., version, confidence)")

# --- Project Spine Graph Implementation ---

class ProjectSpine:
    """
    Manages the graph representation of the project's code, intent, and state.
    Uses networkx for in-memory graph operations and JSON for persistence.
    """
    def __init__(self, project_id: str, storage_path: str = ".newfang/spine"):
        self.project_id = project_id
        self.storage_path = os.path.join(storage_path, f"{project_id}_spine.json")
        self.graph = nx.MultiDiGraph() # MultiDiGraph allows multiple edges between same nodes
        self._load_spine()

    def _load_spine(self):
        """Loads the graph from storage, or initializes an empty graph."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.graph = nx.node_link_graph(data)
                print(f"Spine loaded from {self.storage_path}")
            except Exception as e:
                print(f"Error loading spine from {self.storage_path}: {e}. Initializing empty spine.")
                self.graph = nx.MultiDiGraph()
        else:
            print(f"No spine found at {self.storage_path}. Initializing empty spine.")
            self.graph = nx.MultiDiGraph()

    def save_spine(self):
        """Saves the current graph to storage."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(nx.node_link_data(self.graph), f, indent=2)
        print(f"Spine saved to {self.storage_path}")

    def add_node(self, node: SpineNode):
        """Adds a node to the graph."""
        if self.graph.has_node(node.id):
            # Update existing node properties
            self.graph.nodes[node.id].update(node.dict(exclude_unset=True))
        else:
            self.graph.add_node(node.id, **node.dict())
        self.save_spine()

    def get_node(self, node_id: str) -> Optional[SpineNode]:
        """Retrieves a node by its ID."""
        if self.graph.has_node(node_id):
            node_data = self.graph.nodes[node_id]
            node_type = NodeType(node_data.get("type"))
            if node_type == NodeType.CODE:
                return CodeNode(**node_data)
            elif node_type == NodeType.DOCUMENTATION:
                return DocNode(**node_data)
            elif node_type == NodeType.UOW:
                # Special handling for UoWNode to deserialize UnitOfWork
                node_data["properties"] = UnitOfWork(**node_data["properties"])
                return UoWNode(**node_data)
            elif node_type == NodeType.DECISION:
                return DecisionNode(**node_data)
            else:
                return SpineNode(**node_data)
        return None

    def add_edge(self, edge: SpineEdge):
        """Adds an edge to the graph."""
        if not self.graph.has_node(edge.source):
            print(f"Warning: Source node {edge.source} not found. Adding as generic node.")
            self.add_node(SpineNode(id=edge.source, type=NodeType.CODE)) # Default to CodeNode
        if not self.graph.has_node(edge.target):
            print(f"Warning: Target node {edge.target} not found. Adding as generic node.")
            self.add_node(SpineNode(id=edge.target, type=NodeType.CODE)) # Default to CodeNode
            
        self.graph.add_edge(edge.source, edge.target, key=edge.type.value, **edge.dict())
        self.save_spine()

    def get_edges(self, source: str, target: str, edge_type: Optional[EdgeType] = None) -> List[SpineEdge]:
        """Retrieves edges between two nodes, optionally filtered by type."""
        edges = []
        if self.graph.has_edge(source, target):
            for key, data in self.graph[source][target].items():
                if edge_type is None or EdgeType(key) == edge_type:
                    edges.append(SpineEdge(**data))
        return edges

    def get_neighbors(self, node_id: str, edge_type: Optional[EdgeType] = None) -> List[SpineNode]:
        """Retrieves direct neighbors of a node, optionally filtered by edge type."""
        neighbors = []
        if self.graph.has_node(node_id):
            for neighbor_id in self.graph.neighbors(node_id):
                # Check incoming edges for MultiDiGraph
                for key, data in self.graph[node_id][neighbor_id].items():
                    if edge_type is None or EdgeType(key) == edge_type:
                        if self.graph.has_node(neighbor_id):
                            neighbors.append(self.get_node(neighbor_id))
                            break # Only add once per neighbor, even if multiple edge types
        return [n for n in neighbors if n is not None]

    def get_all_nodes_by_type(self, node_type: NodeType) -> List[SpineNode]:
        """Retrieves all nodes of a specific type."""
        nodes = []
        for node_id in self.graph.nodes:
            node = self.get_node(node_id)
            if node and node.type == node_type:
                nodes.append(node)
        return nodes

    def get_uow_node(self, uow_id: str) -> Optional[UoWNode]:
        """Convenience method to get a UoWNode."""
        node = self.get_node(uow_id)
        if node and node.type == NodeType.UOW:
            return node
        return None

    def update_uow_node(self, uow: UnitOfWork):
        """Updates or adds a UoWNode based on a UnitOfWork instance."""
        uow_node = UoWNode(id=uow.id, properties=uow)
        self.add_node(uow_node)
        self.save_spine() # Save after update

# Example usage
if __name__ == "__main__":
    project_id = "test_project"
    spine_storage_path = ".newfang/spine_test"
    # Clean up previous test spine if it exists
    if os.path.exists(os.path.join(spine_storage_path, f"{project_id}_spine.json")):
        os.remove(os.path.join(spine_storage_path, f"{project_id}_spine.json"))

    spine = ProjectSpine(project_id=project_id, storage_path=spine_storage_path)

    # Add some nodes
    code_node = CodeNode(id="auth_module.py", properties={"file_path": "src/auth.py", "language": "python"})
    doc_node = DocNode(id="auth_spec.md", properties={"file_path": "docs/auth_spec.md", "format": "markdown"})
    
    uow_instance = UnitOfWork(
        id="UOW-AUTH-001",
        objective="Implement user authentication",
        acceptance_criteria=["User can login", "User can logout"],
        state=UoWState.DEFINED
    )
    uow_node = UoWNode(id=uow_instance.id, properties=uow_instance)

    decision_node = DecisionNode(id="ADR-001", properties={"title": "Auth Mechanism Choice", "decision": "OAuth2"})

    spine.add_node(code_node)
    spine.add_node(doc_node)
    spine.add_node(uow_node)
    spine.add_node(decision_node)

    # Add some edges
    spine.add_edge(SpineEdge(source="UOW-AUTH-001", target="auth_module.py", type=EdgeType.IMPLEMENTS))
    spine.add_edge(SpineEdge(source="auth_spec.md", target="UOW-AUTH-001", type=EdgeType.DOCUMENTS))
    spine.add_edge(SpineEdge(source="auth_module.py", target="ADR-001", type=EdgeType.REFERENCES))
    spine.add_edge(SpineEdge(source="auth_module.py", target="dependency_x.py", type=EdgeType.DEPENDS_ON)) # Target node not yet added

    # Test retrieval
    print("\n--- Nodes ---")
    retrieved_code = spine.get_node("auth_module.py")
    print(f"Retrieved Code Node: {retrieved_code.json(indent=2)}")
    
    retrieved_uow = spine.get_uow_node("UOW-AUTH-001")
    print(f"Retrieved UoW Node: {retrieved_uow.json(indent=2)}")
    assert retrieved_uow.properties.id == uow_instance.id

    print("\n--- Edges ---")
    uow_implements_edges = spine.get_edges("UOW-AUTH-001", "auth_module.py", EdgeType.IMPLEMENTS)
    print(f"UoW implements edges: {[e.json() for e in uow_implements_edges]}")

    print("\n--- Neighbors of auth_module.py ---")
    auth_neighbors = spine.get_neighbors("auth_module.py")
    for neighbor in auth_neighbors:
        print(f"- {neighbor.id} ({neighbor.type})")

    # Test update UoW
    uow_instance.state = UoWState.IN_PROGRESS
    spine.update_uow_node(uow_instance)
    updated_uow_node = spine.get_uow_node("UOW-AUTH-001")
    print(f"\nUpdated UoW state: {updated_uow_node.properties.state}")
    assert updated_uow_node.properties.state == UoWState.IN_PROGRESS

    # Test loading from saved state
    print("\n--- Loading new spine instance from saved state ---")
    new_spine = ProjectSpine(project_id=project_id, storage_path=spine_storage_path)
    assert new_spine.get_node("auth_module.py") is not None
    assert new_spine.get_uow_node("UOW-AUTH-001").properties.state == UoWState.IN_PROGRESS
    print("Spine successfully loaded and verified.")

    # Clean up test spine
    os.remove(os.path.join(spine_storage_path, f"{project_id}_spine.json"))
    os.rmdir(spine_storage_path)