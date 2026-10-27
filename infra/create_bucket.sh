#!/bin/sh
# Creates the recordings bucket in the local SeaweedFS S3 store. Run once,
# after infra/attendee.sh up -d. Reads the bucket name and keys from attendee/.env.
cd "$(dirname "$0")" || exit 1
exec ./attendee.sh exec -T attendee-app-local python -c '
import boto3
from dotenv import load_dotenv
load_dotenv("/attendee/.env")
import os
s3 = boto3.client("s3", endpoint_url="http://s3:8333")
bucket = os.environ["AWS_RECORDING_STORAGE_BUCKET_NAME"]
if bucket not in [b["Name"] for b in s3.list_buckets().get("Buckets", [])]:
    s3.create_bucket(Bucket=bucket)
print("Bucket ready:", bucket)
'
