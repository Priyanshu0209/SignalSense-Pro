import React, { useState, useEffect } from 'react';
import { Target, Activity, Settings, CheckCircle2, Play, RefreshCw, Trash2, Database, Wifi } from 'lucide-react';

interface CalibrationSample {
  timestamp: number;
  actual_distance: number;
  rssi: number;
  filtered_rssi: number;
  ema_rssi: number;
  variance: number;
  std_dev: number;
  environment: string;
  los_status: string;
}

interface CalibrationStatus {
  is_collecting: boolean;
  samples_collected: number;
  current_distance: number;
  last_sample: CalibrationSample | null;
}

interface CalibrationProfile {
  name: string;
  rssi_0: number | null;
  path_loss_exponent: number | null;
  environment: string;
  created_at: number;
  sample_count: number;
  calibration_confidence: number;
}

export const CalibrationStudio: React.FC = () => {
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

  // Collection State
  const [distance, setDistance] = useState<number>(1.0);
  const [duration, setDuration] = useState<number>(10);
  const [environment, setEnvironment] = useState<string>('Home Office');
  const [losStatus, setLosStatus] = useState<string>('LOS');
  
  // Status State
  const [status, setStatus] = useState<CalibrationStatus | null>(null);
  const [profiles, setProfiles] = useState<Record<string, CalibrationProfile>>({});
  
  // Action State
  const [isCalibrating, setIsCalibrating] = useState<boolean>(false);
  const [calibrationResult, setCalibrationResult] = useState<CalibrationProfile | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>('');

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/calibration/collection_status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchProfiles = async () => {
    try {
      const res = await fetch(`${API_URL}/calibration/profiles`);
      if (res.ok) {
        const data = await res.json();
        setProfiles(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchProfiles();
    const interval = setInterval(fetchStatus, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleStartCollection = async () => {
    try {
      setErrorMsg('');
      const res = await fetch(`${API_URL}/calibration/start_collection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          actual_distance: distance,
          duration_sec: duration,
          environment: environment,
          los_status: losStatus
        })
      });
      if (!res.ok) {
        const err = await res.json();
        setErrorMsg(err.detail || 'Failed to start collection');
      }
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const handleClearSamples = async () => {
    try {
      await fetch(`${API_URL}/calibration/clear_samples`, { method: 'POST' });
      setCalibrationResult(null);
      fetchStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleCalibrate = async () => {
    try {
      setErrorMsg('');
      setIsCalibrating(true);
      const res = await fetch(`${API_URL}/calibration/calibrate`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setCalibrationResult(data.profile);
        fetchProfiles();
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || 'Calibration failed');
      }
    } catch (e: any) {
      setErrorMsg(e.message);
    } finally {
      setIsCalibrating(false);
    }
  };

  return (
    <div className="w-full h-full flex flex-col gap-6 overflow-y-auto custom-scrollbar p-6 bg-[#020617] text-text-primary">
      
      {/* Header */}
      <div className="glass-panel p-6 rounded-2xl border border-border flex items-center justify-between shadow-neon-blue bg-background-secondary/80 backdrop-blur-md">
        <div>
          <h2 className="text-2xl font-black tracking-widest text-text-primary flex items-center gap-3">
            <Target className="text-cyan-400" /> CALIBRATION STUDIO
          </h2>
          <p className="text-sm text-text-muted mt-1 font-mono">
            Ground-Truth Environmental Distance Estimation Tuning
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono font-bold tracking-widest">
          <div className="flex items-center gap-2 bg-card px-4 py-2 rounded-lg border border-border">
            <Database size={16} className="text-emerald-400" />
            SAMPLES BUFFERED: <span className="text-emerald-400 text-lg">{status?.samples_collected || 0}</span>
          </div>
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 bg-status-error/10 border border-status-error text-status-error rounded-xl font-mono text-sm shadow-[0_0_15px_rgba(239,68,68,0.2)]">
          {errorMsg}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Data Collection Panel */}
        <div className="glass-panel rounded-2xl border border-border p-6 bg-background-secondary/60">
          <h3 className="text-lg font-bold tracking-widest mb-6 border-b border-border pb-4 flex items-center gap-2">
            <Activity className="text-accent-primary" size={20} />
            1. COLLECT GROUND TRUTH
          </h3>
          
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-text-muted uppercase tracking-wider mb-2">Distance (Meters)</label>
                <input 
                  type="number" step="0.5" min="0.5" max="20"
                  value={distance} onChange={e => setDistance(parseFloat(e.target.value))}
                  disabled={status?.is_collecting}
                  className="w-full bg-card border border-border rounded-lg p-3 text-sm font-mono text-text-primary outline-none focus:border-cyan-500 transition-colors"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-text-muted uppercase tracking-wider mb-2">Duration (Seconds)</label>
                <input 
                  type="number" min="5" max="60"
                  value={duration} onChange={e => setDuration(parseInt(e.target.value))}
                  disabled={status?.is_collecting}
                  className="w-full bg-card border border-border rounded-lg p-3 text-sm font-mono text-text-primary outline-none focus:border-cyan-500 transition-colors"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-text-muted uppercase tracking-wider mb-2">Environment</label>
                <input 
                  type="text" 
                  value={environment} onChange={e => setEnvironment(e.target.value)}
                  disabled={status?.is_collecting}
                  className="w-full bg-card border border-border rounded-lg p-3 text-sm font-mono text-text-primary outline-none focus:border-cyan-500 transition-colors"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-text-muted uppercase tracking-wider mb-2">Line of Sight</label>
                <select 
                  value={losStatus} onChange={e => setLosStatus(e.target.value)}
                  disabled={status?.is_collecting}
                  className="w-full bg-card border border-border rounded-lg p-3 text-sm font-mono text-text-primary outline-none focus:border-cyan-500 transition-colors"
                >
                  <option value="LOS">Line of Sight (LOS)</option>
                  <option value="NLOS">Non-Line of Sight (NLOS)</option>
                </select>
              </div>
            </div>

            <div className="mt-8 flex gap-3">
              <button 
                onClick={handleStartCollection}
                disabled={status?.is_collecting}
                className={`flex-1 flex justify-center items-center gap-2 py-3 rounded-lg font-bold tracking-widest text-sm transition-all ${
                  status?.is_collecting 
                    ? 'bg-status-success/20 text-status-success border border-status-success cursor-not-allowed animate-pulse' 
                    : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-[0_0_15px_rgba(6,182,212,0.4)] hover:shadow-[0_0_25px_rgba(6,182,212,0.6)]'
                }`}
              >
                {status?.is_collecting ? (
                  <><RefreshCw className="animate-spin" size={18} /> COLLECTING {status?.current_distance}m...</>
                ) : (
                  <><Play size={18} /> RECORD RSSI SAMPLES</>
                )}
              </button>
              
              <button 
                onClick={handleClearSamples}
                disabled={status?.is_collecting || status?.samples_collected === 0}
                className="px-4 py-3 rounded-lg border border-status-error/50 text-status-error hover:bg-status-error/10 transition-colors disabled:opacity-50"
              >
                <Trash2 size={18} />
              </button>
            </div>
            
            <p className="text-xs text-text-muted mt-4 font-mono text-center">
              Recommendation: Collect samples at 1m, 3m, and 5m for optimal path loss calculation.
            </p>
          </div>
        </div>

        {/* Engine Calculation Panel */}
        <div className="glass-panel rounded-2xl border border-border p-6 bg-background-secondary/60">
          <h3 className="text-lg font-bold tracking-widest mb-6 border-b border-border pb-4 flex items-center gap-2">
            <Settings className="text-emerald-400" size={20} />
            2. CALIBRATE ESTIMATOR
          </h3>
          
          <div className="flex flex-col h-full justify-between pb-8">
            <div className="space-y-4">
              <div className="flex justify-between items-center p-4 bg-card rounded-xl border border-border">
                <span className="font-mono text-sm text-text-muted">Total Samples Available:</span>
                <span className="font-mono font-bold text-lg">{status?.samples_collected || 0}</span>
              </div>
              <div className="flex justify-between items-center p-4 bg-card rounded-xl border border-border">
                <span className="font-mono text-sm text-text-muted">Environment Target:</span>
                <span className="font-mono font-bold text-lg">{environment}</span>
              </div>
            </div>

            <div className="mt-8">
              <button 
                onClick={handleCalibrate}
                disabled={status?.is_collecting || (status?.samples_collected || 0) < 10 || isCalibrating}
                className="w-full flex justify-center items-center gap-2 py-4 rounded-xl font-bold tracking-widest text-sm transition-all bg-emerald-600 hover:bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.4)] disabled:opacity-50 disabled:shadow-none"
              >
                {isCalibrating ? <RefreshCw className="animate-spin" size={20} /> : <Target size={20} />}
                GENERATE CALIBRATION PROFILE
              </button>
              {(status?.samples_collected || 0) < 10 && (
                <p className="text-xs text-status-error mt-3 font-mono text-center">
                  Minimum 10 samples required across distinct distances.
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Result Profile Panel */}
        <div className="glass-panel rounded-2xl border border-border p-6 bg-background-secondary/60 lg:col-span-2">
          <h3 className="text-lg font-bold tracking-widest mb-6 border-b border-border pb-4 flex items-center gap-2">
            <Wifi className="text-purple-400" size={20} />
            ACTIVE CALIBRATION PROFILE
          </h3>
          
          {calibrationResult ? (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="bg-card p-5 rounded-xl border border-border flex flex-col items-center justify-center text-center relative overflow-hidden">
                <div className="absolute top-0 right-0 p-2"><CheckCircle2 className="text-status-success" size={16} /></div>
                <span className="text-xs text-text-muted uppercase tracking-widest font-bold mb-2">Base RSSI (1m)</span>
                <span className="text-3xl font-black text-cyan-400 font-mono">
                  {calibrationResult.rssi_0 !== null ? calibrationResult.rssi_0.toFixed(2) : 'N/A'} <span className="text-sm">dBm</span>
                </span>
              </div>
              <div className="bg-card p-5 rounded-xl border border-border flex flex-col items-center justify-center text-center relative overflow-hidden">
                <div className="absolute top-0 right-0 p-2"><CheckCircle2 className="text-status-success" size={16} /></div>
                <span className="text-xs text-text-muted uppercase tracking-widest font-bold mb-2">Path Loss (n)</span>
                <span className="text-3xl font-black text-emerald-400 font-mono">
                  {calibrationResult.path_loss_exponent !== null ? calibrationResult.path_loss_exponent.toFixed(2) : 'N/A'}
                </span>
              </div>
              <div className="bg-card p-5 rounded-xl border border-border flex flex-col items-center justify-center text-center">
                <span className="text-xs text-text-muted uppercase tracking-widest font-bold mb-2">Confidence</span>
                <span className="text-3xl font-black text-purple-400 font-mono">
                  {calibrationResult.calibration_confidence}%
                </span>
              </div>
              <div className="bg-card p-5 rounded-xl border border-border flex flex-col items-center justify-center text-center">
                <span className="text-xs text-text-muted uppercase tracking-widest font-bold mb-2">Samples</span>
                <span className="text-3xl font-black text-text-primary font-mono">
                  {calibrationResult.sample_count}
                </span>
              </div>
            </div>
          ) : (
            <div className="py-12 flex flex-col items-center justify-center text-text-muted">
              <Database size={48} className="opacity-20 mb-4" />
              <p className="font-mono text-sm">No calibration generated yet. Please record samples and run the engine.</p>
              
              {/* Show default/existing profiles if they exist */}
              {Object.keys(profiles).length > 0 && (
                <div className="mt-8 text-xs font-mono w-full max-w-lg bg-card p-4 rounded-xl border border-border text-left">
                  <p className="mb-2 font-bold text-text-primary">Saved Profiles:</p>
                  <ul className="space-y-2">
                    {Object.values(profiles).map(p => (
                      <li key={p.name} className="flex justify-between border-b border-border/50 pb-1">
                        <span>{p.name} (Env: {p.environment})</span>
                        <span className="text-cyan-400">n={p.path_loss_exponent?.toFixed(2) || '?'}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-4 text-[10px] text-text-muted">Note: Profile activation happens automatically in the backend upon successful calibration.</p>
                </div>
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  );
};
