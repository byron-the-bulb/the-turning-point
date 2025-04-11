import React, { useState, useEffect } from 'react';
import './App.css';

interface StatusMonitorProps {
  apiUrl: string;
  identifier?: string; // Can be either participant ID or room URL
  pollInterval?: number;
  onStatusChange?: (status: ConversationStatus) => void;
}

export interface ConversationStatus {
  status: string;
  identifier?: string;
  context?: Record<string, any>;
}

const StatusMonitor: React.FC<StatusMonitorProps> = ({
  apiUrl,
  identifier,
  pollInterval = 2000,
  onStatusChange
}) => {
  const actualIdentifier = identifier;
  const [status, setStatus] = useState<ConversationStatus>({ status: 'initializing' });
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    if (!actualIdentifier) {
      setStatus({ status: 'waiting for participant' });
      return;
    }
    
    // Start polling for status updates
    const encodedIdentifier = encodeURIComponent(actualIdentifier);
    const statusUrl = `${apiUrl}/conversation-status/${encodedIdentifier}`;
    let isActive = true;
    
    const pollStatus = async () => {
      try {
        const response = await fetch(statusUrl);
        if (!response.ok) {
          throw new Error(`Status API returned ${response.status}`);
        }
        
        const statusData = await response.json();
        if (isActive) {
          setStatus(statusData);
          setError(null);
          
          // Call the status change callback if provided
          if (onStatusChange) {
            onStatusChange(statusData);
          }
        }
      } catch (err) {
        if (isActive) {
          console.error('Error fetching status:', err);
          setError(`Failed to get status: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    };
    
    // Initial fetch
    pollStatus();
    
    // Set up polling interval
    const intervalId = setInterval(pollStatus, pollInterval);
    
    // Cleanup function
    return () => {
      isActive = false;
      clearInterval(intervalId);
    };
  }, [apiUrl, actualIdentifier, pollInterval, onStatusChange]);
  
  if (error) {
    return (
      <div className="status-monitor error">
        <p>Error: {error}</p>
      </div>
    );
  }
  
  return (
    <div className="status-monitor">
      <div className="status-indicator">
        <span className="status-label">Status:</span> 
        <span className="status-value">{status.status}</span>
      </div>
      {status.context && Object.keys(status.context).length > 0 && (
        <div className="status-context">
          <h4>Context</h4>
          <ul>
            {Object.entries(status.context).map(([key, value]) => (
              <li key={key}>
                <strong>{key}:</strong> {JSON.stringify(value)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default StatusMonitor;
