const getLocalDate = date => {
  if (typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date)) return date
  return new Date(date).toLocaleDateString('en-CA')
}

export default function StreakBadge({ entries }) {
  if (!entries || entries.length === 0) return null
  let streak = 0
  const today = new Date()
  for (let i = 0; i < 60; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    const ds = getLocalDate(d)
    if (entries.find(e => e.date?.slice(0, 10) === ds)) streak++
    else if (i > 0) break
  }
  if (streak === 0) return null
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--amber-bg)', borderRadius: 'var(--radius-md)', padding: '6px 12px' }}>
      <span style={{ fontSize: 14 }}>🔥</span>
      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--amber-txt)' }}>{streak} day streak</span>
    </div>
  )
}
