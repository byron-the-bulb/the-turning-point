import React, { useState } from 'react';
import SpeedSelector from './SpeedSelector';
import EmotionSelector from './EmotionSelector';

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
    <div className="voice-settings-panel">
      <button 
        className="settings-toggle-btn" 
        onClick={togglePanel}
        aria-expanded={isExpanded}
      >
        <span>Advanced Voice Settings</span>
        <span className={`chevron ${isExpanded ? 'up' : 'down'}`}>
          {isExpanded ? '▲' : '▼'}
        </span>
      </button>
      
      {isExpanded && (
        <div className="settings-content">          
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
