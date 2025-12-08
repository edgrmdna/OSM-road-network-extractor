# OSM Road Network Extractor

A Streamlit web application for extracting OpenStreetMap road networks by place name or polygon boundary.

## Features

- 🗺️ Extract road networks by place name (e.g., "El Segundo, California, USA")
- 📤 Upload custom polygon boundaries (Shapefile, GeoJSON, GeoPackage)
- 🚗 Multiple network types: Drive, Walk, Bike, or All
- 📥 Export as Shapefile, GeoJSON, or GeoPackage
- 🗺️ Interactive map preview
- 📊 Network statistics and attribute table preview

## Local Setup

### Prerequisites

- Python 3.8 or higher
- pip

### Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the app:
```bash
streamlit run osm_extractor_app.py
```

4. Open your browser to `http://localhost:8501`

## Deployment to Streamlit Cloud (FREE!)

### Step 1: Prepare Your Repository

1. Create a new GitHub repository

2. Upload these files:
   - `osm_extractor_app.py`
   - `requirements.txt`
   - `README.md`

3. Commit and push to GitHub

### Step 2: Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)

2. Click "New app"

3. Connect your GitHub account (if not already connected)

4. Select:
   - Repository: `your-username/your-repo-name`
   - Branch: `main` (or `master`)
   - Main file path: `osm_extractor_app.py`

5. Click "Deploy!"

6. Wait 2-5 minutes for deployment

7. Your app will be live at: `https://your-app-name.streamlit.app`

### That's it! 🎉

Your app is now publicly accessible and will auto-update when you push changes to GitHub.

## Usage

### Extract by Place Name

1. Select "Place Name" in the sidebar
2. Choose network type (Drive, Walk, Bike, All)
3. Choose output format
4. Enter a place name (city, neighborhood, address)
5. Click "Extract Network"
6. View the map preview and download your data

### Extract by Polygon Upload

1. Select "Upload Polygon" in the sidebar
2. Choose network type and output format
3. Upload your boundary file:
   - Shapefile: Upload as .zip containing .shp, .shx, .dbf, .prj files
   - GeoJSON: Upload .geojson file
   - GeoPackage: Upload .gpkg file
4. Click "Extract Network"
5. View results and download

## Network Types

- **Drive**: Drivable roads only (cars, trucks)
- **Walk**: Pedestrian paths and walkways
- **Bike**: Cycling routes and bike lanes
- **All**: Complete network (all road types)

## Output Formats

- **GeoJSON**: Web-friendly, works great with web mapping libraries
- **Shapefile**: Industry standard for GIS, works with ArcGIS/QGIS
- **GeoPackage**: Modern open standard, single file format

## Tips

- For large areas, extraction may take 1-2 minutes
- Be specific with place names (include city, state, country)
- Polygon files should contain valid polygon geometries
- The map preview shows a sample of edges for performance

## Data Source

All road network data comes from [OpenStreetMap](https://www.openstreetmap.org/), a collaborative project to create a free editable map of the world.

## Built With

- [Streamlit](https://streamlit.io/) - Web framework
- [OSMnx](https://osmnx.readthedocs.io/) - Python package for street networks
- [GeoPandas](https://geopandas.org/) - Spatial data manipulation
- [Folium](https://python-visualization.github.io/folium/) - Interactive maps

## Troubleshooting

**"No results found for place name"**
- Try being more specific (add city, state, country)
- Check spelling
- Try alternative names

**"Invalid polygon geometry"**
- Ensure your file contains valid polygon features
- Check that the file isn't corrupted
- Try converting to GeoJSON first

**App is slow/timing out**
- Large areas take longer to process
- Try extracting smaller regions
- Consider using the polygon method for precise boundaries

## License

This project uses OpenStreetMap data which is © OpenStreetMap contributors and available under the Open Database License (ODbL).

## Support

For issues or questions:
1. Check the tips section above
2. Review OSMnx documentation
3. Open an issue on GitHub
