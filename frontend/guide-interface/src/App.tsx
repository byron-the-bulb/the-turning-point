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
import VoiceSelector from './VoiceSelector';

// Generate a truly unique ID for messages
function generateUniqueId() {
  return Date.now().toString() + '-' + Math.random().toString(36).substring(2, 15);
}

// Server URL constants
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8765';
const API_WS_URL = process.env.REACT_APP_API_WS_URL || 'ws://localhost:8765';
// Cartesia API key - in production, this should be stored in environment variables
const CARTESIA_API_KEY = process.env.REACT_APP_CARTESIA_API_KEY || '';
console.log("API URL:", API_URL)

// Default TTS configuration
const defaultTtsConfig = {
  provider: 'cartesia',
  voiceId: '146485fd-8736-41c7-88a8-7cdd0da34d84', // Default voice ID
  model: 'sonic-2-2025-03-07',
  language: 'en',
  speed: 'slowest',
  emotion: ['curiosity:high']
};

// Function to create a Pipecat client with the given TTS configuration
const createClient = (ttsConfig = defaultTtsConfig) => {
  try {
    return new RTVIClient({
      params: {
        baseUrl: API_URL,
        requestData: {
          tts: ttsConfig
        },
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
};

// We'll create the client only when the user starts the conversation
let clientInstance: RTVIClient | null = null;


// Define VoiceBot component outside of App
interface VoiceBotProps {
  addChatMessage: (text: string, type: MessageType) => void;
  setIsWaitingForUser: React.Dispatch<React.SetStateAction<boolean>>;
  setIsUserSpeaking: React.Dispatch<React.SetStateAction<boolean>>;
  setStatusText: React.Dispatch<React.SetStateAction<string>>;
  setParticipantId: React.Dispatch<React.SetStateAction<string | undefined>>;
  setUIOverride: React.Dispatch<React.SetStateAction<any>>;
  pendingUIOverride: any | null;
  setPendingUIOverride: React.Dispatch<React.SetStateAction<any | null>>;
  setConversationStatus: React.Dispatch<React.SetStateAction<String | null>>;
  ttsConfig: any;
}

const VoiceBot = React.memo(({ addChatMessage, setIsWaitingForUser, setIsUserSpeaking, setStatusText, setParticipantId, setUIOverride, pendingUIOverride, setPendingUIOverride, setConversationStatus, ttsConfig }: VoiceBotProps) => {
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const initialMessageSent = useRef(false);

  // Log mounting and unmounting for debugging
  useEffect(() => {
    console.log("VoiceBot mounted blah, blah!");
    console.log("API URL:", API_URL);
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

  // Define event handler functions
  const setupEventHandlers = (client: RTVIClient) => {
    console.log("Setting up Pipecat event handlers");

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
        setUIOverride(null);
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
      setUIOverride(null);
      setIsConnected(false);
      setIsConnecting(false);
      addChatMessage('Disconnected from the server', 'system');
      setIsWaitingForUser(false);
    };

    const handleServerMessage = (event: any) => {
      console.log('Server message received:', event);
      if (event) {
        //its either status or trigger. TODO : Make this better
        if (event.status) {
          addChatMessage(event.status, 'system');
          setConversationStatus(event.status_context?.node || null);
        
          if (event.ui_override) {
            console.log('UI override received:', event.ui_override);
            setPendingUIOverride(event.ui_override);
          }
        } else if (event.trigger === "UIOverride") {
          console.log('UI override trigger received');
          if (pendingUIOverride) {
            console.log('Setting UI override:', pendingUIOverride);
            setUIOverride(pendingUIOverride);
            setPendingUIOverride(null);
            setIsWaitingForUser(true);
          }
        }
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

    // Attach event handlers
    client.on('connected', handleConnected);
    client.on('disconnected', handleDisconnected);
    client.on(RTVIEvent.ServerMessage, handleServerMessage);
    client.on('error', handleError);
    client.on('botConnected', handleBotConnected);
    client.on('botDisconnected', handleBotDisconnected);
    client.on(RTVIEvent.UserTranscript, handleTranscription);
    client.on(RTVIEvent.BotTranscript, handleTextResponse);
    client.on(RTVIEvent.BotStartedSpeaking, handleBotStartedSpeaking);
    client.on(RTVIEvent.BotStoppedSpeaking, handleBotStoppedSpeaking);
    client.on(RTVIEvent.UserStartedSpeaking, handleUserStartedSpeaking);
    client.on(RTVIEvent.UserStoppedSpeaking, handleUserStoppedSpeaking);

    // Return cleanup function
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
      client.off(RTVIEvent.BotStartedSpeaking, handleBotStartedSpeaking);
      client.off(RTVIEvent.BotStoppedSpeaking, handleBotStoppedSpeaking);
      client.off(RTVIEvent.UserStartedSpeaking, handleUserStartedSpeaking);
      client.off(RTVIEvent.UserStoppedSpeaking, handleUserStoppedSpeaking);
    };
  };

  const handleStartConnection = useCallback(() => {
    console.log('Starting connection with TTS config:', ttsConfig);
    setStatusText('Starting connection...');
    setIsConnecting(true);
    
    // Create a new client with the current TTS configuration
    clientInstance = createClient(ttsConfig);
    
    if (!clientInstance) {
      console.error('Failed to create client');
      setStatusText('Failed to create client');
      setIsConnecting(false);
      return;
    }
    
    // Set up event handlers for the new client
    const cleanup = setupEventHandlers(clientInstance);
    
    // Connect the client
    clientInstance.connect().catch((err: Error) => {
      console.error('Failed to connect:', err);
      setStatusText(`Connection error: ${err.message}`);
      setIsConnecting(false);
      cleanup(); // Clean up event handlers if connection fails
    });
  }, [ttsConfig]);

  const handleStopConnection = useCallback(() => {
    if (!clientInstance) return;
    console.log('Stopping connection...');
    setStatusText('Disconnecting...');
    
    clientInstance.disconnect().catch((err: Error) => {
      console.error('Failed to disconnect:', err);
      setStatusText(`Disconnection error: ${err.message}`);
    });
  }, []);

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
  const [clientInitialized, setClientInitialized] = useState(true); // Always true since we'll create the client on demand
  const [participantId, setParticipantId] = useState<string | undefined>();
  const [conversationStatus, setConversationStatus] = useState<String | null>(null);
  const [isUserSpeaking, setIsUserSpeaking] = useState(false);
  const [uiOverride, setUIOverride] = useState<any | null>(null);
  const [pendingUIOverride, setPendingUIOverride] = useState<any | null>(null);
  const [selectedVoiceId, setSelectedVoiceId] = useState(defaultTtsConfig.voiceId);
  const [ttsConfig, setTtsConfig] = useState(defaultTtsConfig);

  // No need to check for client initialization since we'll create it on demand
  
  // Handle voice selection
  const handleVoiceSelect = useCallback((voiceId: string) => {
    console.log('Voice selected:', voiceId);
    setSelectedVoiceId(voiceId);
    
    // Update the TTS config with the new voice ID
    const newTtsConfig = {
      ...ttsConfig,
      voiceId
    };
    setTtsConfig(newTtsConfig);
    
    // If client is already connected, we'll need to reconnect to apply the new voice
    // This would be handled when the user clicks the Start Conversation button again
  }, [ttsConfig]);

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

  // We don't need this check anymore since we're creating the client on demand

  return (
    <div className="App">
      <h1>Sphinx Voice Bot Interface</h1>
      <h3><div id="statusText">{statusText}</div></h3>

      <div className="voice-selection-container">
        <VoiceSelector 
          onVoiceSelect={handleVoiceSelect} 
          initialVoiceId={selectedVoiceId}
          apiKey={CARTESIA_API_KEY}
        />
      </div>

      {participantId ? (
        <>
          <div style={{ marginBottom: '10px' }}>
            <strong>Participant in session</strong> 
          </div>
          <div style={{ marginBottom: '10px' }}>
            <strong>Script stage:</strong> {conversationStatus}
          </div>
        </>
      ) : (
        <div style={{ color: 'orange' }}>
          No participant active
        </div>
      )}

      <VoiceBot
        addChatMessage={addChatMessage}
        setIsWaitingForUser={setIsWaitingForUser}
        setIsUserSpeaking={setIsUserSpeaking}
        setStatusText={setStatusText}
        setParticipantId={setParticipantId}
        setUIOverride={setUIOverride}
        pendingUIOverride={pendingUIOverride}
        setPendingUIOverride={setPendingUIOverride}
        setConversationStatus={setConversationStatus}
        ttsConfig={ttsConfig}
      />
      {clientInstance ? (
        <RTVIClientProvider client={clientInstance}>
          <RTVIClientAudio />
          <ChatLog 
            messages={chatMessages} 
            isWaitingForUser={isWaitingForUser} 
            isUserSpeaking={isUserSpeaking} 
            uiOverride={uiOverride}
          />
        </RTVIClientProvider>
      ) : (
        <ChatLog 
          messages={chatMessages} 
          isWaitingForUser={isWaitingForUser} 
          isUserSpeaking={isUserSpeaking} 
          uiOverride={uiOverride}
        />
      )}
    </div>
  );
}

export default App;
