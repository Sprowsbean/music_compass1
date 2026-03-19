import type { ScoredSong } from '../services/api';

interface Props {
  songs: ScoredSong[];
}

const SOURCE_BADGE: Record<string, { label: string; cls: string }> = {
  kaggle_exact:     { label: 'DB',    cls: 'badge badge-kaggle' },
  kaggle_fuzzy:     { label: 'Fuzzy', cls: 'badge badge-fuzzy'  },
  gemini_predicted: { label: 'AI',    cls: 'badge badge-gemini' },
  default:          { label: '—',     cls: 'badge badge-default'},
};

export default function TopSongsTable({ songs }: Props) {
  const plotted = songs
    .filter(s => s.energy != null && s.valence != null)
    .slice(0, 30);

  return (
    <div className="nebula-card" style={{ padding: 24 }}>
      <h3 style={{
        fontFamily: 'Orbitron', fontWeight: 700, fontSize: '0.8rem',
        letterSpacing: '0.12em', color: '#818cf8',
        textTransform: 'uppercase', marginBottom: 16,
      }}>
        Top Songs by Listening Time
      </h3>

      <div style={{ maxHeight: 380, overflowY: 'auto' }}>
        {plotted.map((s, i) => {
          const badge = SOURCE_BADGE[s.source] ?? SOURCE_BADGE.default;
          return (
            <div
              key={`${s.track}-${s.artist}`}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '9px 0',
                borderBottom: '1px solid rgba(79,70,229,0.08)',
                fontSize: 11, fontFamily: 'DM Mono',
              }}
            >
              <span style={{ color: '#2e2c50', minWidth: 22, fontFamily: 'Orbitron', fontSize: 10 }}>
                {i + 1}
              </span>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: '#e8e6ff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {s.track}
                </div>
                <div style={{ color: '#4a4870', fontSize: 10, marginTop: 1 }}>{s.artist}</div>
              </div>

              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ color: '#fbbf24' }}>{Math.round(s.total_ms / 60000)} min</div>
                <div style={{ fontSize: 9, color: '#3a3860' }}>
                  E:{s.energy?.toFixed(2)} · V:{s.valence?.toFixed(2)}
                </div>
              </div>

              <span className={badge.cls} style={{ minWidth: 44, textAlign: 'center' }}>
                {badge.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
