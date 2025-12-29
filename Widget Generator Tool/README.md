# Notion Map Widget Generator

A Flask application that fetches Notion map views and generates embeddable widgets for your website.

## Features

- 🗺️ Fetches Notion map views using BeautifulSoup4
- 🔄 Generates embeddable HTML widgets
- 🚀 Easy to integrate into any website
- ⚡ Automatic refresh with scheduler support
- 🎨 Clean, responsive design

## Requirements

- Python 3.10+
- beautifulsoup4
- lxml
- requests
- flask
- apscheduler
- python-dotenv

## Installation

1. Install dependencies:

```bash
pip install beautifulsoup4 lxml requests flask apscheduler python-dotenv
```

2. Configure your environment variables in `.env`:

```bash
export NOTION_API_KEY="your_notion_api_key"
export NOTION_DATABASE_ID="your_database_id"
export NOTION_MAP_EMBED_URL="your_notion_map_url"
```

## Usage

### Running the Flask App

```bash
python3 main.py
```

The app will start on `http://localhost:5000`

### Endpoints

- **`GET /`** - Widget generator interface
- **`POST /generate`** - Generate a new widget with custom parameters
- **`GET /refresh`** or **`POST /refresh`** - Refresh the widget using environment variables
- **`GET /widget`** - Serve the generated widget HTML

### Generating a Widget

1. Visit `http://localhost:5000` in your browser
2. Enter your Notion API credentials
3. Click "Generate Widget"
4. Copy the generated HTML code
5. Paste it into your website

### Using the Widget

The generated widget is a standalone HTML file that can be:

- Embedded via `<iframe>` on your website
- Used as a standalone page
- Hosted on any web server

Example embed code:

```html
<iframe
  src="http://your-server/widget"
  style="width:100%;height:600px;border:none;"
  allowfullscreen
>
</iframe>
```

## How It Works

1. **Fetch**: The application uses BeautifulSoup4 to fetch the Notion map view page from the URL specified in `NOTION_MAP_EMBED_URL`
2. **Parse**: Extracts the map content and page structure
3. **Generate**: Creates an embeddable HTML widget with responsive design
4. **Serve**: Makes the widget available via HTTP endpoints

The widget uses an iframe to embed the Notion map view, ensuring:

- Full functionality of Notion's map features
- Proper rendering without JavaScript conflicts
- Responsive design that works on all devices

## Files

- `main.py` - Main Flask application
- `public/widget.html` - Generated widget output
- `.env` - Environment configuration
- `test_fetch.py` - Test script for Notion map fetching
- `ukraine_settlements.py` - Manual mapping of Ukrainian settlements to coordinates

## Configuration

### Geocoding Services

The application uses a multi-tier geocoding approach for best Ukrainian address coverage:

1. **Manual Mapping** (`ukraine_settlements.py`) - Fastest, most reliable for known places. Contains 400+ Ukrainian cities and villages with pre-defined coordinates.

2. **Google Geocoding API** (optional but recommended) - Best coverage for Ukrainian addresses. Set `GOOGLE_MAPS_API_KEY` in your `.env` file.

3. **OpenStreetMap Nominatim** - Free fallback service.

#### Setting up Google Geocoding API

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new project or select an existing one
3. Enable the "Geocoding API"
4. Create an API key
5. Add to your `.env` file:
   ```bash
   GOOGLE_MAPS_API_KEY=your_api_key_here
   ```

#### Adding Custom Settlements

If a location isn't being geocoded correctly, add it to `ukraine_settlements.py`:

```python
UKRAINE_SETTLEMENTS = {
    # ... existing entries ...
    "your settlement name": (latitude, longitude),
}
```

### Widget Modes

The application supports embedding Notion map views. The widget uses an iframe approach which is the most reliable method for embedding Notion content.

### Automatic Refresh

The app includes a background scheduler that automatically refreshes the widget daily at midnight. This ensures your widget always shows the latest data from Notion.

## Testing

Run the test script to verify Notion map fetching:

```bash
python3 test_fetch.py
```

This will:

- Fetch the Notion map page
- Display page information (title, scripts, content size)
- Generate and show the iframe embed code

## Troubleshooting

### Import Errors

If you get "Unable to import" errors, make sure all dependencies are installed:

```bash
pip install beautifulsoup4 lxml --break-system-packages
```

### Notion Page Not Loading

- Ensure your `NOTION_MAP_EMBED_URL` is publicly accessible
- Check that the URL includes the view ID parameter
- Verify the Notion page permissions are set to "Public"

### Widget Not Displaying

- Check browser console for iframe/CORS errors
- Ensure the Notion page allows embedding
- Try opening the widget URL directly in a browser

## License

MIT License - feel free to use this for your projects!

## Credits

Built with:

- Flask - Web framework
- BeautifulSoup4 - HTML parsing
- Notion - Map data source
