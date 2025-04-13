import React from 'react';

interface LoadingSpinnerProps {
  message?: string;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ message = 'Loading...' }) => {
  return (
    <div className="loading-spinner-container">
      <div className="loading-spinner"></div>
      <div className="loading-message">{message}</div>
    </div>
  );
};

export default LoadingSpinner;
