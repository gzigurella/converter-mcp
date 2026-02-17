# Contributing to Converter MCP Server

Thank you for your interest in contributing! This document provides guidelines for development.

## Development Setup

### Prerequisites

- Python 3.9+
- FFmpeg (for video/audio processing)
- Calibre (for ebook conversion)
- Cairo + cairosvg (optional, for SVG support)

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd converter-mcp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Install optional SVG support
pip install -e ".[svg]"

# Verify installation
python -c "from converter.deps import verify_dependencies; import asyncio; asyncio.run(verify_dependencies())"
```

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get install ffmpeg calibre libcairo2-dev
```

**macOS:**
```bash
brew install ffmpeg calibre cairo
```

**Windows:**
- FFmpeg: https://ffmpeg.org/download.html
- Calibre: https://calibre-ebook.com/download
- Cairo: https://www.cairographics.org/download/

## Project Structure

```
converter-mcp/
├── src/converter/
│   ├── __init__.py          # Package initialization
│   ├── __main__.py          # Entry point
│   ├── server.py            # MCP server (FastMCP)
│   ├── deps.py              # Dependency verification
│   ├── async_utils.py       # Concurrency utilities
│   ├── file_manager.py      # File operations
│   ├── logging_config.py    # Error hierarchy & logging
│   ├── config.py            # Configuration management
│   ├── queue.py             # Conversion queue
│   ├── monitor.py           # Resource monitoring
│   ├── progress.py          # Progress reporting
│   └── converters/
│       ├── image.py         # Pillow converter
│       ├── video.py         # FFmpeg video
│       ├── audio.py         # FFmpeg audio
│       ├── ebook.py         # Calibre ebooks
│       └── router.py        # Format routing
├── tests/
│   ├── test_*.py            # Unit tests
│   ├── test_integration.py  # Integration tests
│   ├── test_edge_cases.py   # Edge case tests
│   └── test_large_files.py  # Large file tests
├── pyproject.toml           # Project config
└── README.md                # User documentation
```

## Code Style

### Formatting

We use Black for code formatting:

```bash
# Format all code
black src/ tests/

# Check formatting
black --check src/ tests/
```

### Linting

We use Ruff for linting:

```bash
# Run linter
ruff check src/

# Fix auto-fixable issues
ruff check --fix src/
```

### Type Hints

Add type hints to all public functions:

```python
# Good
async def convert(
    source_path: str | Path,
    target_format: str,
    output_path: Optional[Path] = None,
) -> Path:
    ...

# Bad
async def convert(source_path, target_format, output_path=None):
    ...
```

### Docstrings

Use descriptive docstrings for public APIs:

```python
async def convert(
    self,
    source_path: str | Path,
    target_format: str,
) -> Path:
    """Convert file to target format.
    
    Args:
        source_path: Path to source file
        target_format: Target format (e.g., 'jpg', 'mp4')
        
    Returns:
        Path to converted file
        
    Raises:
        FormatNotSupportedError: If format is not supported
        ConversionError: If conversion fails
    """
```

## Testing

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_image_converter.py -v

# Run with coverage
pytest tests/ --cov=converter --cov-report=html

# Skip slow tests
pytest tests/ -v -m "not slow"

# Run only integration tests
pytest tests/ -v -m integration
```

### Test Categories

- **Unit tests**: Fast, isolated tests (`test_*.py`)
- **Integration tests**: Real file conversions (`test_integration.py`)
- **Edge cases**: Boundary conditions (`test_edge_cases.py`)
- **Performance tests**: Benchmarks (`test_performance.py`)
- **Large file tests**: Memory efficiency (`test_large_files.py`)

### Writing Tests

```python
import pytest
from pathlib import Path
from src.converter.converters.image import ImageConverter

class TestImageConverter:
    """Tests for ImageConverter."""
    
    @pytest.fixture
    def sample_image(self, tmp_path):
        """Create sample image for testing."""
        from PIL import Image
        img_path = tmp_path / "test.png"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(img_path, "PNG")
        img.close()
        return img_path
    
    @pytest.mark.asyncio
    async def test_convert_png_to_jpg(self, sample_image, tmp_path):
        """Test PNG to JPG conversion."""
        converter = ImageConverter()
        output = tmp_path / "output.jpg"
        
        result = await converter.convert(sample_image, "jpg", output_path=output)
        
        assert result.exists()
        assert result.suffix == ".jpg"
```

## Pull Request Process

### Before Submitting

1. **Run all tests**:
   ```bash
   pytest tests/ -v
   ```

2. **Check code style**:
   ```bash
   black --check src/ tests/
   ruff check src/
   ```

3. **Update documentation** if adding new features

4. **Add tests** for new functionality

### PR Guidelines

1. **Title**: Clear, descriptive title
2. **Description**: What changes and why
3. **Tests**: All tests pass
4. **Documentation**: Updated if needed
5. **Breaking changes**: Clearly noted

### PR Template

```markdown
## Changes
- Brief description of changes

## Testing
- [ ] All tests pass
- [ ] New tests added for new functionality

## Documentation
- [ ] README updated
- [ ] Code comments added where needed

## Breaking Changes
- None / List breaking changes
```

## Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Release Checklist

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Create git tag: `git tag v1.0.0`
5. Push tag: `git push origin v1.0.0`

## Architecture

### Converter Pattern

All converters follow the same interface:

```python
class Converter:
    @staticmethod
    def is_format_supported(format: str, for_output: bool = False) -> bool:
        """Check if format is supported."""
        
    async def convert(
        self,
        source_path: str | Path,
        target_format: str,
        output_path: Optional[Path] = None,
        **kwargs
    ) -> Path:
        """Convert file to target format."""
```

### Error Hierarchy

```
ConverterError (base)
├── UserError
│   ├── FormatNotSupportedError
│   └── InvalidInputError
├── SystemError
│   ├── DependencyError
│   └── DiskSpaceError
└── ConversionError
    └── ProcessingTimeoutError
```

### Async Patterns

All converters are async and use:
- `asyncio.create_subprocess_exec()` for external tools
- `asyncio.Semaphore` for concurrency control
- `run_in_executor()` for CPU-bound operations

## Getting Help

- **Issues**: Open a GitHub issue for bugs/features
- **Discussions**: Use GitHub discussions for questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
