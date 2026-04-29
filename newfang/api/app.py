from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import json
from pathlib import Path

from newfang.core.scanner import Scanner
from newfang.utils.config import load_config
from newfang.models.project import ProjectState
from newfang.core.registry import ProjectRegistry
from newfang.utils.llm import LLMClient

app = FastAPI(
    title="NewFang Agency Tool",
    description="Local web command center for project planning and documentation.",
    version="0.1.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize registry and config
registry = ProjectRegistry()
global_config = load_config()

# Ensure Spine itself is always in the registry for this session
if "spine" not in registry.list_projects():
    registry.add_project("Spine", ".")

class AttachProjectRequest(BaseModel):
    name: str
    path: str

@app.get("/", response_class=HTMLResponse)
async def home():
    # Basic HTML for the dashboard
    return """
    <html>
        <head>
            <title>NewFang Agency Tool</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f4f7f6; }
                header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px; }
                h1 { color: #2c3e50; }
                .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
                .project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
                .status-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
                .status-online { background: #e7f4e4; color: #2e7d32; }
                button { background: #3498db; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
                button:hover { background: #2980b9; }
                .stats { font-size: 0.9em; color: #7f8c8d; }
                #attach-modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); align-items: center; justify-content: center; z-index: 100; }
                .modal-content { background: white; padding: 30px; border-radius: 8px; width: 400px; }
                .form-group { margin-bottom: 15px; }
                .form-group label { display: block; margin-bottom: 5px; }
                .form-group input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            </style>
        </head>
        <body>
            <header>
                <h1>NewFang Agency Tool</h1>
                <div><button onclick="document.getElementById('attach-modal').style.display='flex'">Attach New Project</button></div>
            </header>
            
            <div id="attach-modal">
                <div class="modal-content">
                    <h2>Attach New Project</h2>
                    <div class="form-group">
                        <label>Project Name</label>
                        <input type="text" id="proj-name" placeholder="e.g. My Awesome Repo">
                    </div>
                    <div class="form-group">
                        <label>Path to Root</label>
                        <input type="text" id="proj-path" placeholder="/Users/me/projects/my-repo">
                    </div>
                    <div style="text-align: right;">
                        <button style="background: #95a5a6;" onclick="document.getElementById('attach-modal').style.display='none'">Cancel</button>
                        <button onclick="attachProject()">Attach</button>
                    </div>
                </div>
            </div>

            <section>
                <h2>Active Projects</h2>
                <div class="project-grid" id="project-list">
                    <p>Loading projects...</p>
                </div>
            </section>

            <script>
                async function loadProjects() {
                    const response = await fetch('/api/projects');
                    const data = await response.json();
                    const container = document.getElementById('project-list');
                    container.innerHTML = '';
                    
                    data.projects.forEach(p => {
                        const card = document.createElement('div');
                        card.className = 'card';
                        card.innerHTML = `
                            <h3>${p.name}</h3>
                            <p class="stats">Root: ${p.root}</p>
                            <div style="margin-top: 10px;">
                                <span class="status-badge status-online">Attached</span>
                                <button style="float: right; padding: 5px 10px; font-size: 0.8em;" onclick="window.location.href='/project/${p.id}'">View Spine</button>
                            </div>
                        `;
                        container.appendChild(card);
                    });
                }

                async function attachProject() {
                    const name = document.getElementById('proj-name').value;
                    const path = document.getElementById('proj-path').value;
                    
                    const response = await fetch('/api/projects/attach', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name, path })
                    });
                    
                    if (response.ok) {
                        document.getElementById('attach-modal').style.display = 'none';
                        loadProjects();
                    } else {
                        alert('Failed to attach project. Check the path and try again.');
                    }
                }

                loadProjects();
            </script>
        </body>
    </html>
    """

@app.get("/api/projects")
async def api_list_projects():
    projects_list = []
    for pid, root in registry.list_projects().items():
        try:
            scanner = Scanner(root)
            state = scanner.scan()
            projects_list.append({
                "id": pid,
                "name": state.name,
                "root": root,
                "stats": state.stats
            })
        except Exception:
            continue
    return {"projects": projects_list}

@app.post("/api/projects/attach")
async def api_attach_project(req: AttachProjectRequest):
    path = Path(req.path)
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Path does not exist or is not a directory")
    
    project_id = registry.add_project(req.name, str(path.resolve()))
    return {"id": project_id, "status": "attached"}

@app.get("/project/{project_id}", response_class=HTMLResponse)
async def project_detail(project_id: str):
    projects = registry.list_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    root = projects[project_id]
    scanner = Scanner(root)
    state = scanner.scan()
    
    return f"""
    <html>
        <head>
            <title>{state.name} - NewFang</title>
            <style>
                body {{ font-family: -apple-system, sans-serif; display: flex; height: 100vh; margin: 0; background: #f9fafb; }}
                .sidebar {{ width: 350px; background: white; border-right: 1px solid #e5e7eb; display: flex; flex-direction: column; overflow-y: auto; }}
                .main {{ flex: 1; display: flex; flex-direction: column; }}
                .chat-container {{ flex: 1; display: flex; flex-direction: column; padding: 20px; overflow-y: auto; }}
                .chat-input-area {{ padding: 20px; background: white; border-top: 1px solid #e5e7eb; display: flex; gap: 10px; }}
                .message {{ margin-bottom: 15px; padding: 12px; border-radius: 8px; max-width: 80%; }}
                .message.user {{ align-self: flex-end; background: #3498db; color: white; }}
                .message.ai {{ align-self: flex-start; background: #f3f4f6; color: #1f2937; border: 1px solid #e5e7eb; }}
                input {{ flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 6px; outline: none; }}
                button {{ padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 6px; cursor: pointer; }}
                .sidebar-header {{ padding: 20px; border-bottom: 1px solid #eee; }}
                .file-item {{ padding: 8px 20px; font-size: 0.85em; color: #4b5563; border-bottom: 1px solid #f3f4f6; }}
                .file-item:hover {{ background: #f9fafb; }}
                h2 {{ font-size: 1em; padding: 10px 20px; background: #f3f4f6; margin: 0; }}
            </style>
        </head>
        <body>
            <div class="sidebar">
                <div class="sidebar-header">
                    <a href="/" style="font-size: 0.8em; color: #3498db; text-decoration: none;"><- Dashboard</a>
                    <h1 style="font-size: 1.2em; margin: 10px 0 0 0;">{state.name}</h1>
                    <p style="font-size: 0.7em; color: #6b7280; word-break: break-all;">{state.root}</p>
                </div>
                
                <h2>Documentation</h2>
                {" ".join([f'<div class="file-item">{f.path}</div>' for f in state.docs_files])}
                
                <h2 style="margin-top: 10px;">Code Modules</h2>
                {" ".join([f'<div class="file-item">{f.path}</div>' for f in state.code_files[:10]])}
                {f'<div class="file-item" style="font-style:italic">...and {len(state.code_files)-10} more</div>' if len(state.code_files) > 10 else ''}
            </div>
            
            <div class="main">
                <div class="chat-container" id="chat-box">
                    <div class="message ai">Welcome to the <b>{state.name}</b> Spine. How can I help you with your planning or documentation today?</div>
                </div>
                
                <div class="chat-input-area">
                    <input type="text" id="user-input" placeholder="Ask about the roadmap, architecture, or drift..." onkeypress="if(event.key === 'Enter') sendMessage()">
                    <button onclick="sendMessage()">Send</button>
                </div>
            </div>

            <script>
                const project_id = "{project_id}";
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const socket = new WebSocket(`${protocol}//${window.location.host}/ws/chat/${project_id}`);
                const chatBox = document.getElementById('chat-box');
                let currentAiMessage = null;

                socket.onmessage = function(event) {{
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'start') {{
                        currentAiMessage = document.createElement('div');
                        currentAiMessage.className = 'message ai';
                        currentAiMessage.innerHTML = '...';
                        chatBox.appendChild(currentAiMessage);
                        chatBox.scrollTop = chatBox.scrollHeight;
                    }} else if (data.type === 'chunk') {{
                        if (currentAiMessage.innerHTML === '...') currentAiMessage.innerHTML = '';
                        currentAiMessage.innerHTML += data.content.replace(/\\n/g, '<br>');
                        chatBox.scrollTop = chatBox.scrollHeight;
                    }} else if (data.type === 'end') {{
                        currentAiMessage = null;
                    }}
                }};

                function sendMessage() {{
                    const input = document.getElementById('user-input');
                    const text = input.value.trim();
                    if (!text) return;

                    const userMsg = document.createElement('div');
                    userMsg.className = 'message user';
                    userMsg.innerText = text;
                    chatBox.appendChild(userMsg);
                    chatBox.scrollTop = chatBox.scrollHeight;

                    socket.send(JSON.stringify({{ message: text }}));
                    input.value = '';
                }}
            </script>
        </body>
    </html>
    """

@app.websocket("/ws/chat/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await websocket.accept()
    
    projects = registry.list_projects()
    if project_id not in projects:
        await websocket.send_json({"type": "error", "content": "Project not found"})
        await websocket.close()
        return

    root = projects[project_id]
    scanner = Scanner(root)
    state = scanner.scan()
    
    # Simple context: Names of files
    context_files = [f.path for f in state.docs_files] + [f.path for f in state.code_files[:5]]
    
    client = LLMClient(base_url=global_config.endpoints.ollama, provider="ollama")
    
    try:
        while True:
            data = await websocket.receive_text()
            user_msg = json.loads(data)["message"]
            
            # Build a prompt with basic repo awareness
            prompt = f"Project: {state.name}\nFiles identified: {', '.join(context_files)}\n\nUser: {user_msg}\n\nAI:"
            
            await websocket.send_json({"type": "start"})
            
            async for chunk in client.stream_chat(
                model=global_config.models.planner,
                messages=[
                    {"role": "system", "content": "You are the NewFang Spine Agent. You help users plan and document their software projects based on the repo reality."},
                    {"role": "user", "content": prompt}
                ]
            ):
                await websocket.send_json({"type": "chunk", "content": chunk})
            
            await websocket.send_json({"type": "end"})
            
    except WebSocketDisconnect:
        print(f"Client disconnected from project {project_id}")
