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

# ── Config ──────────────────────────────────────────────────────────────────────
PAY_TO_ADDRESS = os.getenv("EVM_ADDRESS", "0x7c2e102FC6D1FbCd3E62C936d3d394Bd55C949f2")
NETWORK: Network = "eip155:84532"         # Base Sepolia (testnet - x402.org facilitator)
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")
PRICE = "$0.02"

SUPPORTED_FORMATS = {"jpeg", "jpg", "png", "webp"}

# ── App ─────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="x402 File Converter",
    version="1.0.0",
    description="Convert images between PNG/JPG/WebP formats. Costs $0.02 USDC per conversion via x402.",
)

# ── x402 Middleware ─────────────────────────────────────────────────────────────
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
        description="Convert image format ($0.02 USDC)",
    ),
}

app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)

# ── Routes ──────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": "x402 File Converter",
        "version": "1.0.0",
        "payment": f"{PRICE} USDC on Base Sepolia (eip155:84532)",
        "supported_formats": sorted(SUPPORTED_FORMATS),
        "usage": "POST /convert with file + output_format",
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/convert")
async def convert_image(
    file: UploadFile = File(...),
    output_format: str = Form(...),
):
    """
    Convert an uploaded image to the specified format.
    Requires x402 payment header.
    """
    output_format = output_format.lower()
    if output_format not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{output_format}'. Use one of: {', '.join(sorted(SUPPORTED_FORMATS))}",
        )

    try:
        # Read uploaded file
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # Convert if needed (handle palette mode)
        if image.mode in ("P", "RGBA") and output_format in {"jpg", "jpeg"}:
            image = image.convert("RGB")

        # Save to bytes
        output = io.BytesIO()
        save_format = "JPEG" if output_format in {"jpg", "jpeg"} else output_format.upper()
        image.save(output, format=save_format)
        output.seek(0)

        media_type = f"image/{output_format}"
        return Response(content=output.read(), media_type=media_type)

    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")
