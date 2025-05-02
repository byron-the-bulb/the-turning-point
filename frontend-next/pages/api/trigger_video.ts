import type { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';

type TriggerVideoRequest = {
  empowered_state_data: {
    empowered_state: string;
    combined_emotions: { [key: string]: number };
    challenge?: string;
    user_name?: string;
  };
};

type ResolumeVideoRequest = {
  name: string;
  challenge_point: string;
  envi_state: string;
  emotions: { [key: string]: number };
};

type ResponseData = {
  success?: boolean;
  error?: string;
};

// Resolume control server URL
const RESOLUME_CONTROL_URL = process.env.RESOLUME_CONTROL_URL || 'http://localhost:8000';

/**
 * API handler to relay video trigger requests to the resolume_control server
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<ResponseData>
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { empowered_state_data } = req.body as TriggerVideoRequest;

    // Prepare payload for resolume_control server
    const payload: ResolumeVideoRequest = {
      name: empowered_state_data.user_name || '', // Leave empty for now as requested
      challenge_point: empowered_state_data.challenge || '',  // Not specified in requirements, leaving empty
      envi_state: empowered_state_data.empowered_state, // As specified in requirements
      emotions: empowered_state_data.combined_emotions
    };

    console.log('Sending video trigger request to resolume control:', payload);

    // Send request to resolume_control server
    const response = await axios.post(
      `${RESOLUME_CONTROL_URL}/trigger_video`,
      payload
    );

    console.log('Resolume control response:', response.data);
    
    return res.status(200).json({ success: true });
  } catch (error: any) {
    console.error('Error in trigger_video API:', error);
    return res.status(500).json({ 
      error: error.response?.data?.detail || error.message || 'Unknown error' 
    });
  }
}
