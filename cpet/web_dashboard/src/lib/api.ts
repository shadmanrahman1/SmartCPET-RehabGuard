import { Session, SessionStats, PredictionEvent, DeviceStatus, SystemStatus } from '@/types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * Thrown when the FastAPI backend is simply not reachable.
 * Callers can check `instanceof BackendOfflineError` to treat
 * this as an expected state rather than a real error.
 */
export class BackendOfflineError extends Error {
  constructor() {
    super('Backend server is not running. Please start the FastAPI server.')
    this.name = 'BackendOfflineError'
  }
}

async function fetchWithErrorHandling(url: string, options?: RequestInit) {
  try {
    const response = await fetch(url, options)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return response
  } catch (error) {
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      throw new BackendOfflineError()
    }
    throw error
  }
}

// ==================== System Status ====================

export async function getSystemStatus(): Promise<SystemStatus> {
  const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/status`)
  return response.json()
}

export async function getDeviceStatus(): Promise<DeviceStatus> {
  const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/devices/status`)
  return response.json()
}

// ==================== Session Management ====================

export async function getSessions(status?: string): Promise<{ sessions: Session[] }> {
  const url = status 
    ? `${API_BASE_URL}/api/sessions?status=${status}`
    : `${API_BASE_URL}/api/sessions`
  
  const response = await fetchWithErrorHandling(url)
  return response.json()
}

export async function getSession(sessionId: string): Promise<{ session: Session }> {
  const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/sessions/${sessionId}`)
  return response.json()
}

export async function startSession(data: {
  patient_id: string
  patient_name: string
  age: number
  gender: string
}): Promise<{ session_id: string; session: Session }> {
  const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/sessions/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  return response.json()
}

export async function stopSession(sessionId: string): Promise<{ session: Session }> {
  const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/sessions/${sessionId}/stop`, {
    method: 'POST'
  })
  return response.json()
}

// ==================== Event & Statistics ====================

export async function getSessionStats(sessionId: string): Promise<SessionStats> {
  const response = await fetchWithErrorHandling(`${API_BASE_URL}/api/sessions/${sessionId}/stats`)
  return response.json()
}

export async function getSessionEvents(
  sessionId: string, 
  limit = 100, 
  offset = 0
): Promise<{ session_id: string; total_events: number; returned: number; events: PredictionEvent[] }> {
  const response = await fetchWithErrorHandling(
    `${API_BASE_URL}/api/sessions/${sessionId}/events?limit=${limit}&offset=${offset}`
  )
  return response.json()
}
