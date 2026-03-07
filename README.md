# x402 File Converter

A pay-per-use image conversion API built with FastAPI and the [x402 payment protocol](https://x402.org). Each conversion costs **$0.02 USDC** on Base, paid automatically by any x402-compatible client.

## What It Does

- Accepts image uploads (PNG, JPG, JPEG, WebP, GIF, BMP, TIFF)
- Converts them to any of: `png`, `jpg`, `jpeg`, `webp`
- Charges **$0.02 USDC per conversion** via the x402 protocol
- Returns a 402 Payment Required response to non-paying clients with full payment details
- Verifies payment on-chain before processing the file

**Payment wallet:** `0x65F204B928a32806FCb364cB8d36B49b647c9f30`
**Network:** Base (base-mainnet)
**Price:** $0.02 USDC per conversion

---

## Deploy on Railway

### 1. Fork or clone this repo

```bash
git clone https://github.com/Rationaloptimist140/x402-file-converter.git
cd x402-file-converter
```

### 2. Connect to Railway

1. Go to [railway.app](https://railway.app) and create a new project
2. Choose **Deploy from GitHub repo** and select `x402-file-converter`
3. Railway auto-detects Python via Nixpacks and uses `railway.json` for the start command

### 3. Set environment variables

In Railway > your service > **Variables**, add:

| Variable | Value |
|---|---|
| `PAYMENT_WALLET_ADDRESS` | `0x65F204B928a32806FCb364cB8d36B49b647c9f30` |
| `PRICE_USDC` | `0.02` |
| `NETWORK` | `base` |
| `ENV` | `production` |

> `PORT` is set automatically by Railway - do not override it.

### 4. Deploy

Railway will install from `requirements.txt` and start the server. Your service URL will appear in the Railway dashboard.

---

## Test the /convert Endpoint

### Without payment (expect 402)

```bash
curl -X POST https://your-service.up.railway.app/convert \
  -F "file=@photo.png" \
  -F "format=webp"
```

Returns HTTP 402 with x402 payment details:

```json
{
  "x402Version": 1,
  "accepts": [
    {
      "scheme": "exact",
      "network": "base-mainnet",
      "maxAmountRequired": "20000",
      "resource": "https://your-service.up.railway.app/convert",
      "description": "Image format conversion - $0.02 USDC",
      "mimeType": "application/json",
      "payTo": "0x65F204B928a32806FCb364cB8d36B49b647c9f30",
      "maxTimeoutSeconds": 300,
      "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    }
  ]
}
```

### With an x402-compatible client (Python)

```python
import httpx
from x402.client import wrap

client = wrap(httpx.Client(), private_key="YOUR_PRIVATE_KEY")

with open("photo.png", "rb") as f:
    response = client.post(
        "https://your-service.up.railway.app/convert",
        files={"file": f},
        data={"format": "webp"},
    )

with open("photo_converted.webp", "wb") as out:
    out.write(response.content)
```

---

## Local Development

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
# Docs at http://localhost:8000/docs
```

---

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | None | Service info and pricing |
| GET | `/health` | None | Health check (used by Railway) |
| POST | `/convert` | x402 payment | Convert an image |
| GET | `/docs` | None | Swagger UI |

---

## Tech Stack

- [FastAPI](https://fastapi.tiangolo.com/) - API framework
- [Pillow](https://python-pillow.org/) - Image processing
- [x402](https://x402.org) - HTTP 402 payment protocol (USDC on Base)
- [Railway](https://railway.app) - Deployment