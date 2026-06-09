#!/usr/bin/env bash
# ==============================================================================
# Phoenix - One time Google Cloud setup
# ==============================================================================
# Enables required APIs, creates service accounts, and provisions
# Artifact Registry. Run this once after creating your GCP project.
# ==============================================================================

set -euo pipefail

# Load .env if present
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID in your environment or .env}"
: "${GCP_REGION:=us-central1}"

CYAN='\033[36m'
GREEN='\033[32m'
RESET='\033[0m'

echo -e "${CYAN}Configuring gcloud for project: ${GCP_PROJECT_ID}${RESET}"
gcloud config set project "${GCP_PROJECT_ID}"
gcloud config set run/region "${GCP_REGION}"

echo -e "${CYAN}Enabling required APIs...${RESET}"
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  logging.googleapis.com \
  iam.googleapis.com

echo -e "${CYAN}Creating Artifact Registry repository...${RESET}"
if ! gcloud artifacts repositories describe phoenix --location="${GCP_REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create phoenix \
    --repository-format=docker \
    --location="${GCP_REGION}" \
    --description="Phoenix container images"
else
  echo "  Repository 'phoenix' already exists."
fi

echo -e "${CYAN}Configuring Docker auth for Artifact Registry...${RESET}"
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

echo -e "${CYAN}Creating service account for Phoenix...${RESET}"
SA_NAME="phoenix-runtime"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Phoenix Runtime Service Account"
else
  echo "  Service account already exists."
fi

echo -e "${CYAN}Granting required IAM roles...${RESET}"
for role in \
  "roles/aiplatform.user" \
  "roles/datastore.user" \
  "roles/secretmanager.secretAccessor" \
  "roles/logging.logWriter" \
  "roles/run.invoker"; do
  gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" \
    --condition=None \
    --quiet >/dev/null
done

echo -e "${CYAN}Initializing Firestore (Native mode)...${RESET}"
if ! gcloud firestore databases describe --database="(default)" >/dev/null 2>&1; then
  gcloud firestore databases create \
    --location="${GCP_REGION}" \
    --type=firestore-native
else
  echo "  Firestore database already exists."
fi

echo ""
echo -e "${GREEN}Phoenix is ready on Google Cloud.${RESET}"
echo "  Project:          ${GCP_PROJECT_ID}"
echo "  Region:           ${GCP_REGION}"
echo "  Service account:  ${SA_EMAIL}"
echo "  Artifact Registry: ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/phoenix"
echo ""
echo "Next: run ./infra/scripts/deploy-all.sh to deploy services."
