## server.py
import asyncio
import time
import random
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .project_router import project_router
from .physics_engine import PhysicsEngine, Vector3  # Ensure correct import path

app = FastAPI()

# Setup Template and Static directories
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast(self, data: dict):
        for connection in self.active_connections:
            await connection.send_json(data)

manager = ConnectionManager()
physics = PhysicsEngine()

# The Heart of the Digital Twin: The Sync Loop
async def run_physics_loop():
    # Pre-add a test drone for the simulation
    physics.add_object("Drone_Alpha", [0, 100, 0], mass=1.5)
    
    while True:
        # 1. Update Physics (dt = 0.1s)
        current_time = time.time()
        # Note: Your physics_engine.py update() expects a dict with 'timestamp'
        state = physics.update({"timestamp": current_time})
        
        # 2. Add random sensor noise
        state["sensors"] = [
            {"id": "Lidar_1", "value": random.uniform(9.5, 10.5)},
            {"id": "Temp_1", "value": 22.4}
        ]
        
        # 3. Broadcast to all open browsers
        await manager.broadcast(state)
        await asyncio.sleep(0.1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_physics_loop())

@app.get("/")
async def get_ide(request: Request):
    return templates.TemplateResponse("digital_twin.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

app.include_router(project_router)