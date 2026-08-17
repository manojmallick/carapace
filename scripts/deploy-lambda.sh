#!/usr/bin/env bash
# Package and deploy the carapace-writeback Lambda (Python 3.12).
# Requires: AWS credentials; CARAPACE_DB_WRITE_URL exported; an IAM role
# ARN for basic Lambda execution in CARAPACE_LAMBDA_ROLE_ARN.
set -euo pipefail
cd "$(dirname "$0")/../lambda"

FN="${CARAPACE_WRITEBACK_LAMBDA:-carapace-writeback}"
REGION="${AWS_REGION:-us-east-1}"
ROLE="${CARAPACE_LAMBDA_ROLE_ARN:?set CARAPACE_LAMBDA_ROLE_ARN}"
: "${CARAPACE_DB_WRITE_URL:?set CARAPACE_DB_WRITE_URL}"

rm -rf build && mkdir build
pip3 install --quiet --target build "psycopg[binary]>=3.1" \
  --platform manylinux2014_aarch64 --only-binary=:all: --python-version 3.12
cp writeback_handler.py build/
(cd build && zip -qr ../writeback.zip .)

if aws lambda get-function --function-name "$FN" --region "$REGION" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FN" --region "$REGION" \
    --zip-file fileb://writeback.zip >/dev/null
else
  aws lambda create-function --function-name "$FN" --region "$REGION" \
    --runtime python3.12 --architectures arm64 --timeout 30 \
    --handler writeback_handler.handler --role "$ROLE" \
    --zip-file fileb://writeback.zip >/dev/null
fi
aws lambda update-function-configuration --function-name "$FN" --region "$REGION" \
  --environment "Variables={CARAPACE_DB_WRITE_URL=$CARAPACE_DB_WRITE_URL}" >/dev/null
echo "Deployed $FN in $REGION."
