import type { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';

type NeedsHelpRequest = {
  help_data: {
    user: string;
    needs_help: boolean;
  };
};

type ResponseData = {
  success?: boolean;
  error?: string;
  help_needed?: boolean;
  message?: string;
};

// Resolume control server URL
const RESOLUME_CONTROL_URL = process.env.RESOLUME_CONTROL_URL || 'http://localhost:8000';

/**
 * API handler to relay help requests to the resolume_control server
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<ResponseData>
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { help_data } = req.body as NeedsHelpRequest;

    if (!help_data || typeof help_data.user !== 'string' || typeof help_data.needs_help !== 'boolean') {
      return res.status(400).json({ error: 'Invalid request body. Missing or invalid help_data.' });
    }

    console.log('Sending needs_help request to resolume control:', help_data);

    // Send request to resolume_control server
    const response = await axios.post(
      `${RESOLUME_CONTROL_URL}/needs_help`,
      {
        user: help_data.user,
        needs_help: help_data.needs_help
      }
    );

    console.log('Resolume control needs_help response:', response.data);
    
    return res.status(200).json(response.data);
  } catch (error: any) {
    console.error('Error in needs_help API:', error);
    return res.status(500).json({ 
      error: error.response?.data?.detail || error.message || 'Unknown error' 
    });
  }
} 