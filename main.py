"""
x402 File Converter API
Accepts image uploads, converts between PNG/JPG/JPEG/WebP formats.
Payment: $0.02 USDC per conversion via x402 protocol.
"""

import io
import os
import logging
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.server import x402ResourceServer

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
WALLET_ADDRESS: str = os.getenv(
    "PAYMENT_WALLET_ADDRESS",
    "0x65F204B928a32806FCB364cB8d36B49b647c9f30",
)
PRICE_USDC: str = os.getenv("PRICE_USDC", "0.02")
NETWORK = "eip155:8453"  # Base mainnet
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")
SERVICE_NAME: str = "x402 File Converter"
SERVICE_VERSION: str = "1.0.0"

SUPPORTED_FORMATS = {"png", "jpg", "jpeg", "webp"}

PIL_FORMAT_MAP: dict[str, str] = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
}

MIME_MAP: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(
    title=SERVICE_NAME,
    version=SERVICE_VERSION,
    description=(
        "Convert images between PNG, JPG, JPEG, and WebP formats. "
        f"Each conversion costs ${PRICE_USDC} USDC (paid via x402 protocol)."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# -----------------------------------------------------------------------------
# x402 Payment Middleware (v2.0.0 API)
# -----------------------------------------------------------------------------
facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServer(facilitator)
server.register(NETWORK, ExactEvmServerScheme())

routes = {
    "POST /convert": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to=WALLET_ADDRESS,
                price=f"${PRICE_USDC}",
                network=NETWORK,
            )
        ],
        mime_type="application/octet-stream",
        description="Image format conversion",
    ),
}

app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/", summary="Service info")
async def root():
    """Return metadata about this service."""
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "description": "Convert images between PNG, JPG, JPEG, and WebP formats.",
        "pricing": {
            "amount": PRICE_USDC,
            "currency": "USDC",
            "network": NETWORK,
        },
        "supported_formats": list(SUPPORTED_FORMATS),
        "endpoints": {
            "GET /": "This information",
            "POST /convert": "Convert an uploaded image to a new format",
            "GET /health": "Health check",
        },
    }


@app.get("/health", summary="Health check")
async def health():
    """Return 200 if service is alive."""
    return {"status": "ok"}


@app.post("/convert", summary="Convert image format")
async def convert_image(
    file: UploadFile = File(..., description="Image file to convert"),
    to_format: Literal["png", "jpg", "jpeg", "webp"] = Form(
        ..., description="Target format"
    ),
):
    """
    Convert an uploaded image to the desired format.
    Requires x402 payment header.
    """
    logger.info(f"Received conversion request: {file.filename} -> {to_format}")

    if to_format not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{to_format}'. Use: {SUPPORTED_FORMATS}",
        )

    try:
        image_bytes = await file.read()
        logger.info(f"Read {len(image_bytes)} bytes")
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        raise HTTPException(status_code=400, detail="Could not read uploaded file")

    try:
        image = Image.open(io.BytesIO(image_bytes))
        logger.info(f"Opened image: {image.format} {image.size} {image.mode}")
    except Exception as e:
        logger.error(f"Failed to open image: {e}")
        raise HTTPException(status_code=400, detail="Invalid image file")

    if to_format in {"jpg", "jpeg"} and image.mode in {"RGBA", "P", "LA"}:
        logger.info(f"Converting {image.mode} -> RGB for JPEG")
        rgb = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "P":
            image = image.convert("RGBA")
        rgb.paste(image, mask=image.split()[-1] if image.mode in {"RGBA", "LA"} else None)
        image = rgb

    output = io.BytesIO()
    try:
        pil_format = PIL_FORMAT_MAP[to_format]
        image.save(output, format=pil_format)
        output.seek(0)
        logger.info(f"Converted to {pil_format}, size={output.getbuffer().nbytes}")
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        raise HTTPException(status_code=500, detail="Image conversion failed")

    mime = MIME_MAP[to_format]
    filename = f"converted.{to_format}"
    return Response(
        content=output.getvalue(),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
