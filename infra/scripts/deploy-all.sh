#!/usr/bin/env bash
# ==============================================================================
# Phoenix - Deploy all services to Google Cloud Run
# ==============================================================================

set -euo pipefail

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${GCP_REGION:=us-central1}"

REGISTRY="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/phoenix"
SA_EMAIL="phoenix-runtime@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
TAG="$(date +%Y%m%d-%H%M%S)"

CYAN='\033[36m'
GREEN='\033[32m'
RESET='\033[0m'

build_and_push() {
  local name="$1"
  local context="$2"
  echo -e "${CYAN}Building ${name}...${RESET}"
  docker build -t "${REGISTRY}/${name}:${TAG}" -t "${REGISTRY}/${name}:latest" "${context}"
  docker push "${REGISTRY}/${name}:${TAG}"
  docker push "${REGISTRY}/${name}:latest"
}

deploy_service() {
  local name="$1"
  local port="$2"
  shift 2
  echo -e "${CYAN}Deploying ${name} to Cloud Run...${RESET}"
  gcloud run deploy "${name}" \
    --image="${REGISTRY}/${name}:${TAG}" \
    --region="${GCP_REGION}" \
    --platform=managed \
    --port="${port}" \
    --service-account="${SA_EMAIL}" \
    --allow-unauthenticated \
    --quiet \
    "$@"
}

# 1. Parser (Rust) - internal only
build_and_push "phoenix-parser" "./apps/parser"
deploy_service "phoenix-parser" 8001 \
  --no-allow-unauthenticated \
  --set-env-vars="PARSER_PORT=8001"

PARSER_URL=$(gcloud run services describe phoenix-parser \
  --region="${GCP_REGION}" --format='value(status.url)')

# 2. Agent (Python ADK)
build_and_push "phoenix-agent" "./apps/agent"
deploy_service "phoenix-agent" 8000 \
  --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID},GCP_REGION=${GCP_REGION},PARSER_URL=${PARSER_URL},GITLAB_BASE_URL=${GITLAB_BASE_URL:-https://gitlab.com}" \
  --set-secrets="GITLAB_TOKEN=gitlab-token:latest" \
  --memory=2Gi \
  --cpu=2

AGENT_URL=$(gcloud run services describe phoenix-agent \
  --region="${GCP_REGION}" --format='value(status.url)')

# 3. Gateway (Go Fiber)
build_and_push "phoenix-gateway" "./apps/gateway"
deploy_service "phoenix-gateway" 8080 \
  --set-env-vars="AGENT_URL=${AGENT_URL},GATEWAY_PORT=8080" \
  --set-secrets="GITLAB_WEBHOOK_SECRET=gitlab-webhook-secret:latest"

GATEWAY_URL=$(gcloud run services describe phoenix-gateway \
  --region="${GCP_REGION}" --format='value(status.url)')

# 4. Web (React)
build_and_push "phoenix-web" "./apps/web"
deploy_service "phoenix-web" 5173 \
  --set-env-vars="VITE_GATEWAY_URL=${GATEWAY_URL}"

WEB_URL=$(gcloud run services describe phoenix-web \
  --region="${GCP_REGION}" --format='value(status.url)')

echo ""
echo -e "${GREEN}Phoenix deployed.${RESET}"
echo "  Dashboard: ${WEB_URL}"
echo "  Gateway:   ${GATEWAY_URL}"
echo "  Agent:     ${AGENT_URL}"
echo "  Parser:    ${PARSER_URL}"
echo ""
echo "Configure your GitLab webhook to POST to: ${GATEWAY_URL}/webhooks/gitlab"
