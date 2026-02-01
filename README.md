# EndOfLife Fetcher

[![CI](https://github.com/Tophetei/EndOfLife-Fetcher/actions/workflows/ci.yml/badge.svg)](https://github.com/Tophetei/EndOfLife-Fetcher/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A CLI tool to fetch end-of-life data from [endoflife.date](https://endoflife.date/) API and save as JSON. Perfect for CI/CD pipelines to monitor your stack's lifecycle.

```bash
$ endoflife-fetcher python nodejs --check --warn-days 90
Fetching data for 'python'...
  [OK] Successfully fetched data for 'python'
Fetching data for 'nodejs'...
  [OK] Successfully fetched data for 'nodejs'

[WARNING] EOL Check Failed:
  - python 3.8: EOL in 89 days (2025-10-31)
```

## Features

- **Multi-product support** — Fetch one or many products in a single command
- **CI/CD integration** — `--check` mode with configurable warning threshold
- **Automatic retry** — Exponential backoff for transient failures (5xx errors)
- **Flexible output** — One file per product or combined JSON
- **TOML configuration** — Store defaults in config files
- **Quiet mode** — Script-friendly output for automation

## Installation

```bash
# Install from source
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks (contributors)
pre-commit install
```

After installation, you can use either:
- `endoflife-fetcher` (installed command)
- `python endoflife_fetcher.py` (direct script)

## Quick Start

```bash
# Fetch EOL data for a product
endoflife-fetcher python

# Fetch multiple products
endoflife-fetcher python nodejs ubuntu

# Check for EOL products (exits 1 if found)
endoflife-fetcher python nodejs --check

# Warn if EOL within 90 days
endoflife-fetcher python nodejs --check --warn-days 90

# List all available products
endoflife-fetcher --list-products
```

## Configuration

### CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Output file path | `Output/{product}-eol.json` |
| `--timeout` | `-t` | HTTP timeout in seconds | `15` |
| `--max-retries` | | Retry attempts for transient failures | `3` |
| `--one-file` | | Combine all products in single JSON | `false` |
| `--check` | | Check for EOL products, exit 1 if found | `false` |
| `--warn-days` | | Days threshold for EOL warning | `0` |
| `--quiet` | `-q` | Suppress progress output | `false` |
| `--list-products` | | List all available products | |
| `--config` | | Path to TOML config file | |
| `--version` | `-V` | Show version | |

### Config File

Store defaults in a TOML configuration file. The tool looks for configs in this order (later overrides earlier):

1. `~/.config/endoflife-fetcher/config.toml` (user config)
2. `./endoflife-fetcher.toml` (project config)
3. `--config /path/to/file.toml` (explicit path)

**Example `endoflife-fetcher.toml`:**

```toml
# HTTP settings
timeout = 15.0
max_retries = 3

# Default behavior
quiet = false
one_file = false
warn_days = 30

# Output settings
output_dir = "Output"
combined_filename = "all-products-eol.json"

# Default products (used when none specified on CLI)
products = ["python", "nodejs", "postgresql"]
```

CLI arguments always override config file values.

## Usage Examples

### Basic Usage

```bash
# Single product → Output/python-eol.json
endoflife-fetcher python

# Multiple products → separate files
endoflife-fetcher python nodejs ubuntu

# Combined output → Output/all-products-eol.json
endoflife-fetcher python nodejs ubuntu --one-file

# Custom output path
endoflife-fetcher python -o reports/python.json
```

### CI/CD Integration

```bash
# Fail pipeline if any product is past EOL
endoflife-fetcher python nodejs postgresql --check

# Fail if EOL within 90 days (plan ahead!)
endoflife-fetcher python nodejs postgresql --check --warn-days 90

# Quiet mode for cleaner CI logs
endoflife-fetcher python nodejs --check --quiet
```

**GitHub Actions example:**

```yaml
- name: Check EOL status
  run: |
    pip install -e .
    endoflife-fetcher python nodejs postgresql --check --warn-days 90
```

### Scripting

```bash
# List products and filter
endoflife-fetcher --list-products | grep -i python

# Quiet mode (only errors shown)
endoflife-fetcher python nodejs -q

# Disable retries for faster failure
endoflife-fetcher python --max-retries 0
```

### Output Format

**Per-product (default):**

```json
[
  {
    "cycle": "3.12",
    "releaseDate": "2023-10-02",
    "eol": "2028-10-31",
    "latest": "3.12.0",
    "lts": false
  }
]
```

**Combined (`--one-file`):**

```json
{
  "python": [...],
  "nodejs": [...],
  "ubuntu": [...]
}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | EOL check failed (`--check` found EOL products) |
| `5` | Partial success (some products failed) |
| `10` | Product not found (404) |
| `11` | API or network error |
| `12` | File writing error |
| `13` | Rate limit exceeded (429) |

## Contributing

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=endoflife_fetcher --cov-report=html
```

### Linting

```bash
# Check
ruff check .

# Format
ruff format .
```

Pre-commit hooks run automatically on commit if installed.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Resources

- [endoflife.date](https://endoflife.date/) — Data source
- [API Documentation](https://endoflife.date/docs/api) — API reference
- [Available Products](https://endoflife.date/api/v1/products) — Full product list
