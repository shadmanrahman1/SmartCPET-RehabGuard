import { NextRequest, NextResponse } from 'next/server'

const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY
const OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
const MODEL = 'google/gemma-3-27b-it'  // Gemma 4 on OpenRouter

export async function POST(req: NextRequest) {
  if (!OPENROUTER_API_KEY) {
    return NextResponse.json(
      { error: 'OpenRouter API key not configured. Add OPENROUTER_API_KEY to .env.local' },
      { status: 500 }
    )
  }

  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }

  const { processedData, cpetParameters, mpuData, latestPrediction, statistics, sessionDuration, testResult } = body as {
    processedData?: Record<string, unknown> | null
    cpetParameters?: Record<string, unknown> | null
    mpuData?: Record<string, unknown> | null
    latestPrediction?: Record<string, unknown> | null
    statistics?: Record<string, unknown> | null
    sessionDuration?: string
    testResult?: Record<string, unknown> | null
  }

  const numberOrNull = (value: unknown): number | null =>
    typeof value === 'number' && Number.isFinite(value) ? value : null

  const formatNumber = (value: unknown, digits = 1): string => {
    const n = numberOrNull(value)
    return n === null ? 'N/A' : n.toFixed(digits)
  }

  const testParameters = (testResult?.parameters as Record<string, unknown> | undefined) ?? null
  const patientSection = testResult
    ? `
PATIENT IDENTITY:
- Patient ID: ${testResult.patient_id ?? 'N/A'}
- Patient Name: ${testResult.patient_name ?? 'N/A'}`
    : '\nPATIENT IDENTITY: Not provided'
  const motionPayload =
    mpuData ??
    (processedData?.respiratory_motion as Record<string, unknown> | undefined) ??
    (cpetParameters?.respiratory_motion as Record<string, unknown> | undefined) ??
    null

  // Build a structured clinical context from all available sensor data
  const vitalsSection = processedData
    ? `
LIVE VITALS (Last 1-Hz Sample):
- Heart Rate: ${processedData.bpm ?? processedData.hr ?? 'N/A'} BPM (Source: ${processedData.bpm_source ?? 'auto'})
- SpO2: ${processedData.spo2 ?? 'N/A'}%
- EtCO2: ${processedData.co2_exh ?? 'N/A'} mmHg
- Ambient CO2: ${processedData.co2_amb ?? 'N/A'} mmHg
- Flow: ${processedData.flow ?? 'N/A'} L/min`
    : '\nLIVE VITALS: No live data received (offline demo mode)'

  const cpetSection = cpetParameters
    ? `
CPET PARAMETERS:
- LRC Ratio (Lung-Resp-Cardiac): ${((cpetParameters.lrc_ratio ?? cpetParameters.lrc_index) as number | null | undefined)?.toFixed(4) ?? 'N/A'} (Status: ${cpetParameters.lrc_status ?? 'ok'})
- Respiratory Rate: ${(cpetParameters.respiratory_rate_bpm as number | null | undefined)?.toFixed(1) ?? 'N/A'} breaths/min (Source: ${cpetParameters.respiratory_rate_source ?? 'N/A'})
- O2 Pulse Surrogate: ${((cpetParameters.o2_pulse_surrogate ?? cpetParameters.oxygen_pulse) as number | null | undefined)?.toFixed(2) ?? 'N/A'} ml/beat
- CO2 Delta: ${((cpetParameters.co2_delta ?? cpetParameters.net_co2) as number | null | undefined)?.toFixed(1) ?? 'N/A'} ppm
- VE/VCO2 Slope Surrogate: ${((cpetParameters.ve_vco2_slope_surrogate ?? cpetParameters.ve_vco2_slope) as number | null | undefined)?.toFixed(2) ?? 'N/A'} (raw-sensor/project surrogate)
- PTT (Pulse Transit Time): ${(cpetParameters.ptt_ms as number | null | undefined)?.toFixed(1) ?? 'N/A'} ms (Available: ${cpetParameters.ptt_available === false ? 'NO' : 'maybe'}, Status: ${cpetParameters.ptt_status ?? 'ok'})
- MPU Respiratory Rate: ${(cpetParameters.respiratory_rate_mpu_bpm as number | null | undefined)?.toFixed(1) ?? 'N/A'} breaths/min
- Respiratory Motion Quality: ${cpetParameters.respiratory_motion_quality ?? 'N/A'}
- Motion State: ${cpetParameters.motion_state ?? 'N/A'}
- Data Quality: ${cpetParameters.data_quality ?? 'N/A'}`
    : '\nCPET PARAMETERS: Not available'

  const motionSection = motionPayload || testParameters
    ? `
RESPIRATORY MOTION / ARTIFACT CONTEXT:
- Live MPU6050 Respiratory Rate: ${formatNumber(motionPayload?.resp_rate_mpu ?? motionPayload?.respiratory_rate_mpu)} breaths/min
- Test MPU6050 Respiratory Rate: ${formatNumber(testParameters?.respiratory_rate_mpu)} breaths/min
- Motion State/Quality: ${motionPayload?.motion_state ?? testParameters?.motion_quality ?? 'N/A'}
- Respiratory Signal Quality: ${motionPayload?.resp_signal_quality ?? motionPayload?.respiratory_motion_quality ?? testParameters?.respiratory_motion_quality ?? 'N/A'}
- Acc Magnitude: ${formatNumber(motionPayload?.acc_mag_g ?? motionPayload?.acc_magnitude ?? testParameters?.avg_acc_magnitude_g ?? testParameters?.avg_acc_magnitude)} g/raw
- Gyro Magnitude: ${formatNumber(motionPayload?.gyro_mag_dps ?? motionPayload?.gyro_magnitude ?? testParameters?.avg_gyro_magnitude_dps ?? testParameters?.avg_gyro_magnitude)} dps/raw`
    : '\nRESPIRATORY MOTION / ARTIFACT CONTEXT: No MPU6050 data available'

  const arrhythmiaSection = latestPrediction
    ? `
CNN ARRHYTHMIA CLASSIFICATION:
- Class: ${latestPrediction.predicted_class} — ${latestPrediction.class_name}
- Confidence: ${(((latestPrediction.confidence as number) ?? 0) * 100).toFixed(1)}%
- Critical Alert: ${latestPrediction.is_critical ? 'YES — Immediate attention required' : 'No'}

NOTE: The CNN model is currently v1 and retraining is in progress. Accuracy on MIT-BIH test set is 22.1%. Classification should be used as a screening aid only, not as a standalone clinical diagnosis.`
    : '\nCNN CLASSIFICATION: No prediction data available'

  const statsSection = statistics
    ? `
SESSION STATISTICS:
- Total Beats Analyzed: ${(statistics as Record<string, Record<string, number>>).class_distribution ? Object.values((statistics as Record<string, Record<string, number>>).class_distribution).reduce((a, b) => a + b, 0) : 'N/A'}
- Class Distribution: ${JSON.stringify(statistics.class_distribution ?? {})}`
    : '\nSTATISTICS: No historical session data'

  const prompt = `You are a sports cardiology screening assistant integrated into the SmartCPET system, developed by KUET BME students for cardiopulmonary exercise testing (CPET).

Generate a careful CPET screening report based on the following real-time sensor data from the Raspberry Pi monitoring system. Avoid diagnostic certainty and clearly state when findings require clinician review:

SESSION INFO:
- Date: ${new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' })}
- Duration: ${sessionDuration ?? 'N/A'}
- System: SmartCPET v1.0 — KUET BME 2026
${patientSection}
${vitalsSection}
${cpetSection}
${motionSection}
${arrhythmiaSection}
${statsSection}

INSTRUCTIONS:
1. Write in a professional clinical tone suitable for a sports medicine screening report.
2. Structure the report with clear headers: CARDIAC ASSESSMENT, RESPIRATORY ASSESSMENT, RESPIRATORY MOTION / ARTIFACT ASSESSMENT, CPET PARAMETERS INTERPRETATION, CLINICAL RECOMMENDATION.
3. Compare values against normal ranges (HR: 60-100 BPM, SpO2: >95%, EtCO2: 35-45 mmHg, LRC: 0.5-1.5).
4. Flag any abnormalities clearly, but do not claim a definitive diagnosis.
5. Give a clear RECOMMENDATION at the end (e.g. "Cleared for training", "Requires follow-up", "Immediate referral").
6. Keep it concise — under 500 words.
7. End with: "[Powered by SmartCPET + Gemma via OpenRouter — KUET BME 2026]"

If data is missing or N/A, acknowledge it honestly and generate a partial assessment.`

  try {
    const response = await fetch(OPENROUTER_URL, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://smartcpet.kuet.local',
        'X-Title': 'SmartCPET Dashboard',
      },
      body: JSON.stringify({
        model: MODEL,
        messages: [{ role: 'user', content: prompt }],
        max_tokens: 800,
        temperature: 0.3,
      }),
    })

    if (!response.ok) {
      const errText = await response.text()
      console.error('OpenRouter error:', errText)
      return NextResponse.json(
        { error: `OpenRouter API error: ${response.status} ${response.statusText}` },
        { status: 502 }
      )
    }

    const data = await response.json() as {
      choices?: Array<{ message?: { content?: string } }>
      error?: { message?: string }
    }

    if (data.error) {
      return NextResponse.json({ error: data.error.message ?? 'Unknown model error' }, { status: 502 })
    }

    const report = data.choices?.[0]?.message?.content
    if (!report) {
      return NextResponse.json({ error: 'Empty response from Gemma model' }, { status: 502 })
    }

    return NextResponse.json({ report })
  } catch (err) {
    console.error('Report generation error:', err)
    return NextResponse.json({ error: 'Network error reaching OpenRouter API' }, { status: 503 })
  }
}
