# Live Manuscript Q&A Proxy

This optional Worker turns the static `Ask the manuscript` panel into live RAG:

1. Load the public `data/site-data.json` snapshot.
2. Embed the reviewer question.
3. Embed or reuse the manuscript chunks.
4. Rank chunks by cosine similarity.
5. Send only the top cited chunks to a Responses-compatible language model.

Do not put provider keys, provider URLs, or model credentials in `reviewer_site/`.
Use deployment secrets and variables instead.

## Required Secrets

Set these as platform secrets:

```bash
wrangler secret put EMBEDDING_API_KEY
wrangler secret put LLM_API_KEY
```

## Required Variables

Set these as Worker variables, not in the public page:

```text
SITE_DATA_URL=https://<your-pages-site>/data/site-data.json
ALLOWED_ORIGIN=https://<your-pages-site>
EMBEDDING_ENDPOINT=<provider embedding endpoint>
EMBEDDING_MODEL=<embedding model name>
LLM_RESPONSES_ENDPOINT=<provider responses endpoint>
LLM_MODEL=<language model name>
MODEL_REASONING_EFFORT=xhigh
RAG_TOP_K=5
```

If your provider uses a base URL convention, you can set `EMBEDDING_BASE_URL`
instead of `EMBEDDING_ENDPOINT`, and `LLM_BASE_URL` instead of
`LLM_RESPONSES_ENDPOINT`.

## Frontend Connection

The GitHub Pages site should point to the Worker URL without exposing provider
credentials:

```js
window.INVDES_RAG_API_URL = "https://<your-worker>/ask";
```

For a custom domain, route `/ask` to the Worker and set:

```js
window.INVDES_RAG_API_URL = "/ask";
```

The Worker URL itself is not a secret. The provider credentials stay on the
Worker platform and are never sent to the browser.
