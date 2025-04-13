import React from 'react';
import styles from '@/styles/SpeedSelector.module.css';

interface SpeedSelectorProps {
  onSpeedSelect: (speed: string) => void;
  initialSpeed?: string;
}

const SpeedSelector: React.FC<SpeedSelectorProps> = ({ onSpeedSelect, initialSpeed = 'slow' }) => {
  const speeds = [
    { value: 'slowest', label: 'Very slow speech' },
    { value: 'slow', label: 'Slower than normal speech' },
    { value: 'normal', label: 'Default speech rate' },
    { value: 'fast', label: 'Faster than normal speech' },
    { value: 'fastest', label: 'Very fast speech' }
  ];

  const handleSpeedChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const speed = event.target.value;
    onSpeedSelect(speed);
  };

  return (
    <div className={styles.speedSelector}>
      <label htmlFor="speed-select">Voice Speed: </label>
      <select 
        id="speed-select" 
        value={initialSpeed} 
        onChange={handleSpeedChange}
        className={styles.speedSelect}
      >
        {speeds.map(speed => (
          <option key={speed.value} value={speed.value}>
            {speed.label}
          </option>
        ))}
      </select>
    </div>
  );
};

export default SpeedSelector;
