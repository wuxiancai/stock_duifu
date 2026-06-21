export interface HealthResponse {
  status: 'ok'
  service: string
  environment: 'development' | 'test' | 'production'
  database: {
    engine: 'postgresql'
    configured: boolean
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/health`)

  if (!response.ok) {
    throw new Error(`API health check failed: ${response.status}`)
  }

  return response.json() as Promise<HealthResponse>
}
