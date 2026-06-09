# ==============================================================================
# Phoenix Web Dashboard - React + Vite
# ==============================================================================

FROM node:20-alpine AS base
WORKDIR /app

# Install dependencies first for layer caching
COPY package.json ./
RUN npm install

# Copy source
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
