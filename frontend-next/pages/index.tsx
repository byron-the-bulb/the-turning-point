import { useState, useEffect, useCallback, useRef } from 'react';
import Head from 'next/head';
import styles from '@/styles/Home.module.css';
import { RTVIClientProvider, RTVIClientAudio, useRTVIClient } from '@pipecat-ai/client-react';
import { RTVIClient, RTVIEvent } from '@pipecat-ai/client-js';
import { DailyTransport } from '@pipecat-ai/daily-transport';

// Import components
import ChatLog, { ChatMessage, MessageType } from '@/components/ChatLog';
import VoiceSelector from '@/components/VoiceSelector';
import VoiceSettingsPanel from '@/components/VoiceSettingsPanel';
import LoadingSpinner from '@/components/LoadingSpinner';
import EmotionTracker, { EmotionData } from '@/components/EmotionTracker';

// Import types
import { TTSConfig } from '@/types';

// Generate a truly unique ID for messages
function generateUniqueId() {
  return Date.now().toString() + '-' + Math.random().toString(36).substring(2, 15);
}

// Server URL constants from environment variables
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000/api';
const CARTESIA_API_KEY = process.env.NEXT_PUBLIC_CARTESIA_API_KEY || '';

// Default TTS configuration
const defaultTtsConfig: TTSConfig = {
  provider: 'cartesia',
  voiceId: 'ec58877e-44ae-4581-9078-a04225d42bd4', // Default voice ID
  model: 'sonic-2-2025-03-07',
  language: 'en',
  speed: 'slow',
  emotion: null
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
        endpoints: { connect: process.env.NEXT_PUBLIC_API_ENDPOINT || '/connect' },
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

export default function Home() {
  const [statusText, setStatusText] = useState('Ready to connect');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isWaitingForUser, setIsWaitingForUser] = useState(false);
  const [clientInitialized, setClientInitialized] = useState(true); // Always true since we'll create the client on demand
  const [participantId, setParticipantId] = useState<string | undefined>();
  const [conversationStatus, setConversationStatus] = useState<String | null>(null);
  const [isUserSpeaking, setIsUserSpeaking] = useState(false);
  const [uiOverride, setUIOverride] = useState<any | null>(null);
  const [pendingUIOverride, setPendingUIOverride] = useState<any | null>(null);
  const pendingUIOverrideRef = useRef<any | null>(null);
  const [selectedVoiceId, setSelectedVoiceId] = useState(defaultTtsConfig.voiceId);
  const [selectedSpeed, setSelectedSpeed] = useState(defaultTtsConfig.speed);
  const [selectedEmotions, setSelectedEmotions] = useState<string[] | null>(defaultTtsConfig.emotion);
  const [ttsConfig, setTtsConfig] = useState<TTSConfig>(defaultTtsConfig);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isWaitingForParticipant, setIsWaitingForParticipant] = useState(false);
  const [emotionData, setEmotionData] = useState<EmotionData | null>(null);
  const eventHandlersAttached = useRef(false);
  const initialMessageSent = useRef(false);

  // Custom setter to log all updates to pendingUIOverride
  const logSetPendingUIOverride = useCallback((newValue: any | null) => {
    setPendingUIOverride((prev: any | null) => {
      console.log('pendingUIOverride updated from:', prev, 'to:', newValue);
      pendingUIOverrideRef.current = newValue; // Update ref synchronously
      return newValue;
    });
  }, []);

  // useEffect to catch any change to pendingUIOverride, including state rebuilds
  useEffect(() => {
    console.log('pendingUIOverride changed to:', pendingUIOverride);
  }, [pendingUIOverride]);

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
  }, [ttsConfig]);

  // Handle speed selection
  const handleSpeedSelect = useCallback((speed: string) => {
    console.log('Speed selected:', speed);
    setSelectedSpeed(speed);

    // Update the TTS config with the new speed
    const newTtsConfig = {
      ...ttsConfig,
      speed
    };
    setTtsConfig(newTtsConfig);
  }, [ttsConfig]);

  // Handle emotions change
  const handleEmotionsChange = useCallback((emotions: string[] | null) => {
    console.log('Emotions changed:', emotions);
    setSelectedEmotions(emotions);

    // Update the TTS config with the new emotions
    const newTtsConfig = {
      ...ttsConfig,
      emotion: emotions
    };
    setTtsConfig(newTtsConfig);
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

  // Define event handler functions
  const setupEventHandlers = useCallback((client: RTVIClient) => {
    console.log("Setting up Pipecat event handlers");
    if (eventHandlersAttached.current) {
      return;
    }
    eventHandlersAttached.current = true;

    // Define handler functions for better cleanup
    const handleTextResponse = (text: any) => {
      console.log('Received text response:', text);
      if (text.text) {
        addChatMessage(text.text, 'guide');
      }
    };

    const handleTranscription = (transcript: any) => {
      console.log('Received transcription:', transcript);
      if (transcript.text) {
        addChatMessage(transcript.text, 'user');
        setUIOverride(null);
      }
    };

    const handleConnected = () => {
      console.log('Connected to server');
      setStatusText('Connected to server');
      setIsConnected(true);
      setIsConnecting(false);
      addChatMessage('Connected to the Sphinx Voice Bot server', 'system');
      // We're now waiting for a participant to join
      setIsWaitingForParticipant(true);
    };

    const handleDisconnected = () => {
      console.log('Disconnected from server');
      setStatusText('Disconnected from server');
      setUIOverride(null);
      setIsConnected(false);
      setIsConnecting(false);
      setIsWaitingForParticipant(false);
      addChatMessage('Disconnected from the server', 'system');
      setIsWaitingForUser(false);
    };

    const handleServerMessage = (event: any) => {
      console.log('Server message received:', event);
      if (event) {
        // It's either status or trigger or emotion
        if (event.status) {
          addChatMessage(event.status, 'system');
          setConversationStatus(event.status_context?.node || null);

          if (event.ui_override) {
            console.log('UI override received:', event.ui_override);
            logSetPendingUIOverride(event.ui_override);
          }
        } else if (event.trigger === "UIOverride") {
          console.log('UI override trigger received, pendingUIOverride:', pendingUIOverrideRef.current);
          if (pendingUIOverrideRef.current) {
            console.log('Setting UI override:', pendingUIOverrideRef.current);
            setUIOverride(pendingUIOverrideRef.current);
            logSetPendingUIOverride(null);
            setIsWaitingForUser(true);
          }
        } else if (event.emotion) {
          console.log('Emotion received:', event.emotion);
          if (event.emotion.prosody && event.emotion.prosody.predictions && event.emotion.prosody.predictions.length > 0) {
            console.log('Prosody emotion data received:', event.emotion);
            // Update the emotion data state with the prosody predictions
            setEmotionData({
              predictions: event.emotion.prosody.predictions
            });

            // Add emotions as a special message in the chat log
            if (event.emotion.prosody.predictions[0].emotions) {
              // Sort emotions by score and take top 5
              const topEmotions = [...event.emotion.prosody.predictions[0].emotions]
                .sort((a, b) => b.score - a.score)
                .slice(0, 5);

              // Format emotion message
              let emotionMessage = "Prosody emotions: ";
              topEmotions.forEach((emotion, index) => {
                emotionMessage += `${emotion.name} (${(emotion.score * 100).toFixed(1)}%)`;
                if (index < topEmotions.length - 1) {
                  emotionMessage += ", ";
                }
              });

              // Add as a special 'emotion' type message
              addChatMessage(emotionMessage, 'emotion');
            }
          }
        } else if (event.language_emotion && event.language_emotion.language) {
          console.log('Language emotion data received:', event.language_emotion);
          if (event.language_emotion.language.accumulated_emotions) {
            // Sort emotions by score and take top 5
            const topLanguageEmotions = [...event.language_emotion.language.accumulated_emotions]
              .sort((a, b) => b.score - a.score)
              .slice(0, 5);

            // Format language emotion message
            if (topLanguageEmotions.length > 0) {
              let langEmotionMessage = "Semantic emotions: ";
              topLanguageEmotions.forEach((emotion, index) => {
                langEmotionMessage += `${emotion.name} (${(emotion.score * 100).toFixed(1)}%)`;
                if (index < topLanguageEmotions.length - 1) {
                  langEmotionMessage += ", ";
                }
              });

              // Add as a special 'emotion' type message
              addChatMessage(langEmotionMessage, 'emotion');
            }
          }
        }
      }
    };

    const handleError = (error: any) => {
      console.error('Pipecat client error:', error);
      setStatusText(`Error: ${error.message || 'Unknown error'}`);
      addChatMessage(`Error: ${error.message || 'Unknown error'}`, 'system');
      setIsConnecting(false);
      setIsWaitingForParticipant(false);
    };

    const handleBotStoppedSpeaking = () => {
      console.log('Bot stopped speaking');
      if (pendingUIOverrideRef.current) {
        console.log('Setting UI override:', pendingUIOverrideRef.current);
        setUIOverride(pendingUIOverrideRef.current);
        logSetPendingUIOverride(null);
      }
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

    const handleBotConnected = (participant: any) => {
      console.log('Participant joined:', participant);
      if (participant?.id) {
        console.log('Setting participant ID:', participant.id);
        setParticipantId(participant.id);
        // Participant has joined, no longer waiting
        setIsWaitingForParticipant(false);
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

    // Attach event handlers using RTVIEvent constants
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
      console.log("Cleaning up event handlers");
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
      eventHandlersAttached.current = false;
    };
  }, [addChatMessage, logSetPendingUIOverride]);

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

    // Connect the client - this will call our /api/connect endpoint
    clientInstance.connect().catch((err: Error) => {
      console.error('Failed to connect:', err);
      setStatusText(`Connection error: ${err.message}`);
      setIsConnecting(false);

      // Clean up event handlers if connection fails
      if (cleanup) {
        cleanup();
      }

      // Clean up client
      clientInstance = null;
    });
  }, [ttsConfig, setupEventHandlers]);

  const handleStopConnection = useCallback(() => {
    if (!clientInstance) return;
    console.log('Stopping connection...');
    setStatusText('Disconnecting...');

    clientInstance.disconnect().catch((err: Error) => {
      console.error('Failed to disconnect:', err);
      setStatusText(`Disconnection error: ${err.message}`);
    });
  }, []);

  // Send welcome message on mount
  useEffect(() => {
    if (!initialMessageSent.current) {
      addChatMessage('Sphinx Voice Bot ready', 'system');
      initialMessageSent.current = true;
      console.log("Initial welcome message sent");
    }
  }, [addChatMessage]);

  return (
    <div className={styles.container}>
      <Head>
        <title>Sphinx Voice Bot</title>
        <meta name="description" content="Sphinx Voice Bot Interface" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <main className={styles.main}>
        <h1 className={styles.title}>
          Sphinx Voice Bot Interface
        </h1>
        <h3><div id="statusText">{statusText}</div></h3>

        <div className={styles.voiceSettingsContainer}>
          <div className={styles.voiceSelectionContainer}>
            <VoiceSelector
              onVoiceSelect={handleVoiceSelect}
              initialVoiceId={selectedVoiceId}
              apiKey={CARTESIA_API_KEY}
            />
          </div>

          <VoiceSettingsPanel
            selectedSpeed={selectedSpeed}
            selectedEmotions={selectedEmotions}
            onSpeedSelect={handleSpeedSelect}
            onEmotionsChange={handleEmotionsChange}
          />
        </div>

        {participantId ? (
          <>
            <div className={styles.sessionInfo}>
              <strong>Participant in session</strong>
            </div>
            <div className={styles.scriptInfo}>
              <strong>Script stage:</strong> {conversationStatus}
            </div>
          </>
        ) : (
          <div className={styles.noParticipant}>
            No participant active
          </div>
        )}

        <div className={styles.controls}>
          <button
            onClick={handleStartConnection}
            disabled={isConnected || isConnecting}
            className={styles.startButton}
          >
            {isConnecting ? 'Connecting...' : 'Start Experience'}
          </button>
          <button
            onClick={handleStopConnection}
            disabled={!isConnected}
            className={styles.stopButton}
          >
            Stop Experience
          </button>
        </div>

        {clientInstance ? (
          <RTVIClientProvider client={clientInstance}>
            <RTVIClientAudio />
            <ChatLog
              messages={chatMessages}
              isWaitingForUser={isWaitingForUser}
              isUserSpeaking={isUserSpeaking}
              uiOverride={uiOverride}
              emotionData={emotionData}
            />
          </RTVIClientProvider>
        ) : (
          <ChatLog
            messages={chatMessages}
            isWaitingForUser={isWaitingForUser}
            isUserSpeaking={isUserSpeaking}
            uiOverride={uiOverride}
            emotionData={null}
          />
        )}

        {/* 
        Emotion Tracker Component - Keeping component in project but not displaying it
        {isConnected && (
          <EmotionTracker emotionData={emotionData} />
        )}
        */}

        {(isConnecting || isWaitingForParticipant) && (
          <LoadingSpinner message="Waiting for Sphinx to join..." />
        )}
      </main>
    </div>
  );
}
