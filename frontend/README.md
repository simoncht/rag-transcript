# RAG Transcript Frontend

Next.js frontend for the RAG Transcript System.

## Features

- Video management (upload YouTube URLs, view status)
- Conversation creation with video selection
- Real-time chat interface with RAG-powered responses
- Citation tracking with timestamps and relevance scores
- Mock authentication (placeholder for Phase 4)

## Tech Stack

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **TanStack Query** - Data fetching and caching
- **Zustand** - State management
- **Axios** - HTTP client
- **React Markdown** - Markdown rendering for chat responses
- **Lucide React** - Icons
- **date-fns** - Date formatting

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running on `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Run development server
npm run dev
```

The application will be available at `http://localhost:3000`.

### Build for Production

```bash
npm run build
npm start
```

## Project Structure

```
src/
├── app/                      # Next.js App Router pages
│   ├── conversations/        # Conversations list and chat
│   ├── videos/              # Video management
│   ├── login/               # Mock login page
│   ├── layout.tsx           # Root layout
│   ├── page.tsx             # Home page (redirects)
│   └── providers.tsx        # React Query provider
├── components/
│   └── layout/              # Layout components
│       └── MainLayout.tsx   # Main app layout
├── lib/
│   ├── api/                 # API client functions
│   │   ├── client.ts        # Axios instance
│   │   ├── videos.ts        # Videos API
│   │   └── conversations.ts # Conversations API
│   ├── types/               # TypeScript types
│   │   └── index.ts         # Shared types
│   └── store/               # Zustand stores
│       └── auth.ts          # Auth state
└── ...
```

## Environment Variables

Create a `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_V1_PREFIX=/api/v1
```

## Development Notes

### Mock Authentication

The current login system is a mock placeholder. It accepts any email and generates a fake token. Real authentication with JWT and OAuth will be implemented in Phase 4.

### API Integration

All API calls are centralized in `src/lib/api/`. The API client automatically:
- Adds authentication tokens to requests
- Handles 401 errors by redirecting to login
- Provides consistent error handling

### State Management

- **React Query** - Server state (videos, conversations, messages)
- **Zustand** - Client state (authentication)

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript compiler check

## Next Steps

- Implement streaming responses for chat
- Add real JWT authentication (backend required)
- Integrate OAuth providers (Google, GitHub)
- Add comprehensive testing
- Optimize performance and accessibility
