import React, { useState, useRef, useEffect, useCallback } from 'react';
import './App.css';
import * as protobuf from 'protobufjs';
import ChatLog, { ChatMessage, MessageType } from './ChatLog';

// Constants for audio processing
const SAMPLE_RATE = 16000;
const NUM_CHANNELS = 1;
const WEBSOCKET_URL = 'ws://localhost:8765'; // Adjust if your server is elsewhere
const PROTO_PATH = '/frames.proto'; // Assuming frames.proto is in the public folder

// Ensure TypeScript recognizes webkitAudioContext
declare global {
  interface Window {
    webkitAudioContext: typeof AudioContext;
  }
}

// Interface for our protobuf Frame type
interface AudioRawFrame {
  id?: number;
  name?: string;
  audio: Uint8Array | number[];
  sampleRate: number;  // Must use camelCase to match protobuf expectations
  numChannels: number; // Must use camelCase to match protobuf expectations
  pts?: number;
}

// Interface for Pipecat TextFrame type
interface TextFrame {
  id?: number;
  name?: string;
  text: string;
}

// Utility function to convert audio format from Float32 to S16PCM
function convertFloat32ToS16PCM(float32Array: Float32Array): Int16Array {
  const int16Array = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const clampedValue = Math.max(-1, Math.min(1, float32Array[i]));
    int16Array[i] = clampedValue < 0 ? clampedValue * 32768 : clampedValue * 32767;
  }
  return int16Array;
}

function App() {
  // State variables
  const [isAudioStarted, setIsAudioStarted] = useState(false);
  const [statusText, setStatusText] = useState('Loading Protobuf definition...');
  const [isProtoLoaded, setIsProtoLoaded] = useState(false);
  const [isWaitingForUser, setIsWaitingForUser] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  
  // Refs for persistent values across renders
  const ws = useRef<WebSocket | null>(null);
  const audioContext = useRef<AudioContext | null>(null);
  const microphoneStream = useRef<MediaStream | null>(null);
  const scriptProcessor = useRef<ScriptProcessorNode | null>(null);
  const mediaStreamSource = useRef<MediaStreamAudioSourceNode | null>(null);
  const FrameType = useRef<protobuf.Type | null>(null);
  
  // Audio playback timing refs
  const playTime = useRef<number>(0);
  const lastMessageTime = useRef<number>(0);
  // Constant for playback timing
  const PLAY_TIME_RESET_THRESHOLD_MS = 1.0;
  
  // Add a chat message to the log
  const addChatMessage = useCallback((text: string, type: MessageType) => {
    const newMessage: ChatMessage = {
      id: Date.now().toString(),
      text,
      type,
      timestamp: new Date()
    };
    
    setChatMessages(prevMessages => [...prevMessages, newMessage]);
  }, []);

  // Load the Protobuf definition from the public folder
  useEffect(() => {
    protobuf.load(PROTO_PATH)
      .then(root => {
        try {
          // Look up the Frame type in the proto definition
          FrameType.current = root.lookupType('pipecat.Frame');
          console.log('Protobuf Frame definition loaded successfully');
          setStatusText('Ready! Click Start Audio.');
          setIsProtoLoaded(true);
        } catch (error) {
          console.error('Failed to look up Frame type in proto definition:', error);
          setStatusText('Error loading Protobuf definition. Check console.');
        }
      })
      .catch(error => {
        console.error('Failed to load proto file:', error);
        setStatusText('Error loading frames.proto file. Is it in the public folder?');
      });
  }, []);

  // Function to play audio from the received Protobuf message
  const playAudioFromProto = useCallback((arrayBuffer: ArrayBuffer) => {
    if (!FrameType.current || !audioContext.current) {
      console.warn('Cannot play audio: FrameType or audioContext is null');
      return false;
    }
    
    try {
      // Decode the protobuf message
      const parsedFrame = FrameType.current.decode(new Uint8Array(arrayBuffer));
      const audioData = (parsedFrame as any).audio;
      
      if (!audioData) {
        console.log('Received non-audio frame');
        return false;
      }
      
      console.log(`Audio data received: ${audioData.sampleRate}Hz, ${audioData.numChannels} channels`);
      
      // Reset play time if it's been a while since we played anything
      const diffTime = audioContext.current.currentTime - lastMessageTime.current;
      if (playTime.current === 0 || diffTime > PLAY_TIME_RESET_THRESHOLD_MS) {
        playTime.current = audioContext.current.currentTime;
      }
      lastMessageTime.current = audioContext.current.currentTime;
      
      // Match the working implementation in simplehtml/index.html
      // Get the audio data from the frame and ensure it's typed correctly
      const audioVector = Array.from(audioData.audio as Uint8Array | number[]);
      const audioArray = new Uint8Array(audioVector as number[]);
      
      // Use decodeAudioData for better compatibility
      try {
        audioContext.current.decodeAudioData(
          audioArray.buffer, 
          (buffer) => {
            // Create and play the audio
            const source = new AudioBufferSourceNode(audioContext.current!);
            source.buffer = buffer;
            source.start(playTime.current);
            source.connect(audioContext.current!.destination);
            
            // Update playback timing
            playTime.current += buffer.duration;
          },
          (error) => {
            console.error('Error decoding audio data:', error);
          }
        );
      } catch (error) {
        console.error('Exception in decodeAudioData:', error);
        
        // Fallback if decodeAudioData fails
        console.log('Trying fallback audio playback method...');
        
        try {
          // Ensure the buffer length is even for Int16Array
          let pcmData: Uint8Array;
          if (Array.isArray(audioData.audio)) {
            pcmData = new Uint8Array(audioData.audio as number[]);
          } else if (audioData.audio instanceof Uint8Array) {
            pcmData = audioData.audio;
          } else if (audioData.audio instanceof ArrayBuffer) {
            pcmData = new Uint8Array(audioData.audio);
          } else {
            throw new Error('Unexpected audio data format: ' + typeof audioData.audio);
          }
          
          // Ensure even length
          const paddedLength = pcmData.length % 2 === 0 ? pcmData.length : pcmData.length + 1;
          const paddedBuffer = new Uint8Array(paddedLength);
          paddedBuffer.set(pcmData);
          
          // Convert to Int16Array and then to Float32Array
          const audioData16Bit = new Int16Array(paddedBuffer.buffer);
          const floatArray = new Float32Array(audioData16Bit.length);
          
          for (let i = 0; i < audioData16Bit.length; i++) {
            floatArray[i] = audioData16Bit[i] / 32768.0;
          }
          
          // Create buffer and play
          const buffer = audioContext.current!.createBuffer(
            audioData.numChannels, 
            floatArray.length, 
            audioData.sampleRate
          );
          
          const channelData = buffer.getChannelData(0);
          channelData.set(floatArray);
          
          const source = audioContext.current!.createBufferSource();
          source.buffer = buffer;
          source.connect(audioContext.current!.destination);
          source.start(playTime.current);
          
          playTime.current += buffer.duration;
        } catch (fallbackError) {
          console.error('Fallback audio playback also failed:', fallbackError);
          return false;
        }
      }
      
      return true;
    } catch (error) {
      console.error('Error processing audio message:', error);
      return false;
    }
  }, [PLAY_TIME_RESET_THRESHOLD_MS]);
  
  // Function to handle incoming WebSocket messages
  const handleWebSocketMessage = useCallback((event: MessageEvent) => {
    if (!(event.data instanceof ArrayBuffer)) {
      console.warn('Received non-ArrayBuffer message:', event.data);
      return;
    }
    
    console.log('Received WebSocket message, size:', event.data.byteLength, 'bytes');
    
    if (!FrameType.current) {
      console.warn('FrameType not loaded yet');
      return;
    }
    
    try {
      // Decode the protobuf message
      const parsedFrame = FrameType.current.decode(new Uint8Array(event.data));
      const frameData = parsedFrame.toJSON() as any;

      console.log('Received frame:', frameData);
      
      if (frameData.text) {
        // Handle text frame - these are guide responses
        console.log('Received text frame:', frameData.text);
        addChatMessage(frameData.text.text, 'guide');
        
        // The guide has responded, we're now waiting for user
        setIsWaitingForUser(true);
      } 
      else if (frameData.transcription) {
        // Handle transcription frame - this is what the user said
        console.log('Received transcription:', frameData.transcription);
        addChatMessage(frameData.transcription.text, 'user');
        
        // User has spoken, no longer waiting for them
        setIsWaitingForUser(false);
      } 
      else if (frameData.audio) {
        // Handle audio frame - play the audio
        console.log('Received audio frame');
        
        if (isAudioStarted) {
          playAudioFromProto(event.data);
        }
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }, [isAudioStarted, playAudioFromProto, addChatMessage]);
  
  // Function to clean up audio resources
  const cleanupAudio = useCallback(() => {
    console.log('Cleaning up audio resources...');
    
    // Reset audio playback timing
    playTime.current = 0;
    lastMessageTime.current = 0;
    
    // Stop microphone stream tracks
    if (microphoneStream.current) {
      microphoneStream.current.getTracks().forEach((track: MediaStreamTrack) => track.stop());
      microphoneStream.current = null;
    }
    
    // Disconnect audio processors
    if (scriptProcessor.current) {
      scriptProcessor.current.disconnect();
      if (scriptProcessor.current.onaudioprocess) {
        scriptProcessor.current.onaudioprocess = null;
      }
      scriptProcessor.current = null;
    }
    
    if (mediaStreamSource.current) {
      mediaStreamSource.current.disconnect();
      mediaStreamSource.current = null;
    }
    
    // Close AudioContext
    if (audioContext.current && audioContext.current.state !== 'closed') {
      audioContext.current.close().catch((err: Error) => console.error('Error closing AudioContext:', err));
      audioContext.current = null;
    }
    
    // Close WebSocket
    if (ws.current) {
      if (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING) {
        ws.current.close();
      }
      ws.current = null;
    }
    
    setIsAudioStarted(false);
    setStatusText('Audio stopped. Click Start Audio to begin again.');
  }, []);

  // Effect to handle audio capture and WebSocket communication
  useEffect(() => {
    // Only run this effect when audio is started and Protobuf is loaded
    if (!isAudioStarted || !isProtoLoaded || !FrameType.current) {
      return;
    }
    
    // Start function to initialize WebSocket, AudioContext and microphone capture
    const startAudioCapture = async () => {
      setStatusText('Initializing audio...');
      
      try {
        // 1. Create AudioContext
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioContext.current = new AudioContextClass({
          latencyHint: 'interactive',
          sampleRate: SAMPLE_RATE
        });
        
        // 2. Initialize WebSocket
        setStatusText('Connecting to WebSocket...');
        ws.current = new WebSocket(WEBSOCKET_URL);
        ws.current.binaryType = 'arraybuffer';
        
        // Set up WebSocket event handlers
        ws.current.onopen = async () => {
          console.log('WebSocket connection established');
          setStatusText('WebSocket connected. Accessing microphone...');
          
          // Add system message when connection is established
          addChatMessage('Connected to the Sphinx Voice Bot server', 'system');
          
          try {
            // 3. Access Microphone
            const stream = await navigator.mediaDevices.getUserMedia({
              audio: {
                sampleRate: SAMPLE_RATE,
                channelCount: NUM_CHANNELS,
                autoGainControl: true,
                echoCancellation: true,
                noiseSuppression: true,
              }
            });
            
            console.log('Microphone access granted');
            setStatusText('Microphone active. Streaming audio...');
            microphoneStream.current = stream;
            
            // Safety check
            if (!audioContext.current) {
              throw new Error('AudioContext became null');
            }
            
            // 4. Setup Audio Processing
            // Use a smaller buffer size (512) like the working implementation
            // This gives us faster processing and better real-time performance
            const bufferSize = 512; // Match simplehtml for better responsiveness
            scriptProcessor.current = audioContext.current.createScriptProcessor(bufferSize, NUM_CHANNELS, NUM_CHANNELS);
            mediaStreamSource.current = audioContext.current.createMediaStreamSource(stream);
            
            // Connect the mic to the processor
            mediaStreamSource.current.connect(scriptProcessor.current);
            
            // Connect directly to destination like the working implementation
            // This ensures audio processing happens even if we're not playing anything
            scriptProcessor.current.connect(audioContext.current.destination);
            
            // Set up audio processing handler
            scriptProcessor.current.onaudioprocess = (event: AudioProcessingEvent) => {
              // Skip if WebSocket isn't open or FrameType doesn't exist
              if (ws.current?.readyState !== WebSocket.OPEN || !FrameType.current) return;
              
              try {
                // Get audio data from microphone
                const audioData = event.inputBuffer.getChannelData(0);
                
                // Convert to PCM format
                const pcmS16Array = convertFloat32ToS16PCM(audioData);
                
                // Create byte array from samples
                const pcmByteArray = new Uint8Array(pcmS16Array.buffer);
                
                // Create a Protobuf Frame message with AudioRawFrame inside
                const framePayload = {
                  audio: {
                    audio: Array.from(pcmByteArray), // Convert to regular array to avoid buffer ownership issues
                    sampleRate: SAMPLE_RATE,      // Use camelCase to match protobuf field names
                    numChannels: NUM_CHANNELS     // Use camelCase to match protobuf field names
                  }
                };
                
                // Create and encode the frame using protobuf
                const frame = FrameType.current.create(framePayload);
                const encodedFrame = FrameType.current.encode(frame).finish();
                
                // Send the encoded protobuf message
                ws.current.send(encodedFrame);
              } catch (error) {
                console.error('Error in audio processing:', error);
              }
            };
          } catch (micError: unknown) {
            console.error('Error accessing microphone:', micError);
            setStatusText(`Microphone access error: ${micError instanceof Error ? micError.message : 'Unknown error'}`);
            cleanupAudio();
          }
        };
        
        ws.current.onmessage = handleWebSocketMessage;
        
        ws.current.onclose = (event) => {
          console.log(`WebSocket connection closed: ${event.reason || 'Unknown reason'}`);
          setStatusText('WebSocket connection closed. Click Start Audio to reconnect.');
          addChatMessage(`Connection closed: ${event.reason || 'Unknown reason'}`, 'system');
          setIsWaitingForUser(false);
          cleanupAudio();
        };
        
        ws.current.onerror = (event) => {
          console.error('WebSocket error:', event);
          setStatusText('WebSocket error occurred. Check console for details.');
          addChatMessage('Connection error occurred', 'system');
          setIsWaitingForUser(false);
          cleanupAudio();
        };
        
      } catch (error: unknown) {
        console.error('Error initializing audio:', error);
        setStatusText(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
        cleanupAudio();
      }
    };
    
    startAudioCapture();
    
    // Cleanup when component unmounts or isAudioStarted becomes false
    return () => {
      cleanupAudio();
    };
  }, [isAudioStarted, isProtoLoaded, handleWebSocketMessage, cleanupAudio]);



  // Handle Start Audio button click
  const handleStartAudio = () => {
    console.log('Start Audio clicked');
    
    if (!isProtoLoaded) {
      setStatusText('Protobuf definition not loaded yet. Please wait.');
      return;
    }
    
    // Resume context on user interaction if it exists (important for browser policy)
    if (audioContext.current && audioContext.current.state === 'suspended') {
      audioContext.current.resume()
        .then(() => {
          console.log('AudioContext resumed on user interaction');
          setIsAudioStarted(true);
        })
        .catch((err: Error) => console.error('Failed to resume AudioContext:', err));
    } else {
      setIsAudioStarted(true); // Triggers the useEffect hook
    }
  };

  // Handle Stop Audio button click
  const handleStopAudio = () => {
    console.log('Stop Audio clicked');
    cleanupAudio();
  };

  return (
    <div className="App">
      <h1>Sphinx Voice Bot Interface</h1>
      <h3><div id="statusText">{statusText}</div></h3>
      <div className="controls">
        <button
          id="startAudioBtn"
          onClick={handleStartAudio}
          disabled={isAudioStarted || !isProtoLoaded}
        >
          Start Audio
        </button>
        <button
          id="stopAudioBtn"
          onClick={handleStopAudio}
          disabled={!isAudioStarted}
        >
          Stop Audio
        </button>
      </div>
      
      {/* Chat Log Component */}
      {isProtoLoaded && (
        <ChatLog 
          messages={chatMessages} 
          isWaitingForUser={isWaitingForUser} 
        />
      )}
    </div>
  );
}

export default App;
