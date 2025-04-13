import React, { useState, useEffect } from 'react';
import { CartesiaClient } from '@cartesia/cartesia-js';
import styles from '@/styles/VoiceSelector.module.css';

// Define the Voice interface based on Cartesia's response
interface Voice {
  id: string;
  name: string;
  description?: string;
  language: string;
  gender?: string;
  preview_url?: string;
}

interface VoiceSelectorProps {
  onVoiceSelect: (voiceId: string) => void;
  initialVoiceId?: string;
  apiKey: string;
}

const VoiceSelector: React.FC<VoiceSelectorProps> = ({ onVoiceSelect, initialVoiceId, apiKey }) => {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>(initialVoiceId || '');

  useEffect(() => {
    const fetchVoices = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // Initialize the Cartesia client
        const client = new CartesiaClient({ apiKey });
        
        // Fetch all voices
        const allVoices = await client.voices.list();
        
        // Filter for American English voices
        const americanVoices = allVoices.filter(voice => voice.language === 'en');
        
        setVoices(americanVoices);
        
        // If there are voices and no initial voice is selected, select the first one
        if (americanVoices.length > 0 && !selectedVoiceId) {
          setSelectedVoiceId(americanVoices[0].id);
          onVoiceSelect(americanVoices[0].id);
        }
      } catch (err) {
        console.error('Error fetching voices:', err);
        setError('Failed to load voices. Please check your API key and try again.');
      } finally {
        setLoading(false);
      }
    };

    if (apiKey) {
      fetchVoices();
    } else {
      setError('API key is required to fetch voices');
      setLoading(false);
    }
  }, [apiKey, onVoiceSelect, selectedVoiceId]);

  const handleVoiceChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const voiceId = event.target.value;
    setSelectedVoiceId(voiceId);
    onVoiceSelect(voiceId);
  };

  return (
    <div className={styles.voiceSelector}>
      <label htmlFor="voice-select">Select Voice: </label>
      {loading ? (
        <span className={styles.loading}>Loading voices...</span>
      ) : error ? (
        <div className={styles.error}>{error}</div>
      ) : (
        <select 
          id="voice-select" 
          value={selectedVoiceId} 
          onChange={handleVoiceChange}
          disabled={loading}
          className={styles.voiceSelect}
        >
          {voices.length === 0 ? (
            <option value="">No American voices available</option>
          ) : (
            voices.map(voice => (
              <option key={voice.id} value={voice.id}>
                {voice.name} {voice.gender ? `(${voice.gender})` : ''}
              </option>
            ))
          )}
        </select>
      )}
    </div>
  );
};

export default VoiceSelector;
