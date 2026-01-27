FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source files
COPY . .

# Build arguments for Next.js public env vars (passed from Railway)
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_API_V1_PREFIX

# Set environment variables for build
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_V1_PREFIX=$NEXT_PUBLIC_API_V1_PREFIX
ENV NEXT_TELEMETRY_DISABLED=1

# Build the application
RUN npm run build

# Expose port
EXPOSE 3000

# Production command
CMD ["npm", "run", "start"]
