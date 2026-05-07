import { useState, useEffect, useCallback } from 'react'
import StatsBar from '../components/StatsBar'
import BandiTable from '../components/BandiTable'
import RadiusSlider from '../components/RadiusSlider'

const API = `${import.meta.env.VITE_API_BASE || ''}/api`

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [bandi, setBandi] = useState([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  const [semaforo, setSemaforo] = useState('')
  const [radiusKm, setRadiusKm] = useState(50)
  const [soloAttivi, setSoloAttivi] = useState(false)
  const [ordinamento, setOrdinamento] = useState('scadenza')

  const fetchStats = useCallback(async () => {
    try {
      const r = await fetch(`${API}/stats`)
      setStats(await r.json())
    } catch (e) {
      console.error(e)
    }
  }, [])

  const fetchBandi = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (semaforo) params.set('semaforo', semaforo)
      if (radiusKm) params.set('radius_km', radiusKm)
      if (soloAttivi) params.set('solo_attivi', 'true')
      const r = await fetch(`${API}/bandi?${params}`)
      let data = await r.json()

      if (ordinamento === 'scadenza') {
        data = data.sort((a, b) => (a.data_scadenza || '').localeCompare(b.data_scadenza || ''))
      } else if (ordinamento === 'importo') {
        data = data.sort((a, b) => (b.importo_base || 0) - (a.importo_base || 0))
      } else {
        data = data.sort((a, b) => (b.data_pubblicazione || '').localeCompare(a.data_pubblicazione || ''))
      }

      setBandi(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [semaforo, radiusKm, soloAttivi, ordinamento])

  useEffect(() => {
    fetchStats()
    fetchBandi()
  }, [fetchStats, fetchBandi])

  const handleRadiusChange = async (newRadius) => {
    setRadiusKm(newRadius)
    await fetch(`${API}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ radius_km: String(newRadius) }),
    })
  }

  const handleRunNow = async () => {
    setRunning(true)
    await fetch(`${API}/run-now`, { method: 'POST' })
    setTimeout(() => {
      setRunning(false)
      fetchStats()
      fetchBandi()
    }, 3000)
  }

  const lastRun = stats?.last_run
  const lastRunTime = lastRun?.started_at
    ? new Date(lastRun.started_at).toLocaleString('it-IT', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
    : '—'

  return (
    <div className="min-h-screen bg-paper">
      {/* Header */}
      <header className="bg-navy text-paper px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="font-mono text-xl font-semibold tracking-tight">BandiScout</h1>
          <p className="text-xs text-gray-400 font-sans mt-0.5">CBS Serramenti · Gerenzano VA</p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs font-mono text-gray-400">
            Ultimo controllo: {lastRunTime}
          </span>
          <button
            onClick={handleRunNow}
            disabled={running}
            className="bg-accent text-white font-mono text-sm px-4 py-2 rounded hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            {running ? 'In corso...' : 'Controlla Ora'}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        <StatsBar stats={stats} />

        {/* Filtri */}
        <div className="flex flex-wrap items-center gap-4 mb-5 p-4 bg-white rounded border border-gray-200">
          <RadiusSlider value={radiusKm} onChange={handleRadiusChange} />

          <label className="flex items-center gap-2 text-sm font-sans cursor-pointer">
            <input
              type="checkbox"
              checked={soloAttivi}
              onChange={(e) => setSoloAttivi(e.target.checked)}
              className="accent-accent"
            />
            Solo non scaduti
          </label>

          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 font-sans">Semaforo:</span>
            {['', 'verde', 'giallo', 'rosso'].map((s) => (
              <button
                key={s || 'tutti'}
                onClick={() => setSemaforo(s)}
                className={`font-mono text-xs px-3 py-1 rounded border transition-colors ${semaforo === s ? 'bg-navy text-paper border-navy' : 'border-gray-300 hover:border-navy'}`}
              >
                {s === '' ? 'Tutti' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 font-sans">Ordina:</span>
            <select
              value={ordinamento}
              onChange={(e) => setOrdinamento(e.target.value)}
              className="font-mono text-xs border border-gray-300 rounded px-2 py-1"
            >
              <option value="scadenza">Scadenza</option>
              <option value="pubblicazione">Pubblicazione</option>
              <option value="importo">Importo</option>
            </select>
          </div>
        </div>

        <BandiTable bandi={bandi} loading={loading} />
      </main>
    </div>
  )
}
