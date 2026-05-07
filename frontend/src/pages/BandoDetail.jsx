import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import SemaforoIcon from '../components/SemaforoIcon'

function fmt(val) {
  if (val == null) return '—'
  return `€ ${Number(val).toLocaleString('it-IT')}`
}

function fmtData(val) {
  if (!val) return '—'
  return new Date(val).toLocaleDateString('it-IT', { day: '2-digit', month: 'long', year: 'numeric' })
}

function Tag({ children, color = 'navy' }) {
  const cls = {
    navy: 'bg-navy text-paper',
    verde: 'bg-verde/10 text-verde border border-verde/30',
    giallo: 'bg-giallo/10 text-giallo border border-giallo/30',
    rosso: 'bg-rosso/10 text-rosso border border-rosso/30',
    gray: 'bg-gray-100 text-gray-600',
  }[color] || 'bg-gray-100 text-gray-600'
  return <span className={`font-mono text-xs px-2 py-0.5 rounded ${cls}`}>{children}</span>
}

export default function BandoDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [bando, setBando] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_BASE || ''}/api/bandi/${id}`)
      .then((r) => r.json())
      .then(setBando)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="min-h-screen bg-paper flex items-center justify-center font-mono text-gray-400">Caricamento...</div>
  if (!bando) return <div className="min-h-screen bg-paper flex items-center justify-center font-mono text-gray-400">Bando non trovato.</div>

  const req = bando.agent4_requisiti || {}
  const semColor = bando.agent4_semaforo || 'gray'

  return (
    <div className="min-h-screen bg-paper">
      <header className="bg-navy text-paper px-6 py-4 flex items-center gap-4">
        <button onClick={() => nav(-1)} className="font-mono text-sm text-gray-400 hover:text-paper transition-colors">← Indietro</button>
        <h1 className="font-mono text-lg font-semibold">BandiScout</h1>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* Titolo + semaforo */}
        <div className="bg-white rounded border border-gray-200 p-6">
          <div className="flex items-start gap-4">
            <SemaforoIcon semaforo={bando.agent4_semaforo} size="lg" />
            <div className="flex-1">
              <h2 className="font-sans font-semibold text-xl leading-snug">{bando.titolo}</h2>
              <p className="text-sm text-gray-500 font-sans mt-1">
                {bando.stazione_appaltante} · {bando.comune} ({bando.provincia})
                {bando.distanza_km != null && <span className="ml-2 font-mono text-xs bg-gray-100 px-1 rounded">{bando.distanza_km} km</span>}
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                {bando.agent3_trovato_da_hunter && <Tag color="rosso">🎯 Trovato da Hunter</Tag>}
                <Tag color="gray">CIG: {bando.cig}</Tag>
                <Tag color="gray">CPV: {bando.cpv_code}</Tag>
                <Tag color="gray">Fonte: {bando.fonte}</Tag>
              </div>
            </div>
          </div>
          {bando.agent4_note && (
            <div className={`mt-4 p-3 rounded text-sm font-sans border-l-4 ${semColor === 'verde' ? 'border-verde bg-verde/5' : semColor === 'giallo' ? 'border-giallo bg-giallo/5' : 'border-rosso bg-rosso/5'}`}>
              {bando.agent4_note}
            </div>
          )}
        </div>

        {/* Riassunto AI */}
        {bando.agent4_riassunto && (
          <div className="bg-white rounded border border-gray-200 p-6">
            <h3 className="font-mono text-xs uppercase tracking-widest text-gray-500 mb-3">Analisi AI</h3>
            <p className="font-sans text-base leading-relaxed">{bando.agent4_riassunto}</p>
          </div>
        )}

        {/* Dati economici */}
        <div className="bg-white rounded border border-gray-200 p-6">
          <h3 className="font-mono text-xs uppercase tracking-widest text-gray-500 mb-4">Dati economici</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-gray-500 font-sans">Base d'asta</div>
              <div className="font-mono text-2xl font-semibold mt-1">{fmt(bando.importo_base)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 font-sans">Scadenza offerta</div>
              <div className="font-mono text-lg font-semibold mt-1">{fmtData(bando.data_scadenza)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 font-sans">Pubblicazione</div>
              <div className="font-sans text-sm mt-1">{fmtData(bando.data_pubblicazione)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 font-sans">Link bando</div>
              {bando.url_bando
                ? <a href={bando.url_bando} target="_blank" rel="noopener noreferrer" className="font-mono text-sm text-accent underline mt-1 block">Apri bando ↗</a>
                : <span className="text-sm text-gray-400 mt-1 block">—</span>
              }
            </div>
          </div>
        </div>

        {/* Procedura e difficoltà */}
        <div className="bg-white rounded border border-gray-200 p-6">
          <h3 className="font-mono text-xs uppercase tracking-widest text-gray-500 mb-4">Procedura</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-xs text-gray-500 font-sans">Tipo procedura</div>
              <div className="font-mono mt-1 capitalize">{req.tipo_procedura?.replace('_', ' ') || '—'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 font-sans">Tipo lavoro</div>
              <div className="font-mono mt-1 capitalize">{req.tipo_lavoro?.replace('+', ' + ') || '—'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 font-sans">Difficoltà</div>
              <div className="font-mono mt-1">
                {req.difficolta
                  ? <><span className={req.difficolta === 'bassa' ? 'text-verde' : req.difficolta === 'media' ? 'text-giallo' : 'text-rosso'}>{req.difficolta.toUpperCase()}</span>{req.difficolta_motivo && <span className="text-gray-400 ml-2 font-sans normal-case">— {req.difficolta_motivo}</span>}</>
                  : '—'
                }
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 font-sans">Azione consigliata</div>
              <div className="font-mono mt-1 capitalize">{req.azione_consigliata || '—'}</div>
            </div>
            {req.materiali_richiesti?.length > 0 && (
              <div className="col-span-2">
                <div className="text-xs text-gray-500 font-sans mb-1">Materiali richiesti</div>
                <div className="flex flex-wrap gap-1">{req.materiali_richiesti.map(m => <Tag key={m} color="gray">{m}</Tag>)}</div>
              </div>
            )}
          </div>
        </div>

        {/* Requisiti */}
        <div className="bg-white rounded border border-gray-200 p-6">
          <h3 className="font-mono text-xs uppercase tracking-widest text-gray-500 mb-4">Requisiti</h3>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="py-2 text-gray-500 font-sans w-48">SOA richiesta</td>
                <td className="py-2 font-mono">
                  {req.soa_richiesta
                    ? `✓ ${req.soa_categoria || 'N/D'}${req.soa_classifica && req.soa_classifica !== 'non_richiesta' ? ` class. ${req.soa_classifica}` : ''}`
                    : '✗ No'}
                </td>
              </tr>
              <tr><td className="py-2 text-gray-500 font-sans">Fatturato minimo</td><td className="py-2 font-mono">{fmt(req.fatturato_minimo)}</td></tr>
              <tr><td className="py-2 text-gray-500 font-sans">CAM obbligatori</td><td className="py-2 font-mono">{req.cam_obbligatori ? `✓ Sì${req.cam_note ? ` — ${req.cam_note}` : ''}` : '✗ No'}</td></tr>
              <tr><td className="py-2 text-gray-500 font-sans">Subappalto ammesso</td><td className="py-2 font-mono">{req.subappalto_ammesso == null ? '—' : req.subappalto_ammesso ? '✓ Sì' : '✗ No'}</td></tr>
              <tr>
                <td className="py-2 text-gray-500 font-sans">Certificazioni</td>
                <td className="py-2">
                  {req.certificazioni_richieste?.length
                    ? <div className="flex flex-wrap gap-1">{req.certificazioni_richieste.map(c => <Tag key={c} color="gray">{c}</Tag>)}</div>
                    : <span className="font-mono">—</span>
                  }
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </main>
    </div>
  )
}
