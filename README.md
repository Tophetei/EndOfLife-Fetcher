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

```bash
python endoflife_fetcher.py python
```

This command will:

- Fetch EOL data for Python
- Automatically create the `Output/` folder if it doesn't exist
- Save the result to `Output/python-eol.json`

### Examples

**Fetch info for Node.js:**

```bash
python endoflife_fetcher.py nodejs
```

**Specify a custom output file:**

```bash
python endoflife_fetcher.py ubuntu -o data/ubuntu-versions.json
```

**Change HTTP timeout:**

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
python endoflife_fetcher.py [-h] [-o OUTPUT] [--timeout TIMEOUT] product

Arguments:
  product              Product slug (e.g., python, ubuntu, nodejs)

Options:
  -h, --help           Show help message
  -o, --output OUTPUT  JSON output file path
                       Default: Output/{product}-eol.json
  --timeout TIMEOUT    HTTP timeout in seconds (default: 15)
```

## 📊 Output format

The script generates a JSON file containing the product's lifecycle with information such as:

- Versions
- Release dates
- End of support dates
- End of life (EOL) dates
- Current support status

## ⚠️ Error handling

The script handles errors properly with distinct exit codes:

- `10`: Product not found (404)
- `11`: API or network error
- `12`: File writing error
- `13`: Rate limit hit (429) - too many requests

## 🛠️ Architecture

The code is organized in a simple and modular way:

- **fetch_product()**: Fetches data from the API
- **save_json()**: Saves data in JSON format
- **Custom exceptions**: Clear and specific error handling

Easy to modify and extend according to your needs!

## 📝 Sample retrieved data

The returned data typically includes:

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

## 📚 Resources

- [endoflife.date API](https://endoflife.date/docs/api)
- [List of supported products](https://endoflife.date/)
