import React, { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';
import ChatLog, { ChatMessage, MessageType } from './ChatLog';
import { BotLLMTextData, RTVIClient, RTVIEvent, TranscriptData } from '@pipecat-ai/client-js';
import {
  RTVIClientProvider,
  RTVIClientAudio,
  useRTVIClient
} from '@pipecat-ai/client-react';
import { DailyTransport } from '@pipecat-ai/daily-transport';

// Generate a truly unique ID for messages
function generateUniqueId() {
  return Date.now().toString() + '-' + Math.random().toString(36).substring(2, 15);
}

// Server URL constants
const API_URL = 'http://localhost:8765';
const API_WS_URL = 'ws://localhost:8765';

// Create the Pipecat client instance
const client = (() => {
  try {
    return new RTVIClient({
      params: {
        baseUrl: API_URL,
        endpoint: { connect: '/connect' },
        wsUrl: API_WS_URL
      },
      transport: new DailyTransport(),
      enableMic: true
    });
  } catch (error) {
    console.error('Failed to initialize Pipecat client:', error);
    return null;
  }
})();

// Define VoiceBot component outside of App
interface VoiceBotProps {
  addChatMessage: (text: string, type: MessageType) => void;
  setIsWaitingForUser: React.Dispatch<React.SetStateAction<boolean>>;
  setIsUserSpeaking: React.Dispatch<React.SetStateAction<boolean>>;
  setStatusText: React.Dispatch<React.SetStateAction<string>>;
  setParticipantId: React.Dispatch<React.SetStateAction<string | undefined>>;
}

const VoiceBot = React.memo(({ addChatMessage, setIsWaitingForUser, setIsUserSpeaking, setStatusText, setParticipantId }: VoiceBotProps) => {
  const client = useRTVIClient();
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const eventHandlersAttached = useRef(false);
  const initialMessageSent = useRef(false);

  // Log mounting and unmounting for debugging
  useEffect(() => {
    console.log("VoiceBot mounted");
    return () => {
      console.log("VoiceBot unmounted");
    };
  }, []);

  // Send welcome message only once on mount
  useEffect(() => {
    if (!initialMessageSent.current) {
      addChatMessage('Sphinx Voice Bot ready', 'system');
      initialMessageSent.current = true;
      console.log("Initial welcome message sent");
    }
  }, [addChatMessage]);

  // Set up event listeners for the Pipecat client
  useEffect(() => {
    if (!client || eventHandlersAttached.current) return;

    console.log("Setting up Pipecat event handlers");
    eventHandlersAttached.current = true;

    const handleTextResponse = (text : BotLLMTextData) => {
      console.log('Received text response:', text);
      if (text.text) {
        addChatMessage(text.text, 'guide');
        //setIsWaitingForUser(true);
      }
    };

    const handleTranscription = (transcript : TranscriptData) => {
      console.log('Received transcription:', transcript);
      if (transcript.text) {
        addChatMessage(transcript.text, 'user');
        //setIsWaitingForUser(false);
      }
    };

    const handleConnected = () => {
      console.log('Connected to server');
      setStatusText('Connected to server');
      setIsConnected(true);
      setIsConnecting(false);
      addChatMessage('Connected to the Sphinx Voice Bot server', 'system');
    };

    const handleBotConnected = (participant: any) => {
      console.log('Participant joined:', participant);
      if (participant?.id) {
        console.log('Setting participant ID:', participant.id);
        setParticipantId(participant.id);
      }
    };

    const handleBotDisconnected = (participant: any) => {
      console.log('Participant disconnected:', participant);
      if (participant?.id) {
        console.log('Clearing participant ID:', participant.id);
        setParticipantId(undefined);
        addChatMessage('Participant disconnected', 'system');
      }
    };

    const handleDisconnected = () => {
      console.log('Disconnected from server');
      setStatusText('Disconnected from server');
      setIsConnected(false);
      setIsConnecting(false);
      addChatMessage('Disconnected from the server', 'system');
      setIsWaitingForUser(false);
    };

    const handleServerMessage = (event: any) => {
      console.log('Server message received:', event);
      if (event.status) { 
        addChatMessage(event.status, 'system');
      }
    };

    const handleError = (error: any) => {
      console.error('Pipecat client error:', error);
      setStatusText(`Error: ${error.message || 'Unknown error'}`);
      addChatMessage(`Error: ${error.message || 'Unknown error'}`, 'system');
      setIsConnecting(false);
    };

    const handleBotStoppedSpeaking = () => {
      console.log('Bot stopped speaking');
      setIsWaitingForUser(true);
    };

    const handleBotStartedSpeaking = () => {
      console.log('Bot started speaking');
      setIsWaitingForUser(false);
    };

    const handleUserStartedSpeaking = () => {
      console.log('User started speaking');
      setIsWaitingForUser(false);
      setIsUserSpeaking(true);
    };

    const handleUserStoppedSpeaking = () => {
      console.log('User stopped speaking');
      setIsUserSpeaking(false);
    };

    client.on('connected', handleConnected);
    client.on('disconnected', handleDisconnected);
    client.on(RTVIEvent.ServerMessage, handleServerMessage);
    client.on('error', handleError);
    client.on('botConnected', handleBotConnected);
    client.on('botDisconnected', handleBotDisconnected);
    client.on(RTVIEvent.UserTranscript, handleTranscription)
    client.on(RTVIEvent.BotTranscript, handleTextResponse)
    client.on(RTVIEvent.BotStartedSpeaking, handleBotStartedSpeaking)
    client.on(RTVIEvent.BotStoppedSpeaking, handleBotStoppedSpeaking)
    client.on(RTVIEvent.UserStartedSpeaking, handleUserStartedSpeaking)
    client.on(RTVIEvent.UserStoppedSpeaking, handleUserStoppedSpeaking)

    return () => {
      console.log("Cleaning up Pipecat event handlers");
      client.off('connected', handleConnected);
      client.off('disconnected', handleDisconnected);
      client.off(RTVIEvent.ServerMessage, handleServerMessage);
      client.off('error', handleError);
      client.off('botConnected', handleBotConnected);
      client.off('botDisconnected', handleBotDisconnected);
      client.off(RTVIEvent.UserTranscript, handleTranscription);
      client.off(RTVIEvent.BotTranscript, handleTextResponse);
      eventHandlersAttached.current = false;
    };
  }, [client, addChatMessage, setIsWaitingForUser, setStatusText, setParticipantId]);

  const handleStartConnection = useCallback(() => {
    if (!client) return;
    console.log('Starting connection...');
    setStatusText('Starting connection...');
    setIsConnecting(true);
    client.connect().catch((err: Error) => {
      console.error('Failed to connect:', err);
      setStatusText(`Connection error: ${err.message}`);
      setIsConnecting(false);
    });
  }, [client, setStatusText]);

  const handleStopConnection = useCallback(() => {
    if (!client) return;
    console.log('Stopping connection...');
    setStatusText('Disconnecting...');
    client.disconnect().catch((err: Error) => {
      console.error('Failed to disconnect:', err);
      setStatusText(`Disconnection error: ${err.message}`);
    });
  }, [client, setStatusText]);

  return (
    <div className="controls">
      <button
        onClick={handleStartConnection}
        disabled={isConnected || isConnecting}
      >
        {isConnecting ? 'Connecting...' : 'Start Conversation'}
      </button>
      <button
        onClick={handleStopConnection}
        disabled={!isConnected}
      >
        Stop Conversation
      </button>
    </div>
  );
});

// Main App component
function App() {
  const [statusText, setStatusText] = useState('Ready to connect');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isWaitingForUser, setIsWaitingForUser] = useState(false);
  const [clientInitialized, setClientInitialized] = useState(!!client);
  const [participantId, setParticipantId] = useState<string | undefined>();
  const [conversationStatus, setConversationStatus] = useState<String | null>(null);
  const [isUserSpeaking, setIsUserSpeaking] = useState(false);

  useEffect(() => {
    if (!client) {
      setStatusText('Error: Failed to initialize Pipecat client. Check console for details.');
    }
  }, []);

  /*useEffect(() => {
    if (!participantId) return;

    console.log(`Setting up status polling for participant: ${participantId}`);
    const fetchStatus = async () => {
      try {
        const response = await fetch(`${API_URL}/conversation-status/${participantId}`);
        if (!response.ok) throw new Error(`Status error: ${response.status}`);
        const data = await response.json();
        handleStatusChange(data);
      } catch (error) {
        console.error('Failed to fetch conversation status:', error);
      }
    };

    fetchStatus();
    const intervalId = setInterval(fetchStatus, 1000);
    return () => clearInterval(intervalId);
  }, [participantId, handleStatusChange]);*/

  const addChatMessage = useCallback((text: string, type: MessageType) => {
    if (!text) return;
    console.log(`Adding ${type} message: ${text}`);
    setChatMessages(prevMessages => {
      const isDuplicate = prevMessages.some(
        msg => msg.text === text && msg.type === type &&
          (new Date().getTime() - msg.timestamp.getTime() < 2000)
      );
      if (isDuplicate) {
        console.log(`Prevented duplicate message: ${text}`);
        return prevMessages;
      }
      const newMessage = {
        id: generateUniqueId(),
        text,
        type,
        timestamp: new Date()
      };
      return [...prevMessages, newMessage];
    });
  }, []);

  if (!clientInitialized) {
    return (
      <div className="App">
        <h1>Sphinx Voice Bot Interface</h1>
        <h3><div id="statusText" style={{ color: 'red' }}>{statusText}</div></h3>
        <p>Could not initialize audio client. Please check console for details.</p>
      </div>
    );
  }

  return (
    <div className="App">
      <h1>Sphinx Voice Bot Interface</h1>
      <h3><div id="statusText">{statusText}</div></h3>

      {participantId ? (
        <>
          <div style={{ marginBottom: '10px' }}>
            <strong>Participant ID:</strong> {participantId}
          </div>
          <div style={{ marginBottom: '10px' }}>
            <strong>Conversation Status:</strong> {conversationStatus}
          </div>
        </>
      ) : (
        <div style={{ color: 'orange' }}>
          Status monitor unavailable - No participant ID detected
        </div>
      )}

      {client && (
        <RTVIClientProvider client={client}>
          <VoiceBot
            addChatMessage={addChatMessage}
            setIsWaitingForUser={setIsWaitingForUser}
            setIsUserSpeaking={setIsUserSpeaking}
            setStatusText={setStatusText}
            setParticipantId={setParticipantId}
          />
          <RTVIClientAudio />
        </RTVIClientProvider>
      )}

      <ChatLog messages={chatMessages} isWaitingForUser={isWaitingForUser} isUserSpeaking={isUserSpeaking} />
    </div>
  );
}

export default App;