import React, { useState, useEffect, useRef, useCallback } from 'react';
import './components/agri/agri-theme.css';

// Live dashboard stack - using REST polling (Socket.IO not implemented in backend)
import { useNexusStore } from './store/nexusStore';
import { formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';

// Agri Components
import AppSidebar from './components/agri/AppSidebar';
import TopNavbar from './components/agri/TopNavbar';
import OverviewDashboard from './components/agri/OverviewDashboard';
import AIWorkspace from './components/agri/AIWorkspace';
import InventoryIntelligence from './components/agri/InventoryIntelligence';
import MarketIntelligence from './components/agri/MarketIntelligence';
import LogisticsIntelligence from './components/agri/LogisticsIntelligence';
import RiskCentre from './components/agri/RiskCentre';
import DecisionsReports from './components/agri/DecisionsReports';
import DataSources from './components/agri/DataSources';
import SettingsPage from './components/agri/SettingsPage';

// Secondary Utility Pages (Preserved)
import CodeCorePage from './CodeCorePage';
import PhoneMirrorPage from './PhoneMirrorPage';
import GalleryPage from './GalleryPage';
import NotificationCenter from './components/NotificationCenter';

// Voice Integration
import { useVoice } from './hooks/useVoice';
import { detectLang, pickBrowserVoice } from './langDetect';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([
    {
      sender: 'nexus',
      text: 'NEXUS Agricultural Intelligence Platform initialized. Grounded with 526,397 verified records across Maharashtra and Telangana. How can I assist your FPO network today?',
      time: 'Live',
      fileData: null
    }
  ]);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [centerOpen, setCenterOpen] = useState(false);
  const [centerData, setCenterData] = useState(null);
  const [centerLoading, setCenterLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  // Live store bindings
  const unreadCount = useNexusStore((s) => s.unreadCount);
  const setUnreadCountStore = useNexusStore((s) => s.setUnreadCount);
  const online = useNexusStore((s) => s.online);
  const setOnlineStore = useNexusStore((s) => s.setOnline);
  const netState = useNexusStore((s) => s.netState);
  const setNetStateStore = useNexusStore((s) => s.setNetState);

  // Fetch unread notifications count (REST polling - Socket.IO not available)
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
        const count = json.unread_count || 0;
        setUnreadCountStore(count);
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

  // Command & Chat Handler
  const handleSendMessage = async (promptText) => {
    if (!promptText || !promptText.trim() || busy) return;
    const cleanPrompt = promptText.trim();

    // Append user message
    const now = new Date();
    setMessages(prev => [...prev, {
      sender: 'user',
      text: cleanPrompt,
      time: formatDistanceToNow(now, { addSuffix: true }),
      fileData: null
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
          time: formatDistanceToNow(new Date(), { addSuffix: true }),
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
          time: formatDistanceToNow(new Date(), { addSuffix: true })
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        sender: 'nexus',
        text: `Network Error: ${err.message}`,
        time: formatDistanceToNow(new Date(), { addSuffix: true })
      }]);
    } finally {
      setBusy(false);
    }
  };

  // Voice Hook integration
  const voiceHook = useVoice({
    onCommand: (spoken) => {
      handleSendMessage(spoken);
    },
    enabled: voiceEnabled
  });

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
        riskCount={88}
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

        {/* Dynamic Page Router */}
        <main className="nexus-page-content" key={refreshKey}>
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
