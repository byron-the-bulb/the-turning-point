import React, { useState, useEffect, useRef } from 'react';
import styles from '@/styles/EmotionTracker.module.css';

// Types for the emotion data
export interface Emotion {
  name: string;
  score: number;
}

export interface EmotionPrediction {
  emotions: Emotion[];
  time?: {
    begin: number;
    end: number;
  };
}

export interface EmotionData {
  predictions: EmotionPrediction[];
}

interface EmotionTrackerProps {
  emotionData: EmotionData | null;
}

const EmotionTracker: React.FC<EmotionTrackerProps> = ({ emotionData }) => {
  // Store history of emotion predictions for the scrolling graph
  const [emotionHistory, setEmotionHistory] = useState<EmotionPrediction[]>([]);
  // Store the top 4 emotions from the latest prediction
  const [topEmotions, setTopEmotions] = useState<Emotion[]>([]);
  
  const maxHistoryLength = 10; // Maximum number of predictions to keep in history
  const graphContainerRef = useRef<HTMLDivElement>(null);

  // Process new emotion data when it's received
  useEffect(() => {
    if (emotionData?.predictions && emotionData.predictions.length > 0) {
      // Get the latest prediction
      const latestPrediction = emotionData.predictions[0];
      
      // Find the top 4 emotions by score
      const sortedEmotions = [...latestPrediction.emotions].sort((a, b) => b.score - a.score);
      setTopEmotions(sortedEmotions.slice(0, 4));
      
      // Add the new prediction to history and limit its size
      setEmotionHistory(prevHistory => {
        // Add new prediction at the end for time-based plotting
        const newHistory = [...prevHistory, latestPrediction];
        return newHistory.slice(-maxHistoryLength);
      });
    }
  }, [emotionData]);

  // Get a color for an emotion based on its name
  const getEmotionColor = (emotionName: string): string => {
    // Simple hash function to generate a color
    const hash = emotionName.split('').reduce((acc, char) => {
      return char.charCodeAt(0) + ((acc << 5) - acc);
    }, 0);
    
    // Generate a hue between 0 and 360
    const hue = Math.abs(hash) % 360;
    return `hsl(${hue}, 70%, 60%)`;
  };

  // Check if an emotion is in the top 4
  const isTopEmotion = (emotion: Emotion): boolean => {
    return topEmotions.some(topEmotion => topEmotion.name === emotion.name);
  };
  
  // Prepare the data for the polygraph chart
  const prepareChartData = () => {
    if (emotionHistory.length === 0) return { emotions: [], timePoints: [] };
    
    // Extract all unique emotions from history
    const allEmotions = new Set<string>();
    emotionHistory.forEach(prediction => {
      prediction.emotions.forEach(emotion => {
        if (isTopEmotion(emotion)) {
          allEmotions.add(emotion.name);
        }
      });
    });
    
    // Create points for X-axis based on incrementing indices instead of time
    const timePoints = emotionHistory.map((_, index) => 
      `#${index + 1}`
    );
    
    // Create emotion lines data
    const emotions = Array.from(allEmotions).map(emotionName => {
      const color = getEmotionColor(emotionName);
      const values = emotionHistory.map(prediction => {
        const emotion = prediction.emotions.find(e => e.name === emotionName);
        return emotion ? emotion.score : 0;
      });
      
      return { name: emotionName, color, values };
    });
    
    return { emotions, timePoints };
  };

  return (
    <div className={styles.emotionTracker}>
      <h3>Emotion Tracking</h3>
      
      {/* Top Emotions Section */}
      <div className={styles.topEmotions}>
        <h4>Top Emotions</h4>
        <div className={styles.emotionGrid}>
          {topEmotions.map((emotion, index) => (
            <div 
              key={index} 
              className={styles.topEmotionItem}
              style={{ backgroundColor: getEmotionColor(emotion.name) }}
            >
              <div className={styles.emotionName}>{emotion.name}</div>
              <div className={styles.emotionScore}>{(emotion.score * 100).toFixed(1)}%</div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Graph Section - XY Plot (Polygraph style) */}
      <div className={styles.graphContainer} ref={graphContainerRef}>
        {emotionHistory.length > 0 ? (
          <div className={styles.xyPlot}>
            {/* Y-axis labels */}
            <div className={styles.yAxis}>
              <div className={styles.yLabel}>100%</div>
              <div className={styles.yLabel}>75%</div>
              <div className={styles.yLabel}>50%</div>
              <div className={styles.yLabel}>25%</div>
              <div className={styles.yLabel}>0%</div>
            </div>
            
            {/* Chart area */}
            <div className={styles.chartArea}>
              {/* Grid lines */}
              <div className={styles.gridLines}>
                <div className={styles.horizontalGrid}></div>
                <div className={styles.horizontalGrid}></div>
                <div className={styles.horizontalGrid}></div>
                <div className={styles.horizontalGrid}></div>
              </div>
              
              {/* Emotion lines */}
              {(() => {
                const { emotions, timePoints } = prepareChartData();
                return emotions.map((emotion, index) => (
                  <div key={index} className={styles.emotionLine}>
                    {/* Create the polyline for each emotion */}
                    <svg className={styles.lineSvg} viewBox={`0 0 ${timePoints.length * 100} 100`} preserveAspectRatio="none">
                      <polyline
                        points={emotion.values.map((value, i) => 
                          `${i * 100}, ${100 - (value * 100)}`
                        ).join(' ')}
                        fill="none"
                        stroke={emotion.color}
                        strokeWidth="2"
                      />
                    </svg>
                    
                    {/* Data points */}
                    {emotion.values.map((value, i) => (
                      <div 
                        key={i}
                        className={styles.dataPoint}
                        style={{
                          left: `${(i / (timePoints.length - 1)) * 100}%`,
                          bottom: `${value * 100}%`,
                          backgroundColor: emotion.color,
                          borderColor: emotion.color
                        }}
                        title={`${emotion.name}: ${(value * 100).toFixed(1)}%`}
                      />
                    ))}
                  </div>
                ));
              })()}
              
              {/* Legend */}
              <div className={styles.chartLegend}>
                {(() => {
                  const { emotions } = prepareChartData();
                  return emotions.map((emotion, index) => (
                    <div key={index} className={styles.legendItem}>
                      <div 
                        className={styles.legendColor} 
                        style={{ backgroundColor: emotion.color }}
                      />
                      <div className={styles.legendName}>{emotion.name}</div>
                    </div>
                  ));
                })()}
              </div>
            </div>
            
            {/* X-axis with time labels */}
            <div className={styles.xAxis}>
              {prepareChartData().timePoints.map((time, index) => (
                <div 
                  key={index} 
                  className={styles.timeLabel}
                  style={{ left: `${(index / (prepareChartData().timePoints.length - 1)) * 100}%` }}
                >
                  {time}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className={styles.noDataMessage}>No emotion data available yet</div>
        )}
      </div>
    </div>
  );
};

export default EmotionTracker;
