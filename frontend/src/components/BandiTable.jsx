import { useNavigate } from 'react-router-dom'
import SemaforoIcon from './SemaforoIcon'

function fmt(val) {
  if (val == null) return '—'
  return `€ ${Number(val).toLocaleString('it-IT')}`
}

function fmtData(val) {
  if (!val) return '—'
  return new Date(val).toLocaleDateString('it-IT', { day: '2-digit', month: 'short' })
}

function isScaduto(val) {
  if (!val) return false
  return new Date(val) < new Date()
}

export default function BandiTable({ bandi, loading }) {
  const nav = useNavigate()

  if (loading) {
    return <div className="text-center py-16 font-mono text-gray-400">Caricamento...</div>
  }
  if (!bandi.length) {
    return <div className="text-center py-16 font-mono text-gray-400">Nessun bando trovato.</div>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-navy text-paper font-mono text-xs uppercase tracking-wider">
            <th className="px-3 py-3 text-left w-10"></th>
            <th className="px-3 py-3 text-left">Comune</th>
            <th className="px-3 py-3 text-left">Titolo</th>
            <th className="px-3 py-3 text-right">Importo</th>
            <th className="px-3 py-3 text-right">Scadenza</th>
            <th className="px-3 py-3 text-center">km</th>
            <th className="px-3 py-3"></th>
          </tr>
        </thead>
        <tbody>
          {bandi.map((b, i) => {
            const scaduto = isScaduto(b.data_scadenza)
            return (
            <tr
              key={b.id}
              className={`border-b border-gray-200 hover:bg-gray-50 cursor-pointer transition-colors ${scaduto ? 'opacity-60' : ''} ${i % 2 === 0 ? 'bg-paper' : 'bg-white'}`}
              onClick={() => nav(`/bando/${b.id}`)}
            >
              <td className="px-3 py-3 text-center">
                <SemaforoIcon semaforo={b.agent4_semaforo} />
              </td>
              <td className="px-3 py-3 font-sans whitespace-nowrap">
                {b.comune || '—'}
                {b.agent3_trovato_da_hunter && (
                  <span className="ml-1 text-xs text-accent font-mono" title="Trovato da Hunter">🎯</span>
                )}
              </td>
              <td className="px-3 py-3 font-sans max-w-xs">
                <span className="line-clamp-2">{b.titolo}</span>
              </td>
              <td className="px-3 py-3 font-mono text-right whitespace-nowrap">{fmt(b.importo_base)}</td>
              <td className={`px-3 py-3 font-mono text-right whitespace-nowrap ${scaduto ? 'text-gray-400 line-through' : ''}`}>
                {fmtData(b.data_scadenza)}
                {!b.data_scadenza && <span className="text-xs text-gray-400">N/D</span>}
              </td>
              <td className="px-3 py-3 font-mono text-center text-gray-500">
                {b.distanza_km != null ? `${b.distanza_km}` : '—'}
              </td>
              <td className="px-3 py-3">
                <button
                  className="text-xs font-mono bg-navy text-paper px-2 py-1 rounded hover:bg-accent transition-colors"
                  onClick={(e) => { e.stopPropagation(); nav(`/bando/${b.id}`) }}
                >
                  Dettaglio
                </button>
              </td>
            </tr>
          )})}
        </tbody>
      </table>
    </div>
  )
}
