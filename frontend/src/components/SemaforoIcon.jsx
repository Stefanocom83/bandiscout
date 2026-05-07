export default function SemaforoIcon({ semaforo, size = 'md' }) {
  const map = {
    verde:  { emoji: '🟢', label: 'Partecipa', cls: 'text-verde' },
    giallo: { emoji: '🟡', label: 'Valuta',    cls: 'text-giallo' },
    rosso:  { emoji: '🔴', label: 'Salta',     cls: 'text-rosso' },
  }
  const s = map[semaforo] || { emoji: '⚪', label: 'N/D', cls: 'text-gray-400' }
  const sz = size === 'lg' ? 'text-3xl' : 'text-lg'

  return (
    <span className={`font-mono ${sz} ${s.cls}`} title={s.label}>
      {s.emoji}
    </span>
  )
}
