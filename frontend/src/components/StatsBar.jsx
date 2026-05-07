export default function StatsBar({ stats }) {
  const cards = [
    { label: 'Totale', value: stats?.totale ?? '—', cls: 'border-navy' },
    { label: '🟢 Verdi', value: stats?.verdi ?? '—', cls: 'border-verde' },
    { label: '🟡 Gialli', value: stats?.gialli ?? '—', cls: 'border-giallo' },
    { label: '🔴 Rossi', value: stats?.rossi ?? '—', cls: 'border-rosso' },
  ]

  return (
    <div className="grid grid-cols-4 gap-3 mb-6">
      {cards.map((c) => (
        <div key={c.label} className={`bg-white border-l-4 ${c.cls} p-4 rounded`}>
          <div className="text-xs text-gray-500 uppercase tracking-wide font-sans">{c.label}</div>
          <div className="text-3xl font-mono font-semibold mt-1">{c.value}</div>
        </div>
      ))}
    </div>
  )
}
