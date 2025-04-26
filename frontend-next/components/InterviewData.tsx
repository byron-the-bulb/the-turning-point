import React from 'react';
import styles from '@/styles/InterviewData.module.css';

interface InterviewDataProps {
  name: string | null;
  challenge: string | null;
  envisionedState: string | null;
  challenge_emotions: string[] | null;
  empowered_emotions: string[] | null;
}

const InterviewData: React.FC<InterviewDataProps> = ({ 
  name, 
  challenge, 
  envisionedState, 
  challenge_emotions,
  empowered_emotions 
}) => {
  return (
    <div className={styles.interviewData}>
      <h3>Interview Data</h3>
      <div className={styles.dataContainer}>
        <div className={styles.dataItem}>
          <span className={styles.label}>Name:</span>
          <span className={styles.value}>{name || 'Not yet provided'}</span>
        </div>
        <div className={styles.dataItem}>
          <span className={styles.label}>Current Challenge:</span>
          <span className={styles.value}>{challenge || 'Not yet identified'}</span>
        </div>
        <div className={styles.dataItem}>
          <span className={styles.label}>Challenge Emotions:</span>
          <div className={styles.emotionsList}>
            {challenge_emotions && challenge_emotions.length > 0 ? (
              challenge_emotions.map((emotion, index) => (
                <span key={index} className={styles.emotionTag}>{emotion}</span>
              ))
            ) : (
              <span className={styles.placeholder}>No emotions recorded yet</span>
            )}
          </div>
        </div>
        <div className={styles.dataItem}>
          <span className={styles.label}>Envisioned State:</span>
          <span className={styles.value}>{envisionedState || 'Not yet envisioned'}</span>
        </div>
        <div className={styles.dataItem}>
          <span className={styles.label}>Empowered Emotions:</span>
          <div className={styles.emotionsList}>
            {empowered_emotions && empowered_emotions.length > 0 ? (
              empowered_emotions.map((emotion, index) => (
                <span key={index} className={styles.emotionTag}>{emotion}</span>
              ))
            ) : (
              <span className={styles.placeholder}>No emotions recorded yet</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default InterviewData; 