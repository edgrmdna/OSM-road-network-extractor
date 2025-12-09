import streamlit as st
import osmnx as ox
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import tempfile
import zipfile
import os
import io

st.set_page_config(page_title="OSM Road Network Extractor", layout="wide")

# Configure OSMnx
ox.settings.use_cache = True
ox.settings.log_console = False

st.title("🗺️ OpenStreetMap Road Network Extractor")
st.markdown("Extract road networks by place name or upload a boundary polygon")

# Sidebar for inputs
st.sidebar.header("Configuration")
extraction_method = st.sidebar.radio("Choose extraction method:", 
                                     ["Place Name", "Bounding Box (Coordinates)", "Upload Polygon"])

network_type = st.sidebar.selectbox("Network Type:", 
                                    ["drive", "walk", "bike", "all"],
                                    help="Drive: car roads only | Walk: pedestrian paths | Bike: cycling routes | All: everything")

output_format = st.sidebar.selectbox("Output Format:",
                                     ["GeoJSON", "Shapefile", "GeoPackage"])

# Main content area
if extraction_method == "Place Name":
    st.subheader("Extract by Place Name")
    
    st.info("💡 **Place Name Tips:** Be specific! Use format like 'City, State, Country' (e.g., 'Manhattan, New York, USA' or 'Downtown Los Angeles, California, USA')")
    
    place_name = st.text_input("Enter place name:", 
                               placeholder="e.g., El Segundo, California, USA",
                               help="Format: City/Neighborhood, State, Country")
    
    # Add examples in an expander
    with st.expander("📝 See example place names that work well"):
        st.markdown("""
        **Cities:**
        - `Manhattan, New York, USA`
        - `San Francisco, California, USA`
        - `Chicago, Illinois, USA`
        
        **Neighborhoods:**
        - `Downtown Los Angeles, California, USA`
        - `Brooklyn Heights, New York, USA`
        - `Georgetown, Washington DC, USA`
        
        **Specific Areas:**
        - `UCLA, Los Angeles, California, USA`
        - `Golden Gate Park, San Francisco, California, USA`
        - `Times Square, Manhattan, New York, USA`
        
        **Tips:**
        - Always include state/province and country
        - Use official names (check OpenStreetMap.org)
        - Avoid abbreviations when possible
        """)
    
    if st.button("🚀 Extract Network", type="primary"):
        if place_name:
            with st.spinner(f"Searching for '{place_name}'..."):
                try:
                    # Try to geocode first to verify the place exists
                    try:
                        location = ox.geocode(place_name)
                        st.success(f"✓ Found location at coordinates: {location[0]:.4f}, {location[1]:.4f}")
                    except Exception as geocode_error:
                        st.error(f"❌ Could not find '{place_name}'")
                        st.warning("""
                        **Suggestions:**
                        - Check spelling and try again
                        - Add more detail: City, State, Country
                        - Try searching on [OpenStreetMap.org](https://www.openstreetmap.org) first
                        - Use the 'Upload Polygon' method instead for precise boundaries
                        """)
                        st.stop()
                    
                    # Download network
                    with st.spinner(f"Downloading road network..."):
                        G = ox.graph_from_place(place_name, network_type=network_type)
                        nodes, edges = ox.graph_to_gdfs(G)
                    
                    # Display stats
                    st.success("✅ Network extracted successfully!")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Nodes", f"{len(nodes):,}")
                    col2.metric("Edges", f"{len(edges):,}")
                    col3.metric("Total Length (km)", f"{edges['length'].sum()/1000:.2f}")
                    
                    # Create map
                    st.subheader("Network Preview")
                    map_center = [nodes.geometry.y.mean(), nodes.geometry.x.mean()]
                    m = folium.Map(location=map_center, zoom_start=13)
                    
                    # Sample edges if too many (for performance)
                    edges_to_plot = edges.sample(min(1000, len(edges)))
                    
                    # Add edges to map
                    for idx, row in edges_to_plot.iterrows():
                        coords = list(row.geometry.coords)
                        folium.PolyLine(
                            locations=[(coord[1], coord[0]) for coord in coords],
                            color='blue',
                            weight=2,
                            opacity=0.6
                        ).add_to(m)
                    
                    if len(edges) > 1000:
                        st.info(f"📍 Showing 1,000 of {len(edges):,} edges for performance")
                    
                    folium_static(m, width=700, height=500)
                    
                    # Prepare download
                    st.subheader("Download Your Data")
                    
                    with tempfile.TemporaryDirectory() as tmpdir:
                        if output_format == "Shapefile":
                            shp_path = os.path.join(tmpdir, "roads.shp")
                            edges.to_file(shp_path, driver='ESRI Shapefile')
                            
                            # Zip the shapefile components
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                                    file_path = os.path.join(tmpdir, f"roads{ext}")
                                    if os.path.exists(file_path):
                                        zipf.write(file_path, f"roads{ext}")
                            
                            zip_buffer.seek(0)
                            st.download_button(
                                label="📥 Download Shapefile (ZIP)",
                                data=zip_buffer,
                                file_name="roads.zip",
                                mime="application/zip"
                            )
                        
                        elif output_format == "GeoJSON":
                            geojson_str = edges.to_json()
                            st.download_button(
                                label="📥 Download GeoJSON",
                                data=geojson_str,
                                file_name="roads.geojson",
                                mime="application/json"
                            )
                        
                        elif output_format == "GeoPackage":
                            gpkg_path = os.path.join(tmpdir, "roads.gpkg")
                            edges.to_file(gpkg_path, driver='GPKG')
                            
                            with open(gpkg_path, 'rb') as f:
                                gpkg_bytes = f.read()
                            
                            st.download_button(
                                label="📥 Download GeoPackage",
                                data=gpkg_bytes,
                                file_name="roads.gpkg",
                                mime="application/geopackage+sqlite3"
                            )
                    
                    # Show attribute table sample
                    with st.expander("📊 View Attribute Table (first 10 rows)"):
                        display_cols = [col for col in edges.columns if col != 'geometry']
                        st.dataframe(edges[display_cols].head(10))
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    st.info("💡 Try a more specific place name or check your spelling")
        else:
            st.warning("⚠️ Please enter a place name")

elif extraction_method == "Bounding Box (Coordinates)":
    st.subheader("Extract by Bounding Box")
    
    st.info("💡 **Tip:** Get coordinates from [bboxfinder.com](http://bboxfinder.com) or [OpenStreetMap.org](https://www.openstreetmap.org)")
    
    col1, col2 = st.columns(2)
    with col1:
        north = st.number_input("North Latitude:", value=34.0, format="%.6f", help="Northern boundary")
        south = st.number_input("South Latitude:", value=33.9, format="%.6f", help="Southern boundary")
    with col2:
        east = st.number_input("East Longitude:", value=-118.3, format="%.6f", help="Eastern boundary")
        west = st.number_input("West Longitude:", value=-118.4, format="%.6f", help="Western boundary")
    
    # Show bbox on mini map
    with st.expander("🗺️ Preview Bounding Box"):
        preview_map = folium.Map(location=[(north+south)/2, (east+west)/2], zoom_start=11)
        folium.Rectangle(
            bounds=[[south, west], [north, east]],
            color='red',
            fill=True,
            fillOpacity=0.2
        ).add_to(preview_map)
        folium_static(preview_map, width=600, height=400)
    
    if st.button("🚀 Extract Network", type="primary"):
        # Validate bbox
        if north <= south:
            st.error("❌ North latitude must be greater than South latitude")
            st.stop()
        if east <= west:
            st.error("❌ East longitude must be greater than West longitude")
            st.stop()
        
        with st.spinner(f"Downloading road network for bounding box..."):
            try:
                # Download network
                G = ox.graph_from_bbox(north, south, east, west, network_type=network_type)
                nodes, edges = ox.graph_to_gdfs(G)
                
                # Display stats
                st.success("✅ Network extracted successfully!")
                col1, col2, col3 = st.columns(3)
                col1.metric("Nodes", f"{len(nodes):,}")
                col2.metric("Edges", f"{len(edges):,}")
                col3.metric("Total Length (km)", f"{edges['length'].sum()/1000:.2f}")
                
                # Create map
                st.subheader("Network Preview")
                map_center = [nodes.geometry.y.mean(), nodes.geometry.x.mean()]
                m = folium.Map(location=map_center, zoom_start=13)
                
                # Add bounding box
                folium.Rectangle(
                    bounds=[[south, west], [north, east]],
                    color='red',
                    fill=False,
                    weight=2
                ).add_to(m)
                
                # Sample edges if too many (for performance)
                edges_to_plot = edges.sample(min(1000, len(edges)))
                
                # Add edges to map
                for idx, row in edges_to_plot.iterrows():
                    coords = list(row.geometry.coords)
                    folium.PolyLine(
                        locations=[(coord[1], coord[0]) for coord in coords],
                        color='blue',
                        weight=2,
                        opacity=0.6
                    ).add_to(m)
                
                if len(edges) > 1000:
                    st.info(f"📍 Showing 1,000 of {len(edges):,} edges for performance")
                
                folium_static(m, width=700, height=500)
                
                # Prepare download
                st.subheader("Download Your Data")
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    if output_format == "Shapefile":
                        shp_path = os.path.join(tmpdir, "roads.shp")
                        edges.to_file(shp_path, driver='ESRI Shapefile')
                        
                        # Zip the shapefile components
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                            for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                                file_path = os.path.join(tmpdir, f"roads{ext}")
                                if os.path.exists(file_path):
                                    zipf.write(file_path, f"roads{ext}")
                        
                        zip_buffer.seek(0)
                        st.download_button(
                            label="📥 Download Shapefile (ZIP)",
                            data=zip_buffer,
                            file_name="roads.zip",
                            mime="application/zip"
                        )
                    
                    elif output_format == "GeoJSON":
                        geojson_str = edges.to_json()
                        st.download_button(
                            label="📥 Download GeoJSON",
                            data=geojson_str,
                            file_name="roads.geojson",
                            mime="application/json"
                        )
                    
                    elif output_format == "GeoPackage":
                        gpkg_path = os.path.join(tmpdir, "roads.gpkg")
                        edges.to_file(gpkg_path, driver='GPKG')
                        
                        with open(gpkg_path, 'rb') as f:
                            gpkg_bytes = f.read()
                        
                        st.download_button(
                            label="📥 Download GeoPackage",
                            data=gpkg_bytes,
                            file_name="roads.gpkg",
                            mime="application/geopackage+sqlite3"
                        )
                
                # Show attribute table sample
                with st.expander("📊 View Attribute Table (first 10 rows)"):
                    display_cols = [col for col in edges.columns if col != 'geometry']
                    st.dataframe(edges[display_cols].head(10))
            
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.info("💡 Try a smaller bounding box or check your coordinates")

elif extraction_method == "Upload Polygon":
    st.subheader("Extract by Polygon Upload")
    st.markdown("Upload a boundary file (Shapefile as .zip, GeoJSON, or GeoPackage)")
    
    uploaded_file = st.file_uploader("Choose a file", 
                                     type=['zip', 'geojson', 'gpkg'],
                                     help="Your polygon will be used as the boundary for extraction")
    
    if uploaded_file and st.button("🚀 Extract Network", type="primary"):
        with st.spinner("Processing polygon and downloading network..."):
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    # Save uploaded file
                    if uploaded_file.name.endswith('.zip'):
                        zip_path = os.path.join(tmpdir, "boundary.zip")
                        with open(zip_path, 'wb') as f:
                            f.write(uploaded_file.read())
                        
                        # Extract zip
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(tmpdir)
                        
                        # Find .shp file
                        shp_files = [f for f in os.listdir(tmpdir) if f.endswith('.shp')]
                        if shp_files:
                            boundary_path = os.path.join(tmpdir, shp_files[0])
                        else:
                            st.error("❌ No shapefile found in zip")
                            st.stop()
                    else:
                        boundary_path = os.path.join(tmpdir, uploaded_file.name)
                        with open(boundary_path, 'wb') as f:
                            f.write(uploaded_file.read())
                    
                    # Read boundary
                    boundary = gpd.read_file(boundary_path)
                    
                    # Show boundary info
                    st.info(f"📍 Boundary loaded: {len(boundary)} feature(s), CRS: {boundary.crs}")
                    
                    # Use first feature if multiple
                    polygon = boundary.geometry.iloc[0]
                    
                    # Download network
                    G = ox.graph_from_polygon(polygon, network_type=network_type)
                    nodes, edges = ox.graph_to_gdfs(G)
                    
                    # Display stats
                    st.success("✅ Network extracted successfully!")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Nodes", f"{len(nodes):,}")
                    col2.metric("Edges", f"{len(edges):,}")
                    col3.metric("Total Length (km)", f"{edges['length'].sum()/1000:.2f}")
                    
                    # Create map
                    st.subheader("Network Preview")
                    map_center = [nodes.geometry.y.mean(), nodes.geometry.x.mean()]
                    m = folium.Map(location=map_center, zoom_start=13)
                    
                    # Add boundary to map
                    folium.GeoJson(
                        boundary,
                        style_function=lambda x: {
                            'fillColor': 'transparent',
                            'color': 'red',
                            'weight': 3
                        }
                    ).add_to(m)
                    
                    # Sample edges if too many
                    edges_to_plot = edges.sample(min(1000, len(edges)))
                    
                    # Add edges to map
                    for idx, row in edges_to_plot.iterrows():
                        coords = list(row.geometry.coords)
                        folium.PolyLine(
                            locations=[(coord[1], coord[0]) for coord in coords],
                            color='blue',
                            weight=2,
                            opacity=0.6
                        ).add_to(m)
                    
                    if len(edges) > 1000:
                        st.info(f"📍 Showing 1,000 of {len(edges):,} edges for performance")
                    
                    folium_static(m, width=700, height=500)
                    
                    # Prepare download
                    st.subheader("Download Your Data")
                    
                    if output_format == "Shapefile":
                        shp_path = os.path.join(tmpdir, "roads.shp")
                        edges.to_file(shp_path, driver='ESRI Shapefile')
                        
                        # Zip the shapefile components
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                            for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                                file_path = os.path.join(tmpdir, f"roads{ext}")
                                if os.path.exists(file_path):
                                    zipf.write(file_path, f"roads{ext}")
                        
                        zip_buffer.seek(0)
                        st.download_button(
                            label="📥 Download Shapefile (ZIP)",
                            data=zip_buffer,
                            file_name="roads.zip",
                            mime="application/zip"
                        )
                    
                    elif output_format == "GeoJSON":
                        geojson_str = edges.to_json()
                        st.download_button(
                            label="📥 Download GeoJSON",
                            data=geojson_str,
                            file_name="roads.geojson",
                            mime="application/json"
                        )
                    
                    elif output_format == "GeoPackage":
                        gpkg_path = os.path.join(tmpdir, "roads.gpkg")
                        edges.to_file(gpkg_path, driver='GPKG')
                        
                        with open(gpkg_path, 'rb') as f:
                            gpkg_bytes = f.read()
                        
                        st.download_button(
                            label="📥 Download GeoPackage",
                            data=gpkg_bytes,
                            file_name="roads.gpkg",
                            mime="application/geopackage+sqlite3"
                        )
                    
                    # Show attribute table sample
                    with st.expander("📊 View Attribute Table (first 10 rows)"):
                        display_cols = [col for col in edges.columns if col != 'geometry']
                        st.dataframe(edges[display_cols].head(10))
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.info("💡 Make sure your file is a valid polygon geometry")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("""
💡 **About**

This tool extracts OpenStreetMap road networks using OSMnx.

**Network Types:**
- **Drive**: Drivable roads only
- **Walk**: Pedestrian paths
- **Bike**: Cycling routes
- **All**: Complete network

Data source: OpenStreetMap contributors
""")

st.sidebar.markdown("---")
st.sidebar.caption("Built with ❤️ using Streamlit & OSMnx")
