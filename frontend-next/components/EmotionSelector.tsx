import React, { useState } from 'react';
import styles from '@/styles/EmotionSelector.module.css';

interface EmotionOption {
  name: string;
  level: string | null;
}

type EmotionTag = string; // Format: "emotion_name:level" or just "emotion_name"

interface EmotionSelectorProps {
  onEmotionsChange: (emotions: EmotionTag[] | null) => void;
  initialEmotions?: EmotionTag[] | null;
}

const EmotionSelector: React.FC<EmotionSelectorProps> = ({ 
  onEmotionsChange, 
  initialEmotions = null
}) => {
  const emotionNames = ['anger', 'positivity', 'surprise', 'sadness', 'curiosity'];
  const emotionLevels = ['lowest', 'low', '', 'high', 'highest']; // '' represents moderate (no level specified)
  
  // Initialize selectedEmotions based on initialEmotions
  const parseInitialEmotions = (): EmotionOption[] => {
    if (!initialEmotions || initialEmotions.length === 0) {
      return [];
    }
    
    return initialEmotions.map(tag => {
      const [name, level] = tag.split(':');
      return { name, level: level || null };
    });
  };

  const [selectedEmotions, setSelectedEmotions] = useState<EmotionOption[]>(parseInitialEmotions());

  // Update the selected emotions and notify parent component
  const updateEmotions = (updatedEmotions: EmotionOption[]) => {
    setSelectedEmotions(updatedEmotions);
    
    if (updatedEmotions.length === 0) {
      // If no emotions are selected, pass null to indicate no emotions
      onEmotionsChange(null);
      return;
    }
    
    // Convert the selected emotions back to tags format
    const tags: EmotionTag[] = updatedEmotions.map(emotion => 
      emotion.level ? `${emotion.name}:${emotion.level}` : emotion.name
    );
    
    onEmotionsChange(tags);
  };

  // Handle adding a new emotion to the list
  const handleAddEmotion = () => {
    // Default to first emotion not yet selected
    const availableEmotions = emotionNames.filter(
      name => !selectedEmotions.some(emotion => emotion.name === name)
    );
    
    if (availableEmotions.length > 0) {
      const newEmotions = [
        ...selectedEmotions, 
        { name: availableEmotions[0], level: null }
      ];
      updateEmotions(newEmotions);
    }
  };

  // Handle removing an emotion from the list
  const handleRemoveEmotion = (index: number) => {
    const newEmotions = [...selectedEmotions];
    newEmotions.splice(index, 1);
    updateEmotions(newEmotions);
  };

  // Handle changing the emotion name
  const handleEmotionNameChange = (index: number, name: string) => {
    const newEmotions = [...selectedEmotions];
    newEmotions[index].name = name;
    updateEmotions(newEmotions);
  };

  // Handle changing the emotion level
  const handleEmotionLevelChange = (index: number, level: string) => {
    const newEmotions = [...selectedEmotions];
    newEmotions[index].level = level === '' ? null : level;
    updateEmotions(newEmotions);
  };

  // Check if all emotions are already selected
  const allEmotionsSelected = selectedEmotions.length >= emotionNames.length;

  return (
    <div className={styles.emotionSelector}>
      <label>Voice Emotions:</label>
      {selectedEmotions.length === 0 ? (
        <div className={styles.noEmotionsMessage}>No emotions selected (neutral voice)</div>
      ) : (
        <div className={styles.emotionList}>
          {selectedEmotions.map((emotion, index) => (
          <div key={index} className={styles.emotionItem}>
            <select 
              value={emotion.name}
              onChange={(e) => handleEmotionNameChange(index, e.target.value)}
              className={styles.emotionNameSelect}
            >
              {emotionNames.map(name => (
                <option 
                  key={name} 
                  value={name}
                  disabled={name !== emotion.name && selectedEmotions.some(e => e.name === name)}
                >
                  {name}
                </option>
              ))}
            </select>
            
            <select 
              value={emotion.level || ''}
              onChange={(e) => handleEmotionLevelChange(index, e.target.value)}
              className={styles.emotionLevelSelect}
            >
              {emotionLevels.map((level, levelIndex) => (
                <option key={levelIndex} value={level}>
                  {level === '' ? 'moderate' : level}
                </option>
              ))}
            </select>
            
            <button 
              type="button" 
              onClick={() => handleRemoveEmotion(index)}
              className={styles.removeEmotionBtn}
            >
              Remove
            </button>
          </div>
        ))}
      </div>
      )}
      
      <button 
        type="button" 
        onClick={handleAddEmotion}
        className={styles.addEmotionBtn}
        disabled={allEmotionsSelected}
      >
        {selectedEmotions.length === 0 ? 'Add an Emotion' : 'Add Another Emotion'}
      </button>
      
      <div className={styles.emotionInfo}>
        <small>Emotion controls are additive, they cannot reduce emotions.</small>
      </div>
    </div>
  );
};

export default EmotionSelector;
