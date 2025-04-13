# Sphinx Voice Bot Frontend (Next.js)

This is a Next.js 15.3 implementation of the Sphinx Voice Bot guide interface.

## Features

- Built with Next.js 15.3 and React 19
- Integrated with Pipecat SDK using Daily Transport
- API endpoints for connecting to RunPod GPU instances
- Voice selection and configuration

## Getting Started

First, install the dependencies:

```bash
npm install
# or
yarn install
```

Then, run the development server:

```bash
npm run dev
# or
yarn dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Environment Variables

Create a `.env.local` file with the following variables:

```
# API URLs
NEXT_PUBLIC_API_URL=http://localhost:3000/api
NEXT_PUBLIC_WS_URL=ws://localhost:3000

# External API keys
NEXT_PUBLIC_CARTESIA_API_KEY=your_cartesia_api_key

# For API routes (server-side)
RUNPOD_API_KEY=your_runpod_api_key
DAILY_API_KEY=your_daily_api_key
```

## Project Structure

- `pages/` - Next.js pages including API routes
- `components/` - React components
- `styles/` - CSS and styling
- `lib/` - Utility functions and API clients
- `types/` - TypeScript type definitions
- `public/` - Static assets

## API Routes (To Be Implemented)

- `/api/connect` - Creates a Daily room and launches a Sphinx bot on RunPod
- `/api/disconnect` - Stops a RunPod instance

## Next Steps

1. Migrate components from the original React application
2. Implement API endpoints
3. Update WebSocket handling for Next.js
4. Connect to RunPod for Sphinx bot instances
