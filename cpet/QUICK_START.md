# 🎯 Integration Complete - Quick Start Guide

## ✅ What's Been Done

I've integrated your **arrhythmia detection ML model** with the **existing Next.js dashboard** and created a **complete FastAPI backend**.

### Files Modified/Created:

#### Backend
- ✅ **backend/main.py** - Complete REST API with 10 endpoints
- ✅ **backend/test_api.py** - API testing script
- ✅ **backend/requirements.txt** - Updated (needs updating, see below)

#### Dashboard  
- ✅ **web_dashboard/src/types/index.ts** - Added arrhythmia types
- ✅ **web_dashboard/src/lib/api.ts** - API client functions
- ✅ **web_dashboard/src/app/dashboard/page.tsx** - Real-time monitoring
- ✅ **web_dashboard/src/app/analysis/[id]/page.tsx** - Live session analysis
- ✅ **web_dashboard/.env.local** - Environment configuration

#### Documentation
- ✅ **INTEGRATION_README.md** - Complete setup guide

---

## 🚀 How to Run (Step-by-Step)

### Terminal 1: Start Backend

```powershell
# Navigate to backend
cd F:\Skill_WORK\CODE\CPET_system\backend

# Install requests (for testing)
pip install requests

# Start FastAPI server
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Expected output:**
```
INFO: Uvicorn running on http://127.0.0.1:8000
INFO: Application startup complete.
```

### Terminal 2: Start Dashboard

```powershell
# Navigate to dashboard
cd F:\Skill_WORK\CODE\CPET_system\web_dashboard

# Install dependencies (first time only)
npm install

# Start development server
npm run dev
```

**Expected output:**
```
  ▲ Next.js 16.1.1
  - Local:        http://localhost:3000
```

### Terminal 3: Test the System

```powershell
# Navigate to backend
cd F:\Skill_WORK\CODE\CPET_system\backend

# Run test script
python test_api.py
```

This will:
1. Create a test session
2. Send 5 sample heartbeat detections
3. Show you the session ID

---

## 📊 Dashboard Pages

### 1. Main Dashboard (`http://localhost:3000/dashboard`)

Shows:
- 🔌 Hardware connection status
- 📊 Active sessions count
- ❤️ Total heartbeats analyzed
- 🚨 Alert count
- 📈 Real-time AAMI class distribution (bar + pie charts)
- 📋 Detailed classification table with clinical significance

**Auto-refreshes every 2 seconds**

### 2. Live Session Analysis (`http://localhost:3000/analysis/[session_id]`)

Shows:
- 📉 Real-time confidence chart (last 50 beats)
- 🔴 Alert highlights for dangerous beats
- 📋 Live feed of latest 10 detections
- 📊 Session statistics summary

**Auto-refreshes every 1 second**

---

## 🔌 API Endpoints Created

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/status` | System status (sessions, hardware) |
| POST | `/api/devices/heartbeat` | Device ping |
| GET | `/api/devices/status` | Get device status |
| POST | `/api/sessions/start` | Start monitoring session |
| POST | `/api/sessions/{id}/stop` | Stop session |
| GET | `/api/sessions` | List all sessions |
| GET | `/api/sessions/{id}` | Get session details |
| POST | `/api/events` | Store prediction events |
| GET | `/api/sessions/{id}/events` | Get session events |
| GET | `/api/sessions/{id}/stats` | Get real-time stats |

Full API docs: `http://localhost:8000/docs`

---

## 🧪 Testing Without Hardware

### Option 1: Use FastAPI Docs Interface

1. Open `http://localhost:8000/docs`
2. Click `POST /api/sessions/start`
3. Click "Try it out"
4. Enter:
   ```json
   {
     "patient_id": "P001",
     "patient_name": "Test Patient",
     "age": 35,
     "gender": "Male"
   }
   ```
5. Click "Execute" → Copy the `session_id`
6. Use `POST /api/events` to send test heartbeats
7. Open dashboard and navigate to `/analysis/{session_id}`

### Option 2: Use Test Script

```powershell
cd backend
python test_api.py
```

This automatically:
- Creates a session
- Sends 5 sample predictions (3 Normal, 1 Supraventricular, 1 Ventricular)
- Shows the session ID
- You can then view it in the dashboard

---

## 🎨 AAMI Classification in Dashboard

| Class | Name | Color | Dashboard Display |
|-------|------|-------|-------------------|
| 0 | Normal | 🟢 Green | "✓ Healthy rhythm" |
| 1 | Supraventricular | 🟡 Yellow | "⚠ Monitor closely" |
| 2 | Ventricular | 🔴 Red | "🚨 DANGEROUS - Immediate attention" |
| 3 | Fusion | 🟣 Purple | "⚠ Atypical beat" |
| 4 | Unknown/Paced | 🔵 Blue | "ℹ Unclassified/Paced" |

---

## 🔮 Next Steps (When Ready for Hardware)

The system is **ready to receive data from real hardware**. When you're ready:

1. **Arduino**: Upload 360 Hz ECG sampling code
2. **Raspberry Pi**: Create Python edge agent that:
   - Reads from Arduino serial
   - Runs TFLite inference
   - POSTs to `/api/events`
3. **Model Conversion**: Convert your trained Keras model to TFLite

All backend endpoints are waiting for real data!

---

## 📡 Data Flow

```
Hardware (later)              Backend (now)           Dashboard (now)
─────────────────            ──────────────           ───────────────
AD8232 Sensor                                        
     ↓                                               
Arduino (360Hz)                                      
     ↓ (USB Serial)                                  
Raspberry Pi                                         
  - Read serial                                      
  - Preprocess                FastAPI                
  - TFLite inference    ←─────────────→     Next.js Dashboard
  - POST /api/events          (REST API)            (Polling every 1-2s)
                              
                              Stores:
                              - Sessions
                              - Events
                              - Statistics
```

---

## 🐛 Troubleshooting

### Backend won't start
```powershell
# Check if port 8000 is in use
netstat -ano | findstr :8000

# If occupied, use different port:
uvicorn main:app --reload --port 8001

# Update .env.local:
NEXT_PUBLIC_API_URL=http://localhost:8001
```

### Dashboard shows no data
1. ✅ Check backend is running: `http://localhost:8000/docs`
2. ✅ Check browser console for errors (F12)
3. ✅ Verify `.env.local` has correct API URL
4. ✅ Create test session using `/docs` or `test_api.py`

### CORS errors
- Already configured to allow all origins
- For production, update `allow_origins` in `main.py`

---

## 📝 Requirements Update Needed

Update `backend/requirements.txt`:
```
fastapi
uvicorn[standard]
pydantic
requests
```

Then run:
```powershell
pip install -r requirements.txt
```

---

## 🎓 What You Can Do Right Now

1. **✅ Start backend** → See FastAPI docs at `/docs`
2. **✅ Start dashboard** → See UI at `http://localhost:3000`
3. **✅ Run test script** → Create sample data
4. **✅ View in browser** → Navigate to `/analysis/{session_id}`
5. **✅ See real-time updates** → Dashboard auto-refreshes

**Everything is ready for testing!** 🎉

When you want to connect real hardware, just implement the Pi edge agent that POSTs to `/api/events` - the rest is done!
