# Developer Setup Guide

Step-by-step guide for setting up the RAG Transcript System on a new machine (optimized for MacBook with Apple Silicon).

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Clone the Repository](#clone-the-repository)
3. [Backend Setup](#backend-setup)
4. [Frontend Setup](#frontend-setup)
5. [Verify Installation](#verify-installation)
6. [Optional: Local LLM with Ollama](#optional-local-llm-with-ollama)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### 1. Install Homebrew (Package Manager)

Open Terminal and run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

After installation, follow the on-screen instructions to add Homebrew to your PATH. Typically:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### 2. Install Git

```bash
brew install git
```

Verify installation:

```bash
git --version
# Should output: git version 2.x.x
```

### 3. Install Docker Desktop for Mac

Download and install Docker Desktop from: https://www.docker.com/products/docker-desktop/

**Important for Apple Silicon (M1/M2/M3/M4 and later):**
- Download the "Apple Silicon" version (not Intel)
- After installation, open Docker Desktop and wait for it to start
- Go to Settings → Resources → Advanced and allocate at least:
  - **CPUs**: 4+
  - **Memory**: 8GB+ (16GB recommended for Whisper transcription)
  - **Swap**: 2GB+
  - **Disk**: 60GB+

Verify Docker is running:

```bash
docker --version
# Should output: Docker version 24.x.x or higher

docker compose version
# Should output: Docker Compose version v2.x.x
```

### 4. Install Node.js (v18 or later)

We recommend using `nvm` (Node Version Manager) for easier version management:

```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Restart terminal or run:
source ~/.zshrc

# Install Node.js 18 LTS
nvm install 18
nvm use 18
nvm alias default 18
```

Verify installation:

```bash
node --version
# Should output: v18.x.x or higher

npm --version
# Should output: 9.x.x or higher
```

---

## Clone the Repository

```bash
# Navigate to your projects directory
cd ~/Projects  # or wherever you keep your code

# Clone the repository (replace with your fork URL if applicable)
git clone https://github.com/simoncht/rag-transcript.git

# Enter the project directory
cd rag-transcript
```

---

## Backend Setup

The backend uses Docker Compose to run 6 containers: PostgreSQL, Redis, Qdrant, FastAPI app, Celery worker, and Celery beat.

### 1. Create Storage Directory

```bash
# Create local storage directories
mkdir -p storage/audio storage/transcripts
```

### 2. Set Up Environment Variables

```bash
# Copy the example environment file
cp backend/.env.example backend/.env
```

Edit `backend/.env` if needed (the defaults work for local development). Key settings:
- `LLM_PROVIDER`: Set to `ollama` for local LLM or `openai`/`anthropic` for cloud
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`: Required if using cloud LLM providers

### 3. Start Docker Services

```bash
# Build and start all containers (first run takes 5-10 minutes)
docker compose up -d

# Watch the logs to monitor startup
docker compose logs -f
# Press Ctrl+C to exit logs (containers keep running)
```

### 4. Run Database Migrations

```bash
# Apply database migrations
docker compose exec app alembic upgrade head
```

### 5. Verify Backend is Running

```bash
# Check container status (all 6 should be running)
docker compose ps

# Test the health endpoint
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

You can also visit the API documentation at: http://localhost:8000/docs

---

## Frontend Setup

### 1. Install Dependencies

```bash
# Navigate to frontend directory
cd frontend

# Install npm packages
npm install
```

### 2. Set Up Environment Variables

```bash
# Create local environment file
cat > .env.local << EOF
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_V1_PREFIX=/api/v1
EOF
```

### 3. Start Development Server

```bash
npm run dev
```

The frontend will be available at: http://localhost:3000

---

## Verify Installation

### Quick Health Check

```bash
# Backend API
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# Check all Docker containers
docker compose ps
# All 6 containers should show "running"

# Frontend (in browser)
# Visit http://localhost:3000
```

### Test Video Ingestion

1. Open http://localhost:3000 in your browser
2. Navigate to Videos page
3. Click "Ingest Video" and enter a YouTube URL
4. Watch the status progress from "pending" → "downloading" → "transcribing" → "completed"

---

## Optional: Local LLM with Ollama

For RAG chat functionality, you need an LLM. Ollama provides free local LLM inference.

### 1. Install Ollama

```bash
# Download and install from https://ollama.ai
# Or use Homebrew:
brew install ollama
```

### 2. Start Ollama

```bash
ollama serve
```

### 3. Pull a Model

```bash
# Pull a model (llama2 is a good starting point)
ollama pull llama2

# Or for better quality (requires more RAM):
ollama pull llama3
```

### 4. Configure the Backend

Edit `backend/.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama2
```

Restart the app container:

```bash
docker compose restart app worker
```

---

## Troubleshooting

### Apple Silicon (M1/M2/M3/M4 and later) Specific Issues

#### Docker Performance
If containers are slow or unresponsive:
1. Open Docker Desktop → Settings → Resources
2. Increase Memory to 16GB or more
3. Enable "Use Virtualization Framework" under General
4. Enable "Use Rosetta for x86/amd64 emulation" if available

#### Port Already in Use
```bash
# Find what's using a port (e.g., 8000)
lsof -i :8000

# Kill the process if needed
kill -9 <PID>
```

#### Container Build Failures
If `docker compose up -d` fails:
```bash
# Clean rebuild
docker compose down -v
docker system prune -af
docker compose build --no-cache
docker compose up -d
```

### Common Issues

#### "Cannot connect to Docker daemon"
- Ensure Docker Desktop is running (check the whale icon in menu bar)

#### Database Connection Errors
```bash
# Check if PostgreSQL is healthy
docker compose ps postgres
docker compose logs postgres

# Restart database
docker compose restart postgres
```

#### Frontend Can't Connect to Backend
- Ensure backend is running: `curl http://localhost:8000/health`
- Check CORS settings in `backend/.env` include `http://localhost:3000`
- Try accessing the API directly: http://localhost:8000/docs

#### Whisper Transcription Fails or is Slow
- Whisper requires significant memory; ensure Docker has 8GB+ allocated
- For faster transcription, the `tiny` or `base` model is recommended for Apple Silicon
- Edit `backend/.env`: `WHISPER_MODEL=tiny`

#### HuggingFace Model Download Issues
If models fail to download:
```bash
# Check if the cache directory exists
ls -la hf_cache/

# Restart with fresh cache
docker compose down
rm -rf hf_cache
docker compose up -d
```

### Useful Commands

```bash
# View logs for specific service
docker compose logs -f app
docker compose logs -f worker

# Restart a specific service
docker compose restart app

# Stop all services
docker compose down

# Stop and remove all data (fresh start)
docker compose down -v

# Check resource usage
docker stats
```

---

## Next Steps

After setup is complete:

1. **Explore the API**: Visit http://localhost:8000/docs for interactive API documentation
2. **Ingest a video**: Add a YouTube URL through the Videos page
3. **Start a conversation**: Create a chat with your ingested videos
4. **Read the docs**:
   - [README.md](./README.md) - Architecture overview
   - [RESUME.md](./RESUME.md) - Current status and quick commands
   - [AGENTS.md](./AGENTS.md) - Development guidelines

---

## Getting Help

If you encounter issues not covered here:

1. Check the existing documentation files in the repository
2. Search for similar issues in the repository
3. Ask a team member or open a discussion

Happy coding! 🚀
