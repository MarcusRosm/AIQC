# Health check
curl http://localhost:8000/api/health
# Trigger a minimal run
curl -X POST http://localhost:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"diff_text": "diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x=1\n+x=2\n"}'
