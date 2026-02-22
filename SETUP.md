# Setup Guide for New Machines

This guide will walk you through setting up the RAG Transcript System on a new machine from scratch. It's designed for users who are new to GitHub and development environments.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install Required Software](#2-install-required-software)
3. [Download the Code from GitHub](#3-download-the-code-from-github)
4. [Configure Environment Variables](#4-configure-environment-variables)
5. [Start the Backend Services](#5-start-the-backend-services)
6. [Run Database Migrations](#6-run-database-migrations)
7. [Set Up the Frontend](#7-set-up-the-frontend)
8. [Verify Everything is Working](#8-verify-everything-is-working)
9. [Common Issues and Troubleshooting](#9-common-issues-and-troubleshooting)
10. [Next Steps](#10-next-steps)

---

## 1. Prerequisites

Before you begin, make sure you have the following:

- **Operating System**: Windows 10/11, macOS, or Linux
- **Internet Connection**: Required for downloading software and dependencies
- **Administrator Access**: You may need admin rights to install software
- **Disk Space**: At least 10 GB free (Docker images can be large)
- **RAM**: Minimum 8 GB recommended (16 GB preferred for running ML models)

---

## 2. Install Required Software

### 2.1 Install Git

Git is a version control system used to download (clone) the code from GitHub.

**Windows:**
1. Go to https://git-scm.com/downloads/win
2. Download the installer for Windows
3. Run the installer and use default options (keep clicking "Next")
4. Click "Install" and then "Finish"

**macOS:**
1. Open Terminal (press Cmd + Space, type "Terminal", press Enter)
2. Run: `xcode-select --install`
3. Click "Install" when prompted

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install git -y
```

**Verify Installation:**
Open a new terminal/command prompt and run:
```bash
git --version
```
You should see something like `git version 2.x.x`

---

### 2.2 Install Docker Desktop

Docker allows you to run the backend services (database, API, etc.) in containers.

**Windows:**
1. Go to https://www.docker.com/products/docker-desktop/
2. Click "Download for Windows"
3. Run the installer
4. When asked, enable "Use WSL 2 instead of Hyper-V" (recommended)
5. Complete the installation and restart your computer
6. After restart, Docker Desktop will start automatically
7. Accept the license agreement

**macOS:**
1. Go to https://www.docker.com/products/docker-desktop/
2. Click "Download for Mac"
3. Choose your chip type (Apple Silicon for M1/M2/M3, Intel for older Macs)
4. Open the downloaded `.dmg` file
5. Drag Docker to your Applications folder
6. Open Docker from Applications
7. Accept the license agreement

**Linux (Ubuntu/Debian):**
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to the docker group (so you don't need sudo)
sudo usermod -aG docker $USER

# Log out and log back in for group changes to take effect
# Or run: newgrp docker

# Install Docker Compose
sudo apt install docker-compose-plugin -y
```

**Verify Installation:**
```bash
docker --version
docker compose version
```

**Important**: Make sure Docker Desktop is running before proceeding!

---

### 2.3 Install Node.js

Node.js is required to run the frontend application.

**Windows and macOS:**
1. Go to https://nodejs.org/
2. Download the "LTS" (Long Term Support) version (recommended)
3. Run the installer and follow the prompts
4. Use default options

**Linux (Ubuntu/Debian):**
```bash
# Install Node.js 18 LTS
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y
```

**Verify Installation:**
```bash
node --version
npm --version
```
You should see versions like `v18.x.x` and `9.x.x` or higher.

---

### 2.4 Install a Code Editor (Optional but Recommended)

**Visual Studio Code (VS Code)** is a free, popular code editor.

1. Go to https://code.visualstudio.com/
2. Download and install for your operating system
3. (Optional) Install recommended extensions:
   - Python
   - Docker
   - ESLint
   - Prettier

---

## 3. Download the Code from GitHub

### 3.1 Open a Terminal

**Windows:** 
- Press `Win + R`, type `cmd`, press Enter
- Or search for "Command Prompt" or "PowerShell"

**macOS:** 
- Press `Cmd + Space`, type "Terminal", press Enter

**Linux:** 
- Press `Ctrl + Alt + T`

### 3.2 Choose Where to Save the Code

Navigate to a folder where you want to store the project. For example:

**Windows:**
```bash
cd C:\Users\YourUsername\Projects
```
If the folder doesn't exist, create it:
```bash
mkdir C:\Users\YourUsername\Projects
cd C:\Users\YourUsername\Projects
```

**macOS/Linux:**
```bash
cd ~/Projects
```
If the folder doesn't exist:
```bash
mkdir ~/Projects
cd ~/Projects
```

### 3.3 Clone the Repository

Run this command to download the code:

```bash
git clone https://github.com/simoncht/rag-transcript.git
```

This will create a folder called `rag-transcript` with all the code.

### 3.4 Enter the Project Folder

```bash
cd rag-transcript
```

---

## 4. Configure Environment Variables

Environment variables store configuration settings like database passwords and API keys.

### 4.1 Create Backend Environment File

**Windows (Command Prompt):**
```bash
copy backend\.env.example backend\.env
```

**Windows (PowerShell), macOS, Linux:**
```bash
cp backend/.env.example backend/.env
```

### 4.2 Review the Configuration (Optional)

Open `backend/.env` in a text editor. The default values work for local development. Key settings include:

- `DATABASE_URL` - PostgreSQL connection (default works with Docker)
- `REDIS_URL` - Redis connection (default works with Docker)
- `LLM_PROVIDER` - Choose `ollama` for local LLM or `openai`/`anthropic` for cloud
- `OPENAI_API_KEY` - Add your OpenAI key if using OpenAI

For local development, the defaults are fine. You can modify these later.

### 4.3 Create Frontend Environment File (Optional)

The frontend uses default settings, but you can customize them:

**Windows (Command Prompt):**
```bash
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > frontend\.env.local
echo NEXT_PUBLIC_API_V1_PREFIX=/api/v1 >> frontend\.env.local
```

**Windows (PowerShell), macOS, Linux:**
```bash
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > frontend/.env.local
echo "NEXT_PUBLIC_API_V1_PREFIX=/api/v1" >> frontend/.env.local
```

---

## 5. Start the Backend Services

The backend uses Docker to run multiple services. Make sure Docker Desktop is running!

### 5.1 Start All Services

From the project root folder (`rag-transcript`), run:

```bash
docker compose up -d
```

**What this does:**
- Downloads required Docker images (first time takes 5-15 minutes)
- Starts 6 services:
  - **postgres** - Database for storing videos, conversations, etc.
  - **redis** - Cache and task queue
  - **qdrant** - Vector database for semantic search
  - **app** - FastAPI backend server
  - **worker** - Background task processor (transcription, etc.)
  - **beat** - Scheduled task runner

### 5.2 Check Service Status

Wait about 30-60 seconds, then check if all services are running:

```bash
docker compose ps
```

You should see all 6 services with "Up" status. Example output:
```
NAME                       STATUS
rag_transcript_postgres    Up (healthy)
rag_transcript_redis       Up (healthy)
rag_transcript_qdrant      Up
rag_transcript_app         Up
rag_transcript_worker      Up
rag_transcript_beat        Up
```

### 5.3 View Logs (if needed)

If something isn't working, check the logs:

```bash
# View all logs
docker compose logs

# View specific service logs (e.g., app)
docker compose logs app

# Follow logs in real-time
docker compose logs -f app worker
```

Press `Ctrl + C` to stop following logs.

---

## 6. Run Database Migrations

Migrations set up the database tables. Run this command:

```bash
docker compose exec app alembic upgrade head
```

You should see output like:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial, initial
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, add_jobs
...
```

---

## 7. Set Up the Frontend

### 7.1 Navigate to Frontend Folder

```bash
cd frontend
```

### 7.2 Install Dependencies

```bash
npm install
```

This downloads all required JavaScript packages. Takes 1-3 minutes.

### 7.3 Start the Development Server

```bash
npm run dev
```

You should see:
```
▲ Next.js 14.x.x
- Local:        http://localhost:3000
- Ready in 2.5s
```

**Keep this terminal open!** The frontend runs as long as this terminal is active.

---

## 8. Verify Everything is Working

### 8.1 Check Backend Health

Open a new terminal (keep the frontend running) and run:

```bash
curl http://localhost:8000/health
```

**Windows users without curl:** Open your browser and go to http://localhost:8000/health

You should see:
```json
{"status":"healthy"}
```

### 8.2 View API Documentation

Open your browser and go to:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 8.3 Access the Frontend

Open your browser and go to:
- **Frontend**: http://localhost:3000

You should see the login page. Enter any email (mock authentication for development).

### 8.4 Test the Full Flow

1. Log in with any email
2. Go to "Videos" page
3. Click "Ingest Video" and paste a YouTube URL
4. Wait for processing (check status in the table)
5. Create a conversation with the processed video
6. Ask questions about the video content!

---

## 9. Common Issues and Troubleshooting

### "Docker is not running"

**Solution:** Start Docker Desktop application. Wait for it to fully start (icon stops animating).

---

### "Port already in use"

**Error:** `Bind for 0.0.0.0:8000 failed: port is already allocated`

**Solution:** Another application is using that port. Either:
1. Stop the other application, or
2. Change the port in `docker-compose.yml`

Find what's using the port:
```bash
# Windows
netstat -ano | findstr :8000

# macOS/Linux
lsof -i :8000
```

---

### "npm install fails"

**Common causes:**
1. **Network issues:** Check internet connection
2. **Permission issues:** Don't use `sudo` with npm on Linux/macOS
3. **Old Node.js:** Update to Node.js 18+

**Solution:** Delete `node_modules` and try again:
```bash
rm -rf node_modules package-lock.json
npm install
```

---

### "Cannot connect to Docker daemon"

**Linux:** Your user may not be in the docker group:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

**Windows/macOS:** Make sure Docker Desktop is running.

---

### "Database connection failed"

**Solution:** Wait for PostgreSQL to be healthy:
```bash
docker compose ps
```

If postgres shows "unhealthy", restart it:
```bash
docker compose restart postgres
# Wait 30 seconds
docker compose exec app alembic upgrade head
```

---

### "Frontend shows 'Failed to fetch' errors"

**Solution:** Backend is not running or has errors.
1. Check if backend is running: `curl http://localhost:8000/health`
2. Check backend logs: `docker compose logs app`

---

### "Out of disk space"

Docker images use significant space. Clean up unused data:
```bash
docker system prune -a
```

⚠️ This removes all unused images, containers, and volumes!

---

### "Slow performance / High CPU"

This is normal during:
- First startup (downloading models)
- Video transcription (Whisper uses CPU)

Ensure you have:
- At least 8 GB RAM
- Close unnecessary applications

---

## 10. Next Steps

### Daily Workflow

**Starting the system:**
```bash
# From project root
docker compose up -d
cd frontend && npm run dev
```

**Stopping the system:**
```bash
# Stop frontend: Press Ctrl+C in the terminal running npm run dev

# Stop backend services:
docker compose down
```

### Updating the Code

When new updates are available:
```bash
# From project root
git pull origin main

# Rebuild Docker images if there are backend changes
docker compose down
docker compose build
docker compose up -d

# Run any new migrations
docker compose exec app alembic upgrade head

# Reinstall frontend dependencies if package.json changed
cd frontend && npm install
```

### Useful Commands

```bash
# View all running containers
docker compose ps

# View logs
docker compose logs -f app worker

# Restart a specific service
docker compose restart app

# Stop all services
docker compose down

# Stop and remove all data (fresh start)
docker compose down -v

# Check API health
curl http://localhost:8000/health

# Run backend tests
docker compose exec app pytest

# Run frontend lint
cd frontend && npm run lint
```

### Documentation

- **[README.md](./README.md)** - Project overview and architecture
- **[RESUME.md](./RESUME.md)** - Current status and quick commands
- **[PROGRESS.md](./PROGRESS.md)** - Development history
- **[AGENTS.md](./AGENTS.md)** - Coding guidelines for contributors

### Getting Help

If you encounter issues:
1. Check the [Troubleshooting](#9-common-issues-and-troubleshooting) section above
2. Review Docker logs: `docker compose logs`
3. Check existing GitHub issues on the repository
4. Create a new issue with:
   - Your operating system
   - Error messages
   - Steps to reproduce

---

Happy coding! 🎉
