"use client"

import { useParams } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useEffect, useState } from "react"
import { getSession, getSessionEvents, getSessionStats, stopSession } from "@/lib/api"
import { Session, PredictionEvent, SessionStats } from "@/types"
import { AlertTriangle, Heart, Activity, TrendingUp, StopCircle, ArrowLeft } from "lucide-react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import Link from "next/link"

export default function AnalysisPage() {
  const params = useParams()
  const sessionId = params.id as string

  const [session, setSession] = useState<Session | null>(null)
  const [stats, setStats] = useState<SessionStats | null>(null)
  const [events, setEvents] = useState<PredictionEvent[]>([])
  const [realtimeData, setRealtimeData] = useState<Array<{ beat: number; confidence: number; alert: number | null; class: string }>>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const toConfidencePercent = (value: number) => (value > 1 ? value : value * 100)

    const fetchData = async () => {
      try {
        const [sessionData, statsData, eventsData] = await Promise.all([
          getSession(sessionId),
          getSessionStats(sessionId),
          getSessionEvents(sessionId, 50)
        ])

        setSession(sessionData.session)
        setStats(statsData)
        setEvents(eventsData.events)

        // Prepare real-time confidence chart data (last 50 beats)
        const chartData = eventsData.events.slice(-50).map((event, index) => ({
          beat: index + 1,
          confidence: toConfidencePercent(event.confidence),
          alert: event.is_alert ? toConfidencePercent(event.confidence) : null,
          class: event.class_name
        }))
        setRealtimeData(chartData)

      } catch (error) {
        console.error('Error fetching session data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    
    // Poll every 1 second for real-time updates
    const interval = setInterval(fetchData, 1000)
    return () => clearInterval(interval)
  }, [sessionId])

  const handleStopSession = async () => {
    try {
      await stopSession(sessionId)
      alert('Session stopped successfully')
      window.location.href = '/dashboard'
    } catch (error) {
      console.error('Error stopping session:', error)
      alert('Failed to stop session')
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-96">Loading session...</div>
  }

  if (!session) {
    return <div className="flex items-center justify-center h-96">Session not found</div>
  }

  const latestEvents = events.slice(-10).reverse()

  return (
    <div className="space-y-6">
      {/* Session Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Link href="/dashboard" className="p-2 hover:bg-muted text-muted-foreground hover:text-foreground rounded-md transition-colors">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-3xl font-bold">{session.patient_name}</h1>
            <p className="text-muted-foreground">
              {session.age} years old • {session.gender} • Started: {new Date(session.start_time).toLocaleTimeString()}
            </p>
          </div>
        </div>
        {session.status === 'active' && (
          <Button onClick={handleStopSession} variant="destructive">
            <StopCircle className="mr-2 h-4 w-4" />
            Stop Session
          </Button>
        )}
      </div>

      {/* Real-time Confidence Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Real-time Confidence Monitoring (Last 50 Beats)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={realtimeData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted/30" />
                <XAxis 
                  dataKey="beat" 
                  label={{ value: 'Beat Number', position: 'insideBottom', offset: -5 }}
                />
                <YAxis 
                  label={{ value: 'Confidence %', angle: -90, position: 'insideLeft' }}
                  domain={[0, 100]}
                />
                <Tooltip 
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      return (
                        <div className="bg-card border border-border rounded-lg p-3">
                          <p className="font-semibold">Beat #{payload[0].payload.beat}</p>
                          <p className="text-sm">Class: {payload[0].payload.class}</p>
                          <p className="text-sm">Confidence: {payload[0].value?.toFixed(1)}%</p>
                          {payload[0].payload.alert && (
                            <p className="text-red-500 text-sm font-semibold">🚨 ALERT</p>
                          )}
                        </div>
                      )
                    }
                    return null
                  }}
                />
                <Line 
                  type="monotone" 
                  dataKey="confidence" 
                  stroke="var(--color-primary)" 
                  strokeWidth={2} 
                  dot={false}
                />
                <Line 
                  type="monotone" 
                  dataKey="alert" 
                  stroke="var(--red-color)" 
                  strokeWidth={3} 
                  dot={{ r: 4, fill: 'var(--red-color)' }}
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4 flex gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-primary rounded-full"></div>
              <span>Confidence Score</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: 'var(--red-color)' }}></div>
              <span>Alert Triggered</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Live Events Table */}
      <Card>
        <CardHeader>
          <CardTitle>Latest Detections (Live Feed)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">Time</th>
                  <th className="text-left p-2">Classification</th>
                  <th className="text-left p-2">Confidence</th>
                  <th className="text-left p-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {latestEvents.map((event, index) => (
                  <tr 
                    key={index} 
                    className={`border-b ${event.is_alert ? 'bg-destructive/10' : ''}`}
                  >
                    <td className="p-2">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="p-2">
                      <span className={`font-semibold ${
                        event.predicted_class === 0 ? 'text-[var(--emerald-color)]' :
                        event.predicted_class === 1 ? 'text-[var(--amber-color)]' :
                        event.predicted_class === 2 ? 'text-[var(--red-color)]' :
                        event.predicted_class === 3 ? 'text-[var(--purple-color)]' :
                        'text-[var(--blue-color)]'
                      }`}>
                        Class {event.predicted_class}: {event.class_name}
                      </span>
                    </td>
                    <td className="p-2">
                      {(event.confidence > 1 ? event.confidence : event.confidence * 100).toFixed(1)}%
                    </td>
                    <td className="p-2">
                      {event.is_alert && (
                        <span className="text-red-600 font-semibold flex items-center gap-1">
                          <AlertTriangle className="h-4 w-4" />
                          ALERT
                        </span>
                      )}
                      {!event.is_alert && event.predicted_class === 0 && (
                        <span className="text-green-600">Normal</span>
                      )}
                      {!event.is_alert && event.predicted_class !== 0 && (
                        <span className="text-yellow-600">Monitor</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Statistics Summary */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Beats</CardTitle>
              <Heart className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.session.total_beats}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Arrhythmias</CardTitle>
              <Activity className="h-4 w-4 text-yellow-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.session.arrhythmia_count}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Alerts</CardTitle>
              <AlertTriangle className="h-4 w-4 text-red-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.alert_count}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Confidence</CardTitle>
              <TrendingUp className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(stats.avg_confidence > 1 ? stats.avg_confidence : stats.avg_confidence * 100).toFixed(1)}%
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
