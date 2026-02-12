#project_router.py

"""
Project Router for Digital Twin IDE
Handles 3D model uploads, project persistence, and CRUD operations
"""

"""
Project Router for Digital Twin IDE - 100% Completion Version
Handles 3D model uploads, full project state persistence, and Explorer compatibility.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json
import hashlib
import shutil
import aiofiles

project_router = APIRouter(prefix="/api/projects", tags=["projects"])

# --- Configuration ---
UPLOAD_DIR = Path("uploads/models")
PROJECT_DIR = Path("data/projects")
LAST_STATE_FILE = PROJECT_DIR / "last_state.json"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_MODEL_EXTENSIONS = {".gltf", ".glb", ".obj", ".fbx", ".dae"}

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_DIR.mkdir(parents=True, exist_ok=True)

# --- Consolidated Pydantic Models ---

class CameraState(BaseModel):
    position: Dict[str, float]
    heading: float
    pitch: float
    roll: float

class UIState(BaseModel):
    currentFile: str = "main.js"
    sidebarCollapsed: bool = False
    activeTab: str = "explorer"

class ModelMetadata(BaseModel):
    name: str
    lon: float
    lat: float
    height: float
    fileName: str
    uniqueFileName: str
    fileSize: int
    timestamp: int

class EntityData(BaseModel):
    name: str
    id: str
    lon: float
    lat: float
    height: float
    type: str
    properties: Optional[Dict[str, Any]] = None

class ProjectData(BaseModel):
    version: int = 1
    name: str = "Untitled Project"
    savedAt: str
    scripts: Dict[str, str]  # Handles main.js, scene.js, etc.
    models: List[ModelMetadata]
    entities: List[EntityData] = []
    uiState: UIState
    cameraState: Optional[CameraState] = None

class ProjectListItem(BaseModel):
    id: str
    name: str
    lastSaved: str
    modelCount: int
    scriptCount: int

# --- Utility Functions ---

def generate_file_hash(file_content: bytes) -> str:
    return hashlib.sha256(file_content).hexdigest()

def sanitize_filename(filename: str) -> str:
    return "".join(c for c in filename if c.isalnum() or c in ('-', '_', '.')).rstrip()

# --- API Routes ---

@project_router.post("/upload-model")
async def upload_model(
    file: UploadFile = File(...),
    name: Optional[str] = Query(None),
    lon: float = Query(-74.0060),
    lat: float = Query(40.7128),
    height: float = Query(100.0)
):
    """Uploads a 3D model to persistent storage."""
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_MODEL_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type.")
    
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large.")
    
    file_hash = generate_file_hash(content)
    unique_filename = f"{file_hash[:16]}_{sanitize_filename(file.filename)}"
    file_path = UPLOAD_DIR / unique_filename
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    return {
        "success": True,
        "model": {
            "name": name or file.filename,
            "fileName": file.filename,
            "uniqueFileName": unique_filename,
            "url": f"/api/projects/models/{unique_filename}",
            "fileSize": len(content),
            "lon": lon,
            "lat": lat,
            "height": height,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
    }

@project_router.get("/models/{filename}")
async def get_model(filename: str):
    """Serves model files to the Cesium viewer."""
    file_path = UPLOAD_DIR / sanitize_filename(filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")
    return FileResponse(file_path)

@project_router.post("/save")
async def save_project(project: ProjectData, project_id: Optional[str] = Query(None)):
    """Saves the full project state including scripts and model metadata."""
    target_id = project_id or f"project_{int(datetime.now().timestamp())}"
    project_path = PROJECT_DIR / sanitize_filename(target_id)
    project_path.mkdir(parents=True, exist_ok=True)
    
    # Save main JSON state
    state_json = project.model_dump_json(indent=2)
    async with aiofiles.open(project_path / "project.json", 'w') as f:
        await f.write(state_json)
    
    # Update "Last State" for auto-load functionality
    async with aiofiles.open(LAST_STATE_FILE, 'w') as f:
        await f.write(state_json)
    
    # Persistence for the Explorer: Write individual script files
    scripts_dir = project_path / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    for filename, content in project.scripts.items():
        async with aiofiles.open(scripts_dir / sanitize_filename(filename), 'w') as f:
            await f.write(content)
            
    return {"success": True, "projectId": target_id, "message": "Project saved."}

@project_router.get("/load")
async def load_last_project():
    """Returns the most recently saved project for auto-restore."""
    if not LAST_STATE_FILE.exists():
        raise HTTPException(status_code=404, detail="No previous state found.")
    async with aiofiles.open(LAST_STATE_FILE, 'r') as f:
        return json.loads(await f.read())

@project_router.get("/load/{project_id}")
async def load_project(project_id: str):
    """Loads a specific project by ID."""
    project_file = PROJECT_DIR / sanitize_filename(project_id) / "project.json"
    if not project_file.exists():
        raise HTTPException(status_code=404, detail="Project not found.")
    async with aiofiles.open(project_file, 'r') as f:
        return json.loads(await f.read())

@project_router.get("/list")
async def list_projects():
    """Lists all projects for the project browser."""
    projects = []
    for d in PROJECT_DIR.iterdir():
        if d.is_dir() and (d / "project.json").exists():
            async with aiofiles.open(d / "project.json", 'r') as f:
                data = json.loads(await f.read())
                projects.append(ProjectListItem(
                    id=d.name,
                    name=data.get("name", "Untitled"),
                    lastSaved=data.get("savedAt", ""),
                    modelCount=len(data.get("models", [])),
                    scriptCount=len(data.get("scripts", {}))
                ))
    return sorted(projects, key=lambda x: x.lastSaved, reverse=True)

@project_router.get("/stats")
async def get_stats():
    """Returns storage usage statistics."""
    proj_size = sum(f.stat().st_size for f in PROJECT_DIR.rglob('*') if f.is_file())
    mod_size = sum(f.stat().st_size for f in UPLOAD_DIR.rglob('*') if f.is_file())
    return {
        "projects": len(list(PROJECT_DIR.iterdir())),
        "models": len(list(UPLOAD_DIR.iterdir())),
        "storageMB": round((proj_size + mod_size) / (1024 * 1024), 2)
    }