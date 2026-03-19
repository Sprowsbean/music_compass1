import { useMemo } from 'react';
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import type { ScoredSong } from '../services/api';
import type { RegressionResult } from '../services/api';

interface Props {
  songs:      ScoredSong[];
  userColor:  string;
  userName:   string;
  regression: RegressionResult | null;
  multiUser?: { name: string; color: string }[];
}

const SOURCE_COLOR: Record<string, string> = {
  kaggle_exact:     '#00e5ff',
  kaggle_fuzzy:     '#fbbf24',
  gemini_predicted: '#f472b6',
  default:          '#3730a3',
};

const SOURCE_LABEL: Record<string, string> = {
  kaggle_exact:     'Kaggle DB',
  kaggle_fuzzy:     'Kaggle Fuzzy',
  gemini_predicted: 'Gemini AI',
  default:          'Default',
};

function SongTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const s: ScoredSong & { x: number; y: number; r: number; user_color?: string } =
    payload[0]?.payload;
  if (!s) return null;

  const srcColor = SOURCE_COLOR[s.source] ?? '#5a5880';
  const srcLabel = SOURCE_LABEL[s.source] ?? s.source;

  return (
    <div style={{
      background: 'rgba(3,1,15,0.97)',
      border: '1px solid rgba(79,70,229,0.4)',
      borderRadius: 12, padding: '12px 15px', minWidth: 210,
      fontFamily: 'DM Mono', backdropFilter: 'blur(20px)',
    }}>
      <p style={{ color: '#e8e6ff', fontSize: 13, fontWeight: 600, marginBottom: 2 }}>
        {s.track}
      </p>
      <p style={{ color: '#4a4870', fontSize: 11, marginBottom: 10 }}>{s.artist}</p>
      <div style={{ fontSize: 11, borderTop: '1px solid rgba(79,70,229,0.2)', paddingTop: 8 }}>
        {[
          ['Play time', `${Math.round((s.total_ms || 0) / 60000)} min`, '#fbbf24'],
          ['Energy',    (s.energy  ?? 0).toFixed(3),                   '#00e5ff'],
          ['Valence',   (s.valence ?? 0).toFixed(3),                   '#f472b6'],
          ['Genre',     s.genre || '—',                                '#a78bfa'],
        ].map(([label, val, col]) => (
          <div key={label as string} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <span style={{ color: '#4a4870' }}>{label}</span>
            <span style={{ color: col as string }}>{val}</span>
          </div>
        ))}
      </div>
      <span style={{
        display: 'inline-block', marginTop: 8,
        background: srcColor + '18', color: srcColor,
        border: `1px solid ${srcColor}35`,
        padding: '2px 8px', borderRadius: 4, fontSize: 10,
      }}>{srcLabel}</span>
    </div>
  );
}

export default function MusicMap({ songs, userColor, userName, regression, multiUser }: Props) {
  const isMulti = multiUser && multiUser.length > 0;

  const plotSongs = useMemo(
    () => songs.filter(s => s.energy != null && s.valence != null),
    [songs],
  );

  // Dot size proportional to listening time
  const sizes = useMemo(() => {
    const msList = plotSongs.map(s => s.total_ms || 1);
    const maxMs  = Math.max(...msList, 1);
    const minMs  = Math.min(...msList, 1);
    const range  = maxMs - minMs || 1;
    return plotSongs.map(s => { const norm = ((s.total_ms || minMs) - minMs) / range; return 4 + Math.pow(norm, 0.25) * 20; });
  }, [plotSongs]);

  const chartData = useMemo(
    () => plotSongs.map((s, i) => ({ ...s, x: s.energy!, y: s.valence!, r: sizes[i] })),
    [plotSongs, sizes],
  );

  // Regression line end-points
  const regLine = useMemo(() => {
    if (!regression || regression.error) return null;
    const { slope, intercept } = regression;
    return [
      { x: 0, y: Math.max(0, Math.min(1, intercept)) },
      { x: 1, y: Math.max(0, Math.min(1, slope + intercept)) },
    ];
  }, [regression]);

  return (
    <div className="nebula-card" style={{ padding: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 18, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{
            fontFamily: 'Orbitron', fontWeight: 800, fontSize: '1rem',
            color: '#00e5ff', letterSpacing: '0.05em', marginBottom: 4,
          }}>
            {isMulti ? 'COMBINED NEBULA MAP' : `${userName.toUpperCase()}'S NEBULA MAP`}
          </h2>
          <p style={{ fontSize: 11, color: '#3a3860', fontFamily: 'DM Mono' }}>
            X = Energy · Y = Valence · Dot size = listening time
            {regLine ? ' · Gold line = regression' : ''}
          </p>
        </div>

        {/* Source legend (single-user) */}
        {!isMulti && (
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {[
              ['Kaggle DB',    '#00e5ff'],
              ['Kaggle Fuzzy', '#fbbf24'],
              ['Gemini AI',    '#f472b6'],
            ].map(([label, color]) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: color, fontFamily: 'DM Mono' }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: color, display: 'inline-block' }} />
                {label}
              </div>
            ))}
          </div>
        )}

        {/* Multi-user legend */}
        {isMulti && (
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {multiUser!.map(u => (
              <div key={u.name} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: u.color, fontFamily: 'Orbitron' }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: u.color, display: 'inline-block' }} />
                {u.name}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Chart */}
      <div style={{ height: 540, position: 'relative' }}>
        {/* Quadrant labels */}
        {([
          ['↗ Energetic & Happy', '66%', '4%',  '#34d399'],
          ['↖ Energetic & Dark',  '4%',  '4%',  '#f87171'],
          ['↘ Chill & Happy',     '66%', '89%', '#60a5fa'],
          ['↙ Melancholic',       '4%',  '89%', '#c084fc'],
        ] as const).map(([label, left, top, col]) => (
          <div key={label} style={{
            position: 'absolute', left, top,
            fontSize: 9, color: col, opacity: 0.55,
            letterSpacing: '0.05em', pointerEvents: 'none', fontFamily: 'DM Mono',
          }}>{label}</div>
        ))}

        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 30, right: 30, bottom: 44, left: 14 }}>
            <CartesianGrid strokeDasharray="1 8" stroke="rgba(79,70,229,0.13)" />
            <XAxis
              type="number" dataKey="x" domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]}
              tick={{ fill: '#3a3860', fontFamily: 'DM Mono', fontSize: 10 }}
              stroke="rgba(79,70,229,0.25)"
              label={{ value: 'Energy →', position: 'insideBottom', offset: -14, fill: '#4a4870', fontFamily: 'DM Mono', fontSize: 11 }}
            />
            <YAxis
              type="number" dataKey="y" domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]}
              tick={{ fill: '#3a3860', fontFamily: 'DM Mono', fontSize: 10 }}
              stroke="rgba(79,70,229,0.25)"
              label={{ value: 'Valence →', angle: -90, position: 'insideLeft', offset: 18, fill: '#4a4870', fontFamily: 'DM Mono', fontSize: 11 }}
            />
            <Tooltip
              content={<SongTooltip />}
              cursor={{ strokeDasharray: '3 3', stroke: 'rgba(255,255,255,0.06)' }}
            />

            {/* Midpoint grid lines */}
            <ReferenceLine x={0.5} stroke="rgba(255,255,255,0.04)" />
            <ReferenceLine y={0.5} stroke="rgba(255,255,255,0.04)" />

            {/* Regression line */}
            {regLine && (
              <ReferenceLine
                segment={regLine}
                stroke="#fbbf24"
                strokeWidth={2}
                strokeDasharray="6 4"
                label={{
                  value: `slope ${regression!.slope > 0 ? '+' : ''}${regression!.slope}  R²=${regression!.r_squared}`,
                  fill: '#fbbf24', fontFamily: 'DM Mono', fontSize: 9,
                  position: 'insideTopRight',
                }}
              />
            )}

            <Scatter data={chartData} shape={(props: any) => {
                const { cx, cy, payload } = props;
                const color = isMulti
                  ? ((payload as any).user_color || userColor)
                  : SOURCE_COLOR[payload.source] ?? userColor;
                const radius = Math.max(4, Math.min(Math.sqrt(payload.r / 1000) * 0.8, 25));
                return <circle cx={cx} cy={cy} r={radius} fill={color} fillOpacity={0.75} />;
              }}>

            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
