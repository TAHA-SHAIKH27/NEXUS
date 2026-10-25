import React, { useState, useEffect } from 'react';
import {
  Settings,
  Key,
  Database,
  Cpu,
  Mail,
  Volume2,
  Check,
  Save,
  RefreshCw,
  Eye,
  EyeOff,
  Server,
  Cpu as CpuIcon,
  Shield,
  AlertTriangle,
  Wifi,
  WifiOff,
  Link,
  Unlink,
  CheckCircle2,
  XCircle
} from 'lucide-react';

export default function SettingsPage() {
  const [config, setConfig] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [showKeys, setShowKeys] = useState(false);
  const [meterlessStatus, setMeterlessStatus] = useState(null);
  const [nvidiaStatus, setNvidiaStatus] = useState(null);
  const [checkingMeterless, setCheckingMeterless] = useState(false);
  const [checkingNvidia, setCheckingNvidia] = useState(false);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/config');
      if (res.ok) {
        const json = await res.json();
        setConfig(json);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      setSaveMsg('');
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (res.ok) {
        setSaveMsg('Configuration updated successfully!');
        setTimeout(() => setSaveMsg(''), 3000);
      }
    } catch (e) {
      setSaveMsg(`Error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (key, val) => {
    setConfig(prev => ({ ...prev, [key]: val }));
  };

  const checkMeterlessStatus = async () => {
    setCheckingMeterless(true);
    try {
      const res = await fetch('/api/meterless/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config })
      });
      if (res.ok) {
        const json = await res.json();
        setMeterlessStatus(json);
      }
    } catch (e) {
      setMeterlessStatus({ status: 'error', message: e.message });
    } finally {
      setCheckingMeterless(false);
    }
  };

  const checkNvidiaStatus = async () => {
    setCheckingNvidia(true);
    try {
      const res = await fetch('/api/nvidia/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config })
      });
      if (res.ok) {
        const json = await res.json();
        setNvidiaStatus(json);
      }
    } catch (e) {
      setNvidiaStatus({ status: 'error', message: e.message });
    } finally {
      setCheckingNvidia(false);
    }
  };

  const getStatusBadge = (status) => {
    if (!status) return <span className="agri-badge ghost">Not checked</span>;
    switch (status.status) {
      case 'online':
        return <span className="agri-badge emerald"><CheckCircle2 size={10} /> Online</span>;
      case 'unauthorized':
        return <span className="agri-badge amber"><AlertTriangle size={10} /> Invalid Token</span>;
      case 'unconfigured':
        return <span className="agri-badge ghost"><XCircle size={10} /> Not Configured</span>;
      case 'offline':
        return <span className="agri-badge rose"><WifiOff size={10} /> Offline</span>;
      default:
        return <span className="agri-badge ghost">{status.status}</span>;
    }
  };

  return (
    <div style={{ maxWidth: '950px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div className="agri-card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
              <Settings size={20} color="#38bdf8" />
              <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#fff', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                Platform Settings & API Configurations
              </h2>
            </div>
            <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              Manage AI LLM provider credentials, Zetaris Data Gateway connections, and system preferences.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setShowKeys(!showKeys)}
            className="agri-btn ghost"
            style={{ fontSize: '0.75rem' }}
          >
            {showKeys ? <EyeOff size={14} /> : <Eye size={14} />}
            <span>{showKeys ? 'Hide Keys' : 'Reveal Keys'}</span>
          </button>
        </div>
      </div>

      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Zetaris Gateway Config */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Database size={18} color="#10b981" />
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              Zetaris AI Data Gateway Credentials
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                UI Proxy Base URL (Port 3000)
              </label>
              <input
                type="text"
                value={config.zetaris_base_url || config.zetaris_rest_url || 'http://localhost:3000'}
                onChange={(e) => handleChange('zetaris_base_url', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
                placeholder="http://localhost:3000"
              />
              <p style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginTop: '0.25rem' }}>
                Use the UI proxy origin (port 3000), not the internal API (8888/8889)
              </p>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Zetaris Username
              </label>
              <input
                type="text"
                value={config.zetaris_username || 'admin@zetaris.com'}
                onChange={(e) => handleChange('zetaris_username', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Zetaris Password
              </label>
              <input
                type={showKeys ? 'text' : 'password'}
                value={config.zetaris_password || ''}
                onChange={(e) => handleChange('zetaris_password', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Org ID (optional, auto-discovered)
              </label>
              <input
                type="text"
                value={config.zetaris_org_id || ''}
                onChange={(e) => handleChange('zetaris_org_id', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </div>

        {/* Meterless Runtime (Nightshift) */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Server size={18} color="#10b981" />
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              Meterless Runtime (Nightshift Hotspot)
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Runtime Base URL
              </label>
              <input
                type="text"
                value={config.meterless_base_url || 'http://127.0.0.1:8088/v1'}
                onChange={(e) => handleChange('meterless_base_url', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
                placeholder="http://127.0.0.1:8088/v1"
              />
              <p style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginTop: '0.25rem' }}>
                Auto-normalized to {'<host>'}/v1. Accepts full URLs with /chat/completions or /models.
              </p>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Runtime Token (from Nightshift stateDir/proxy-token)
              </label>
              <input
                type={showKeys ? 'text' : 'password'}
                value={config.meterless_runtime_token || ''}
                onChange={(e) => handleChange('meterless_runtime_token', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
                placeholder="Paste proxy-token here"
              />
              <p style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginTop: '0.25rem' }}>
                Placeholder <code>rt-local</code> is rejected. Get token from Nightshift runtime directory.
              </p>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                App ID
              </label>
              <input
                type="text"
                value={config.meterless_app_id || 'nexus'}
                onChange={(e) => handleChange('meterless_app_id', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Default Routing Mode
              </label>
              <select
                value={config.meterless_model || 'meterless/auto'}
                onChange={(e) => handleChange('meterless_model', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              >
                <option value="meterless/auto">meterless/auto (balanced)</option>
                <option value="meterless/fast">meterless/fast (speed)</option>
                <option value="meterless/deep">meterless/deep (reasoning)</option>
                <option value="meterless/cheap">meterless/cheap (cost)</option>
                <option value="meterless/local">meterless/local (on-device)</option>
                <option value="meterless/fusion">meterless/fusion (multi-modal)</option>
                <option value="meterless/text">meterless/text</option>
                <option value="meterless/vision">meterless/vision</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={checkMeterlessStatus}
              disabled={checkingMeterless}
              className="agri-btn secondary"
            >
              <RefreshCw size={14} className={checkingMeterless ? 'animate-spin' : ''} />
              <span>{checkingMeterless ? 'Checking...' : 'Check Meterless Status'}</span>
            </button>
            {getStatusBadge(meterlessStatus)}
            {meterlessStatus && meterlessStatus.message && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{meterlessStatus.message}</span>
            )}
            {meterlessStatus && meterlessStatus.live && meterlessStatus.models && (
              <details style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                <summary>Available routing modes ({meterlessStatus.models.length})</summary>
                <ul style={{ marginTop: '0.5rem' }}>
                  {meterlessStatus.models.filter(m => m.startsWith('meterless/')).slice(0, 10).map((m, i) => (
                    <li key={i} style={{ fontFamily: 'var(--font-mono)' }}>{m}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        </div>

        {/* NVIDIA NIM Nemotron (FPO Adapter) */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <CpuIcon size={18} color="#76b900" />
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              NVIDIA NIM Nemotron (FPO Agricultural Adapter)
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                NVIDIA API Key (NIM)
              </label>
              <input
                type={showKeys ? 'text' : 'password'}
                value={config.nvidia_api_key || ''}
                onChange={(e) => handleChange('nvidia_api_key', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
                placeholder="nvapi-..."
              />
              <p style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginTop: '0.25rem' }}>
                Separate from Code Core's nvidia_model (z-ai/glm-5.3-flash). FPO uses Nemotron models.
              </p>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                FPO Nemotron Model
              </label>
              <select
                value={config.nvidia_fpo_model || 'nvidia/nemotron-3.5-bolt-e4b'}
                onChange={(e) => handleChange('nvidia_fpo_model', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              >
                <option value="nvidia/nemotron-3.5-bolt-e4b">Nemotron 3.5 Bolt E4B - Fast reasoning / tool-calling</option>
                <option value="nvidia/nemotron-3.5-lightning-30b-a3b">Nemotron 3.5 Lightning 30B A3B - Longer agentic FPO analysis</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Request Timeout (seconds)
              </label>
              <input
                type="number"
                value={config.nvidia_fpo_timeout_seconds || 120}
                onChange={(e) => handleChange('nvidia_fpo_timeout_seconds', parseInt(e.target.value) || 120)}
                className="agri-input"
                style={{ width: '100%' }}
                min="10"
                max="300"
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Max Retries
              </label>
              <input
                type="number"
                value={config.nvidia_fpo_max_retries || 2}
                onChange={(e) => handleChange('nvidia_fpo_max_retries', parseInt(e.target.value) || 2)}
                className="agri-input"
                style={{ width: '100%' }}
                min="0"
                max="5"
              />
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={checkNvidiaStatus}
              disabled={checkingNvidia}
              className="agri-btn secondary"
            >
              <RefreshCw size={14} className={checkingNvidia ? 'animate-spin' : ''} />
              <span>{checkingNvidia ? 'Checking...' : 'Check NVIDIA NIM Status'}</span>
            </button>
            {getStatusBadge(nvidiaStatus)}
            {nvidiaStatus && nvidiaStatus.message && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{nvidiaStatus.message}</span>
            )}
            {nvidiaStatus && nvidiaStatus.live && nvidiaStatus.models && (
              <details style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                <summary>Available FPO models</summary>
                <ul style={{ marginTop: '0.5rem' }}>
                  {nvidiaStatus.models.map((m, i) => (
                    <li key={i} style={{ fontFamily: 'var(--font-mono)' }}>
                      {m.label} ({m.id}) - {m.role}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        </div>

        {/* AI Model Providers (Legacy/Other) */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Cpu size={18} color="#38bdf8" />
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              Other AI LLM Providers
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Google Gemini API Key
              </label>
              <input
                type={showKeys ? 'text' : 'password'}
                value={config.gemini_api_key || ''}
                onChange={(e) => handleChange('gemini_api_key', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Groq API Key
              </label>
              <input
                type={showKeys ? 'text' : 'password'}
                value={config.groq_api_key || ''}
                onChange={(e) => handleChange('groq_api_key', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Code Core NVIDIA Model (Legacy)
              </label>
              <input
                type={showKeys ? 'text' : 'password'}
                value={config.nvidia_model || 'z-ai/glm-5.3-flash'}
                onChange={(e) => handleChange('nvidia_model', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              />
              <p style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginTop: '0.25rem' }}>
                Used by Code Core / recovery engine. FPO adapter uses separate nvidia_fpo_model above.
              </p>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                HuggingFace API Key
              </label>
              <input
                type={showKeys ? 'text' : 'password'}
                value={config.huggingface_api_key || ''}
                onChange={(e) => handleChange('huggingface_api_key', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </div>

        {/* Save Bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: '#34d399', fontSize: '0.85rem' }}>{saveMsg}</span>
          <button type="submit" disabled={saving} className="agri-btn primary" style={{ minWidth: '140px' }}>
            <Save size={16} />
            <span>{saving ? 'Saving...' : 'Save Preferences'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}