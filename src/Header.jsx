import React from 'react';
import { Settings, Mic, MicOff, Bell } from 'lucide-react';

export default function Header({ online, netState, busy, chatMode, setChatMode, isSpeaking, onOpenSettings, voiceActive, toggleVoice, voiceEnabled, setVoiceEnabled, onToggleVoiceEnabled, unreadCount = 0, onOpenNotifications }) {
  const NET_LABELS = {
    online: ['ONLINE', ''],
    wifi_off: ['WIFI OFF', 'offline'],
    disconnected: ['NO NETWORK', 'offline'],
    local_only: ['NO INTERNET', 'offline'],
    no_dns: ['DNS FAIL', 'offline'],
    gemini_unreachable: ['GOOGLE DOWN', 'offline'],
    backend_offline: ['OFFLINE', 'offline'],
    unknown: ['OFFLINE', 'offline'],
  };
  let statusLabel = 'ONLINE';
  let statusClass = '';
  let statusTitle = 'All systems operational';
  if (!online) {
    statusLabel = 'OFFLINE'; statusClass = 'offline';
    statusTitle = 'NEXUS backend unreachable';
  } else if (netState && netState !== 'online') {
    const entry = NET_LABELS[netState];
    if (entry) {
      statusLabel = entry[0]; statusClass = entry[1];
      statusTitle = `Network: ${netState.replace(/_/g, ' ')} — local controls still work`;
    }
  }
  if (online && (!netState || netState === 'online')) {
    if (busy) statusLabel = 'PROCESSING', statusClass = 'busy';
    else if (isSpeaking) statusLabel = 'SPEAKING', statusClass = 'awake';
    else if (voiceActive) statusLabel = 'LISTENING', statusClass = 'awake';
  }

  return (
    <div className="topbar-header">
      <div className="wordmark">N.E.X.U.S.</div>

      <div className="header-cluster">
        <div className="status-pill" title={statusTitle}>
          <span className={`status-dot ${statusClass}`} />
          {statusLabel}
        </div>

        <button
          className={`icon-btn mic-btn ${voiceActive ? 'active' : ''}`}
          onClick={toggleVoice}
          title={voiceActive ? 'Disable Wake Word (listening)' : 'Enable Wake Word (offline)'}
        >
          {voiceActive ? <Mic size={15} /> : <MicOff size={15} />}
        </button>

        <button
          className={`icon-btn chat-mode-btn ${chatMode ? 'active' : ''}`}
          onClick={() => setChatMode(v => !v)}
          title={chatMode ? 'Chat mode — click for command mode' : 'Command mode — click for chat mode'}
        >
          {chatMode ? '💬' : '⚡'}
        </button>

        <button
          className="icon-btn notif-btn"
          onClick={onOpenNotifications}
          title={unreadCount > 0 ? `${unreadCount} unread notification${unreadCount === 1 ? '' : 's'} — open Notification Center` : 'Open Notification Center'}
          aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'}
        >
          <Bell size={15} />
          {unreadCount > 0 && (
            <span className="notif-badge" aria-hidden="true">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </button>

        <button
          className={`icon-btn ${voiceEnabled ? 'active' : ''}`}
          onClick={onToggleVoiceEnabled || (() => setVoiceEnabled(v => !v))}
          title={voiceEnabled ? 'Mute NEXUS voice' : 'Unmute NEXUS voice'}
          aria-label={voiceEnabled ? 'Mute NEXUS voice' : 'Unmute NEXUS voice'}
        >
          {voiceEnabled ? '🔊' : '🔇'}
        </button>

        <button className="icon-btn" onClick={onOpenSettings} title="Settings" aria-label="Settings">
          <Settings size={15} />
        </button>
      </div>
    </div>
  );
}
