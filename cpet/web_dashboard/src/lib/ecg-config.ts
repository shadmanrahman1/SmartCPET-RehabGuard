// Raspberry Pi Backend Configuration
export const ECG_SERVER_CONFIG = {
  // Pi hostname resolves via mDNS on local network
  url: process.env.NEXT_PUBLIC_PI_SERVER_URL || 'http://mypi.local:5000',

  // Socket.IO connection options
  options: {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    reconnectionAttempts: Infinity,
    timeout: 8000,
  },

  // Pi event names
  events: {
    // Core realtime protocol
    sensorData: 'sensor_data',
    sensorStatus: 'sensor_status',
    processedSlow1hz: 'processed_slow_1hz',
    cpetParameters: 'cpet_parameters',
    heartRate: 'heart_rate',
    respiratoryRate: 'respiratory_rate',
    prediction: 'prediction',

    // Diagnostic streams
    ecgRaw: 'ecg_raw',
    cpetStream: 'cpet_stream',
    ecgHeartRate: 'ecg_heart_rate',

    // Alerts
    alert: 'alert',

    // Commands
    setEcgMode: 'set_ecg_mode',
    setEcgConnection: 'set_ecg_connection',
    setPatientId: 'set_patient_id',
    requestSensorStatus: 'request_sensor_status',
    requestStats: 'request_stats',

    // 2-Minute Screening Test
    startTest: 'start_test',
    stopTest: 'stop_test',
    getTestStatus: 'get_test_status',
    getTestStatusLegacy: 'get_test_status_request',
    getTestResult: 'get_test_result',
    testProgress: 'test_progress',
    testStatus: 'test_status',
    testLiveEcg: 'test_live_ecg',
    testStarted: 'test_started',
    testStopped: 'test_stopped',
    testComplete: 'test_complete',
    testResult: 'test_result',
    patientIdSet: 'patient_id_set',
    error: 'error',
    allTestResults: 'all_test_results',
    getAllResults: 'get_all_results',

    // Legacy / compatibility
    serverStatus: 'server_status',
    statistics: 'statistics',
    requestStatistics: 'request_statistics',
  },

  // Chart / buffer settings
  chart: {
    maxDataPoints: 300,
    updateInterval: 50,
    bufferSize: 10,
    downsampleFactor: 1,
  },
}

// Arrhythmia class map
export const ARRHYTHMIA_CLASSES = {
  0: { name: 'Normal', color: 'var(--emerald-color)', severity: 'low' },
  1: { name: 'Supraventricular', color: 'var(--amber-color)', severity: 'medium' },
  2: { name: 'Ventricular', color: 'var(--red-color)', severity: 'high' },
  3: { name: 'Fusion', color: 'var(--purple-color)', severity: 'medium' },
  4: { name: 'Unknown/Paced', color: 'var(--cyan-color)', severity: 'low' },
} as const

// Vitals reference ranges
export const VITALS_RANGES = {
  heart_rate: { low: 60, high: 100, unit: 'BPM' },
  spo2: { low: 95, high: 100, unit: '%' },
  co2: { low: 35, high: 45, unit: 'mmHg' },
  ptt: { low: 100, high: 300, unit: 'ms' },
  lrc: { low: 0, high: 1, unit: '' },
} as const
