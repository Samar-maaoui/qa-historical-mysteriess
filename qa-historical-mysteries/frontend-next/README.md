# Frontend

Next.js app of QA Historical Mysteries. Requests to `/api/*` are rewritten to the FastAPI server (`next.config.mjs`),
so the browser only talks to one address and the session cookie is forwarded.

```
npm install
npm run dev        # http://localhost:3000   (API expected on http://127.0.0.1:8000, or set API_URL in .env.local)
npm test           # rendering and streaming checks, offline
npm run lint
```
