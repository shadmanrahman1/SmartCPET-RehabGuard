# Real-time ECG Dashboard - Setup Guide

## 🎯 Overview

This dashboard connects to your Raspberry Pi ECG server via Socket.IO to display:
- **Real-time ECG waveform** at 360Hz sampling rate
- **AI-powered arrhythmia predictions** with confidence scores
- **Live statistics** and beat classification distribution
- **Critical alerts** for dangerous arrhythmias

---

## 📋 Prerequisites

### On Raspberry Pi:
- ✅ `pi_server.py` running on the Pi
- ✅ Arduino connected via USB with ECG sensor
- ✅ AI model loaded (`arrhythmia_cnn_final.keras`)
- ✅ Server accessible at: `http://192.168.1.101:5000` (or your Pi's IP)

### On Laptop:
- Node.js 18+ installed
- This Next.js dashboard

---

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
cd web_dashboard
npm install
```

This installs all required packages including `socket.io-client`.

### Step 2: Configure Pi Server URL

Create a `.env.local` file in the `web_dashboard` folder:

```bash
cp .env.local.example .env.local
```

Edit `.env.local` and set your Raspberry Pi's IP address:

```env
NEXT_PUBLIC_PI_SERVER_URL=http://192.168.1.101:5000
```

**Important:** Replace `192.168.1.101` with your actual Raspberry Pi IP address.

### Step 3: Start the Dashboard

```bash
npm run dev
```

The dashboard will be available at: `http://localhost:3000`

### Step 4: Navigate to ECG Monitor

Open your browser and go to:
```
http://localhost:3000/ecg-monitor
```

Or click **"ECG Monitor"** in the sidebar navigation.

---

## 🎨 Features

### 1. **Connection Status**
- Real-time connection indicator (Green = Connected, Red = Disconnected)
- Server status: Arduino connection, AI model status, uptime
- Latency and performance metrics

### 2. **Live ECG Waveform**
- Smooth real-time plotting at 360Hz
- Auto-scaling Y-axis
- Grid background for medical chart appearance
- Displays last ~3 seconds of data (1000 samples)

### 3. **AI Predictions**
Every 0.5 seconds, the dashboard shows:
- **Classification**: Normal, Supraventricular, Ventricular, Fusion, or Unknown/Paced
- **Confidence**: Percentage (0-100%)
- **Alert Status**: Red border and warning for critical arrhythmias
- Color-coded by severity

### 4. **Statistics Dashboard**
- **Total Beats Analyzed**
- **Predictions per Second** (processing speed)
- **Alert Count** (critical events)
- **Bar Chart**: Beat distribution by classification
- **Pie Chart**: Percentage breakdown

---

## 🔧 Configuration Options

### Change Server URL (Dynamic)
Edit [`src/lib/ecg-config.ts`](src/lib/ecg-config.ts):

```typescript
export const ECG_SERVER_CONFIG = {
  url: process.env.NEXT_PUBLIC_PI_SERVER_URL || 'http://192.168.1.101:5000',
  // ... other options
}
```

### Adjust Chart Performance
In [`src/lib/ecg-config.ts`](src/lib/ecg-config.ts):

```typescript
chart: {
  maxDataPoints: 1000,  // Number of samples to keep (affects memory)
  updateInterval: 50,   // Chart refresh rate in ms
}
```

- **Increase `maxDataPoints`** for longer history (uses more memory)
- **Decrease `updateInterval`** for smoother animation (uses more CPU)

### Customize Arrhythmia Colors
In [`src/lib/ecg-config.ts`](src/lib/ecg-config.ts):

```typescript
export const ARRHYTHMIA_CLASSES = {
  0: { name: 'Normal', color: '#22c55e', severity: 'low' },
  1: { name: 'Supraventricular', color: '#f59e0b', severity: 'medium' },
  // ... customize colors here
}
```

---

## 📡 Socket.IO Events

### Events Received from Pi:

| Event | Frequency | Description |
|-------|-----------|-------------|
| `server_status` | On connect | Server health info |
| `ecg_raw` | 360/sec | Raw ECG amplitude value |
| `prediction` | 2/sec | AI classification result |
| `statistics` | On request | Aggregated statistics |

### Events Sent to Pi:

| Event | Purpose |
|-------|---------|
| `request_statistics` | Get current stats |

---

## 🏗️ Project Structure

```
web_dashboard/
├── src/
│   ├── app/
│   │   └── ecg-monitor/
│   │       └── page.tsx              # Main ECG monitor page
│   ├── components/
│   │   └── ecg/
│   │       ├── ECGWaveform.tsx       # Real-time waveform chart
│   │       ├── PredictionDisplay.tsx # AI prediction card
│   │       └── ECGStatisticsDisplay.tsx # Stats dashboard
│   ├── lib/
│   │   ├── useECGSocket.ts           # Socket.IO hook
│   │   └── ecg-config.ts             # Configuration
│   └── types/
│       └── index.ts                  # TypeScript types
└── .env.local                         # Environment config
```

---

## 🐛 Troubleshooting

### ❌ "Disconnected" Status

**Problem:** Dashboard shows disconnected.

**Solutions:**
1. Check if Pi server is running:
   ```bash
   # On Raspberry Pi
   python3 pi_server.py
   ```

2. Verify Pi IP address:
   ```bash
   # On Raspberry Pi
   hostname -I
   ```

3. Test connection manually:
   ```bash
   # On your laptop
   curl http://192.168.1.101:5000
   ```

4. Check firewall settings on Pi:
   ```bash
   sudo ufw allow 5000
   ```

### ❌ CORS Errors in Browser Console

**Problem:** Browser blocks Socket.IO connection.

**Solution:** The Pi server already has CORS enabled for all origins:
```python
socketio = SocketIO(app, cors_allowed_origins="*")
```

If issues persist, explicitly add your laptop's IP in `pi_server.py`.

### ❌ No ECG Data Appearing

**Problem:** Connected but no waveform.

**Solutions:**
1. Check Arduino connection on Pi:
   ```bash
   # On Raspberry Pi
   ls /dev/ttyUSB*
   # Should show /dev/ttyUSB0 or similar
   ```

2. Verify Arduino is sending data:
   ```bash
   # On Raspberry Pi
   cat /dev/ttyUSB0
   # Should see streaming numbers
   ```

3. Check Pi server logs for errors

### ❌ Slow/Choppy Waveform

**Problem:** Chart stutters or lags.

**Solutions:**
1. Reduce `maxDataPoints` in config (e.g., 500 instead of 1000)
2. Increase `updateInterval` (e.g., 100ms instead of 50ms)
3. Check network latency between laptop and Pi
4. Close other browser tabs/applications

---

## 🔐 Network Setup

### Same WiFi Network
Both devices must be on the same network:
- **Pi**: Connect to WiFi (e.g., `YourHomeWiFi`)
- **Laptop**: Connect to same WiFi

### Find Pi IP Address
```bash
# On Raspberry Pi
hostname -I
# Example output: 192.168.1.101
```

### Static IP (Recommended)
To prevent IP changes, set static IP on Pi:

Edit `/etc/dhcpcd.conf`:
```
interface wlan0
static ip_address=192.168.1.101/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8
```

---

## 🎓 Usage Tips

1. **Start Pi server first**, then open dashboard
2. **Refresh statistics** manually using the button for latest data
3. **Clear data** button resets the chart (useful for new sessions)
4. **Watch for alerts**: Red borders indicate critical arrhythmias
5. **Monitor confidence**: Low confidence (<50%) may need review

---

## 🚦 Production Deployment

### Build for Production
```bash
npm run build
npm run start
```

### Environment Variables
Set in production environment:
```env
NEXT_PUBLIC_PI_SERVER_URL=http://your-pi-ip:5000
```

### Security Considerations
1. Use HTTPS/WSS in production
2. Implement authentication on Pi server
3. Restrict CORS to specific origins
4. Use VPN for remote access

---

## 📚 Next Steps

1. **Add Audio Alerts**: Implement sound notifications for critical alerts
2. **Export Data**: Add CSV/PDF export functionality
3. **Patient Profiles**: Link ECG sessions to patient records
4. **Historical Playback**: View past ECG recordings
5. **Multi-Device Support**: Monitor multiple patients simultaneously

---

## 📞 Support

For issues or questions:
- Check the troubleshooting section above
- Review Pi server logs: `pi_server.py` console output
- Inspect browser console for errors (F12 → Console)
- Verify network connectivity between devices

---

## ✨ Quick Reference

| Task | Command |
|------|---------|
| Install dependencies | `npm install` |
| Start dev server | `npm run dev` |
| Build production | `npm run build` |
| Start production | `npm run start` |
| Find Pi IP | `hostname -I` (on Pi) |
| Test Pi server | `curl http://PI_IP:5000` |

---

**🎉 You're all set! Navigate to `/ecg-monitor` to start monitoring.**
