import React, { useRef, useEffect, useState } from 'react';
import { useRTVIClient } from '@pipecat-ai/client-react';
import { v4 as uuidv4 } from 'uuid';
import './ChatLog.css';
import { RTVIMessage } from '@pipecat-ai/client-js';

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
  isUserSpeaking: boolean;
  uiOverride: any | null;
}

const ChatLog: React.FC<ChatLogProps> = ({ messages, isWaitingForUser, isUserSpeaking, uiOverride }) => {
  const chatEndRef = useRef<HTMLDivElement>(null);
  const uiOverrideRef = useRef<HTMLDivElement>(null);
  const client = useRTVIClient();
  const [selectedOption, setSelectedOption] = useState('');
  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Scroll to UI override when it appears
  useEffect(() => {
    if (uiOverride && uiOverrideRef.current) {
      uiOverrideRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [uiOverride]);

  const handleButtonClick = async () => {
    if (client && uiOverride?.type === 'button') {
      console.log('Sending uiOverride action : ', uiOverride);
      const action = await client.action({
        service: 'conversation',
        action: 'uioverride_response',
        arguments: [
          { name : 'message', value: uiOverride.action_text}
        ]
      })
    }
  };

  const handleListSelection = () => {
    if (client && uiOverride?.type === 'list' && selectedOption) {
      console.log('Sending uiOverride action : ', uiOverride);
      const action = client.action({
        service: 'conversation',
        action: 'uioverride_response',
        arguments: [
          { name : 'message', value: selectedOption}
        ]
      })
      setSelectedOption(''); // Reset selection after submission
    }
  };

  return (
    <div className="chat-log">
      <div className="chat-header">
        <h2>Conversation Log</h2>
        {isWaitingForUser && (
          <div className="waiting-indicator">
            Waiting for your response...
          </div>
        )}
        {isUserSpeaking && (
          <div className="speaking-indicator">
            Speaking detected...
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
                {message.type === 'user' ? 'Participant' : 
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
        {uiOverride && (
          <div className="ui-override-container" ref={uiOverrideRef}>
            {uiOverride.type === 'button' && (
              <div>
                <p>{uiOverride.prompt}</p>
                <button onClick={handleButtonClick}>{uiOverride.action_text}</button>
              </div>
            )}
            {uiOverride.type === 'list' && (
              <div>
                <p>{uiOverride.prompt}</p>
                <select 
                  value={selectedOption} 
                  onChange={(e) => setSelectedOption(e.target.value)}
                >
                  <option value="">Select an option</option>
                  {uiOverride.options.map((option: string, index: number) => (
                    <option key={index} value={option}>{option}</option>
                  ))}
                </select>
                <button onClick={handleListSelection} disabled={!selectedOption}>
                  Submit
                </button>
              </div>
            )}
          </div>
        )}
        <div ref={chatEndRef} />
      </div>
    </div>
  );
};
export default ChatLog;
