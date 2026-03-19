import { useMemo } from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, ResponsiveContainer,
} from 'recharts';
import type { ScoredSong } from '../services/api';

interface Props {
  songs:     ScoredSong[];
  userColor: string;
  userName:  string;
}

const FEATURES: { key: keyof ScoredSong; label: string }[] = [
  { key: 'energy',   label: 'Energy'   },
  { key: 'valence',  label: 'Valence'  },
];

export default function TasteRadar({ songs, userColor, userName }: Props) {
  const data = useMemo(() => {
    const valid = songs.filter(s => s.energy != null && s.valence != null);
    if (!valid.length) return [];
    const totalW = valid.reduce((s, x) => s + (x.total_ms || 1), 0);
    return FEATURES.map(({ key, label }) => {
      const wAvg = valid.reduce((s, x) => s + (x.total_ms || 1) * (Number(x[key]) || 0), 0) / totalW;
      return { trait: label, value: Math.round(wAvg * 100) };
    });
  }, [songs]);

  if (data.length === 0) return null;

  return (
    <div className="nebula-card" style={{ padding: 24 }}>
      <h3 style={{
        fontFamily: 'Orbitron', fontWeight: 700, fontSize: '0.8rem',
        letterSpacing: '0.1em', color: userColor, textTransform: 'uppercase',
        textAlign: 'center', marginBottom: 8,
      }}>
        {userName.toUpperCase()}'S TASTE FINGERPRINT
      </h3>
      <ResponsiveContainer width="100%" height={240}>
        <RadarChart data={data}>
          <PolarGrid stroke="rgba(79,70,229,0.35)" />
          <PolarAngleAxis dataKey="trait" tick={{ fill: '#4a4870', fontFamily: 'DM Mono', fontSize: 11 }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#2e2c50', fontSize: 9 }} />
          <Radar name={userName} dataKey="value" stroke={userColor} fill={userColor} fillOpacity={0.2} strokeWidth={2} />
        </RadarChart>
      </ResponsiveContainer>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 32 }}>
        {data.map(d => (
          <div key={d.trait} style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 9, color: '#4a4870', fontFamily: 'Orbitron', letterSpacing: '0.1em' }}>{d.trait}</div>
            <div style={{ fontSize: 18, fontFamily: 'Orbitron', fontWeight: 800, color: userColor }}>{d.value}%</div>
          </div>
        ))}
      </div>
    </div>
  );
}
