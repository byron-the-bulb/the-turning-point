import type { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import { CloudWatchLogsClient, PutLogEventsCommand } from '@aws-sdk/client-cloudwatch-logs';

// CloudWatch Logs configuration
const AWS_REGION = process.env.AWS_REGION || 'us-east-1';
const CLOUDWATCH_LOG_GROUP = process.env.CLOUDWATCH_LOG_GROUP || '/sphinx-voice-bot';
const CLOUDWATCH_LOG_STREAM = `api-connect-${new Date().toISOString().split('T')[0]}`;

// Create CloudWatch Logs client
let cloudWatchLogsClient: CloudWatchLogsClient | null = null;
let logSequenceToken: string | undefined;

// Initialize CloudWatch Logs client if credentials are available
if (process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY) {
  cloudWatchLogsClient = new CloudWatchLogsClient({
    region: AWS_REGION,
    credentials: {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID,
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
    }
  });
}

// Custom logger that logs to both console and CloudWatch
const logger = {
  log: async (message: string, ...args: any[]) => {
    // Original console.log
    console.log(message, ...args);
    
    // Send to CloudWatch if client is initialized
    if (cloudWatchLogsClient) {
      await sendToCloudWatch('INFO', message, args);
    }
  },
  error: async (message: string, ...args: any[]) => {
    // Original console.error
    console.error(message, ...args);
    
    // Send to CloudWatch if client is initialized
    if (cloudWatchLogsClient) {
      await sendToCloudWatch('ERROR', message, args);
    }
  }
};

// Helper function to send logs to CloudWatch
async function sendToCloudWatch(level: string, message: string, args: any[]) {
  if (!cloudWatchLogsClient) return;
  
  try {
    const timestamp = new Date().getTime();
    const logMessage = `[${level}] ${message} ${args.length > 0 ? JSON.stringify(args) : ''}`;
    
    const params = {
      logGroupName: CLOUDWATCH_LOG_GROUP,
      logStreamName: CLOUDWATCH_LOG_STREAM,
      logEvents: [
        {
          message: logMessage,
          timestamp
        }
      ],
      sequenceToken: logSequenceToken
    };
    
    const command = new PutLogEventsCommand(params);
    const response = await cloudWatchLogsClient.send(command);
    logSequenceToken = response.nextSequenceToken;
  } catch (error) {
    // If there's an error with CloudWatch, log to console but don't throw
    // This prevents logging issues from breaking the main functionality
    console.error('Error sending logs to CloudWatch:', error);
  }
}

type ResponseData = {
  room_url?: string;
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
    await logger.error('Error creating Daily room:', error);
    
    // Provide more specific error messages based on the type of error
    if (axios.isAxiosError(error)) {
      if (error.response) {
        // The request was made and the server responded with a status code outside of 2xx range
        throw new Error(`Failed to create Daily room: ${error.response.status} - ${JSON.stringify(error.response.data)}`);
      } else if (error.request) {
        // The request was made but no response was received
        throw new Error('Failed to create Daily room: No response received from Daily.co API');
      } else {
        // Something happened in setting up the request
        throw new Error(`Failed to create Daily room: ${error.message}`);
      }
    }
    
    throw new Error('Failed to create Daily room');
  }
}

/**
 * Configuration type for RunPod instances
 */
type RunPodConfig = {
  gpuTypeId: string;
  minVcpuCount: number;
  minMemoryInGb: number;
};

/**
 * Launches a RunPod instance with the Sphinx bot
 */
async function launchRunPodInstance(roomUrl: string, token: string, ttsConfig?: any): Promise<string> {
  // Array of configurations in order of preference
  const podConfigs: RunPodConfig[] = [
    {
      gpuTypeId: "NVIDIA RTX 4000 Ada Generation", // Preferred
      minVcpuCount: 8,
      minMemoryInGb: 24
    },
    {
      gpuTypeId: "NVIDIA RTX 4000 Ada Generation", 
      minVcpuCount: 4,
      minMemoryInGb: 24
    },
    {
      gpuTypeId: "NVIDIA RTX 4000 Ada Generation",
      minVcpuCount: 4,
      minMemoryInGb: 15
    },   
    {
      gpuTypeId: "NVIDIA GeForce RTX 4090",
      minVcpuCount: 4,
      minMemoryInGb: 24
    },
    {
      gpuTypeId: "NVIDIA GeForce RTX 4090",
      minVcpuCount: 4,
      minMemoryInGb: 15
    },    
    {
      gpuTypeId: "NVIDIA GeForce RTX 5080", 
      minVcpuCount: 4,
      minMemoryInGb: 24
    },
    {
      gpuTypeId: "NVIDIA GeForce RTX 4080 SUPER",
      minVcpuCount: 4,
      minMemoryInGb: 24
    },
    {
      gpuTypeId: "NVIDIA GeForce RTX 4080",
      minVcpuCount: 4,
      minMemoryInGb: 24
    },
    {
      gpuTypeId: "NVIDIA GeForce RTX 4070 Ti",
      minVcpuCount: 4, 
      minMemoryInGb: 16  // Lower memory requirement for this GPU
    },
    {
      gpuTypeId: "NVIDIA GeForce RTX 3090 Ti",
      minVcpuCount: 4,
      minMemoryInGb: 16  // Lower memory requirement for this GPU
    }
  ];
  
  // Try to launch with the first configuration in the array
  return await attemptRunPodLaunch(roomUrl, token, ttsConfig, podConfigs);
}

/**
 * Helper function that handles the RunPod launch with failover to alternative configurations
 */
async function attemptRunPodLaunch(roomUrl: string, token: string, ttsConfig: any, podConfigs: RunPodConfig[]): Promise<string> {
  try {
    if (podConfigs.length === 0) {
      throw new Error('No configurations available to try');
    }
    
    // Get API keys from environment variables
    const OPENAI_API_KEY = process.env.OPENAI_API_KEY || '';
    const ELEVENLABS_API_KEY = process.env.ELEVENLABS_API_KEY || '';
    const HUME_API_KEY = process.env.HUME_API_KEY || '';
    const CARTESIA_API_KEY = process.env.CARTESIA_API_KEY || '';
    
    // Get AWS CloudWatch configuration
    const AWS_ACCESS_KEY_ID = process.env.AWS_ACCESS_KEY_ID || '';
    const AWS_SECRET_ACCESS_KEY = process.env.AWS_SECRET_ACCESS_KEY || '';
    const AWS_REGION = process.env.AWS_REGION || 'us-east-1';
    const CLOUDWATCH_LOG_GROUP = process.env.CLOUDWATCH_LOG_GROUP || '/sphinx-voice-bot';
    
    // Get Whisper device configuration
    const SPHINX_WHISPER_DEVICE = process.env.SPHINX_WHISPER_DEVICE || 'cuda';
    
    // Unique identifier for this instance
    const IDENTIFIER = `pod-${uuidv4()}`;
    
    // Format and prepare TTS config from client request or use default
    const formattedTtsConfig = JSON.stringify({
      "tts": ttsConfig || {
        provider: 'cartesia',
        voiceId: process.env.DEFAULT_VOICE_ID || 'ec58877e-44ae-4581-9078-a04225d42bd4',
        model: process.env.DEFAULT_TTS_MODEL || 'sonic-turbo-2025-03-07',
        speed: process.env.DEFAULT_TTS_SPEED || 1.0,
        emotion: null
      }
    });
    
    const currentConfig = podConfigs[0];
    await logger.log(`Attempting to launch with configuration: GPU=${currentConfig.gpuTypeId}, vCPUs=${currentConfig.minVcpuCount}, Memory=${currentConfig.minMemoryInGb}GB`);
    await logger.log('Using TTS config:', formattedTtsConfig);
    
    // Base64 encode the config as expected by sphinx_bot.py
    const base64TtsConfig = Buffer.from(formattedTtsConfig).toString('base64');
    
    await logger.log('Template ID:', SPHINX_TEMPLATE_ID);
    
    // Escape all values to safely include them in the query string
    const escapeValue = (value: string) => value.replace(/"/g, '\\"');
    
    // Following RunPod's documentation example with direct string query
    const query = `mutation {
      podFindAndDeployOnDemand(
        input: {
          cloudType: COMMUNITY,
          templateId: "${SPHINX_TEMPLATE_ID}",
          gpuCount: 1,
          volumeInGb: 0,
          containerDiskInGb: 40,
          minVcpuCount: ${currentConfig.minVcpuCount},
          minMemoryInGb: ${currentConfig.minMemoryInGb},
          gpuTypeId: "${currentConfig.gpuTypeId}",
          name: "sphinx-bot-${IDENTIFIER}",
          env: [
            { key: "DAILY_ROOM_URL", value: "${escapeValue(roomUrl)}" },
            { key: "DAILY_TOKEN", value: "${escapeValue(token)}" },
            { key: "IDENTIFIER", value: "${IDENTIFIER}" },
            { key: "OPENAI_API_KEY", value: "${escapeValue(OPENAI_API_KEY)}" },
            { key: "ELEVENLABS_API_KEY", value: "${escapeValue(ELEVENLABS_API_KEY)}" },
            { key: "HUME_API_KEY", value: "${escapeValue(HUME_API_KEY)}" },
            { key: "CARTESIA_API_KEY", value: "${escapeValue(CARTESIA_API_KEY)}" },
            { key: "TTS_CONFIG", value: "${escapeValue(base64TtsConfig)}" },
            { key: "AWS_ACCESS_KEY_ID", value: "${escapeValue(AWS_ACCESS_KEY_ID)}" },
            { key: "AWS_SECRET_ACCESS_KEY", value: "${escapeValue(AWS_SECRET_ACCESS_KEY)}" },
            { key: "AWS_REGION", value: "${escapeValue(AWS_REGION)}" },
            { key: "CLOUDWATCH_LOG_GROUP", value: "${escapeValue(CLOUDWATCH_LOG_GROUP)}" },
            { key: "SPHINX_WHISPER_DEVICE", value: "${escapeValue(SPHINX_WHISPER_DEVICE)}" }
          ]
        }
      ) {
        id
      }
    }`;
    
    // Send the GraphQL request to RunPod using the URL parameter for API key as shown in documentation
    const runpodApiUrlWithKey = `${RUNPOD_API_URL}?api_key=${RUNPOD_API_KEY}`;
    
    // Using the exact same structure as the RunPod curl example
    const response = await axios.post(
      runpodApiUrlWithKey,
      { query },
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
    
    await logger.log('RunPod response:', JSON.stringify(response.data, null, 2));

    // Check if we received a specific error about no instances available
    if (response.data.errors && 
        response.data.errors.length > 0 && 
        response.data.errors[0].message && 
        response.data.errors[0].message.includes("no longer any instances available")) {
      
      // If we have more configurations to try
      if (podConfigs.length > 1) {
        // Remove the failed configuration from the array
        const failedConfig = podConfigs.shift();
        const nextConfig = podConfigs[0];
        await logger.log(`No instances available for GPU type: ${failedConfig?.gpuTypeId}. Trying next option: ${nextConfig.gpuTypeId} with ${nextConfig.minVcpuCount} vCPUs and ${nextConfig.minMemoryInGb}GB memory`);
        
        // Recursively call this function with the modified configurations array
        return await attemptRunPodLaunch(roomUrl, token, ttsConfig, podConfigs);
      } else {
        throw new Error('No instances available for any of the configured options');
      }
    }

    // Extract pod ID from response
    const podId = response.data.data.podFindAndDeployOnDemand.id;
    await logger.log(`RunPod instance launched successfully with configuration: GPU=${currentConfig.gpuTypeId}, vCPUs=${currentConfig.minVcpuCount}, Memory=${currentConfig.minMemoryInGb}GB`, podId);
    return podId;
  } catch (error) {
    await logger.error('Error launching RunPod instance:', error);
    // Special case for exhausting all configurations
    if (error instanceof Error && error.message === 'No instances available for any of the configured options') {
      throw error;
    }
    
    // For any other error, try the next configuration if available
    if (podConfigs.length > 1) {
      const failedConfig = podConfigs.shift();
      const nextConfig = podConfigs[0];
      await logger.log(`Failed with configuration: GPU=${failedConfig?.gpuTypeId}, vCPUs=${failedConfig?.minVcpuCount}, Memory=${failedConfig?.minMemoryInGb}GB. Trying next option: GPU=${nextConfig.gpuTypeId}, vCPUs=${nextConfig.minVcpuCount}, Memory=${nextConfig.minMemoryInGb}GB`);
      
      // Add a small delay before retrying to prevent rate limiting
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Recursively call this function with the modified configurations array
      return await attemptRunPodLaunch(roomUrl, token, ttsConfig, podConfigs);
    } else {
      throw new Error('Failed to launch RunPod instance with any of the configured options');
    }
  }
}

/**
 * API handler to create a Daily room and launch a RunPod instance
 */
// Helper function to add CORS headers to response
const setCorsHeaders = (res: NextApiResponse) => {
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Origin', '*'); // Replace with your specific origins in production
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
  res.setHeader(
    'Access-Control-Allow-Headers',
    'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version'
  );
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<ResponseData>
) {
  // Handle OPTIONS request for CORS preflight
  if (req.method === 'OPTIONS') {
    setCorsHeaders(res);
    return res.status(200).end();
  }
  
  // Set CORS headers for all responses
  setCorsHeaders(res);

  logger.log('API request received');
  // Add a timeout to ensure the request doesn't hang indefinitely
  const requestTimeout = setTimeout(async () => {
    if (!res.writableEnded) {
      await logger.error('API request timed out');
      res.status(504).json({ error: 'Request timed out' });
    }
  }, 60000); // 60 second timeout

  try {
    if (req.method !== 'POST') {
      clearTimeout(requestTimeout);
      return res.status(405).json({ error: 'Method not allowed' });
    }

    // Check if API keys are configured
    if (!RUNPOD_API_KEY || !DAILY_API_KEY) {
      clearTimeout(requestTimeout);
      return res.status(500).json({ 
        error: 'API keys not configured. Please set RUNPOD_API_KEY and DAILY_API_KEY environment variables.' 
      });
    }

    // Extract TTS configuration from request body
    const { tts } = req.body || {};
    await logger.log('Received TTS configuration:', tts);
    
    // Create Daily room with error handling
    await logger.log('Creating Daily room...');
    let roomUrl, token;
    try {
      const dailyRoom = await createDailyRoom();
      roomUrl = dailyRoom.roomUrl;
      token = dailyRoom.token;
    } catch (dailyError) {
      await logger.error('Error creating Daily room:', dailyError);
      clearTimeout(requestTimeout);
      return res.status(500).json({ 
        error: 'Failed to create Daily room. Please try again later.'
      });
    }
    
    // Launch RunPod instance with TTS config from request
    await logger.log('Launching RunPod instance...');
    try {
      await launchRunPodInstance(roomUrl, token, tts);
    } catch (runPodError: any) {
      // Check for specific errors that should be reported to the client
      if (runPodError instanceof Error && 
          runPodError.message === 'No instances available for any of the configured options') {
        await logger.error('No RunPod instances available:', runPodError);
        clearTimeout(requestTimeout);
        return res.status(503).json({ 
          error: 'No GPU instances are currently available. Please try again later.'
        });
      }
      
      await logger.error('Error launching RunPod instance:', runPodError);
      clearTimeout(requestTimeout);
      return res.status(500).json({ 
        error: 'Failed to launch instance. Please try again later.'
      });
    }

    // Clear the timeout as we've completed successfully
    clearTimeout(requestTimeout);
    
    // Return connection details to client
    return res.status(200).json({ room_url: roomUrl, token: token});
  } catch (error) {
    // This is a fallback for any unhandled errors
    await logger.error('Unhandled error in connect API:', error);
    
    // Clear the timeout
    clearTimeout(requestTimeout);
    
    // Send a meaningful error message to the client
    if (!res.writableEnded) {
      return res.status(500).json({ 
        error: 'An unexpected error occurred. Please try again later.'
      });
    }
    
    // If we've already started writing the response, we can't send another
    return;
  }
}
