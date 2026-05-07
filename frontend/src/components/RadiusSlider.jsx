const STEPS = [10, 25, 50, 75, 100]

export default function RadiusSlider({ value, onChange }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm font-sans text-gray-600 whitespace-nowrap">Raggio:</span>
      <input
        type="range"
        min={0}
        max={STEPS.length - 1}
        step={1}
        value={STEPS.indexOf(value) !== -1 ? STEPS.indexOf(value) : 2}
        onChange={(e) => onChange(STEPS[Number(e.target.value)])}
        className="w-32 accent-accent"
      />
      <span className="font-mono text-sm font-semibold w-16">{value} km</span>
    </div>
  )
}
