import React, { useState } from 'react';
import SpeedSelector from './SpeedSelector';
import EmotionSelector from './EmotionSelector';
import styles from '@/styles/VoiceSettingsPanel.module.css';

interface VoiceSettingsPanelProps {
  selectedSpeed: string;
  selectedEmotions: string[] | null;
  onSpeedSelect: (speed: string) => void;
  onEmotionsChange: (emotions: string[] | null) => void;
}

const VoiceSettingsPanel: React.FC<VoiceSettingsPanelProps> = ({
  selectedSpeed,
  selectedEmotions,
  onSpeedSelect,
  onEmotionsChange
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const togglePanel = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <div className={styles.voiceSettingsPanel}>
      <button 
        className={styles.settingsToggleBtn} 
        onClick={togglePanel}
        aria-expanded={isExpanded}
      >
        <span>Advanced Voice Settings</span>
        <span className={`${styles.chevron} ${isExpanded ? styles.up : styles.down}`}>
          {isExpanded ? '▲' : '▼'}
        </span>
      </button>
      
      {isExpanded && (
        <div className={styles.settingsContent}>          
          <SpeedSelector
            onSpeedSelect={onSpeedSelect}
            initialSpeed={selectedSpeed}
          />
          
          <EmotionSelector
            onEmotionsChange={onEmotionsChange}
            initialEmotions={selectedEmotions}
          />
        </div>
      )}
    </div>
  );
};

export default VoiceSettingsPanel;
