# ==============================================================================
# Phoenix Parser - Rust log parser
# ==============================================================================

FROM rust:1.79-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

COPY Cargo.toml ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release && rm -rf src target/release/deps/phoenix_parser*

COPY src src
RUN cargo build --release

# Runtime
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y ca-certificates curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/target/release/phoenix-parser /usr/local/bin/phoenix-parser

EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["/usr/local/bin/phoenix-parser"]
