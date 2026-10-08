# Deployment

The app is a stateless Streamlit server. Every option below serves the same code; pick by cost and how
"production-like" you want the demo to look.

| Option | Cost | Cold start | Best for |
|---|---|---|---|
| Streamlit Community Cloud | Free | Sleeps after inactivity | Quickest public demo link |
| Hugging Face Spaces (Docker) | Free (CPU basic) | Sleeps after 48 h idle | Visibility in the ML/AI community |
| Google Cloud Run | Free tier, then per request | ~5-10 s | Production-style container hosting with a custom domain |
| Render | Free web service, paid for always-on | ~30-60 s on free tier | Simple Git-based container deploys |

## Streamlit Community Cloud

1. Sign in at share.streamlit.io with GitHub.
2. **Create app** → repository `mbote-droid/CDISC-SAFETY-DASHBOARD`, branch `main`, main file `app/streamlit_app.py`.
3. Deploy. `requirements.txt` is installed automatically and the app adds `src/` to its import path.

## Hugging Face Spaces (Docker)

1. Create a new Space, SDK **Docker**, hardware **CPU basic**.
2. Push this repository to the Space, adding this block at the top of the Space's README:

   ```yaml
   ---
   title: CDISC Safety Dashboard
   sdk: docker
   app_port: 8501
   ---
   ```

## Google Cloud Run (uses the image published by CD)

```bash
gcloud run deploy cdisc-safety-dashboard \
  --image ghcr.io/mbote-droid/cdisc-safety-dashboard:latest \
  --region europe-west1 --port 8501 --memory 1Gi --allow-unauthenticated
```

If Cloud Run cannot pull from GHCR, copy the image to Artifact Registry first, or build with
`gcloud builds submit --tag <region>-docker.pkg.dev/<project>/<repo>/cdisc-safety-dashboard`.

## Render

New → Web Service → connect the repository → runtime **Docker**. Render injects `PORT`, which the image honours.

## Health check

All platforms can use `GET /_stcore/health` (returns `ok`). The Docker image runs as a non-root user and works
with a read-only root filesystem (see `docker-compose.yml`).
