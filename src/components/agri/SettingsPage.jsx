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
  EyeOff
} from 'lucide-react';

export default function SettingsPage() {
  const [config, setConfig] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [showKeys, setShowKeys] = useState(false);

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

  return (
    <div style={{ maxWidth: '850px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
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
                REST Query URL
              </label>
              <input
                type="text"
                value={config.zetaris_rest_url || 'http://localhost:8888/api/v1.0'}
                onChange={(e) => handleChange('zetaris_rest_url', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Auth Service URL
              </label>
              <input
                type="text"
                value={config.zetaris_auth_url || 'http://localhost:8889'}
                onChange={(e) => handleChange('zetaris_auth_url', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-faint)', marginBottom: '0.35rem' }}>
                Zetaris Admin Username
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
          </div>
        </div>

        {/* AI Model Providers */}
        <div className="agri-card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Cpu size={18} color="#38bdf8" />
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff', fontWeight: 600 }}>
              AI LLM & Reasoning Providers
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
                NVIDIA NIM API Key (Nemotron)
              </label>
              <input
                type={showKeys ? 'text' : 'password'}
                value={config.nvidia_api_key || ''}
                onChange={(e) => handleChange('nvidia_api_key', e.target.value)}
                className="agri-input"
                style={{ width: '100%' }}
              />
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
