import { useState, useEffect, useRef } from 'react'
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

function RischioTag({ rischio }) {
  const cls = { basso: 'text-verde', medio: 'text-giallo', alto: 'text-rosso' }[rischio] || 'text-gray-500'
  return <span className={`font-mono uppercase ${cls}`}>{rischio}</span>
}

function UploadZone({ label, hint, onFiles, loadingCount }) {
  const refFiles = useRef()
  const refFolder = useRef()
  const busy = loadingCount > 0

  function handleChange(e) {
    const pdfs = Array.from(e.target.files).filter(f => f.name.toLowerCase().endsWith('.pdf'))
    if (pdfs.length) onFiles(pdfs)
    e.target.value = ''
  }

  return (
    <div className={`border-2 border-dashed rounded-lg p-5 text-center transition-colors ${busy ? 'border-gray-200 bg-gray-50' : 'border-gray-300'}`}>
      <input ref={refFiles} type="file" accept=".pdf" multiple className="hidden" onChange={handleChange} />
      <input ref={refFolder} type="file" webkitdirectory="" className="hidden" onChange={handleChange} />
      {busy
        ? <div className="font-mono text-sm text-gray-400 animate-pulse">Analisi {loadingCount} file in corso…</div>
        : <>
            <div className="text-2xl mb-2">📄</div>
            <div className="font-sans font-medium text-sm text-gray-700 mb-3">{label}</div>
            <div className="flex gap-2 justify-center">
              <button onClick={() => refFiles.current.click()}
                className="font-mono text-xs px-3 py-1.5 rounded border border-gray-300 hover:border-accent hover:text-accent transition-colors">
                Seleziona file
              </button>
              <button onClick={() => refFolder.current.click()}
                className="font-mono text-xs px-3 py-1.5 rounded border border-gray-300 hover:border-accent hover:text-accent transition-colors">
                Seleziona cartella
              </button>
            </div>
            <div className="font-sans text-xs text-gray-400 mt-2">{hint}</div>
          </>
      }
    </div>
  )
}

export default function BandoDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [bando, setBando] = useState(null)
  const [loading, setLoading] = useState(true)
  const [analisi, setAnalisi] = useState([])
  const [analisiMio, setAnalisiMio] = useState([])
  const [loadingDoc, setLoadingDoc] = useState(0)
  const [loadingMio, setLoadingMio] = useState(0)

  async function uploadSingle(file, tipo) {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('tipo', tipo)
    const r = await fetch(`${import.meta.env.VITE_API_BASE || ''}/api/bandi/${id}/analizza-doc`, { method: 'POST', body: fd })
    if (!r.ok) { const d = await r.json(); throw new Error(d.detail || 'Errore server') }
    return r.json()
  }

  async function uploadFiles(files, tipo) {
    const setL = tipo === 'bando' ? setLoadingDoc : setLoadingMio
    const setA = tipo === 'bando' ? setAnalisi : setAnalisiMio
    setL(files.length)
    const results = []
    for (const file of files) {
      try {
        const data = await uploadSingle(file, tipo)
        results.push(data)
      } catch (e) {
        results.push({ nome_file: file.name, errore: e.message })
      }
      setL(prev => prev - 1)
      setA(prev => [...prev, results[results.length - 1]])
    }
  }

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

        {/* Checklist documenti */}
        {req.checklist_documenti?.length > 0 && (
          <div className="bg-white rounded border border-gray-200 p-6">
            <h3 className="font-mono text-xs uppercase tracking-widest text-gray-500 mb-1">Checklist documenti</h3>
            <p className="text-xs text-gray-400 font-sans mb-4">Documenti necessari per partecipare — basata su D.Lgs. 36/2023</p>
            {['amministrativa', 'tecnica', 'economica'].map(busta => {
              const docs = req.checklist_documenti.filter(d => d.busta === busta)
              if (!docs.length) return null
              return (
                <div key={busta} className="mb-4">
                  <div className="font-mono text-xs text-gray-400 uppercase mb-2">Busta {busta}</div>
                  <div className="space-y-1">
                    {docs.map((d, i) => (
                      <div key={i} className="flex items-start gap-3 text-sm py-1 border-b border-gray-50">
                        <span className={`mt-0.5 text-base ${d.obbligatorio ? 'text-verde' : 'text-giallo'}`}>
                          {d.obbligatorio ? '✓' : '○'}
                        </span>
                        <div className="flex-1">
                          <span className="font-sans font-medium">{d.documento}</span>
                          {d.nota && <span className="text-gray-400 font-sans ml-2 text-xs">{d.nota}</span>}
                        </div>
                        {!d.obbligatorio && <Tag color="gray">facoltativo</Tag>}
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}

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

        {/* Analisi documenti */}
        <div className="bg-white rounded border border-gray-200 p-6">
          <h3 className="font-mono text-xs uppercase tracking-widest text-gray-500 mb-1">Analisi documenti</h3>
          <p className="text-xs text-gray-400 font-sans mb-5">Carica uno o più PDF dal sito del bando oppure i tuoi documenti per verificarne la conformità</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="font-mono text-xs text-gray-500 uppercase mb-2">Documenti del bando</div>
              <UploadZone
                label="Carica disciplinare / capitolato"
                hint="Anche più PDF insieme — prime 12 pagine per file"
                loadingCount={loadingDoc}
                onFiles={files => uploadFiles(files, 'bando')}
              />
            </div>
            <div>
              <div className="font-mono text-xs text-gray-500 uppercase mb-2">Miei documenti</div>
              <UploadZone
                label="Carica DGUE / dichiarazione / offerta"
                hint="Verifico conformità rispetto al bando"
                loadingCount={loadingMio}
                onFiles={files => uploadFiles(files, 'mio')}
              />
            </div>
          </div>

          {/* Risultati analisi bando */}
          {analisi.map((item, idx) => (
            <div key={idx} className="mt-6 border-t border-gray-100 pt-5">
              <div className="flex items-center justify-between mb-3">
                <span className="font-mono text-xs text-gray-500 uppercase">Analisi: {item.nome_file}</span>
                {item.pagine_lette && <span className="font-mono text-xs text-gray-400">{item.pagine_lette} pagine lette</span>}
              </div>
              {item.errore
                ? <p className="text-xs text-rosso font-sans">{item.errore}</p>
                : <div className="space-y-3 text-sm">
                    {item.analisi?.riassunto && <p className="font-sans text-base leading-relaxed">{item.analisi.riassunto}</p>}
                    {item.analisi?.requisiti_tecnici?.length > 0 && (
                      <div>
                        <div className="font-mono text-xs text-gray-400 uppercase mb-1">Requisiti tecnici</div>
                        <ul className="space-y-0.5">{item.analisi.requisiti_tecnici.map((r, i) => <li key={i} className="font-sans text-sm text-gray-700 flex gap-2"><span className="text-verde">•</span>{r}</li>)}</ul>
                      </div>
                    )}
                    {item.analisi?.requisiti_amministrativi?.length > 0 && (
                      <div>
                        <div className="font-mono text-xs text-gray-400 uppercase mb-1">Requisiti amministrativi</div>
                        <ul className="space-y-0.5">{item.analisi.requisiti_amministrativi.map((r, i) => <li key={i} className="font-sans text-sm text-gray-700 flex gap-2"><span className="text-giallo">•</span>{r}</li>)}</ul>
                      </div>
                    )}
                    {item.analisi?.scadenze?.length > 0 && (
                      <div>
                        <div className="font-mono text-xs text-gray-400 uppercase mb-1">Scadenze</div>
                        <ul className="space-y-0.5">{item.analisi.scadenze.map((r, i) => <li key={i} className="font-sans text-sm text-gray-700 flex gap-2"><span className="text-accent">•</span>{r}</li>)}</ul>
                      </div>
                    )}
                    {item.analisi?.alert_cbs?.length > 0 && (
                      <div className="bg-giallo/5 border border-giallo/20 rounded p-3">
                        <div className="font-mono text-xs text-giallo uppercase mb-1">Alert CBS</div>
                        <ul className="space-y-0.5">{item.analisi.alert_cbs.map((r, i) => <li key={i} className="font-sans text-sm flex gap-2"><span>⚠</span>{r}</li>)}</ul>
                      </div>
                    )}
                  </div>
              }
            </div>
          ))}

          {/* Risultati analisi documenti miei */}
          {analisiMio.map((item, idx) => (
            <div key={idx} className="mt-6 border-t border-gray-100 pt-5">
              <div className="flex items-center justify-between mb-3">
                <span className="font-mono text-xs text-gray-500 uppercase">Verifica: {item.nome_file}</span>
                {item.analisi?.conformita && (
                  <span className={`font-mono text-xs px-2 py-0.5 rounded border ${item.analisi.conformita === 'conforme' ? 'text-verde border-verde/30 bg-verde/5' : item.analisi.conformita === 'parziale' ? 'text-giallo border-giallo/30 bg-giallo/5' : 'text-rosso border-rosso/30 bg-rosso/5'}`}>
                    {item.analisi.conformita.toUpperCase()}
                  </span>
                )}
              </div>
              {item.errore
                ? <p className="text-xs text-rosso font-sans">{item.errore}</p>
                : <div className="space-y-3 text-sm">
                    {item.analisi?.tipo_documento_rilevato && <div className="font-mono text-xs text-gray-400">Tipo: {item.analisi.tipo_documento_rilevato.replace(/_/g, ' ')}</div>}
                    {item.analisi?.elementi_ok?.length > 0 && (
                      <div>
                        <div className="font-mono text-xs text-gray-400 uppercase mb-1">OK</div>
                        <ul className="space-y-0.5">{item.analisi.elementi_ok.map((r, i) => <li key={i} className="font-sans text-sm flex gap-2"><span className="text-verde">✓</span>{r}</li>)}</ul>
                      </div>
                    )}
                    {item.analisi?.elementi_mancanti?.length > 0 && (
                      <div>
                        <div className="font-mono text-xs text-gray-400 uppercase mb-1">Mancanti</div>
                        <ul className="space-y-0.5">{item.analisi.elementi_mancanti.map((r, i) => <li key={i} className="font-sans text-sm flex gap-2"><span className="text-giallo">○</span>{r}</li>)}</ul>
                      </div>
                    )}
                    {item.analisi?.elementi_errati?.length > 0 && (
                      <div>
                        <div className="font-mono text-xs text-gray-400 uppercase mb-1">Da correggere</div>
                        <ul className="space-y-0.5">{item.analisi.elementi_errati.map((r, i) => <li key={i} className="font-sans text-sm flex gap-2"><span className="text-rosso">✗</span>{r}</li>)}</ul>
                      </div>
                    )}
                    {item.analisi?.azioni_richieste?.length > 0 && (
                      <div className="bg-rosso/5 border border-rosso/20 rounded p-3">
                        <div className="font-mono text-xs text-rosso uppercase mb-1">Azioni richieste</div>
                        <ol className="space-y-0.5 list-decimal list-inside">{item.analisi.azioni_richieste.map((r, i) => <li key={i} className="font-sans text-sm">{r}</li>)}</ol>
                      </div>
                    )}
                    {item.analisi?.rischio_esclusione && (
                      <div className="flex items-center gap-2 text-xs font-sans text-gray-500">
                        Rischio esclusione: <RischioTag rischio={item.analisi.rischio_esclusione} />
                        {item.analisi.rischio_note && <span>— {item.analisi.rischio_note}</span>}
                      </div>
                    )}
                  </div>
              }
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
