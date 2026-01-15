# Optional Private S3 / Cloudflare R2 Vault (Opt-in)

Default behavior: local-only. No cloud activity.

If you enable cloud for private use, the backend uses S3-compatible APIs:
- AWS S3
- Cloudflare R2
- other S3-compatible providers

Required environment variables (ONLY when enable_cloud=true):
- S3_ENDPOINT_URL
- S3_ACCESS_KEY_ID
- S3_SECRET_ACCESS_KEY
- S3_BUCKET
- S3_REGION (optional)
