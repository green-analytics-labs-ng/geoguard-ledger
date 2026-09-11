"""Shared helpers for handling uploaded files."""

from fastapi import HTTPException, UploadFile

from app.config import settings

# Starlette renamed HTTP_413_REQUEST_ENTITY_TOO_LARGE to
# HTTP_413_CONTENT_TOO_LARGE (RFC 9110). The literal keeps this working
# regardless of which name the pinned Starlette version exposes.
PAYLOAD_TOO_LARGE = 413


def _max_upload_size_mb() -> float:
    """Human-readable form of the configured upload limit, in megabytes."""
    return settings.max_upload_size_bytes / (1024 * 1024)


def _too_large_error() -> HTTPException:
    return HTTPException(
        status_code=PAYLOAD_TOO_LARGE,
        detail=f"File too large - maximum upload size is {_max_upload_size_mb():.0f} MB",
    )


async def read_upload(file: UploadFile) -> bytes:
    """Read an uploaded file into memory, enforcing the size limit.

    Starlette fills ``UploadFile.size`` from the multipart headers, so the
    cheap check happens before the body is read. The post-read check is a
    defence-in-depth guard for clients that omit or misreport their size.

    Raises:
        HTTPException: 413 if the upload exceeds ``settings.max_upload_size_bytes``.
    """
    max_bytes = settings.max_upload_size_bytes

    if file.size is not None and file.size > max_bytes:
        raise _too_large_error()

    content = await file.read()

    if len(content) > max_bytes:
        raise _too_large_error()

    return content
