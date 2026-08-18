from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

app = FastAPI(title="KUET BME CPET System Backend")

# Allow CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Data Models ====================


class DeviceHeartbeat(BaseModel):
    device_id: str
    timestamp: datetime
    status: str  # "online", "offline", "error"
    latency_ms: Optional[float] = None


class SessionCreate(BaseModel):
    patient_id: str
    patient_name: str
    age: int
    gender: str


class Session(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    age: int
    gender: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str  # "active", "completed", "aborted"
    total_beats: int = 0
    arrhythmia_count: int = 0


class PredictionEvent(BaseModel):
    timestamp: datetime
    predicted_class: int
    class_name: str
    confidence: float
    is_alert: bool  # True if Class 2 (Ventricular) or confidence > 95%


class PredictionBatch(BaseModel):
    session_id: str
    events: List[PredictionEvent]


# ==================== In-Memory Storage (Replace with DB in production) ====================

# Device status tracking
device_status = {
    "device_id": "pi_ecg_01",
    "last_heartbeat": None,
    "status": "offline",
    "latency_ms": 0,
}

# Active sessions storage
sessions_db = {}  # {session_id: Session}
events_db = {}  # {session_id: [PredictionEvent]}

# ==================== Endpoints ====================


@app.get("/")
def read_root():
    return {"message": "Welcome to KUET BME CPET System Backend"}


@app.get("/api/status")
def get_status():
    """Get overall system status"""
    active_sessions = [s for s in sessions_db.values() if s.status == "active"]
    return {
        "status": "operational",
        "hardware_connected": device_status["status"] == "online",
        "device_latency_ms": device_status["latency_ms"],
        "active_sessions": len(active_sessions),
        "total_sessions": len(sessions_db),
    }


# ==================== Device Management ====================


@app.post("/api/devices/heartbeat")
async def device_heartbeat(heartbeat: DeviceHeartbeat):
    """Receive heartbeat ping from Pi/hardware device"""
    device_status["last_heartbeat"] = heartbeat.timestamp
    device_status["status"] = heartbeat.status
    device_status["latency_ms"] = heartbeat.latency_ms or 0
    return {"status": "acknowledged"}


@app.get("/api/devices/status")
async def get_device_status():
    """Get current device status"""
    return device_status


# ==================== Session Management ====================


@app.post("/api/sessions/start")
async def start_session(session_data: SessionCreate):
    """Start a new monitoring session"""
    session_id = str(uuid.uuid4())
    session = Session(
        id=session_id,
        patient_id=session_data.patient_id,
        patient_name=session_data.patient_name,
        age=session_data.age,
        gender=session_data.gender,
        start_time=datetime.now(),
        status="active",
    )
    sessions_db[session_id] = session
    events_db[session_id] = []
    return {"session_id": session_id, "session": session}


@app.post("/api/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop an active monitoring session"""
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions_db[session_id]
    session.end_time = datetime.now()
    session.status = "completed"
    return {"session": session}


@app.get("/api/sessions")
async def get_sessions(status: Optional[str] = None):
    """Get all sessions, optionally filtered by status"""
    sessions = list(sessions_db.values())
    if status:
        sessions = [s for s in sessions if s.status == status]
    return {"sessions": sorted(sessions, key=lambda x: x.start_time, reverse=True)}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get specific session details"""
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": sessions_db[session_id]}


# ==================== Event Storage & Retrieval ====================


@app.post("/api/events")
async def store_events(batch: PredictionBatch):
    """Store prediction events from Pi (batch processing)"""
    if batch.session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")

    # Store events
    events_db[batch.session_id].extend(batch.events)

    # Update session statistics
    session = sessions_db[batch.session_id]
    session.total_beats += len(batch.events)
    session.arrhythmia_count += sum(1 for e in batch.events if e.predicted_class != 0)

    return {
        "stored": len(batch.events),
        "session_total": session.total_beats,
        "arrhythmia_count": session.arrhythmia_count,
    }


@app.get("/api/sessions/{session_id}/events")
async def get_session_events(
    session_id: str, limit: Optional[int] = 100, offset: Optional[int] = 0
):
    """Get prediction events for a session (with pagination)"""
    if session_id not in events_db:
        raise HTTPException(status_code=404, detail="Session not found")

    events = events_db[session_id]
    total = len(events)
    paginated = events[offset : offset + limit] if limit else events[offset:]

    return {
        "session_id": session_id,
        "total_events": total,
        "returned": len(paginated),
        "events": paginated,
    }


@app.get("/api/sessions/{session_id}/stats")
async def get_session_stats(session_id: str):
    """Get real-time statistics for a session"""
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions_db[session_id]
    events = events_db.get(session_id, [])

    # Calculate class distribution
    class_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    for event in events:
        class_counts[event.predicted_class] = (
            class_counts.get(event.predicted_class, 0) + 1
        )

    # Calculate alert count
    alert_count = sum(1 for e in events if e.is_alert)

    return {
        "session": session,
        "class_distribution": {
            "Normal": class_counts[0],
            "Supraventricular": class_counts[1],
            "Ventricular": class_counts[2],
            "Fusion": class_counts[3],
            "Unknown_Paced": class_counts[4],
        },
        "alert_count": alert_count,
        "avg_confidence": sum(e.confidence for e in events) / len(events)
        if events
        else 0,
    }
