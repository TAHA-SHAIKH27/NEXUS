import React, { useState, useEffect, useRef, useCallback, Suspense, lazy } from 'react';
import './components/agri/agri-theme.css';

// Agri shell components (small — kept in the main bundle)
import AppSidebar from './components/agri/AppSidebar';
import TopNavbar from './components/agri/TopNavbar';
import NotificationCenter from './components/NotificationCenter';

// Route-level code splitting: heavy pages load on demand.
const OverviewDashboard = lazy(() => import('./components/agri/OverviewDashboard'));
const AIWorkspace = lazy(() => import('./components/agri/AIWorkspace'));
const InventoryIntelligence = lazy(() => import('./components/agri/InventoryIntelligence'));
const MarketIntelligence = lazy(() => import('./components/agri/MarketIntelligence'));
const LogisticsIntelligence = lazy(() => import('./components/agri/LogisticsIntelligence'));
const RiskCentre = lazy(() => import('./components/agri/RiskCentre'));
const DecisionsReports = lazy(() => import('./components/agri/DecisionsReports'));
const DataSources = lazy(() => import('./components/agri/DataSources'));
const SettingsPage = lazy(() => import('./components/agri/SettingsPage'));

// Preserved secondary tools (also lazy — they pull heavy dependencies)
const CodeCorePage = lazy(() => import('./CodeCorePage'));
const PhoneMirrorPage = lazy(() => import('./PhoneMirrorPage'));
const GalleryPage = lazy(() => import('./GalleryPage'));

// Voice Integration
import { useVoice } from './hooks/useVoice';
import { pickBrowserVoice } from './langDetect';

const VALID_TABS = new Set([
  'overview', 'ai-workspace', 'inventory', 'markets', 'logistics',
  'risk-centre', 'decisions', 'datasources', 'settings', 'code', 'phone', 'files'
]);

function readHashTab() {
  const h = (window.location.hash || '').replace(/^#\/?/, '').trim();
  return VALID_TABS.has(h) ? h : 'overview';
}

function PageLoader() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '50vh', flexDirection: 'column', gap: '0.8rem' }} role="status">
      <div className="agri-skeleton" style={{ width: 220, height: 14 }} />
      <div className="agri-skeleton" style={{ width: 140, height: 12 }} />
      <span style={{ color: 'var(--text-faint)', fontSize: '0.78rem' }}>Loading module…</span>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTabState] = useState(readHashTab);
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([
    {
      sender: 'nexus',
      text: 'NEXUS Agricultural Intelligence Platform online. Connected to the NEXUS_FPO source via Zetaris. Ask about inventory, spoilage risk, markets or logistics.',
      time: 'Live',
      fileData: null
    }
  ]);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);
  const [centerOpen, setCenterOpen] = useState(false);
  const [centerData, setCenterData] = useState(null);
  const [centerLoading, setCenterLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const [riskCount, setRiskCount] = useState(null);

  // ── Hash-based deep linking (no reload, back/forward friendly) ──────────
  useEffect(() => {
    const onHash = () => setActiveTabState(readHashTab());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const setActiveTab = useCallback((tab) => {
    setActiveTabState(tab);
    if (readHashTab() !== tab) window.location.hash = `/${tab}`;
  }, []);

  // ── Backend connection + real high-risk batch count for the sidebar ─────
  useEffect(() => {
    let cancelled = false;
    const loadRiskCount = async () => {
      try {
        const res = await fetch('/api/fpo/stats');
        const json = await res.json().catch(() => null);
        if (!cancelled && res.ok && json?.status === 'success') {
          const n = parseInt(json.overview?.high_risk_batches, 10);
          setRiskCount(Number.isFinite(n) ? n : null);
        }
      } catch { /* sidebar badge simply stays neutral */ }
    };
    loadRiskCount();
    const t = setInterval(loadRiskCount, 120000);
    return () => { cancelled = true; clearInterval(t); };
  }, [refreshKey]);

  // Fetch unread notifications count
  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchUnreadCount = async () => {
    try {
      const res = await fetch('/api/notifications/unread-count');
      if (res.ok) {
        const json = await res.json();
        setUnreadCount(json.unread_count || 0);
      }
    } catch (e) {
      // offline or silent
    }
  };

  const handleOpenNotifications = async () => {
    setCenterOpen(true);
    setCenterLoading(true);
    try {
      const res = await fetch('/api/notifications/center');
      if (res.ok) {
        const json = await res.json();
        setCenterData(json);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setCenterLoading(false);
    }
  };

  // Browser TTS output
  const speakText = useCallback((text, lang = 'en') => {
    if (!voiceEnabled || !window.speechSynthesis || !text) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      const voice = pickBrowserVoice(lang);
      if (voice) utterance.voice = voice;
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('TTS error:', e);
    }
  }, [voiceEnabled]);

  // Command Handler — talks to the existing NEXUS agent (/api/command),
  // which routes explicit `zetaris: …` debug commands to the gateway.
  const handleSendMessageRef = useRef(() => {});

  const handleSendMessage = async (promptText) => {
    if (!promptText || !promptText.trim() || busy) return;
    const cleanPrompt = promptText.trim();

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMessages(prev => [...prev, {
      sender: 'user',
      text: cleanPrompt,
      time: now
    }]);

    setBusy(true);

    try {
      const res = await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: cleanPrompt })
      });

      if (res.ok) {
        const data = await res.json();
        const replyText = data.speak || data.message || (data.logs && data.logs.join('\n')) || 'Query processed successfully.';

        setMessages(prev => [...prev, {
          sender: 'nexus',
          text: replyText,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          fileData: data.file_data || null
        }]);

        if (data.speak) {
          speakText(data.speak, data.speak_lang || 'en');
        }
      } else {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }));
        setMessages(prev => [...prev, {
          sender: 'nexus',
          text: `Error: ${err.detail || 'Failed to process request.'}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        sender: 'nexus',
        text: `Network Error: ${err.message}`,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
    } finally {
      setBusy(false);
    }
  };

  // Keep the voice hook's executor ref pointing at the latest handler.
  useEffect(() => { handleSendMessageRef.current = handleSendMessage; });

  // Voice Hook integration — the hook executes commands via its internal
  // executeCommandRef (set below) once a final transcript is produced.
  const voiceHook = useVoice({
    onTranscript: (event) => {
      if (event && event.type === 'final' && event.text) {
        handleSendMessageRef.current(event.text);
      }
    },
    onError: (error) => {
      setMessages(prev => [...prev, {
        sender: 'nexus',
        text: `Voice error: ${error}`,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
    },
    muted: !voiceEnabled
  });
  const { _setExecuteCommand } = voiceHook;
  useEffect(() => { _setExecuteCommand?.((text) => handleSendMessageRef.current(text)); });

  const handleManualRefresh = () => {
    setRefreshKey(k => k + 1);
    fetchUnreadCount();
  };

  return (
    <div className="nexus-app-shell">
      {/* Sidebar Navigation */}
      <AppSidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        unreadCount={unreadCount}
        riskCount={riskCount}
      />

      {/* Main Viewport */}
      <div className="nexus-main-viewport">
        {/* Top Navbar */}
        <TopNavbar
          activeTab={activeTab}
          onRefresh={handleManualRefresh}
          voiceEnabled={voiceEnabled}
          onToggleVoice={() => setVoiceEnabled(!voiceEnabled)}
          unreadCount={unreadCount}
          onOpenNotifications={handleOpenNotifications}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

        {/* Dynamic Page Router (lazy-loaded per route) */}
        <main className="nexus-page-content" key={refreshKey}>
          <Suspense fallback={<PageLoader />}>
            {activeTab === 'overview' && (
              <OverviewDashboard onNavigate={setActiveTab} />
            )}

            {activeTab === 'ai-workspace' && (
              <AIWorkspace
                messages={messages}
                onSendMessage={handleSendMessage}
                busy={busy}
                voiceEnabled={voiceEnabled}
                onToggleVoice={() => setVoiceEnabled(!voiceEnabled)}
                voiceHook={voiceHook}
              />
            )}

            {activeTab === 'inventory' && (
              <InventoryIntelligence />
            )}

            {activeTab === 'markets' && (
              <MarketIntelligence />
            )}

            {activeTab === 'logistics' && (
              <LogisticsIntelligence />
            )}

            {activeTab === 'risk-centre' && (
              <RiskCentre onNavigate={setActiveTab} />
            )}

            {activeTab === 'decisions' && (
              <DecisionsReports onNavigate={setActiveTab} />
            )}

            {activeTab === 'datasources' && (
              <DataSources />
            )}

            {activeTab === 'settings' && (
              <SettingsPage />
            )}

            {/* Preserved Secondary Tools */}
            {activeTab === 'code' && (
              <CodeCorePage onClose={() => setActiveTab('overview')} />
            )}

            {activeTab === 'phone' && (
              <PhoneMirrorPage onClose={() => setActiveTab('overview')} />
            )}

            {activeTab === 'files' && (
              <GalleryPage onClose={() => setActiveTab('overview')} />
            )}
          </Suspense>
        </main>
      </div>

      {/* Notification Center Drawer / Modal */}
      {centerOpen && (
        <NotificationCenter
          data={centerData}
          loading={centerLoading}
          onClose={() => setCenterOpen(false)}
          onRefresh={handleOpenNotifications}
        />
      )}
    </div>
  );
}
