export interface Patient {
  id: string
  name: string
  age: number
  gender: 'Male' | 'Female' | 'Other'
  condition: string
  lastTestDate: string
  status: 'Active' | 'Archived'
}

export interface CPETData {
  time: number
  vo2: number
  vco2: number
  hr: number
  ve: number
}

// ==================== Arrhythmia Detection Types ====================

export interface Session {
  id: string
  patient_id: string
  patient_name: string
  age: number
  gender: string
  start_time: string
  end_time: string | null
  status: 'active' | 'completed' | 'aborted'
  total_beats: number
  arrhythmia_count: number
}

export interface PredictionEvent {
  timestamp: string
  predicted_class: number
  class_name: string
  confidence: number
  is_alert: boolean
}

export interface SessionStats {
  session: Session
  class_distribution: {
    Normal: number
    Supraventricular: number
    Ventricular: number
    Fusion: number
    Unknown_Paced: number
  }
  alert_count: number
  avg_confidence: number
}

export interface DeviceStatus {
  device_id: string
  last_heartbeat: string | null
  status: 'online' | 'offline' | 'error'
  latency_ms: number
}

export interface SystemStatus {
  status: string
  hardware_connected: boolean
  device_latency_ms: number
  active_sessions: number
  total_sessions: number
}

// ==================== Real-time ECG Socket Types ====================

export interface ECGRawData {
  value: number
  timestamp: number
}

export interface ECGPrediction {
  predicted_class: number
  class_name: string
  confidence: number
  is_alert: boolean
  timestamp: number
}

export interface ServerStatus {
  status: string
  arduino_connected: boolean
  model_loaded: boolean
  uptime: number
}

export interface ECGStatistics {
  total_beats: number
  predictions_per_second: number
  class_distribution: {
    Normal: number
    Supraventricular: number
    Ventricular: number
    Fusion: number
    Unknown_Paced: number
  }
  class_counts?: Record<string, number>
  total_samples?: number
  predictions_made?: number
  uptime_seconds?: number
  alert_count: number
}

export type ECGMode = 'auto' | 'connected' | 'disconnected'

export interface SensorStatusPayload {
  ecg_mode: ECGMode
  ecg_connected_effective: boolean
  ecg_reason: string
  prediction_active?: boolean
  prediction_status?: string | null
  lead_off?: boolean
  lo_pos?: boolean | number
  lo_neg?: boolean | number
  bpm?: number | null
  bpm_source?: 'ecg' | 'max30102' | 'unknown' | string
  bpm_status?: string
  spo2_status: string
  hr_status: string
  arduino_connected?: boolean
  arduino_port?: string | null
  arduino_connection_status?: string
  arduino_status_message?: string | null
  arduino_last_error?: string | null
  arduino_stream_stale?: boolean
  arduino_last_data_age_sec?: number | null
  mpu6050?: MPU6050Data | null
  respiratory_motion?: MPU6050Data | null
}

export interface MPU6050Data {
  status?: string | null
  acc_x: number | null
  acc_y: number | null
  acc_z: number | null
  gyro_x: number | null
  gyro_y: number | null
  gyro_z: number | null
  resp_rate_mpu?: number | null
  respiratory_rate_mpu_bpm?: number | null
  motion_state?: string | null
  resp_signal_quality?: string | null
  respiratory_motion_quality?: string | null
  acc_magnitude?: number | null
  gyro_magnitude?: number | null
  acc_mag_g?: number | null
  gyro_mag_dps?: number | null
  resp_axis?: string | null
  sample_count?: number | null
  sample_rate_hz?: number | null
  duration_seconds?: number | null
  units?: Record<string, string>
}

// ==================== CPET Robust Parameters ====================

export interface CPETParameters {
  // 1. Lung-Respiratory-Cardiac Ratio
  lrc_ratio: number | null              // BR/HR - Respiratory-cardiac balance
  lrc_index?: number | null
  lrc_status?: string                   // e.g. ok | unavailable_rr
  
  // 2. Oxygen Pulse Surrogate (Stroke Volume indicator)
  oxygen_pulse: number | null           // VO2/HR (ml/beat)
  o2_pulse_surrogate?: number | null
  o2_pulse_surrogate_status?: string | null
  
  // 3. Heart Rate Variability - Autonomic Balance
  lf_hf_ratio: number | null            // LF/HF - Stress vs recovery state
  
  // 4. Pulse Transit Time (cuffless BP estimator)
  ptt_ms: number | null                 // ECG R-peak to PPG peak delay (ms)
  ptt_available?: boolean
  ptt_status?: string                   // e.g. ok | unavailable_no_ppg_waveform
  
  // 5. Ventilatory Efficiency
  ve_vco2_slope: number | null          // VE/VCO2 slope - lung efficiency
  ve_vco2_slope_surrogate?: number | null
  ventilatory_efficiency_status?: string | null
  co2_delta?: number | null
  net_co2?: number | null
  
  // 6. Real-time Heart Rate (from R-R intervals)
  heart_rate_bpm: number | null         // Current HR in beats per minute

  // Sensor/source metadata
  heart_rate_source?: 'ecg' | 'max30102' | 'unknown' | string
  respiratory_rate_bpm?: number | null
  respiratory_rate_source?: string | null
  respiratory_rate_mpu_bpm?: number | null
  respiratory_motion_quality?: string | null
  motion_state?: string | null
  respiratory_motion?: MPU6050Data | null
  derived_metrics?: Record<string, unknown>
  
  // Metadata
  timestamp: number
  data_quality: 'excellent' | 'good' | 'fair' | 'poor'
}

// ==================== 2-Minute Screening Test Types ====================

/** Emitted by `test_progress` every 5% during the test */
export interface TestStatus {
  active: boolean
  success?: boolean
  status?: 'idle' | 'recording' | 'processing' | 'completed' | string
  message?: string
  error?: string | null
  missing_fields?: string[]
  patient_id?: string | null
  patient_name?: string | null
  start_time?: number | null
  progress_percent: number        // 0-100 (normalized)
  progress?: number               // raw protocol field
  samples_collected: number       // normalized from ecg_samples_collected/ecg_samples
  ecg_samples_collected?: number
  target_samples?: number
  elapsed_seconds: number
  remaining_seconds: number
}

/** Nested inside TestResult — CPET & lung efficiency params from the 2-min test */
export interface TestParameters {
  heart_rate: number | null
  heart_rate_source: string       // e.g. 'ecg_r_peak'
  respiratory_rate: number | null
  respiratory_rate_source: string // e.g. 'ecg_derived'
  hrv: {
    sdnn: number | null
    rmssd: number | null
    lf_hf_ratio: number | null
  }
  total_peaks_detected: number
  total_rr_intervals: number
  respiratory_rate_mpu?: number | null
  lrc_ratio?: number | null
  lrc_index?: number | null
  o2_pulse_surrogate?: number | null
  co2_delta?: number | null
  net_co2?: number | null
  ve_vco2_slope_surrogate?: number | null
  ventilatory_efficiency_status?: string | null
  ptt_available?: boolean
  ptt_ms?: number | null
  ptt_status?: string | null
  respiratory_motion_quality?: string | null
  motion_quality?: string | null
  avg_acc_magnitude?: number | null
  avg_gyro_magnitude?: number | null
  avg_acc_magnitude_g?: number | null
  avg_gyro_magnitude_dps?: number | null
  max_gyro_magnitude_dps?: number | null
  mpu_sample_count?: number | null
  avg_spo2_percent?: number | null
  max_spo2_percent?: number | null
  avg_ppg_heart_rate?: number | null
  // Lung efficiency (dual MQ-135)
  co2_ambient_ppm: number | null
  co2_exhaled_ppm: number | null
  net_co2_ppm: number | null      // exhaled - ambient
  ve_vco2_slope: number | null    // airflow / net_co2
  lung_efficiency_status: 'good' | 'fair' | 'poor' | string | null
}

/** Nested inside TestResult — downsampled waveform for replay */
export interface TestEcgWaveform {
  data: number[]
  duration_seconds: number
  sample_count: number
  original_sample_count: number
}

/** Nested inside TestResult — CNN arrhythmia analysis */
export interface TestArrhythmia {
  total_predictions: number
  dominant_class: number
  dominant_class_name: string     // e.g. 'Normal (N)'
  confidence: number              // 0-100 (percent, NOT 0-1)
  class_distribution: Record<string, number> | number[]
  class_labels: Record<string, string>         // {"0": "Normal (N)", "1": "Supraventricular (S)"}
  arrhythmia_detected: boolean
  arrhythmia_type: string | null
  threshold_used: number
}

/** Full payload from `test_complete` event */
export interface TestResult {
  success?: boolean
  test_id?: string
  patient_id?: string
  patient_name?: string
  timestamp: string               // normalized ISO string
  duration_seconds?: number
  status?: string
  test_duration_seconds: number
  total_samples: number
  sampling_rate: number
  parameters: TestParameters
  ecg_waveform: TestEcgWaveform
  arrhythmia: TestArrhythmia
  summary: {
    status: string                // 'completed' | 'stopped_early'
    interpretation: string        // Human-readable: "Normal heart rhythm | High confidence..."
  }
  error?: string | null
}

