# Country Currency & Exchange API

A RESTful API built with FastAPI that fetches country data from external APIs, stores it in MySQL, and provides CRUD operations with exchange rate calculations.

## Features

- Fetch and cache country data from RestCountries API
- Fetch real-time exchange rates from Open Exchange Rates API
- Calculate estimated GDP for each country
- CRUD operations for country records
- Filter and sort countries by region, currency, and GDP
- Generate summary images with top countries
- MySQL database with DigitalOcean hosting support

## Prerequisites

- Python 3.11+
- MySQL Database (DigitalOcean or local)
- pip (Python package manager)

## Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd <your-repo-name>
```

2. **Create a virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**

Create a `.env` file in the root directory:

```env
DATABASE_URL=mysql+pymysql://username:password@host:port/database_name
DB_HOST=your-digitalocean-db-host
DB_PORT=25060
DB_USER=your-username
DB_PASSWORD=your-password
DB_NAME=your-database-name
PORT=8000
```

Replace the placeholders with your actual DigitalOcean MySQL credentials.

5. **Create the database**

Make sure your MySQL database exists:
```sql
CREATE DATABASE your_database_name;
```

## Running Locally

1. **Start the server**
```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

2. **Access the API**
- API: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### POST /countries/refresh
Fetch all countries and exchange rates, then cache them in the database.

**Response:**
```json
{
  "message": "Countries data refreshed successfully",
  "total_countries": 250,
  "last_refreshed_at": "2025-10-22T18:00:00Z"
}
```

### GET /countries
Get all countries with optional filters and sorting.

**Query Parameters:**
- `region` - Filter by region (e.g., `Africa`, `Europe`)
- `currency` - Filter by currency code (e.g., `NGN`, `USD`)
- `sort` - Sort results (`gdp_desc`, `gdp_asc`, `name_asc`, `name_desc`)

**Example:**
```
GET /countries?region=Africa&sort=gdp_desc
```

### GET /countries/{name}
Get a single country by name.

**Example:**
```
GET /countries/Nigeria
```

### DELETE /countries/{name}
Delete a country record.

**Example:**
```
DELETE /countries/Nigeria
```

### GET /status
Show total countries and last refresh timestamp.

**Response:**
```json
{
  "total_countries": 250,
  "last_refreshed_at": "2025-10-22T18:00:00Z"
}
```

### GET /countries/image
Serve the generated summary image.

Returns a PNG image with:
- Total number of countries
- Top 5 countries by estimated GDP
- Last refresh timestamp

## Deployment on DigitalOcean

### Option 1: App Platform

1. Push your code to GitHub
2. Go to DigitalOcean App Platform
3. Create a new app from your GitHub repository
4. Add environment variables in the app settings
5. Deploy

### Option 2: Droplet

1. Create a Ubuntu droplet
2. SSH into your droplet
3. Install Python, pip, and MySQL client
4. Clone your repository
5. Install dependencies
6. Set up environment variables
7. Run with uvicorn or use a process manager like systemd

**Example systemd service (`/etc/systemd/system/countryapi.service`):**
```ini
[Unit]
Description=Country API
After=network.target

[Service]
User=your-user
WorkingDirectory=/path/to/your/app
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable countryapi
sudo systemctl start countryapi
```

## Database Schema

### countries table
- `id` - Primary key (auto-increment)
- `name` - Country name (unique)
- `capital` - Capital city
- `region` - Geographic region
- `population` - Population count
- `currency_code` - Currency code (e.g., NGN)
- `exchange_rate` - Exchange rate to USD
- `estimated_gdp` - Calculated GDP estimate
- `flag_url` - URL to country flag image
- `last_refreshed_at` - Last update timestamp

### refresh_metadata table
- `id` - Primary key
- `last_refreshed_at` - Global refresh timestamp

## Dependencies

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM for database operations
- `pymysql` - MySQL driver
- `httpx` - Async HTTP client for API calls
- `pillow` - Image generation
- `python-dotenv` - Environment variable management
- `pydantic` - Data validation

## Error Handling

The API returns consistent JSON error responses:

- `400 Bad Request` - Invalid input
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - External API failure

## Testing

Test endpoints using the interactive docs at `/docs` or use curl:

```bash
# Refresh data
curl -X POST http://localhost:8000/countries/refresh

# Get all countries
curl http://localhost:8000/countries

# Get countries in Africa
curl http://localhost:8000/countries?region=Africa

# Get status
curl http://localhost:8000/status
```

## Notes

- The `estimated_gdp` is recalculated on each refresh with a new random multiplier (1000-2000)
- Countries without currencies are stored with null values for currency_code and exchange_rate
- The summary image is regenerated after each refresh
- Exchange rates are fetched from USD as the base currency

## License

MIT

## Author

HNG Internship - Backend Track
