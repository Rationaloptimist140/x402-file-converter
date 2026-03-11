# x402 File Converter

A pay-per-use image conversion API built with FastAPI and the [x402 payment protocol](https://x402.org). Each conversion costs **$0.02 USDC** on Base Sepolia, paid automatically by any x402-compatible client.

## What It Does

- Accepts image uploads (PNG, JPG, JPEG, WebP)
- Converts to any of: `png`, `jpg`, `jpeg`, `webp`
- Charges **$0.02 USDC per conversion** via the x402 protocol
- Returns a `402 Payment Required` response to non-paying clients with full payment details in the `payment-required` header
- Verifies payment on-chain before processing the file

**Payment wallet:** `0x7c2e102FC6D1FbCd3E62C936d3d394Bd55C949f2`  
**Network:** Base Sepolia (`eip155:84532`) — testnet; mainnet pending x402.org facilitator support  
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
3. Railway auto-detects Python via Nixpacks and uses `railway.toml` for the start command

### 3. Set environment variables

In Railway > your service > **Variables**, add:

| Variable | Value | Notes |
|---|---|---|
| `EVM_ADDRESS` | `0x7c2e102FC6D1FbCd3E62C936d3d394Bd55C949f2` | Wallet receiving USDC |
| `FACILITATOR_URL` | `https://x402.org/facilitator` | x402 payment facilitator |
| `NETWORK` | `eip155:84532` | Base Sepolia testnet |
| `PRICE` | `$0.02` | Dollar-prefixed string |

> `PORT` is set automatically by Railway — do not override it.

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

Returns HTTP `402` with x402 payment details in the `payment-required` response header (Base64-encoded JSON):

```json
{
  "x402Version": 1,
  "accepts": [
    {
      "scheme": "exact",
      "network": "eip155:84532",
      "maxAmountRequired": "20000",
      "resource": "https://your-service.up.railway.app/convert",
      "description": "Convert image format ($0.02 USDC)",
      "mimeType": "image/*",
      "payTo": "0x7c2e102FC6D1FbCd3E62C936d3d394Bd55C949f2",
      "maxTimeoutSeconds": 300,
      "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
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
# Edit .env and set EVM_ADDRESS to your wallet
uvicorn main:app --reload
# Docs at http://localhost:8000/docs
```

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | None | Service info |
| GET | `/health` | None | Health check |
| POST | `/convert` | x402 ($0.02) | Convert image format |

## Upload Limits

| Limit | Value |
|-------|-------|
| Max file size | 10 MB |
| Supported input formats | PNG, JPG, JPEG, WebP |
| Supported output formats | PNG, JPG, JPEG, WebP |

---

## License

MIT