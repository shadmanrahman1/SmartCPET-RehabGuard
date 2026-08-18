# CPET Arrhythmia Detection System - Integration Guide

## 🎯 What's Been Integrated

### Backend (FastAPI)
- **File Updated**: `backend/main.py`
- **New Endpoints**:
  - `POST /api/devices/heartbeat` - Device status ping
  - `GET /api/devices/status` - Get device status
  - `POST /api/sessions/start` - Start monitoring session
  - `POST /api/sessions/{id}/stop` - Stop session
  - `GET /api/sessions` - List all sessions
  - `GET /api/sessions/{id}` - Get session details
  - `POST /api/events` - Store prediction events
  - `GET /api/sessions/{id}/events` - Get session events
  - `GET /api/sessions/{id}/stats` - Get real-time statistics

### Dashboard (Next.js)
- **Files Updated/Created**:
  - `src/types/index.ts` - Added arrhythmia detection types
  - `src/lib/api.ts` - API utility functions
  - `src/app/dashboard/page.tsx` - Real-time monitoring dashboard
  - `src/app/analysis/[id]/page.tsx` - Live session analysis page
  - `.env.local` - Environment configuration

## 🚀 How to Run the System

### 1. Start Backend (FastAPI)

```powershell
# Navigate to backend directory
cd backend

# Activate virtual environment (if you have one)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install fastapi uvicorn pydantic

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will run at: `http://localhost:8000`

### 2. Start Dashboard (Next.js)

Open a new terminal:

```powershell
# Navigate to dashboard directory
cd web_dashboard

# Install dependencies (first time only)
npm install

# Run development server
npm run dev
```

Dashboard will run at: `http://localhost:3000`

## 📊 Dashboard Features

### Main Dashboard (`/dashboard`)
- **System Status**: Hardware connection, latency, active sessions
- **Real-time Stats**: Total beats analyzed, arrhythmia count, alert count
- **Active Session Info**: Patient details, session duration
- **Beat Classification Charts**: 
  - Bar chart showing AAMI class distribution
  - Pie chart showing percentage breakdown
- **Classification Table**: Detailed clinical significance for each class

### Session Analysis (`/analysis/[id]`)
- **Real-time Confidence Chart**: Last 50 beats with alert highlighting
- **Live Events Feed**: Latest 10 detections with timestamps
- **Session Statistics**: Total beats, arrhythmias, alerts, avg confidence
- **Stop Session Button**: End monitoring session

## 🔧 Testing the System

### 1. Test Backend API

```powershell
# Check if backend is running
curl http://localhost:8000/api/status
```

Expected response:
```json
{
  "status": "operational",
  "hardware_connected": false,
  "device_latency_ms": 0,
  "active_sessions": 0,
  "total_sessions": 0
}
```

### 2. Create a Test Session

You can use the FastAPI docs interface at `http://localhost:8000/docs`:

1. Click on `POST /api/sessions/start`
2. Click "Try it out"
3. Enter test data:
```json
{
  "patient_id": "P001",
  "patient_name": "Test Patient",
  "age": 35,
  "gender": "Male"
}
```
4. Click "Execute"
5. Copy the `session_id` from the response

### 3. Send Test Events

Use `POST /api/events` with:
```json
{
  "session_id": "YOUR_SESSION_ID_HERE",
  "events": [
    {
      "timestamp": "2026-01-13T10:30:00",
      "predicted_class": 0,
      "class_name": "Normal",
      "confidence": 0.98,
      "is_alert": false
    },
    {
      "timestamp": "2026-01-13T10:30:01",
      "predicted_class": 2,
      "class_name": "Ventricular",
      "confidence": 0.96,
      "is_alert": true
    }
  ]
}
```

### 4. View in Dashboard

1. Open `http://localhost:3000/dashboard`
2. You should see the active session
3. Click to view details or navigate to `/analysis/{session_id}`

## 📡 Data Flow

```
┌──────────────┐
│  AD8232 ECG  │
│   Sensor     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Arduino    │ ← (360 Hz sampling)
│   (Serial)   │
└──────┬───────┘
       │ USB
       ▼
┌──────────────────────────┐
│   Raspberry Pi / Laptop  │
│   - Serial reader        │
│   - Preprocessing        │
│   - TFLite inference     │
│   - HTTP POST to backend │
└──────┬───────────────────┘
       │ HTTP POST /api/events
       ▼
┌──────────────────────┐
│  FastAPI Backend     │
│  (localhost:8000)    │
│  - Session mgmt      │
│  - Event storage     │
│  - Statistics        │
└──────┬───────────────┘
       │ HTTP GET (polling every 1-2s)
       ▼
┌──────────────────────┐
│  Next.js Dashboard   │
│  (localhost:3000)    │
│  - Real-time charts  │
│  - Alert display     │
│  - Session history   │
└──────────────────────┘
```

## 🎨 AAMI Classification Classes

| Class | Name              | Color    | Clinical Significance          |
|-------|-------------------|----------|--------------------------------|
| 0     | Normal            | Green    | ✓ Healthy rhythm               |
| 1     | Supraventricular  | Yellow   | ⚠ Monitor closely              |
| 2     | Ventricular       | Red      | 🚨 DANGEROUS - Immediate care  |
| 3     | Fusion            | Purple   | ⚠ Atypical beat                |
| 4     | Unknown/Paced     | Blue     | ℹ Unclassified/Paced           |

## 🔜 Next Steps (Hardware Integration)

When you're ready to connect real hardware:

1. **Arduino Setup**: Upload ECG sampling code (360 Hz)
2. **Pi Edge Agent**: Python script for serial → inference → POST
3. **Model Conversion**: Convert Keras model to TFLite
4. **Testing**: Validate with real ECG signals

All backend endpoints are ready to receive data from your hardware!

## ⚙️ Configuration

### Backend Configuration
- Default port: `8000`
- CORS: Currently allows all origins (change for production)
- Storage: In-memory (replace with database for persistence)

### Dashboard Configuration
Edit `.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

For production, change to your server's IP/domain.

## 🐛 Troubleshooting

### Backend not connecting
- Check if port 8000 is available
- Verify `uvicorn` is installed
- Check firewall settings

### Dashboard not updating
- Verify backend is running at `http://localhost:8000`
- Check browser console for CORS errors
- Ensure `.env.local` has correct API URL

### No data showing
- Create a test session using `/docs` interface
- Send test events to verify data flow
- Check browser Network tab for API calls

## 📝 API Documentation

Full interactive API documentation available at:
`http://localhost:8000/docs`

This provides:
- All endpoint details
- Request/response schemas
- Try-it-out functionality
- Example payloads
