"""
x402 File Converter API
Accepts image uploads, converts between PNG/JPG/JPEG/WebP formats.
Payment: $0.02 USDC per conversion via x402 protocol.
"""

import io
import os
import logging

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import Response

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.schemas import Network
from x402.server import x402ResourceServer

from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
# EVM_ADDRESS: wallet address that receives USDC payments
PAY_TO_ADDRESS  = os.getenv("EVM_ADDRESS", "0x7c2e102FC6D1FbCd3E62C936d3d394Bd55C949f2")
NETWORK: Network = os.getenv("NETWORK", "eip155:84532")   # Base Sepolia (x402.org facilitator)
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")
PRICE           = os.getenv("PRICE", "$0.02")             # e.g. "$0.02" — dollar-prefixed string

MAX_UPLOAD_BYTES = 10 * 1024 * 1024   # 10 MB hard cap per upload
SUPPORTED_FORMATS = {"jpeg", "jpg", "png", "webp"}

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="x402 File Converter",
    version="1.0.0",
    description="Convert images between PNG/JPG/WebP formats. Costs $0.02 USDC per conversion via x402.",
)

# ── x402 Middleware ───────────────────────────────────────────────────────────
facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServer(facilitator)
server.register(NETWORK, ExactEvmServerScheme())

routes = {
    "POST /convert": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to=PAY_TO_ADDRESS,
                price=PRICE,
                network=NETWORK,
            )
        ],
        mime_type="image/*",
        description=f"Convert image format ({PRICE} USDC)",
    ),
}

app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "service": "x402 File Converter",
        "version": "1.0.0",
        "payment": f"{PRICE} USDC on {NETWORK}",
        "supported_formats": sorted(SUPPORTED_FORMATS),
        "usage": "POST /convert with file and format params",
    }


@app.post("/convert")
async def convert(file: UploadFile = File(...), format: str = Form(...)):
    """
    Convert uploaded image to specified format.
    Requires x402 payment: $0.02 USDC on Base Sepolia.
    """
    fmt = format.lower().strip()
    if fmt not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{fmt}'. Choose from: {sorted(SUPPORTED_FORMATS)}",
        )

    # Enforce upload size limit
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )

    try:
        img = Image.open(io.BytesIO(contents))

        output = io.BytesIO()

        if fmt in {"jpg", "jpeg"}:
            # Flatten any transparency (RGBA, LA, P with transparency) onto white background
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                background = Image.new("RGB", img.size, (255, 255, 255))
                rgba = img.convert("RGBA")
                background.paste(rgba, mask=rgba.split()[3])  # alpha channel
                img = background
            else:
                img = img.convert("RGB")
            img.save(output, format="JPEG", quality=90)
            media_type = "image/jpeg"

        elif fmt == "png":
            img.save(output, format="PNG")
            media_type = "image/png"

        elif fmt == "webp":
            img.save(output, format="WEBP", quality=90)
            media_type = "image/webp"

        output.seek(0)
        return Response(content=output.read(), media_type=media_type)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Conversion error for file=%s format=%s: %s", file.filename, fmt, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Conversion failed. Please check the file and try again.")