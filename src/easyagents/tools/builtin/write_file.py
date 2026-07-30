import asyncio
import os


async def write_file(
    path: str,
    content: str,
    append: bool = False,
) -> dict:
    """Write content to a local file.

    Args:
        path: File path (relative to current working directory or absolute).
        content: Content to write.
        append: If True, append to file. If False, overwrite (default).

    Returns:
        {"path": str, "bytes_written": int}
        On error: {"path": "", "error": str}
    """
    try:
        normalized = os.path.normpath(path)
        if ".." in normalized.split(os.sep):
            return {"path": "", "error": "Path traversal denied"}

        def _write():
            mode = "a" if append else "w"
            with open(normalized, mode) as f:
                f.write(content)
            return len(content.encode("utf-8"))

        bytes_written = await asyncio.to_thread(_write)
        return {"path": normalized, "bytes_written": bytes_written}
    except Exception as e:
        return {"path": "", "error": str(e)}
