# API runtime: stateless provider, external continuity

The API runtime treats each model request as stateless. It never depends on a provider thread
id or provider-side conversation storage. OpenAI Responses is called with `store=False`; the
external ACS ledger is replayed before every turn.

## Filesystem or mounted-drive backend

```bash
python -m pip install -e ".[api]"
export OPENAI_API_KEY=...

acs --workspace ./kai-api init \
  --variant api \
  --model gpt-5-mini \
  --memory-root /mnt/gdrive/ACS/kai-api-memory \
  --name KAi

acs --workspace ./kai-api once "Что изменилось в твоих выводах?"
```

Only environment variables or the normal OpenAI client configuration should contain the API
key. `acs.json` stores model and backend settings but no credential.

## S3-compatible backend

For a headless or multi-process deployment, install the S3 extra and use the normal AWS
credential chain:

```bash
python -m pip install -e ".[api,s3]"
export AWS_PROFILE=acs-production

acs --workspace ./kai-api-s3 init \
  --variant api \
  --storage s3 \
  --s3-bucket my-private-acs-bucket \
  --s3-prefix characters/kai \
  --model gpt-5-mini
```

An endpoint URL can target MinIO or another S3-compatible service. Use private buckets,
encryption at rest, narrowly scoped IAM permissions, versioning and lifecycle rules. The
backend writes immutable event objects with a conditional create; `snapshots/latest.json` is
only an optimization.

## Provider replacement

Provider state is not canonical. To add another API provider, implement `ModelClient.generate`
and `ModelClient.reflect`, keeping reflection schema-constrained and leaving events external.
Existing memory ids and revision history then survive the provider change.

## Cost and context control

One full turn uses a response call and a compact reflection call. Retrieval defaults to eight
memories and six recent same-session turns. Change `recall_limit` in `acs.json`; do not dump the
whole ledger into every prompt. Run the pressure battery with `--limit` first when estimating
cost.
