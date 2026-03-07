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
from fastapi.responses import JSONResponse, Response
from PIL import Image
from x402.integrations.fastapi import x402_middleware

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
NETWORK: str = os.getenv("NETWORK", "base")
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
# x402 Payment Middleware
# -----------------------------------------------------------------------------
x402_middleware(
    app,
    pay_to=WALLET_ADDRESS,
    network="eip155:8453",
    routes={
        "/convert": {"price": f"${PRICE_USDC}", "description": "Image format conversion"},
    },
)

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
            "/convert": "POST - Convert image format (requires payment)",
            "/health": "GET - Health check endpoint",
        },
    }


@app.get("/health", summary="Health check")
async def health():
    """Simple health check endpoint for Railway/monitoring."""
    return {"status": "healthy", "service": SERVICE_NAME}


@app.post("/convert", summary="Convert image format")
async def convert_image(
    file: UploadFile = File(..., description="Image file to convert"),
    output_format: Literal["png", "jpg", "jpeg", "webp"] = Form(
        ..., description="Target format"
    ),
):
    """
    Convert an uploaded image to a different format.

    **Payment Required:** This endpoint requires payment via x402 protocol headers.
    - Cost: $0.02 USDC
    - Network: Base
    - Wallet: 0x65F204B928a32806FCB364cB8d36B49b647c9f30

    **Supported formats:** PNG, JPG / JPEG, WebP

    **Returns:** The converted image as binary data.
    """
    logger.info(f"Received conversion request: {file.filename} -> {output_format}")

    if output_format not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported output format. Choose from: {SUPPORTED_FORMATS}",
        )

    try:
        contents = await file.read()
        logger.info(f"Read {len(contents)} bytes from upload")

        img = Image.open(io.BytesIO(contents))
        logger.info(f"Opened image: {img.format} {img.size} {img.mode}")

        if output_format in {"jpg", "jpeg"} and img.mode in ("RGBA", "LA", "P"):
            logger.info(f"Converting {img.mode} to RGB for JPEG output")
            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            rgb_img.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = rgb_img

        output = io.BytesIO()
        pil_format = PIL_FORMAT_MAP[output_format]
        img.save(output, format=pil_format)
        output.seek(0)

        logger.info(f"Successfully converted to {output_format}")

        return Response(
            content=output.read(),
            media_type=MIME_MAP[output_format],
            headers={
                "Content-Disposition": f'attachment; filename="converted.{output_format}"'
            },
        )

    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))