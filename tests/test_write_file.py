import pytest

from easyagents.tools.builtin.write_file import write_file


@pytest.mark.asyncio
async def test_write_file_creates_file(tmp_path):
    """Test write_file creates a new file with content."""
    filepath = tmp_path / "test.txt"
    result = await write_file(str(filepath), "hello world")

    assert result["bytes_written"] == 11
    assert filepath.read_text() == "hello world"


@pytest.mark.asyncio
async def test_write_file_append(tmp_path):
    """Test write_file appends to existing file."""
    filepath = tmp_path / "test.txt"
    filepath.write_text("line1\n")

    result = await write_file(str(filepath), "line2\n", append=True)

    assert result["bytes_written"] == 6
    assert filepath.read_text() == "line1\nline2\n"


@pytest.mark.asyncio
async def test_write_file_overwrite(tmp_path):
    """Test write_file overwrites existing file by default."""
    filepath = tmp_path / "test.txt"
    filepath.write_text("old content")

    await write_file(str(filepath), "new")

    assert filepath.read_text() == "new"


@pytest.mark.asyncio
async def test_write_file_rejects_path_traversal(tmp_path):
    """Test write_file rejects path traversal attempts."""
    result = await write_file("../../../etc/passwd", "hacked")

    assert "error" in result
    assert "traversal" in result["error"].lower() or "denied" in result["error"].lower()
