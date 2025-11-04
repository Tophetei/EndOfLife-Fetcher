# EndOfLife Fetcher 🗓️

A simple Python script to fetch end-of-life (EOL) data for products from the [endoflife.date](https://endoflife.date/) API.

## 📋 Description

This script allows you to easily retrieve support and end-of-life information for various products (programming languages, operating systems, frameworks, etc.) and save them in JSON format.

## 🚀 Installation

1. Clone or download this project
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## 💡 Usage

### Basic usage

**Single product:**

```bash
python endoflife_fetcher.py python
```

This command will:

- Fetch EOL data for Python
- Automatically create the `Output/` folder if it doesn't exist
- Save the result to `Output/python-eol.json`

**Multiple products (new!):**

```bash
python endoflife_fetcher.py python nodejs ubuntu
```

This command will:

- Fetch EOL data for Python, Node.js, and Ubuntu
- Save each product in its own file:
  - `Output/python-eol.json`
  - `Output/nodejs-eol.json`
  - `Output/ubuntu-eol.json`

### Examples

**Fetch multiple products:**

```bash
python endoflife_fetcher.py python nodejs php ruby go
```

**Combine everything in a single file with `--one-file`:**

```bash
python endoflife_fetcher.py python nodejs ubuntu --one-file
```

This creates `Output/all-products-eol.json` with the following structure:

```json
{
  "python": [...],
  "nodejs": [...],
  "ubuntu": [...]
}
```

**Specify a custom output file with `--one-file`:**

```bash
python endoflife_fetcher.py python nodejs --one-file -o my-report.json
```

**Specify an output file for a single product:**

```bash
python endoflife_fetcher.py ubuntu -o data/ubuntu-versions.json
```

**Change the HTTP timeout:**

```bash
python endoflife_fetcher.py python --timeout 30
```

### Available products

You can fetch info for many products, for example:

- `python`, `nodejs`, `php`, `ruby`, `go`
- `ubuntu`, `debian`, `windows`, `macos`
- `docker`, `kubernetes`, `postgresql`, `mysql`
- `django`, `rails`, `react`, `angular`

For the complete list: [endoflife.date/api/products](https://endoflife.date/api/v1/products)

## 🎯 Options

```bash
python endoflife_fetcher.py [-h] [-o OUTPUT] [-t TIMEOUT] [--one-file] product [product ...]

Arguments:
  product              One or more product slugs (e.g., python, ubuntu, nodejs)

Options:
  -h, --help           Show help message
  -o, --output OUTPUT  JSON output file path
                       Default: Output/{product}-eol.json for each product
                                Output/all-products-eol.json with --one-file
  -t, --timeout TIMEOUT  HTTP timeout in seconds (default: 15)
  --one-file           Save all products data in a single JSON file
                       (default: one file per product)
```

## 📊 Output format

### One file per product (default)

The script generates a JSON file for each product containing lifecycle information such as:

```json
[
  {
    "cycle": "3.12",
    "releaseDate": "2023-10-02",
    "eol": "2028-10-31",
    "latest": "3.12.0",
    "lts": false
  },
  ...
]
```

### Single file (with `--one-file`)

With the `--one-file` option, all products are grouped in a single file:

```json
{
  "python": [
    {
      "cycle": "3.12",
      "releaseDate": "2023-10-02",
      "eol": "2028-10-31",
      "latest": "3.12.0",
      "lts": false
    }
  ],
  "nodejs": [
    {
      "cycle": "20",
      "releaseDate": "2023-04-18",
      "eol": "2026-04-30",
      "latest": "20.10.0",
      "lts": true
    }
  ]
}
```

## ⚠️ Error handling

The script handles errors properly with distinct exit codes:

- `0`: Complete success (all products fetched successfully)
- `5`: Partial success (some products succeeded, some failed)
- `10`: Product not found (404)
- `11`: API or network error
- `12`: File writing error
- `13`: Rate limit exceeded (429) - too many requests

### Partial success

If you request multiple products and some fail, the script will:

- Continue with the remaining products
- Save data for successful products
- Display an error report at the end
- Return exit code `5` (partial success)

Example:

```bash
python endoflife_fetcher.py python invalid-product nodejs
```

Output:

```bash
Fetching data for 'python'...
  ✓ Successfully fetched data for 'python'
Fetching data for 'invalid-product'...
  ✗ Error: Product 'invalid-product' not found
Fetching data for 'nodejs'...
  ✓ Successfully fetched data for 'nodejs'

Saved data for 2 products:
  - python: Output/python-eol.json
  - nodejs: Output/nodejs-eol.json

1 product(s) failed:
  - invalid-product: Product 'invalid-product' not found
```

Exit code: `5`

## 🛠️ Architecture

The code is organized in a simple and modular way:

- **fetch_product()**: Fetches data from the API
- **save_json()**: Saves data in JSON format
- **parse_args()**: Parses command-line arguments
- **main()**: Main entry point with error handling
- **Custom exceptions**: Clear and specific error handling

Easy to modify and extend according to your needs!

## 📚 Resources

- [endoflife.date API](https://endoflife.date/docs/api)
- [List of supported products](https://endoflife.date/)

## 🧪 Testing

To run the tests:

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run tests
pytest test_endoflife_fetcher.py -v

# With coverage
pytest test_endoflife_fetcher.py --cov=endoflife_fetcher --cov-report=html
```

## 💡 Practical examples

**Monitor multiple programming languages:**

```bash
python endoflife_fetcher.py python nodejs php ruby go --one-file -o languages.json
```

**Compare different OS versions:**

```bash
python endoflife_fetcher.py ubuntu debian centos
```

**Complete web application stack:**

```bash
python endoflife_fetcher.py python django postgresql nginx redis --one-file
```

**Containerized infrastructure:**

```bash
python endoflife_fetcher.py docker kubernetes helm --one-file -o infra.json
```
