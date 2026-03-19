import { useState } from 'react';
import { Compass, Plus, Trash2, AlertTriangle, X } from 'lucide-react';
import { usePipeline } from './hooks/usePipeline';
import UploadZone from './components/UploadZone';
import MusicMap from './components/MusicMap';
import TasteRadar from './components/RadarChart';
import AstrologyCard from './components/AstrologyCard';
import TopSongsTable from './components/TopSongsTable';

type View = 'home' | 'upload' | 'results';

export default function App() {
  const [view, setView] = useState<View>('home');

  const {
    users, phase, progress, error,
    regression, astrology, astrologyLoading,
    selectedIdx, selectedUser, isRunning,
    addUser, removeUser, switchUser, readAstrology,
    reset, clearError,
  } = usePipeline();

  const handleUpload = async (files: File[], name: string, dateOfBirth: string) => {
    await addUser(files, name, dateOfBirth);
    setView('results');
  };

  const handleRemoveUser = (idx: number) => {
    removeUser(idx);
    if (users.length <= 1) setView('home');
  };

  // ── HOME ─────────────────────────────────────────────────────────────────
  if (view === 'home') return (
    <Page>
      <div style={{ textAlign: 'center', paddingTop: '4rem' }}>
        <Tag>GALACTIC MUSIC INTELLIGENCE</Tag>
        <h1 style={{
          fontFamily: 'Orbitron', fontWeight: 900,
          fontSize: 'clamp(2.4rem,8vw,5rem)', letterSpacing: '0.05em', lineHeight: 1.1,
          margin: '16px 0',
        }}>
          <span style={{ color: '#00e5ff', textShadow: '0 0 30px rgba(0,229,255,0.6)' }}>MUSIC</span>
          {' '}
          <span style={{ color: '#f472b6', textShadow: '0 0 30px rgba(244,114,182,0.6)' }}>COMPASS</span>
        </h1>
        <p style={{ color: '#4a4870', fontFamily: 'DM Mono', lineHeight: 1.8, maxWidth: 480, margin: '0 auto 2.5rem' }}>
          Upload your Spotify history. Your songs are matched against<br />
          a 100k-song Kaggle database — unknowns scored by Gemini AI.<br />
          Dot size = how much you listened.
        </p>
        <button className="btn-primary" onClick={() => setView('upload')}>
          <Compass size={16} /> Upload Spotify History
        </button>
      </div>

      {/* Pipeline steps */}
      <div style={{ marginTop: '5rem' }}>
        <p style={{ textAlign: 'center', fontSize: 9, letterSpacing: '0.2em', color: '#3a3860', fontFamily: 'Orbitron', marginBottom: '1.5rem' }}>
          HOW IT WORKS
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 12 }}>
          {[
            { n: '01', title: 'Upload',   body: 'StreamingHistory_music_0.json from Spotify' },
            { n: '02', title: 'Extract',  body: 'Every unique song + sum of all msPlayed' },
            { n: '03', title: 'Kaggle',   body: 'Match track name → get exact energy & valence' },
            { n: '04', title: 'Gemini',   body: 'Predict missing songs calibrated to Kaggle scale' },
            { n: '05', title: 'Plot',     body: 'Scatter map, dot size = listening time' },
          ].map(s => (
            <div key={s.n} className="nebula-card" style={{ padding: '18px 16px', textAlign: 'center' }}>
              <div style={{ fontFamily: 'Orbitron', fontWeight: 800, fontSize: 22, color: 'rgba(79,70,229,0.5)', marginBottom: 6 }}>{s.n}</div>
              <div style={{ fontFamily: 'Orbitron', fontWeight: 600, fontSize: '0.75rem', color: '#00e5ff', marginBottom: 5, letterSpacing: '0.05em' }}>{s.title}</div>
              <div style={{ color: '#3a3860', fontSize: '0.75rem', fontFamily: 'DM Mono', lineHeight: 1.5 }}>{s.body}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="nebula-card" style={{ padding: '24px 28px', marginTop: '3rem', maxWidth: 520, margin: '3rem auto 0' }}>
        <p style={{ fontFamily: 'Orbitron', fontSize: '0.72rem', color: '#fbbf24', letterSpacing: '0.12em', marginBottom: 12 }}>
          GET YOUR SPOTIFY DATA
        </p>
        <ol style={{ fontFamily: 'DM Mono', fontSize: '0.8rem', color: '#4a4870', lineHeight: 2.1, paddingLeft: 0, listStyle: 'none' }}>
          {[
            'Spotify → Settings → Privacy Settings',
            'Click "Request data download"',
            'Wait for email (1–5 business days)',
            'Extract the ZIP file you receive',
            'Upload StreamingHistory_music_0.json here',
          ].map((step, i) => (
            <li key={i} style={{ display: 'flex', gap: 10 }}>
              <span style={{ color: '#f472b6', minWidth: 18 }}>{i + 1}.</span>
              {step}
            </li>
          ))}
        </ol>
      </div>
    </Page>
  );

  // ── UPLOAD ────────────────────────────────────────────────────────────────
  if (view === 'upload') return (
    <Page>
      <div style={{ maxWidth: 520, margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <h2 style={{ fontFamily: 'Orbitron', fontWeight: 800, fontSize: '1.6rem', color: '#00e5ff', letterSpacing: '0.05em', marginBottom: 6 }}>
            {users.length === 0 ? 'ENTER THE NEBULA' : 'ADD TRAVELLER'}
          </h2>
          {users.length > 0 && (
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
              {users.map((u, i) => (
                <span key={i} style={{
                  background: u.color + '18', color: u.color,
                  border: `1px solid ${u.color}40`,
                  padding: '3px 10px', borderRadius: 20, fontSize: 11, fontFamily: 'Orbitron',
                }}>{u.name}</span>
              ))}
            </div>
          )}
        </div>

        <div className="nebula-card" style={{ padding: 28 }}>
          <UploadZone
            onUpload={handleUpload}
            loading={isRunning}
            progress={progress}
            error={error}
          />
        </div>

        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <button className="btn-ghost" onClick={() => setView(users.length > 0 ? 'results' : 'home')}>
            ← {users.length > 0 ? 'Back to Results' : 'Back'}
          </button>
        </div>
      </div>
    </Page>
  );

  // ── RESULTS ───────────────────────────────────────────────────────────────
  return (
    <Page>
      {/* User tabs */}
      <div className="nebula-card" style={{ padding: '12px 18px', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontFamily: 'Orbitron', fontSize: '0.62rem', letterSpacing: '0.15em', color: '#3a3860' }}>
            TRAVELLER
          </span>
          {users.map((u, i) => (
            <button
              key={i}
              onClick={() => switchUser(i)}
              style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '7px 14px', borderRadius: 8, cursor: 'pointer',
                background: selectedIdx === i ? u.color + '18' : 'rgba(255,255,255,0.02)',
                border: `1px solid ${selectedIdx === i ? u.color : 'rgba(255,255,255,0.08)'}`,
                color: selectedIdx === i ? u.color : '#4a4870',
                fontFamily: 'Orbitron', fontSize: '0.72rem', letterSpacing: '0.05em',
                transition: 'all 0.2s',
              }}
            >
              <span className={selectedIdx === i ? 'pulse-dot' : ''} style={{ width: 7, height: 7, borderRadius: '50%', background: u.color }} />
              {u.name}
              <span
                onClick={e => { e.stopPropagation(); handleRemoveUser(i); }}
                style={{ color: '#3a3860', cursor: 'pointer', marginLeft: 2, display: 'flex' }}
              >
                <Trash2 size={11} />
              </span>
            </button>
          ))}
          {users.length < 6 && (
            <button className="btn-ghost" style={{ padding: '7px 14px', fontSize: '0.68rem' }}
                    onClick={() => setView('upload')}>
              <Plus size={12} /> Add
            </button>
          )}
          <button className="btn-ghost" style={{ padding: '7px 14px', fontSize: '0.68rem', marginLeft: 'auto' }}
                  onClick={() => { reset(); setView('home'); }}>
            Reset
          </button>
        </div>
      </div>

      {selectedUser && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Profile stats */}
          <div className="nebula-card" style={{ padding: '24px 28px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
              <span className="pulse-dot" style={{ width: 10, height: 10, borderRadius: '50%', background: selectedUser.color }} />
              <h2 style={{ fontFamily: 'Orbitron', fontWeight: 800, fontSize: '1rem', color: selectedUser.color, letterSpacing: '0.05em' }}>
                {selectedUser.name.toUpperCase()}'S PROFILE
              </h2>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(110px,1fr))', gap: 12 }}>
              {[
                { label: 'UNIQUE SONGS',   val: selectedUser.stats.total,   col: '#e8e6ff' },
                { label: 'LISTENING TIME', val: `${Math.round(selectedUser.totalMs / 3_600_000)}h`, col: '#f472b6' },
                { label: 'FROM KAGGLE',    val: selectedUser.stats.kaggle + selectedUser.stats.fuzzy, col: '#00e5ff' },
                { label: 'AI SCORED',      val: selectedUser.stats.gemini,  col: '#f472b6' },
                { label: 'PLOTTED',        val: selectedUser.stats.plotted, col: '#a78bfa' },
              ].map(item => (
                <div key={item.label} style={{
                  textAlign: 'center', padding: '12px 10px', borderRadius: 8,
                  background: `${item.col}0a`, border: `1px solid ${item.col}20`,
                }}>
                  <div style={{ fontSize: 8, letterSpacing: '0.12em', color: '#3a3860', fontFamily: 'Orbitron', marginBottom: 4 }}>{item.label}</div>
                  <div style={{ fontFamily: 'Orbitron', fontWeight: 800, fontSize: 20, color: item.col }}>{item.val}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Nebula Map */}
          <MusicMap
            songs={selectedUser.songs}
            userColor={selectedUser.color}
            userName={selectedUser.name}
            regression={regression}
          />

          {/* Regression */}
          {regression && !regression.error && (
            <div className="nebula-card" style={{ padding: 24 }}>
              <p style={{ fontFamily: 'Orbitron', fontSize: '0.72rem', color: '#fbbf24', letterSpacing: '0.12em', marginBottom: 14 }}>
                REGRESSION ANALYSIS — ENERGY VS VALENCE
              </p>
              <div style={{ display: 'flex', gap: 24, marginBottom: 14, flexWrap: 'wrap' }}>
                {[
                  { label: 'SLOPE',      val: regression.slope,     col: regression.slope > 0 ? '#34d399' : '#f87171' },
                  { label: 'R²',         val: regression.r_squared,  col: '#00e5ff' },
                  { label: 'SONGS',      val: regression.n_songs,    col: '#a78bfa' },
                ].map(item => (
                  <div key={item.label} style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 8, letterSpacing: '0.12em', color: '#3a3860', fontFamily: 'Orbitron', marginBottom: 3 }}>{item.label}</div>
                    <div style={{ fontFamily: 'Orbitron', fontWeight: 800, fontSize: 22, color: item.col }}>{item.val}</div>
                  </div>
                ))}
              </div>
              <p style={{
                fontFamily: 'DM Mono', fontSize: 13, color: '#7b78a8', lineHeight: 1.8,
                borderLeft: '3px solid #4f46e5', paddingLeft: 14, margin: 0,
              }}>
                {regression.interpretation}
              </p>
            </div>
          )}

          {/* Taste radar */}
          <TasteRadar songs={selectedUser.songs} userColor={selectedUser.color} userName={selectedUser.name} />

          {/* Top songs */}
          <TopSongsTable songs={selectedUser.songs} />

          {/* Music Astrology */}
          <div className="nebula-card" style={{ padding: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14, flexWrap: 'wrap', gap: 10 }}>
              <p style={{ fontFamily: 'Orbitron', fontSize: '0.72rem', color: '#f472b6', letterSpacing: '0.12em' }}>
                🔮 MUSIC ASTROLOGY
              </p>
              {!astrology && (
                <button
                  className="btn-danger"
                  onClick={readAstrology}
                  disabled={astrologyLoading}
                >
                  {astrologyLoading ? 'READING STARS…' : 'READ MY COSMIC CHART'}
                </button>
              )}
            </div>
            {astrology ? (
              <AstrologyCard data={astrology} userColor={selectedUser.color} />
            ) : (
              <p style={{ color: '#3a3860', fontFamily: 'DM Mono', fontSize: 12 }}>
                Gemini Flash will analyze your regression pattern and generate a cosmic music personality reading.
                Requires GEMINI_API_KEY set in backend/.env
              </p>
            )}
          </div>

          {/* Combined map for multi-user */}
          {users.length >= 2 && (
            <MusicMap
              songs={users.flatMap(u => u.songs.map(s => ({ ...s, user_color: u.color } as any)))}
              userColor="#888"
              userName="Squad"
              regression={null}
              multiUser={users.map(u => ({ name: u.name, color: u.color }))}
            />
          )}

        </div>
      )}

      {/* Error toast */}
      {error && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24,
          display: 'flex', alignItems: 'center', gap: 10,
          background: 'rgba(248,113,113,0.12)',
          border: '1px solid rgba(248,113,113,0.35)',
          borderRadius: 10, padding: '11px 16px', maxWidth: 360,
          backdropFilter: 'blur(16px)',
        }}>
          <AlertTriangle size={15} style={{ color: '#f87171', flexShrink: 0 }} />
          <span style={{ color: '#fca5a5', fontFamily: 'DM Mono', fontSize: 12 }}>{error}</span>
          <button onClick={clearError} style={{ color: '#f87171', background: 'none', border: 'none', cursor: 'pointer', marginLeft: 4 }}>
            <X size={14} />
          </button>
        </div>
      )}
    </Page>
  );
}

// ── Layout wrappers ──────────────────────────────────────────────────────────
function Page({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <Nav />
      <main style={{ maxWidth: 980, margin: '0 auto', padding: '36px 20px 80px' }}>
        {children}
      </main>
      <footer style={{ borderTop: '1px solid rgba(79,70,229,0.2)', textAlign: 'center', padding: '20px', fontFamily: 'DM Mono', fontSize: 9, letterSpacing: '0.15em', color: '#2a2848' }}>
        MUSIC COMPASS · KAGGLE DATABASE · GOOGLE GEMINI AI
      </footer>
    </div>
  );
}

function Nav() {
  return (
    <nav style={{
      position: 'sticky', top: 0, zIndex: 50,
      background: 'rgba(3,1,15,0.95)',
      borderBottom: '1px solid rgba(79,70,229,0.3)',
      backdropFilter: 'blur(20px)',
    }}>
      <div style={{ maxWidth: 980, margin: '0 auto', padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Compass size={24} style={{ color: '#00e5ff' }} />
        <span style={{
          fontFamily: 'Orbitron', fontWeight: 800, fontSize: '1.2rem',
          letterSpacing: '0.1em', color: '#00e5ff',
          textShadow: '0 0 20px rgba(0,229,255,0.5)',
        }}>
          MUSIC COMPASS
        </span>
      </div>
    </nav>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'inline-block', padding: '4px 14px', borderRadius: 20,
      background: 'rgba(79,70,229,0.15)', border: '1px solid rgba(79,70,229,0.35)',
      color: '#a78bfa', fontFamily: 'Orbitron', fontSize: '0.65rem', letterSpacing: '0.2em',
      textTransform: 'uppercase', marginBottom: 8,
    }}>
      {children}
    </div>
  );
}
