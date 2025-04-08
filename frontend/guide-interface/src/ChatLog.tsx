import React, { useRef, useEffect } from 'react';
import './ChatLog.css';

// Message types
export type MessageType = 'system' | 'user' | 'guide' | 'status';

// Chat message interface
export interface ChatMessage {
  id: string;
  text: string;
  type: MessageType;
  timestamp: Date;
}

interface ChatLogProps {
  messages: ChatMessage[];
  isWaitingForUser: boolean;
}

const ChatLog: React.FC<ChatLogProps> = ({ messages, isWaitingForUser }) => {
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  return (
    <div className="chat-log">
      <div className="chat-header">
        <h2>Conversation Log</h2>
        {isWaitingForUser && (
          <div className="waiting-indicator">
            Waiting for your response...
          </div>
        )}
      </div>
      
      <div className="chat-messages">
        {messages.map((message) => (
          <div 
            key={message.id} 
            className={`chat-message message-${message.type}`}
          >
            <div className="message-header">
              <span className="message-type">
                {message.type === 'user' ? 'You' : 
                 message.type === 'guide' ? 'Sphinx' : 
                 message.type === 'system' ? 'System' : 'Status'}
              </span>
              <span className="message-time">
                {message.timestamp.toLocaleTimeString()}
              </span>
            </div>
            <div className="message-content">{message.text}</div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>
    </div>
  );
};

export default ChatLog;
