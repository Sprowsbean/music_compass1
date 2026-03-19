interface Props {
  data:      any;
  userColor: string;
}

const ELEMENT_COLORS: Record<string, string> = {
  Fire: '#f97316', Water: '#00e5ff', Earth: '#34d399',
  Air: '#e8e6ff', Void: '#a78bfa', Plasma: '#f472b6',
};

const ZODIAC_SYMBOLS: Record<string, string> = {
  Aries: '♈', Taurus: '♉', Gemini: '♊', Cancer: '♋',
  Leo: '♌', Virgo: '♍', Libra: '♎', Scorpio: '♏',
  Sagittarius: '♐', Capricorn: '♑', Aquarius: '♒', Pisces: '♓',
};

export default function AstrologyCard({ data, userColor }: Props) {
  const reading = data?.reading;
  if (!reading) return null;

  const elColor = ELEMENT_COLORS[reading.element] ?? userColor;
  const zodiac  = reading.zodiac ?? data.zodiac ?? null;

  // Split reading into paragraphs for styled rendering
  const paragraphs: string[] = (reading.reading ?? '')
    .split(/\n\n+/)
    .map((p: string) => p.trim())
    .filter(Boolean);

  const PARA_LABELS = ['AMBITION & DRIVE', 'SOCIAL ENERGY', 'UNDER PRESSURE', 'HIDDEN TRUTH'];

  return (
    <div className="fade-up" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Zodiac banner ───────────────────────────────────────────── */}
      {zodiac && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
          padding: '14px 20px', borderRadius: 12,
          background: `${elColor}0d`,
          border: `1px solid ${elColor}30`,
        }}>
          {/* Big symbol */}
          <div style={{
            fontSize: 44, lineHeight: 1, color: elColor,
            textShadow: `0 0 24px ${elColor}80`,
          }}>
            {zodiac.symbol ?? ZODIAC_SYMBOLS[zodiac.name] ?? '✦'}
          </div>

          <div style={{ flex: 1 }}>
            <div style={{
              fontFamily: 'Orbitron', fontWeight: 900, fontSize: '1.1rem',
              color: elColor, letterSpacing: '0.06em', marginBottom: 4,
            }}>
              {zodiac.name?.toUpperCase()}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {(zodiac.traits ?? []).map((t: string, i: number) => (
                <span key={i} style={{
                  fontFamily: 'DM Mono', fontSize: 10,
                  color: elColor, opacity: 0.8,
                  background: `${elColor}14`,
                  border: `1px solid ${elColor}28`,
                  padding: '3px 9px', borderRadius: 20,
                }}>
                  {t}
                </span>
              ))}
            </div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 8, letterSpacing: '0.15em', color: '#4a4870', fontFamily: 'Orbitron', marginBottom: 2 }}>
              ELEMENT
            </div>
            <div style={{ fontFamily: 'Orbitron', fontWeight: 800, fontSize: 13, color: elColor }}>
              {zodiac.element ?? reading.element}
            </div>
          </div>
        </div>
      )}

      {/* ── Archetype + headline ─────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <div style={{
            fontFamily: 'Orbitron', fontWeight: 900, fontSize: 22,
            color: userColor, letterSpacing: '0.03em', marginBottom: 6,
          }}>
            {reading.archetype}
          </div>
          <div style={{
            fontFamily: 'DM Mono', fontSize: 13, color: '#8b87c0',
            fontStyle: 'italic', maxWidth: 480,
          }}>
            "{reading.headline}"
          </div>
        </div>

        {/* Element + Hz pill (only if no zodiac banner handled it) */}
        {!zodiac && (
          <div style={{
            textAlign: 'center', padding: '12px 18px', borderRadius: 10,
            background: elColor + '12', border: `1px solid ${elColor}35`,
          }}>
            <div style={{ fontSize: 9, letterSpacing: '0.15em', color: '#4a4870', marginBottom: 4, fontFamily: 'Orbitron' }}>
              ELEMENT
            </div>
            <div style={{ fontFamily: 'Orbitron', fontWeight: 800, fontSize: 16, color: elColor }}>
              {reading.element}
            </div>
            <div style={{ fontSize: 9, color: '#3a3860', marginTop: 2, fontFamily: 'DM Mono' }}>
              {reading.hz}
            </div>
          </div>
        )}
      </div>

      {/* ── Hz line (when zodiac banner shown) ──────────────────────── */}
      {zodiac && reading.hz && (
        <div style={{
          fontFamily: 'DM Mono', fontSize: 11, color: '#4a4870',
          letterSpacing: '0.05em', textAlign: 'center',
        }}>
          {reading.sigil ?? '✦'} &nbsp; {reading.hz}
        </div>
      )}

      {/* ── Personality trait chips ──────────────────────────────────── */}
      {reading.traits?.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {reading.traits.map((t: string, i: number) => (
            <span key={i} style={{
              fontFamily: 'DM Mono', fontSize: 11,
              color: userColor,
              background: `${userColor}12`,
              border: `1px solid ${userColor}30`,
              padding: '4px 12px', borderRadius: 20,
            }}>
              {t}
            </span>
          ))}
        </div>
      )}

      {/* ── Four-paragraph reading ───────────────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {paragraphs.map((para, i) => (
          <div key={i} style={{
            padding: '14px 18px',
            background: 'rgba(79,70,229,0.04)',
            border: `1px solid rgba(79,70,229,0.15)`,
            borderLeft: `3px solid ${i === 3 ? elColor : userColor}`,
            borderRadius: '0 10px 10px 0',
          }}>
            {PARA_LABELS[i] && (
              <div style={{
                fontFamily: 'Orbitron', fontSize: 8, letterSpacing: '0.18em',
                color: i === 3 ? elColor : userColor,
                opacity: 0.7, marginBottom: 8,
              }}>
                {PARA_LABELS[i]}
              </div>
            )}
            <p style={{
              fontFamily: 'DM Mono', fontSize: 13, color: '#9b98c8',
              lineHeight: 1.95, margin: 0,
            }}>
              {para}
            </p>
          </div>
        ))}
      </div>

      {/* ── Data summary ─────────────────────────────────────────────── */}
      {data.centroid && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {[
            ['Centroid Energy',  data.centroid.energy?.toFixed(3),  '#00e5ff'],
            ['Centroid Valence', data.centroid.valence?.toFixed(3), '#f472b6'],
            ['Quadrant',         data.quadrant,                      '#fbbf24'],
          ].map(([label, val, col]) => (
            <div key={label} style={{
              flex: 1, minWidth: 110, textAlign: 'center',
              padding: '10px 14px', borderRadius: 8,
              background: `${col}0d`, border: `1px solid ${col}25`,
            }}>
              <div style={{ fontSize: 8, color: '#4a4870', fontFamily: 'Orbitron', letterSpacing: '0.1em', marginBottom: 3 }}>{label}</div>
              <div style={{ fontSize: 13, color: col, fontFamily: 'Orbitron', fontWeight: 700 }}>{val}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
