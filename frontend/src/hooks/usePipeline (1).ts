/**
 * usePipeline.ts
 * Manages the full upload → parse → score pipeline for one user.
 * Keeps logic out of the UI components.
 */

import { useState, useCallback } from 'react';
import { api, ScoredSong, ImportResult, RegressionResult } from '../services/api';

export type PipelinePhase =
  | 'idle' | 'importing' | 'scoring' | 'done' | 'error';

export interface PipelineProgress {
  phase:   string;
  current: number;
  total:   number;
  kaggle:  number;
  gemini:  number;
}

export interface UserData {
  userId:      string;
  name:        string;
  dateOfBirth: string;   // "YYYY-MM-DD"
  color:       string;
  songs:       ScoredSong[];
  totalMs:     number;
  stats: {
    total:    number;
    kaggle:   number;
    fuzzy:    number;
    supabase: number;
    gemini:   number;
    plotted:  number;
  };
}

const USER_COLORS = [
  '#00e5ff', '#f472b6', '#fbbf24', '#a78bfa', '#34d399', '#fb923c',
];

export function usePipeline() {
  const [users, setUsers]       = useState<UserData[]>([]);
  const [phase, setPhase]       = useState<PipelinePhase>('idle');
  const [progress, setProgress] = useState<PipelineProgress | null>(null);
  const [error, setError]       = useState('');
  const [regression, setRegression]         = useState<RegressionResult | null>(null);
  const [astrology, setAstrology]           = useState<any>(null);
  const [astrologyLoading, setAstrologyLoading] = useState(false);
  const [selectedIdx, setSelectedIdx]       = useState(0);

  const addUser = useCallback(async (files: File[], name: string, dateOfBirth: string) => {
    setPhase('importing');
    setError('');
    setAstrology(null);
    setRegression(null);
    setProgress({ phase: 'Parsing Spotify history…', current: 0, total: 0, kaggle: 0, gemini: 0 });

    try {
      // Step 1 – Parse history
      const parsed: ImportResult = await api.importSpotify(files, name);

      // Step 2 – Score all songs in one request.
      // Chunking happens server-side; splitting here would cause multiple
      // separate Gemini calls instead of one consolidated batch.
      setPhase('scoring');
      setProgress({
        phase:   'Scoring songs…',
        current: 0,
        total:   parsed.songs.length,
        kaggle:  0,
        gemini:  0,
      });

      const scored: ScoredSong[] = await api.lookupBatch(parsed.songs, parsed.user_id);

      setProgress({
        phase:   'Scoring songs…',
        current: scored.length,
        total:   parsed.songs.length,
        kaggle:  scored.filter(s => s.source?.includes('kaggle')).length,
        gemini:  scored.filter(s => s.source === 'gemini_predicted').length,
      });

      const color = USER_COLORS[users.length % USER_COLORS.length];
      const newUser: UserData = {
        userId:      parsed.user_id,
        name,
        dateOfBirth,
        color,
        songs:   scored,
        totalMs: parsed.total_ms,
        stats: {
          total:    scored.length,
          kaggle:   scored.filter(s => s.source === 'kaggle_exact').length,
          fuzzy:    scored.filter(s => s.source === 'kaggle_fuzzy').length,
          supabase: scored.filter(s => s.source === 'supabase_cache').length,
          gemini:   scored.filter(s => s.source === 'gemini_predicted').length,
          plotted:  scored.filter(s => s.energy != null && s.valence != null).length,
        },
      };

      const updated = [...users, newUser];
      setUsers(updated);
      setSelectedIdx(updated.length - 1);
      setPhase('done');

      // Trigger regression for new user
      const reg = await api.getRegression(scored).catch(() => null);
      if (reg) setRegression(reg);
    } catch (e: any) {
      setError(e.message || 'Pipeline failed');
      setPhase('error');
    } finally {
      setProgress(null);
    }
  }, [users]);

  const removeUser = useCallback((idx: number) => {
    setUsers(prev => {
      const next = prev.filter((_, i) => i !== idx);
      setSelectedIdx(Math.min(selectedIdx, Math.max(0, next.length - 1)));
      return next;
    });
    setAstrology(null);
    setRegression(null);
    if (users.length <= 1) setPhase('idle');
  }, [users.length, selectedIdx]);

  const switchUser = useCallback(async (idx: number) => {
    setSelectedIdx(idx);
    setAstrology(null);
    const user = users[idx];
    if (!user) return;
    const reg = await api.getRegression(user.songs).catch(() => null);
    if (reg) setRegression(reg);
  }, [users]);

  const readAstrology = useCallback(async () => {
    const user = users[selectedIdx];
    if (!user) return;
    setAstrologyLoading(true);
    try {
      const result = await api.getAstrology(user.name, user.songs, user.dateOfBirth);
      setAstrology(result);
    } catch (e: any) {
      setError('Astrology failed: ' + e.message);
    } finally {
      setAstrologyLoading(false);
    }
  }, [users, selectedIdx]);

  const reset = useCallback(() => {
    setUsers([]);
    setPhase('idle');
    setProgress(null);
    setError('');
    setRegression(null);
    setAstrology(null);
    setSelectedIdx(0);
  }, []);

  return {
    // State
    users, phase, progress, error,
    regression, astrology, astrologyLoading,
    selectedIdx,
    selectedUser: users[selectedIdx] ?? null,
    isRunning: ['importing', 'scoring'].includes(phase),
    // Actions
    addUser, removeUser, switchUser, readAstrology, reset,
    clearError: () => setError(''),
  };
}
