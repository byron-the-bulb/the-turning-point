import styles from '@/styles/CallControls.module.css';
import React from 'react';

const MicIcon = () => <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.49 6-3.31 6-6.72h-1.7z"/></svg>;
const MicOffIcon = () => <svg height="24px" width="24px" viewBox="0 -960 960 960" fill="currentColor"><path d="m710-362-58-58q14-23 21-48t7-52h80q0 44-13 83.5T710-362ZM480-594Zm112 112-72-72v-206q0-17-11.5-28.5T480-800q-17 0-28.5 11.5T440-760v126l-80-80v-46q0-50 35-85t85-35q50 0 85 35t35 85v240q0 11-2.5 20t-5.5 18ZM440-120v-123q-104-14-172-93t-68-184h80q0 83 57.5 141.5T480-320q34 0 64.5-10.5T600-360l57 57q-29 23-63.5 39T520-243v123h-80Zm352 64L56-792l56-56 736 736-56 56Z"/></svg>
const PhoneIcon = () => <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" transform="rotate(135)"><path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.02.74-.25 1.02l-2.2 2.2z"/></svg>;


interface WaveformProps {
  isUserSpeaking: boolean;
}

const Waveform: React.FC<WaveformProps> = ({ isUserSpeaking }) => {
  const dots = Array.from(Array(20).keys());
  return (
    <div className={`${styles.waveform} ${isUserSpeaking ? styles.speaking : ''}`}>
      {dots.map(i => <div key={i} className={styles.dot}></div>)}
    </div>
  );
};

interface CallControlsProps {
  isConnected: boolean;
  isMuted: boolean;
  onStartCall: () => void;
  onStopCall: () => void;
  onToggleMute: () => void;
  isUserSpeaking: boolean;
}

const CallControls: React.FC<CallControlsProps> = ({
  isConnected,
  isMuted,
  onStartCall,
  onStopCall,
  onToggleMute,
  isUserSpeaking,
}) => {
  if (!isConnected) {
    return (
      <button onClick={onStartCall} className={styles.startCallButton}>
        Start Call
      </button>
    );
  }

  return (
    <div className={styles.inCallControls}>
      <button onClick={onToggleMute} className={`${styles.iconButton} ${isMuted ? styles.micOff : styles.micOn}`}>
        {isMuted ? <MicOffIcon /> : <MicIcon />}
      </button>
      <Waveform isUserSpeaking={isUserSpeaking} />
      <button onClick={onStopCall} className={styles.endCallButton}>
        <PhoneIcon />
        <span>End Call</span>
      </button>
    </div>
  );
};

export default CallControls; 