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
from x402.middleware.fastapi import x402_middleware

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WALLET_ADDRESS: str = os.getenv(
    "PAYMENT_WALLET_ADDRESS",
    "0x65F204B928a32806FCb364cB8d36B49b647c9f30",
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

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# x402 Payment Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    x402_middleware,
    wallet_address="0x65F204B928a32806FCb364cB8d36B49b647c9f30",
    routes={
        "/convert": {
            "price": "0.02",
            "network": "base-mainnet",
            "description": "Image format conversion - $0.02 USDC",
        }
    },
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
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
            "payTo": WALLET_ADDRESS,
            "protocol": "x402",
        },
        "supportedFormats": sorted(SUPPORTED_FORMATS),
        "endpoints": {
            "GET /": "Service info (this response)",
            "GET /health": "Health check",
            "POST /convert": "Convert an image (payment required)",
            "GET /docs": "Interactive API docs (Swagger UI)",
        },
    }


@app.get("/health", summary="Health check")
async def health():
    """Liveness probe - returns 200 if the service is running."""
    return {"status": "healthy"}


@app.post(
    "/convert",
    summary="Convert an image",
    responses={
        200: {"description": "Converted image file", "content": {"image/*": {}}},
        400: {"description": "Bad request"},
        402: {"description": "Payment required"},
        415: {"description": "Unsupported media type"},
        500: {"description": "Internal server error"},
    },
)
async def convert_image(
    file: UploadFile = File(..., description="Source image file"),
    target_format: Literal["png", "jpg", "jpeg", "webp"] = Form(
        ...,
        description="Desired output format: png | jpg | jpeg | webp",
        alias="format",
    ),
):
    """
    Upload an image and receive it back in the requested format.

    Payment: Include an X-PAYMENT header with a valid x402 payment proof
    for $0.02 USDC on Base before this endpoint will process your request.
    """
    fmt = target_format.lower().strip()
    if fmt not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target format '{fmt}'. Choose from: {sorted(SUPPORTED_FORMATS)}",
        )

    allowed_input_types = {
        "image/png", "image/jpeg", "image/jpg",
        "image/webp", "image/gif", "image/bmp",
        "image/tiff", "image/x-tiff",
        "application/octet-stream",
    }
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in allowed_input_types:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported input media type: {content_type}",
        )

    try:
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        image: Image.Image = Image.open(io.BytesIO(raw))

        pil_format = PIL_FORMAT_MAP[fmt]
        if pil_format == "JPEG" and image.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None)
            image = background
        elif image.mode == "P":
            image = image.convert("RGBA")

        output_buffer = io.BytesIO()
        save_kwargs: dict = {"format": pil_format}
        if pil_format == "JPEG":
            save_kwargs["quality"] = 92
            save_kwargs["optimize"] = True
        elif pil_format == "WEBP":
            save_kwargs["quality"] = 90
            save_kwargs["method"] = 6

        image.save(output_buffer, **save_kwargs)
        output_buffer.seek(0)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Conversion failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Image conversion failed: {exc}",
        )

    original_stem = os.path.splitext(file.filename or "image")[0]
    output_filename = f"{original_stem}_converted.{fmt}"
    mime_type = MIME_MAP[fmt]

    logger.info(
        "Converted '%s' -> '%s' (%d bytes)",
        file.filename,
        output_filename,
        output_buffer.getbuffer().nbytes,
    )

    return Response(
        content=output_buffer.read(),
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{output_filename}"',
            "X-PAYMENT-RESPONSE": "success",
            "X-Converted-From": file.content_type or "unknown",
            "X-Converted-To": mime_type,
        },
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENV", "production") == "development",
        log_level="info",
    )