#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/deploy.sh
#   ./scripts/deploy.sh prod
#   ./scripts/deploy.sh prod us-east-2 my-profile

ENV="${1:-dev}"
AWS_REGION="${2:-us-east-1}"
AWS_PROFILE="${3:-terraform-lab}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[INFO] Using ENV=${ENV}, REGION=${AWS_REGION}, PROFILE=${AWS_PROFILE}"

# Expose env so Terragrunt/Terraform and AWS CLI can see them
export TG_ENV="${ENV}"
export AWS_REGION
export AWS_PROFILE

########################################
# 0) Remote backend (S3 + DynamoDB)
########################################
echo "[STEP 0] Ensuring remote state backend (S3 bucket + DynamoDB table)..."

ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}")

STATE_BUCKET="tfstate-demo-${ENV}-${ACCOUNT_ID}"
LOCK_TABLE="tfstate-locks-${ACCOUNT_ID}"

export TF_STATE_BUCKET="${STATE_BUCKET}"
export TF_STATE_TABLE="${LOCK_TABLE}"

echo "[STEP 0.1] Checking S3 bucket: ${STATE_BUCKET}"
if aws s3api head-bucket --bucket "${STATE_BUCKET}" --profile "${AWS_PROFILE}" 2>/dev/null; then
  echo "[INFO] S3 bucket exists."
else
  echo "[INFO] Creating S3 bucket..."
  if [ "${AWS_REGION}" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "${STATE_BUCKET}" \
      --region "${AWS_REGION}" \
      --profile "${AWS_PROFILE}"
  else
    aws s3api create-bucket \
      --bucket "${STATE_BUCKET}" \
      --region "${AWS_REGION}" \
      --create-bucket-configuration LocationConstraint="${AWS_REGION}" \
      --profile "${AWS_PROFILE}"
  fi
fi

echo "[STEP 0.2] Checking DynamoDB table: ${LOCK_TABLE}"
if aws dynamodb describe-table \
  --table-name "${LOCK_TABLE}" \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" >/dev/null 2>&1; then
  echo "[INFO] DynamoDB table exists."
else
  echo "[INFO] Creating DynamoDB table..."
  aws dynamodb create-table \
    --table-name "${LOCK_TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}"

  echo "[INFO] Waiting for DynamoDB table to become ACTIVE..."
  aws dynamodb wait table-exists \
    --table-name "${LOCK_TABLE}" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}"
fi

########################################
# 1) Deploy shared (ECR + KMS + IAM GitHub roles)
########################################
echo "[STEP 1] Applying terraform/live/${ENV}/shared..."

cd "${ROOT_DIR}/terraform/live/${ENV}/shared"
terragrunt init --non-interactive -- -reconfigure
terragrunt apply -auto-approve

########################################
# 2) Build & push Docker image
########################################
echo "[STEP 2] Resolving ECR repository URL..."

REPO_URL=$(terragrunt output -raw ecr_repository_url)

echo "[INFO] Using ECR repository: ${REPO_URL}"

echo "[INFO] Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" --profile "${AWS_PROFILE}" \
  | docker login --username AWS --password-stdin "$(echo "${REPO_URL}" | cut -d'/' -f1)"

echo "[INFO] Building Docker image demo-api..."
cd "${ROOT_DIR}/demo-api"

BUILD_TAG="${ENV}-$(date +%Y%m%d%H%M%S)"
echo "[INFO] Build tag: ${BUILD_TAG}"

docker build -t "${REPO_URL}:${BUILD_TAG}" .
docker push "${REPO_URL}:${BUILD_TAG}"

echo "[INFO] Resolving image digest..."
REPO_NAME="$(echo "${REPO_URL}" | cut -d'/' -f2-)"

IMAGE_DIGEST=$(aws ecr describe-images \
  --repository-name "${REPO_NAME}" \
  --image-ids imageTag="${BUILD_TAG}" \
  --query 'imageDetails[0].imageDigest' \
  --output text \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}")

echo "[INFO] Image digest = ${IMAGE_DIGEST}"
export TF_VAR_image_digest="${IMAGE_DIGEST}"

########################################
# 3) Deploy full stack
########################################
echo "[STEP 3] Applying full Terraform stack with Terragrunt..."

cd "${ROOT_DIR}/terraform/live/${ENV}"
terragrunt run --all init --non-interactive -- -reconfigure
terragrunt run --all apply --non-interactive -- -auto-approve

########################################
# 4) Fetch outputs for this ENV
########################################
echo "[STEP 4] Fetching API, ALB/TGs, scale-down Lambda/Rule and GitHub IAM role ARNs..."

# Edge: API Gateway endpoint
cd "${ROOT_DIR}/terraform/live/${ENV}/edge"
API_URL=$(terragrunt output -raw api_endpoint || echo "")

# Global: ALB listener + candidate rule + TGs
cd "${ROOT_DIR}/terraform/live/${ENV}/global"
ALB_LISTENER_ARN=$(terragrunt output -raw alb_listener_arn || echo "")
ALB_CANDIDATE_RULE_ARN=$(terragrunt output -raw alb_cantidate_rule_arn || echo "")
DEMO_BLUE_TG_ARN=$(terragrunt output -raw demo_blue_tg_arn || echo "")
DEMO_GREEN_TG_ARN=$(terragrunt output -raw demo_green_tg_arn || echo "")

# Apps/Fargate: scale-down Lambda + EventBridge rule (when you add these outputs)
cd "${ROOT_DIR}/terraform/live/${ENV}/apps/fargate"
SCALE_DOWN_LAMBDA_ARN=$(terragrunt output -raw scale_down_lambda_arn || echo "")
SCALE_DOWN_RULE_NAME=$(terragrunt output -raw scale_down_rule_name || echo "")

# Shared: IAM roles for GitHub OIDC
cd "${ROOT_DIR}/terraform/live/${ENV}/shared"
GITHUB_CI_ROLE_ARN=$(terragrunt output -raw github_role_terragrunt_ci_arn   || echo "")
GITHUB_CD_ROLE_ARN=$(terragrunt output -raw github_role_terragrunt_cd_arn   || echo "")
APP_CD_ROLE_ARN=$(terragrunt output -raw github_role_app_cd_arn             || echo "")
APP_ROLLBACK_ROLE_ARN=$(terragrunt output -raw github_role_app_rollback_arn || echo "")

########################################
# 5) Final summary (current ENV only)
########################################

echo ""
echo "============================================"
echo " Demo deployed successfully"
echo "============================================"
echo ""

if [ -n "${API_URL}" ]; then
  echo "API Gateway Base URL:"
  echo "  ${API_URL}"
  echo ""
else
  echo "[WARN] Could not read api_endpoint from edge outputs."
fi

echo "AWS / Terraform backend configuration:"
echo "  ENV (TG_ENV)      : ${ENV}"
echo "  AWS_REGION        : ${AWS_REGION}"
echo "  AWS_ACCOUNT_ID    : ${ACCOUNT_ID}"
echo "  TF_STATE_BUCKET   : ${TF_STATE_BUCKET}"
echo "  TF_STATE_TABLE    : ${TF_STATE_TABLE}"
echo ""

echo ""
echo "============================================"
echo " GitHub Actions — OIDC Role Secrets"
echo "============================================"
echo ""
echo "Add these secrets in GitHub:"
echo "  Settings → Secrets and variables → Actions → New repository secret"
echo ""

print_secret () {
  local name="$1"
  local arn="$2"

  if [ -n "${arn}" ]; then
    printf "  %-25s = %s\n" "$name" "$arn"
  else
    printf "  %-25s = [NOT FOUND]\n" "$name"
  fi
}

print_secret "AWS_ROLE_TG_CI"        "${GITHUB_CI_ROLE_ARN}"
print_secret "AWS_ROLE_TG_CD"        "${GITHUB_CD_ROLE_ARN}"
print_secret "AWS_ROLE_APP_CD"       "${APP_CD_ROLE_ARN}"
print_secret "AWS_ROLE_APP_ROLLBACK" "${APP_ROLLBACK_ROLE_ARN}"

echo ""
echo "============================================"
echo " GitHub Actions — Repository Variables (ENV=${ENV})"
echo "============================================"
echo ""

if [ "${ENV}" = "dev" ]; then
  echo "Set these Variables in GitHub:"
  echo "  Settings → Secrets and variables → Actions → Variables"
  echo ""
  echo "  ALB_LISTENER_DEV         = ${ALB_LISTENER_ARN}"
  echo "  ALB_CANDIDATE_RULE_DEV   = ${ALB_CANDIDATE_RULE_ARN}"
  echo "  TG_BLUE_DEV              = ${DEMO_BLUE_TG_ARN}"
  echo "  TG_GREEN_DEV             = ${DEMO_GREEN_TG_ARN}"
  echo "  SCALE_DOWN_RULE_NAME_DEV = ${SCALE_DOWN_RULE_NAME}"
  echo "  SCALE_DOWN_LAMBDA_DEV    = ${SCALE_DOWN_LAMBDA_ARN}"
elif [ "${ENV}" = "prod" ]; then
  echo "Set these **Variables** in GitHub:"
  echo "  Settings → Secrets and variables → Actions → Variables"
  echo ""
  echo "  ALB_LISTENER_PROD         = ${ALB_LISTENER_ARN}"
  echo "  ALB_CANDIDATE_RULE_PROD   = ${ALB_CANDIDATE_RULE_ARN}"
  echo "  TG_BLUE_PROD              = ${DEMO_BLUE_TG_ARN}"
  echo "  TG_GREEN_PROD             = ${DEMO_GREEN_TG_ARN}"
  echo "  SCALE_DOWN_RULE_NAME_PROD = ${SCALE_DOWN_RULE_NAME}"
  echo "  SCALE_DOWN_LAMBDA_PROD    = ${SCALE_DOWN_LAMBDA_ARN}"
else
  echo "[WARN] Unknown ENV=${ENV}, skipping repo variable hints."
fi

echo ""
echo "============================================"
echo " Done. Configure the secrets & variables above in GitHub."
echo "============================================"
