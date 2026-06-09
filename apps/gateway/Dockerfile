# ==============================================================================
# Phoenix Gateway - Go Fiber API
# ==============================================================================

# Build stage
FROM golang:1.22-alpine AS builder

WORKDIR /build

# Install dependencies (we use a cache mount for module downloads)
RUN apk add --no-cache git

COPY go.mod go.sum* ./
RUN go mod download || true

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o gateway ./cmd/server

# Runtime stage
FROM alpine:3.20

RUN apk add --no-cache ca-certificates curl
WORKDIR /app

COPY --from=builder /build/gateway /app/gateway

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["/app/gateway"]
