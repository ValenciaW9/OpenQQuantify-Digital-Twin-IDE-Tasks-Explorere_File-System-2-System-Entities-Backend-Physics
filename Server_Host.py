## Server_Host.py
"""
Flask server for the Digital Twin IDE.

- Serves templates/digital_twin.html
- Serves static files from /static
- Provides AI query endpoint (/ai_query) that uses ai_integration.ai_integration.AIEngine
- Provides a sensor list endpoint for the loader
"""

import os
import sys
import time
import json
import random
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Physics engine import
try:
    from physics.physics_engine import PhysicsEngine, Vector3
    PHYSICS_AVAILABLE = True
except:
    print("Physics engine not available")
    PHYSICS_AVAILABLE = False
    PhysicsEngine = None
    Vector3 = None

# Optional AI module
AI_ENGINE_AVAILABLE = False
try:
    from ai_integration.ai_integration import AIEngine
    AI_ENGINE_AVAILABLE = True
except Exception as e:
    print("AI integration module not found:", e)
    AIEngine = None

# Absolute paths for templates and static
BASE_DIR = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads" / "models"
PROJECT_DIR = BASE_DIR / "data" / "projects"

# Ensure directories exist
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_DIR.mkdir(parents=True, exist_ok=True)

# Flask app setup
app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR),
    static_folder=str(STATIC_DIR)
)
CORS(app)

# Config
CESIUM_ION_TOKEN = os.getenv("CESIUM_ION_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ============================================================================
# Helper: Mock sensor data generator
# ============================================================================
def generate_sensor_data():
    """Simulate sensor readings for the digital twin"""
    return {
        "timestamp": time.time(),
        "sensors": [
            {"id": "LiDAR_01", "type": "distance", "value": random.uniform(10, 50), "unit": "m"},
            {"id": "GPS_01", "type": "position", "lat": 34.05, "lon": -118.24},
            {"id": "Temp_01", "type": "temperature", "value": random.uniform(20, 30), "unit": "°C"}
        ]
    }

# ============================================================================
# Physics engine initialization
# ============================================================================
if PHYSICS_AVAILABLE:
    physics_engine = PhysicsEngine(gravity=-9.81)
    physics_engine.add_object("robot_01", Vector3(0, 5, 0), mass=50)
    physics_engine.add_object("robot_02", Vector3(2, 10, 1), mass=30)
else:
    physics_engine = None

# ============================================================================
# Flask Routes
# ============================================================================
@app.route("/")
def index():
    """Render main Digital Twin page"""
    template_file = TEMPLATE_DIR / "digital_twin.html"
    if template_file.exists():
        return render_template("digital_twin.html", cesium_ion_token=CESIUM_ION_TOKEN)
    else:
        return f"""
        <h1>Template Missing</h1>
        <p>Please create: <code>{template_file}</code></p>
        <p>Copy new_digital_twin.html to templates/digital_twin.html</p>
        """, 404

@app.route("/health")
def health():
    """Server health check"""
    return jsonify({
        "status": "ok",
        "ai_available": AI_ENGINE_AVAILABLE,
        "physics_available": PHYSICS_AVAILABLE
    })

@app.route("/sensor_list", methods=["GET"])
def sensor_list():
    """List sensor JS files"""
    sensor_dir = STATIC_DIR / "js" / "sensors"
    if not sensor_dir.exists():
        return jsonify({"sensors": [], "count": 0})
    files = [f.name for f in sensor_dir.glob("*.js")]
    return jsonify({"sensors": files, "count": len(files)})

@app.route("/ai_query", methods=["POST"])
def ai_query():
    """AI query endpoint"""
    payload = request.get_json(silent=True) or {}
    query = payload.get("query", "")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    if not AI_ENGINE_AVAILABLE:
        return jsonify({
            "message": f"AI module not configured. Echo: {query}",
            "success": False
        }), 200

    try:
        result = AIEngine.process_query(query)
        return jsonify({"message": result, "success": True})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

# ============================================================================
# Project Management Endpoints
# ============================================================================
@app.route("/api/projects/save", methods=["POST"])
def save_project():
    """Save project state"""
    try:
        data = request.get_json()
        project_id = f"project_{int(time.time() * 1000)}"
        project_file = PROJECT_DIR / f"{project_id}.json"
        
        with open(project_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Also save as "last" for auto-restore
        last_file = PROJECT_DIR / "last_project.json"
        with open(last_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({
            "success": True,
            "projectId": project_id,
            "message": "Project saved successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/api/projects/last", methods=["GET"])
def load_last_project():
    """Load the last saved project"""
    last_file = PROJECT_DIR / "last_project.json"
    if not last_file.exists():
        return jsonify({"success": False, "error": "No saved project found"}), 404
    
    try:
        with open(last_file, 'r') as f:
            project = json.load(f)
        return jsonify({"success": True, "project": project})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/projects/list", methods=["GET"])
def list_projects():
    """List all saved projects"""
    projects = []
    for f in PROJECT_DIR.glob("project_*.json"):
        try:
            with open(f, 'r') as fp:
                data = json.load(fp)
                projects.append({
                    "id": f.stem,
                    "name": data.get("name", "Untitled"),
                    "savedAt": data.get("savedAt", ""),
                })
        except:
            continue
    
    return jsonify({"success": True, "projects": projects})

@app.route("/api/models/upload", methods=["POST"])
def upload_model():
    """Handle 3D model upload"""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400
    
    # Get metadata
    name = request.form.get('name', file.filename)
    lon = float(request.form.get('lon', -74.0060))
    lat = float(request.form.get('lat', 40.7128))
    height = float(request.form.get('height', 100))
    
    # Save file
    timestamp = int(time.time() * 1000)
    filename = f"{timestamp}_{file.filename}"
    filepath = UPLOAD_DIR / filename
    file.save(filepath)
    
    return jsonify({
        "success": True,
        "model": {
            "name": name,
            "fileName": file.filename,
            "url": f"/uploads/models/{filename}",
            "lon": lon,
            "lat": lat,
            "height": height,
            "timestamp": timestamp
        }
    })

@app.route("/uploads/models/<filename>")
def serve_model(filename):
    """Serve uploaded model files"""
    return send_from_directory(UPLOAD_DIR, filename)

# ============================================================================
# SocketIO Setup
# ============================================================================
SOCKETIO_AVAILABLE = False
socketio = None

try:
    from flask_socketio import SocketIO, emit
    SOCKETIO_AVAILABLE = True
    
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode="threading",
        logger=False,
        engineio_logger=False
    )

    @socketio.on("connect")
    def handle_connect():
        print(f"Client connected: {request.sid}")
        emit("server_status", {
            "status": "connected",
            "message": "Digital Twin WebSocket Active"
        })

    @socketio.on("disconnect")
    def handle_disconnect():
        print(f"Client disconnected: {request.sid}")

    @socketio.on("request_data")
    def handle_request_data(data):
        """Handle sensor data requests"""
        sensor_data = generate_sensor_data()
        if physics_engine:
            try:
                physics_engine.update(1.0)
                emit("sensor_update", sensor_data)
            except:
                emit("sensor_update", sensor_data)
        else:
            emit("sensor_update", sensor_data)

    # Background sensor stream
    def background_sensor_stream():
        """Background task to emit sensor updates"""
        while True:
            try:
                sensor_data = generate_sensor_data()
                
                if physics_engine:
                    try:
                        physics_engine.update(1.0)
                        physics_state = {
                            **sensor_data,
                            "physics": {
                                "objects": list(physics_engine.objects.keys()) if hasattr(physics_engine, 'objects') else [],
                                "gravity": physics_engine.gravity
                            }
                        }
                    except Exception:
                        physics_state = sensor_data
                else:
                    physics_state = sensor_data
                
                # Updated: emit to all clients (no broadcast)
                socketio.emit("sensor_update", physics_state)
                
                socketio.sleep(1)
            except Exception as e:
                print(f"Error in background stream: {e}")
                socketio.sleep(1)

except ImportError:
    print("Flask-SocketIO not installed, WebSocket disabled")

# ============================================================================
# Startup
# ============================================================================
def print_startup_banner(host, port):
    print("\n" + "="*60)
    print("🚀 OPENQQUANTIFY DIGITAL TWIN SERVER")
    print("="*60)
    print(f"Server URL: http://{host}:{port}")
    print(f"WebSocket: {'Enabled' if SOCKETIO_AVAILABLE else 'Disabled'}")
    print(f"Physics: {'Enabled' if PHYSICS_AVAILABLE else 'Disabled'}")
    print(f"AI: {'Enabled' if AI_ENGINE_AVAILABLE else 'Disabled'}")
    print("="*60)
    print(f"\n📁 Upload directory: {UPLOAD_DIR}")
    print(f"📁 Project directory: {PROJECT_DIR}")
    print(f"📁 Template directory: {TEMPLATE_DIR}")
    print("="*60 + "\n")

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))

    print_startup_banner(host, port)

    if SOCKETIO_AVAILABLE and socketio:
        # Start background physics + sensor updates
        socketio.start_background_task(background_sensor_stream)
        socketio.run(app, host=host, port=port, debug=False, use_reloader=False)
    else:
        app.run(host=host, port=port, debug=False)

