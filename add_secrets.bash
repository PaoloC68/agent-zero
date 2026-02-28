#!/bin/bash

set -euo pipefail

SECRET_ID="mbsec-e00rc2pb5nrjrjs7k7"
NAMESPACE="agent-zero"
SECRET_NAME="agents-secrets"

command -v nebius >/dev/null || { echo "Error: nebius CLI not found" >&2; exit 1; }
command -v kubectl >/dev/null || { echo "Error: kubectl not found" >&2; exit 1; }

get_secret() {
  local key="$1"
  local value
  value="$(nebius mysterybox payload get-by-key \
              --secret-id "$SECRET_ID" \
              --key "$key" \
              --format text | sed -n 's/.*string_value:"\([^"]*\)".*/\1/p')"
  if [ -z "$value" ]; then
    echo "Error: Missing or empty value for key '$key' in MysteryBox secret '$SECRET_ID'" >&2
    exit 1
  fi
  printf '%s' "$value"
}

echo "Ensuring namespace '$NAMESPACE' exists..."
kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || kubectl create namespace "$NAMESPACE"

echo "Creating secret '$SECRET_NAME' in namespace '$NAMESPACE' from MysteryBox '$SECRET_ID'..."

kubectl delete secret "$SECRET_NAME" --namespace "$NAMESPACE" --ignore-not-found

kubectl create secret generic "$SECRET_NAME" \
  --namespace "$NAMESPACE" \
  --from-literal=TELEGRAM_BOT_TOKEN="$(get_secret TELEGRAM_BOT_TOKEN)" \
  --from-literal=NEBIUS_API_KEY="$(get_secret NEBIUS_API_KEY)" \
  --from-literal=GEMINI_API_KEY="$(get_secret GEMINI_API_KEY)" \
  --from-literal=AWS_BEARER_TOKEN_BEDROCK="$(get_secret AWS_BEARER_TOKEN_BEDROCK)" \
  --from-literal=TAVILY_API_KEY="$(get_secret TAVILY_API_KEY)" \
  --from-literal=PERPLEXITY_API_KEY="$(get_secret PERPLEXITY_API_KEY)" \
  --from-literal=SKILL_SCANNER_LLM_API_KEY="$(get_secret SKILL_SCANNER_LLM_API_KEY)" \
  --from-literal=BRAVE_API_KEY="$(get_secret BRAVE_API_KEY)" \
  --from-literal=GHCR_PAT="$(get_secret GHCR_PAT)" \
  --from-literal=SKILL_SCANNER_LLM_MODEL="$(get_secret SKILL_SCANNER_LLM_MODEL)" \
  --from-literal=ANTHROPIC_API_KEY="$(get_secret ANTHROPIC_API_KEY)" \
  --from-literal=LANGSMITH_API_KEY="$(get_secret LANGSMITH_API_KEY)" \
  --from-literal=DEEPINFRA_API_KEY="$(get_secret DEEPINFRA_API_KEY)" \
  --from-literal=GITHUB_PAT="$(get_secret GITHUB_PAT)" \
  --from-literal=VIRUSTOTAL_API_KEY="$(get_secret VIRUSTOTAL_API_KEY)" \
  --from-literal=CONTEXT7_API_KEY="$(get_secret CONTEXT7_API_KEY)" \
  --from-literal=OPENAI_API_KEY="$(get_secret OPENAI_API_KEY)" \
  --from-literal=AUTH_LOGIN="$(get_secret AUTH_LOGIN)" \
  --from-literal=AUTH_PASSWORD="$(get_secret AUTH_PASSWORD)" \
  --from-literal=OPENROUTER_API_KEY="$(get_secret OPENROUTER_API_KEY)" \
  --from-literal=API_KEY_GOOGLE="$(get_secret GEMINI_API_KEY)" \
  --from-literal=API_KEY_BEDROCK="$(get_secret AWS_BEARER_TOKEN_BEDROCK)" \
  --from-literal=API_KEY_DEEPINFRA="$(get_secret DEEPINFRA_API_KEY)"

echo "Created secret '$SECRET_NAME' in namespace '$NAMESPACE'."
