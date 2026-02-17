# Converter MCP Server

A FastMCP-based format conversion server providing bidirectional conversion for images, video, audio, and ebooks.

## Features

- **Image Conversion**: PNG, JPG, GIF, WebP, TIFF, BMP (bidirectional) + SVG (input only)
- **Video Conversion**: MP4, AVI, MOV, WebM, MKV (bidirectional)
- **Audio Conversion**: MP3, WAV, FLAC, AAC, OGG, M4A (bidirectional)
- **Ebook Conversion**: EPUB, PDF, MOBI, AZW3 (via Calibre)
- **SVG to Raster**: Convert SVG to PNG, JPG, WebP, etc. (via CairoSVG)
- **Concurrent Processing**: Semaphore-based concurrency control
- **Progress Reporting**: MCP Context integration for progress updates
- **Resource Monitoring**: Memory, CPU, and disk space tracking
- **Auto-Rename**: File collision handling with sequential numbering

## Requirements

### System Dependencies

- **FFmpeg** (required for video/audio processing)
- **Calibre** (required for ebook conversion)
- **Cairo library** (optional, for SVG conversion)

### Python Dependencies

Installed automatically via pip:
- `mcp>=1.0.0` - MCP server framework
- `ffmpeg-python>=0.2.0` - FFmpeg Python bindings
- `Pillow>=10.0.0` - Image processing
- `psutil>=5.9.0` - Resource monitoring
- `cairosvg>=2.7.0` - SVG conversion (optional, install with `.[svg]`)

## Installation

### Prerequisites

1. **FFmpeg** (required for video/audio):
   ```bash
   # Ubuntu/Debian
   sudo apt-get install ffmpeg

   # macOS
   brew install ffmpeg

   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

2. **Calibre** (required for ebooks):
   ```bash
   # Ubuntu/Debian
   sudo apt-get install calibre

   # macOS
   brew install --cask calibre

   # Windows
   # Download from https://calibre-ebook.com/download
   ```

3. **Cairo library** (optional, for SVG conversion):
   ```bash
   # Ubuntu/Debian
   sudo apt-get install libcairo2-dev
   pip install cairosvg

   # macOS
   brew install cairo
   pip install cairosvg

   # Or install with the svg extra:
   pip install -e ".[svg]"
   ```

### Setup

1. Clone and install:
   ```bash
   git clone <repository-url>
   cd converter-mcp
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

2. Verify dependencies:
   ```bash
   python -c "
   import asyncio
   from converter.deps import verify_dependencies
   asyncio.run(verify_dependencies())
   print('All dependencies OK!')
   "
   ```

## Usage

### Running the MCP Server

```bash
# Activate virtual environment first
source .venv/bin/activate

# Run the server
converter-mcp

# Or using Python module
python -m converter.server
```

The server uses stdio transport for MCP communication.

### MCP Tools

The server exposes three MCP tools:

#### `convert_file`

Convert a file to a target format.

**Parameters:**
- `source` (string): Path to source file
- `target_format` (string): Target format (e.g., "jpg", "mp4", "webm", "pdf")
- `output_dir` (string, optional): Output directory (default: same as source)
- `quality` (string, optional): Quality preset - "low", "medium", "high" (default: "medium")

**Returns:**
```json
{
  "status": "success",
  "output_path": "/path/to/converted/file.jpg",
  "message": "Successfully converted image.png to jpg",
  "format": "jpg"
}
```

#### `list_supported_formats`

List all supported formats by category.

**Returns:**
```json
{
  "image": ["bmp", "gif", "jpg", "png", "tiff", "webp"],
  "video": ["avi", "mkv", "mov", "mp4", "webm"],
  "audio": ["aac", "flac", "m4a", "mp3", "ogg", "wav"],
  "ebook": ["azw3", "epub", "mobi", "pdf"]
}
```

#### `get_conversion_info`

Get information about a specific conversion path.

**Parameters:**
- `source_format` (string): Source format
- `target_format` (string): Target format

**Returns:**
```json
{
  "supported": true,
  "category": "image",
  "quality_options": ["low", "medium", "high"],
  "notes": "Direct image conversion supported"
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CONVERTER_MAX_CONCURRENT` | Maximum concurrent conversions | `min(4, cpu_count)` |
| `CONVERTER_OUTPUT_DIR` | Default output directory | Same as source |
| `CONVERTER_LOG_LEVEL` | Logging level | `INFO` |
| `CONVERTER_MIN_DISK_SPACE_MB` | Minimum disk space (MB) | `100` |

### Example Configuration

```bash
export CONVERTER_MAX_CONCURRENT=2
export CONVERTER_OUTPUT_DIR=/tmp/conversions
export CONVERTER_LOG_LEVEL=DEBUG
```

## Supported Formats

### Images (Pillow + CairoSVG)

| Format | Input | Output | Notes |
|--------|-------|--------|-------|
| PNG | Yes | Yes | Lossless, supports transparency |
| JPEG | Yes | Yes | Lossy, quality parameter supported |
| GIF | Yes | Yes | Supports animation |
| WebP | Yes | Yes | Modern format, good compression |
| TIFF | Yes | Yes | Professional format |
| BMP | Yes | Yes | Uncompressed |
| SVG | Yes | No | Input only, converts to raster via CairoSVG |

### Video (FFmpeg)

| Format | Input | Output | Codecs |
|--------|-------|--------|--------|
| MP4 | Yes | Yes | H.264 + AAC |
| WebM | Yes | Yes | VP9 + Opus |
| AVI | Yes | Yes | MPEG4 + MP3 |
| MOV | Yes | Yes | H.264 + AAC |
| MKV | Yes | Yes | H.264 + AAC |

### Audio (FFmpeg)

| Format | Input | Output | Notes |
|--------|-------|--------|-------|
| MP3 | Yes | Yes | Most compatible |
| WAV | Yes | Yes | Uncompressed |
| FLAC | Yes | Yes | Lossless |
| AAC | Yes | Yes | Good quality/size |
| OGG | Yes | Yes | Open format |
| M4A | Yes | Yes | Apple format |

### Ebooks (Calibre)

| Format | Input | Output |
|--------|-------|--------|
| EPUB | Yes | Yes |
| PDF | Yes | Yes |
| MOBI | Yes | Yes |
| AZW3 | Yes | Yes |

## Quality Presets

### Images
- **low**: 60% quality, fast compression
- **medium**: 85% quality, balanced (default)
- **high**: 95% quality, best quality

### Video
- **low**: CRF 28, faster preset
- **medium**: CRF 23, medium preset (default)
- **high**: CRF 18, slow preset

### Audio
- **low**: 128kbps, 44.1kHz
- **medium**: 192kbps, 44.1kHz (default)
- **high**: 320kbps, 48kHz

## Architecture

```
src/converter/
├── __init__.py          # Package initialization
├── __main__.py          # Entry point
├── server.py            # MCP server with FastMCP
├── deps.py              # Dependency verification
├── async_utils.py       # Concurrency control, subprocess
├── file_manager.py      # Path handling, collision resolution
├── logging_config.py    # Error hierarchy, logging
├── config.py            # Configuration management
├── queue.py             # Conversion queue
├── monitor.py           # Resource monitoring
├── progress.py          # Progress reporting
└── converters/
    ├── __init__.py
    ├── image.py         # Pillow-based image converter
    ├── video.py         # FFmpeg video converter
    ├── audio.py         # FFmpeg audio converter
    ├── ebook.py         # Calibre ebook converter
    └── router.py        # Format detection and routing
```

## Testing

### Run Tests

```bash
# Activate venv
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=converter --cov-report=html

# Skip slow tests
pytest tests/ -v -m "not slow"

# Run only integration tests
pytest tests/ -v -m integration

# Run performance benchmarks
pytest tests/ -v -m slow
```

### Test Categories

| Marker | Description | Command |
|--------|-------------|---------|
| `slow` | Large file and performance tests | `pytest -m slow` |
| `integration` | Integration tests with real files | `pytest -m integration` |

## Development

### Code Quality

```bash
# Run linter
ruff check src/

# Format code
black src/ tests/
```

### Project Structure

```
converter-mcp/
├── src/converter/       # Source code
├── tests/               # Test suite
├── pyproject.toml       # Project configuration
├── README.md            # This file
└── .sisyphus/           # Planning documents
```

## Troubleshooting

### FFmpeg Not Found

```
Error: FFmpeg not found
```

Install FFmpeg:
```bash
sudo apt-get install ffmpeg  # Ubuntu/Debian
brew install ffmpeg          # macOS
```

### Calibre Not Found

```
Error: Calibre not found
```

Install Calibre:
```bash
sudo apt-get install calibre  # Ubuntu/Debian
brew install --cask calibre   # macOS
```

### CairoSVG / Cairo Library Missing

```
Error: SVG conversion requires cairosvg library
```

Install Cairo system library and CairoSVG:
```bash
# Ubuntu/Debian
sudo apt-get install libcairo2-dev
pip install cairosvg

# macOS
brew install cairo
pip install cairosvg

# Windows
# Download Cairo from https://www.cairographics.org/download/
pip install cairosvg
```

### Memory Issues with Large Files

The server uses subprocess calls and never loads entire files into memory. If you still experience memory issues:

1. Reduce `CONVERTER_MAX_CONCURRENT` to 1
2. Use lower quality presets
3. Check available disk space

### File Collision Handling

When output files already exist, the server automatically renames:
```
image.jpg -> image_1.jpg -> image_2.jpg
```

Maximum of 1000 collisions before error.

## API Examples

### Python (Direct)

```python
import asyncio
from converter.converters.image import ImageConverter

async def convert_image():
    converter = ImageConverter()
    result = await converter.convert(
        source_path="input.png",
        target_format="jpg",
        quality="high"
    )
    print(f"Converted to: {result}")

asyncio.run(convert_image())
```

### With Progress Callback

```python
import asyncio
from converter.converters.video import VideoConverter

async def convert_with_progress():
    converter = VideoConverter()
    
    def on_progress(percent):
        print(f"Progress: {percent:.1f}%")
    
    result = await converter.convert(
        source_path="video.mp4",
        target_format="webm",
        quality="medium",
        progress_callback=on_progress
    )
    print(f"Converted to: {result}")

asyncio.run(convert_with_progress())
```

### Using the Router

```python
import asyncio
from converter.converters.router import ConverterRouter

async def auto_convert():
    router = ConverterRouter()
    
    result = await router.convert(
        source_path="document.epub",
        target_format="pdf"
    )
    print(f"Converted to: {result}")

asyncio.run(auto_convert())
```

### Batch Processing

Process multiple files efficiently:

```python
import asyncio
from pathlib import Path
from converter.converters.image import ImageConverter

async def batch_convert():
    converter = ImageConverter()
    input_dir = Path("images")
    
    tasks = []
    for img in input_dir.glob("*.png"):
        output = img.with_suffix(".jpg")
        tasks.append(converter.convert(img, "jpg", output_path=output))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for img, result in zip(input_dir.glob("*.png"), results):
        if isinstance(result, Exception):
            print(f"Failed: {img} - {result}")
        else:
            print(f"Converted: {img} -> {result}")

asyncio.run(batch_convert())
```

### Error Handling

Handle conversion errors gracefully:

```python
import asyncio
from converter.converters.image import ImageConverter
from converter.logging_config import ConversionError, FormatNotSupportedError

async def safe_convert(source, target_format):
    converter = ImageConverter()
    
    try:
        result = await converter.convert(source, target_format, quality="high")
        return result
    except FormatNotSupportedError as e:
        print(f"Format not supported: {e}")
        print(f"Suggestion: {e.suggestion}")
    except ConversionError as e:
        print(f"Conversion failed: {e}")
    except FileNotFoundError:
        print(f"File not found: {source}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    return None

asyncio.run(safe_convert("input.tiff", "webp"))
```

### Configuration via Environment

```python
import os
import asyncio
from converter.converters.router import ConverterRouter

# Configure via environment variables
os.environ["CONVERTER_MAX_CONCURRENT"] = "2"  # Max 2 concurrent conversions
os.environ["CONVERTER_OUTPUT_DIR"] = "/tmp/converted"  # Default output directory
os.environ["CONVERTER_LOG_LEVEL"] = "DEBUG"  # Enable debug logging

async def main():
    router = ConverterRouter()
    result = await router.convert("video.mp4", "webm", quality="medium")
    print(f"Result: {result}")

asyncio.run(main())
```

### Concurrent Conversions with Limits

Control concurrency with semaphores:

```python
import asyncio
from pathlib import Path
from converter.converters.video import VideoConverter

async def convert_with_limit(files, max_concurrent=2):
    converter = VideoConverter()
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def convert_one(file):
        async with semaphore:
            output = file.with_suffix(".webm")
            return await converter.convert(file, "webm", output_path=output)
    
    tasks = [convert_one(f) for f in files]
    return await asyncio.gather(*tasks, return_exceptions=True)

async def main():
    files = list(Path("videos").glob("*.mp4"))
    results = await convert_with_limit(files, max_concurrent=2)
    print(f"Converted {sum(not isinstance(r, Exception) for r in results)} files")

asyncio.run(main())
```

## License

MIT License

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run the test suite
5. Submit a pull request
