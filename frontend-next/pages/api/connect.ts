import type { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';

type ResponseData = {
  roomUrl?: string;
  token?: string;
  error?: string;
};

// RunPod GraphQL endpoint
const RUNPOD_API_URL = 'https://api.runpod.io/graphql';
const RUNPOD_API_KEY = process.env.RUNPOD_API_KEY;
const DAILY_API_KEY = process.env.DAILY_API_KEY;

// Pod template ID for the Sphinx bot
const SPHINX_TEMPLATE_ID = process.env.NEXT_PUBLIC_RUNPOD_TEMPLATE_ID;

/**
 * Creates a Daily.co room and returns the room URL and token
 */
async function createDailyRoom(): Promise<{ roomUrl: string; token: string }> {
  try {
    // Create a new Daily.co room
    const roomResponse = await axios.post(
      'https://api.daily.co/v1/rooms',
      {
        properties: {
          exp: Math.floor(Date.now() / 1000) + 3600, // Expires in 1 hour
          enable_network_ui: false,
          enable_chat: false,
          enable_knocking: false,
          enable_emoji_reactions: false,
          enable_prejoin_ui: false,
          start_audio_off: false,
          start_video_off: true,
        },
      },
      {
        headers: {
          Authorization: `Bearer ${DAILY_API_KEY}`,
          'Content-Type': 'application/json',
        },
      }
    );

    const roomName = roomResponse.data.name;
    const roomUrl = roomResponse.data.url;

    // Create a token for this room
    const tokenResponse = await axios.post(
      'https://api.daily.co/v1/meeting-tokens',
      {
        properties: {
          room_name: roomName,
          exp: Math.floor(Date.now() / 1000) + 3600, // Expires in 1 hour
          is_owner: false,
        },
      },
      {
        headers: {
          Authorization: `Bearer ${DAILY_API_KEY}`,
          'Content-Type': 'application/json',
        },
      }
    );

    return {
      roomUrl,
      token: tokenResponse.data.token,
    };
  } catch (error) {
    console.error('Error creating Daily room:', error);
    throw new Error('Failed to create Daily room');
  }
}

/**
 * Launches a RunPod instance with the Sphinx bot
 */
async function launchRunPodInstance(roomUrl: string, token: string): Promise<string> {
  try {
    // Get API keys from environment variables
    const OPENAI_API_KEY = process.env.OPENAI_API_KEY || '';
    const ELEVENLABS_API_KEY = process.env.ELEVENLABS_API_KEY || '';
    const HUME_API_KEY = process.env.HUME_API_KEY || '';
    const CARTESIA_API_KEY = process.env.CARTESIA_API_KEY || '';
    
    // Unique identifier for this instance
    const IDENTIFIER = `pod-${Date.now()}`;
    
    // Optional TTS config
    const ttsConfig = JSON.stringify({
      provider: 'cartesia',
      voiceId: process.env.DEFAULT_VOICE_ID || 'ec58877e-44ae-4581-9078-a04225d42bd4',
      emotion: null
    });
    
    // GraphQL query to create a RunPod pod
    const query = `
      mutation {
        podFindAndDeployOnDemand(
          input: {
            cloudType: SECURE,
            templateId: "${SPHINX_TEMPLATE_ID}",
            gpuCount: 1,
            volumeInGb: 0,
            containerDiskInGb: 40,
            env: [
              { key: "DAILY_ROOM_URL", value: "${roomUrl}" },
              { key: "DAILY_TOKEN", value: "${token}" },
              { key: "IDENTIFIER", value: "${IDENTIFIER}" },
              { key: "OPENAI_API_KEY", value: "${OPENAI_API_KEY}" },
              { key: "ELEVENLABS_API_KEY", value: "${ELEVENLABS_API_KEY}" },
              { key: "HUME_API_KEY", value: "${HUME_API_KEY}" },
              { key: "CARTESIA_API_KEY", value: "${CARTESIA_API_KEY}" },
              { key: "TTS_CONFIG", value: "${ttsConfig}" }
            ]
          }
        ) {
          id
          imageName
          env
          deploying
          status
        }
      }
    `;

    // Send the GraphQL request to RunPod
    const response = await axios.post(
      RUNPOD_API_URL,
      { query },
      {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${RUNPOD_API_KEY}`,
        },
      }
    );

    // Extract pod ID from response
    const podId = response.data.data.podFindAndDeployOnDemand.id;
    console.log('RunPod instance launched:', podId);
    return podId;
  } catch (error) {
    console.error('Error launching RunPod instance:', error);
    throw new Error('Failed to launch RunPod instance');
  }
}

/**
 * API handler to create a Daily room and launch a RunPod instance
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<ResponseData>
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Check if API keys are configured
    if (!RUNPOD_API_KEY || !DAILY_API_KEY) {
      return res.status(500).json({ 
        error: 'API keys not configured. Please set RUNPOD_API_KEY and DAILY_API_KEY environment variables.' 
      });
    }

    // Create Daily room
    console.log('Creating Daily room...');
    const { roomUrl, token } = await createDailyRoom();
    
    // Launch RunPod instance
    console.log('Launching RunPod instance...');
    await launchRunPodInstance(roomUrl, token);

    // Return connection details to client
    return res.status(200).json({ roomUrl, token });
  } catch (error) {
    console.error('Error in connect API:', error);
    return res.status(500).json({ 
      error: error instanceof Error ? error.message : 'An unknown error occurred' 
    });
  }
}
