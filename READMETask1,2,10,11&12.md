Project README: Task 1, 2, 10, 11, & 12
This README summarizes the work completed for the Digital Twin IDE Core Infrastructure.

OpenQQuantify Digital Twin IDE - Phase 1 & 2
Overview

This project establishes a unified environment for simulating, monitoring, and managing digital twins. It integrates real-time physics, AI-driven insights, and a 3D geospatial interface.

Task 1 & 2: Unified Backend Architecture
Accomplishment: Consolidated fragmented Flask and FastAPI servers into a single FastAPI Unified Server (unified_server.py).

Key Features:

Modular Routing: Integrated project_router for CRUD operations.

Security: Implemented CORS and environment variable management via .env.

Performance: Switched to uvicorn with asyncio for high-concurrency WebSocket handling.

Task 10: Real-Time Physics Synchronization
Accomplishment: Integrated a custom Physics Engine (physics_engine.py) into the server's main loop.

Key Features:

Background Step: The server calculates gravity and velocity vectors for entities at 10Hz.

State Broadcasting: New coordinates are pushed automatically to the 3D frontend via WebSockets.

Task 11: Dynamic Entity & Sensor Management
Accomplishment: Created an extensible entity system (entities.js & sensors.js).

Key Features:

Metadata Injection: Entities carry physical properties (Mass, Friction) that the backend interprets.

Sensor Grids: Automated placement of sensor arrays across geospatial coordinates.

Simulation Manager: Client-side SensorManager that handles data buffering and noise simulation.

Task 12: Live Data Visualization (Dashboard)
Accomplishment: Built a high-performance telemetry dashboard inside the IDE.

Key Features:

Chart.js Integration: Real-time line graphs for Temperature, Humidity, and Pressure.

Live Tables: Scannable logs of sensor history with auto-pruning to prevent memory leaks.

Bidirectional Communication: Frontend can send commands back to the server to toggle sensor states.

Setup & Execution
Install Dependencies: pip install fastapi uvicorn aiofiles python-dotenv

Environment: Configure CESIUM_ION_TOKEN in the .env file.

Launch: python3 Server_Host.py


Access: Open http://127.0.0.1:5000 in a WebGL-compatible browser.
