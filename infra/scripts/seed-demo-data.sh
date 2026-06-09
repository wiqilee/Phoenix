#!/usr/bin/env bash
# ==============================================================================
# Phoenix - Seed Demo Data
# ==============================================================================
# Creates a demo GitLab project with broken CI configurations that Phoenix
# can repair, so you can record a demo video end to end.
# ==============================================================================

set -euo pipefail

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${GITLAB_TOKEN:?Set GITLAB_TOKEN}"
: "${GITLAB_BASE_URL:=https://gitlab.com}"

CYAN='\033[36m'
GREEN='\033[32m'
RESET='\033[0m'

PROJECT_NAME="phoenix-demo-$(date +%s)"

echo -e "${CYAN}Creating demo GitLab project: ${PROJECT_NAME}...${RESET}"

PROJECT_RESPONSE=$(curl -s --request POST \
  --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
  --header "Content-Type: application/json" \
  --data "{
    \"name\": \"${PROJECT_NAME}\",
    \"visibility\": \"private\",
    \"initialize_with_readme\": true
  }" \
  "${GITLAB_BASE_URL}/api/v4/projects")

PROJECT_ID=$(echo "${PROJECT_RESPONSE}" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)

if [ -z "${PROJECT_ID}" ]; then
  echo "Failed to create project. Response:"
  echo "${PROJECT_RESPONSE}"
  exit 1
fi

echo -e "${CYAN}Project created with ID: ${PROJECT_ID}${RESET}"

# Add a deliberately broken package.json + lockfile to trigger Phoenix
echo -e "${CYAN}Adding broken dependency configuration...${RESET}"

BROKEN_PACKAGE_JSON='{"name":"phoenix-demo","version":"1.0.0","dependencies":{"react":"^18.0.0","react-table":"8.20.0","react-dom":"^17.0.0"}}'

curl -s --request POST \
  --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
  --header "Content-Type: application/json" \
  --data "{
    \"branch\": \"main\",
    \"commit_message\": \"chore: introduce dependency conflict for Phoenix demo\",
    \"actions\": [
      {
        \"action\": \"create\",
        \"file_path\": \"package.json\",
        \"content\": ${BROKEN_PACKAGE_JSON@Q}
      },
      {
        \"action\": \"create\",
        \"file_path\": \".gitlab-ci.yml\",
        \"content\": \"test:\\n  image: node:20\\n  stage: test\\n  script:\\n    - npm install\\n    - npm test\\n\"
      }
    ]
  }" \
  "${GITLAB_BASE_URL}/api/v4/projects/${PROJECT_ID}/repository/commits" > /dev/null

echo ""
echo -e "${GREEN}Demo project ready.${RESET}"
echo "  Project ID: ${PROJECT_ID}"
echo "  URL: ${GITLAB_BASE_URL}/$(echo "${PROJECT_RESPONSE}" | grep -o '"path_with_namespace":"[^"]*' | cut -d'"' -f4)"
echo ""
echo "When the test pipeline runs and fails, configure the project webhook"
echo "to fire to the Phoenix gateway, and Phoenix will repair it automatically."
