import streamlit as st
import osmnx as ox
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import tempfile
import zipfile
import os
import io
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from shapely.geometry import Point, MultiPoint
from shapely.ops import unary_union
from scipy.spatial import Voronoi
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from shapely.geometry import Point, MultiPoint
from shapely.ops import unary_union
from shapely.geometry import Polygon as ShapelyPolygon

# Helper functions for road network analysis
def generate_points_along_lines(edges_gdf, spacing_miles=0.5):
    """
    Generate points along each road segment at specified spacing.
    
    Parameters:
    - edges_gdf: GeoDataFrame of road edges
    - spacing_miles: spacing between points in miles
    
    Returns:
    - GeoDataFrame of points
    """
    points = []
    edge_ids = []
    
    # Store original CRS
    original_crs = edges_gdf.crs
    
    # Project to a meter-based CRS if needed (use UTM or local projection)
    # For now, use Web Mercator (EPSG:3857) which is in meters
    if edges_gdf.crs and edges_gdf.crs.to_epsg() == 4326:
        # WGS84 (lat/lon) - need to reproject
        edges_projected = edges_gdf.to_crs(epsg=3857)
    else:
        edges_projected = edges_gdf.copy()
    
    # Convert miles to meters (1 mile = 1609.34 meters)
    spacing_meters = spacing_miles * 1609.34
    
    for idx, row in edges_projected.iterrows():
        line = row.geometry
        line_length = line.length  # in meters (now that we're projected)
        
        # Calculate number of points needed
        num_points = int(line_length / spacing_meters)
        
        if num_points > 0:
            for i in range(num_points + 1):
                distance = i * spacing_meters
                if distance <= line_length:
                    point = line.interpolate(distance)
                    points.append(point)
                    edge_ids.append(idx)
    
    if len(points) == 0:
        # Return empty GeoDataFrame with correct structure
        return gpd.GeoDataFrame({
            'edge_id': [],
            'geometry': []
        }, crs=original_crs)
    
    # Create GeoDataFrame in projected CRS
    points_gdf = gpd.GeoDataFrame({
        'edge_id': edge_ids,
        'geometry': points
    }, crs=edges_projected.crs)
    
    # Reproject back to original CRS
    if original_crs:
        points_gdf = points_gdf.to_crs(original_crs)
    
    return points_gdf

def create_cluster_polygons(points_gdf, n_clusters, edges_gdf):
    """
    Create polygons around clustered points using Voronoi diagrams.
    
    Parameters:
    - points_gdf: GeoDataFrame of points
    - n_clusters: number of clusters
    - edges_gdf: original edges for boundary
    
    Returns:
    - GeoDataFrame of cluster polygons
    """
    # Validate we have enough points
    if len(points_gdf) == 0:
        raise ValueError("No points generated. Try reducing the point spacing distance.")
    
    if len(points_gdf) < n_clusters:
        n_clusters = len(points_gdf)
    
    # Store original CRS
    original_crs = points_gdf.crs
    
    # Project to meter-based CRS for clustering
    if points_gdf.crs and points_gdf.crs.to_epsg() == 4326:
        points_projected = points_gdf.to_crs(epsg=3857)
        edges_projected = edges_gdf.to_crs(epsg=3857)
    else:
        points_projected = points_gdf.copy()
        edges_projected = edges_gdf.copy()
    
    # Perform k-means clustering on projected coordinates
    coords = np.array([[p.x, p.y] for p in points_projected.geometry])
    
    # Adjust n_clusters if we have very few points
    actual_clusters = min(n_clusters, len(points_projected))
    
    kmeans = KMeans(n_clusters=actual_clusters, random_state=42, n_init=10)
    points_projected['cluster'] = kmeans.fit_predict(coords)
    points_gdf['cluster'] = points_projected['cluster'].values
    
    # Get cluster centroids
    centroids = kmeans.cluster_centers_
    
    # Create polygons for each cluster based on the actual roads in that cluster
    polygons = []
    cluster_ids = []
    
    for cluster_id in range(actual_clusters):
        # Get all points in this cluster
        cluster_points = points_projected[points_projected['cluster'] == cluster_id]
        
        if len(cluster_points) < 3:
            continue
        
        # Get the edge IDs that belong to this cluster
        cluster_edge_ids = cluster_points['edge_id'].unique()
        cluster_edges = edges_projected[edges_projected.index.isin(cluster_edge_ids)]
        
        # Create a buffer around the roads in this cluster
        # Merge all road geometries and create a convex hull or buffer
        if len(cluster_edges) > 0:
            # Option 1: Convex hull around all roads in cluster
            all_coords = []
            for idx, edge in cluster_edges.iterrows():
                coords = list(edge.geometry.coords)
                all_coords.extend(coords)
            
            if len(all_coords) >= 3:
                # Create convex hull
                from shapely.geometry import MultiPoint
                multi_point = MultiPoint(all_coords)
                cluster_polygon = multi_point.convex_hull
                
                # Add small buffer to make it look nicer
                cluster_polygon = cluster_polygon.buffer(100)  # 100 meter buffer
                
                polygons.append(cluster_polygon)
                cluster_ids.append(cluster_id)
    
    # Create GeoDataFrame in projected CRS
    cluster_gdf = gpd.GeoDataFrame({
        'cluster_id': cluster_ids,
        'geometry': polygons
    }, crs=edges_projected.crs)
    
    # Reproject back to original CRS
    if original_crs:
        cluster_gdf = cluster_gdf.to_crs(original_crs)
    
    # Calculate stats for each cluster
    cluster_stats = []
    for cluster_id in range(actual_clusters):
        cluster_points = points_gdf[points_gdf['cluster'] == cluster_id]
        cluster_edges = edges_gdf[edges_gdf.index.isin(cluster_points['edge_id'])]
        
        stats = {
            'cluster_id': cluster_id,
            'num_points': len(cluster_points),
            'total_miles': cluster_edges['length_mi'].sum() if 'length_mi' in cluster_edges.columns else 0
        }
        cluster_stats.append(stats)
    
    stats_df = pd.DataFrame(cluster_stats)
    cluster_gdf = cluster_gdf.merge(stats_df, on='cluster_id', how='left')
    
    return cluster_gdf, points_gdf

def process_and_display_network(edges, nodes, enable_clustering=False, 
                                target_miles_per_cluster=50, point_spacing=0.5,
                                output_format="GeoJSON"):
    """
    Process network edges, optionally create clusters, display results and provide downloads.
    
    Returns the processed edges and cluster_gdf (if clustering enabled)
    """
    # Add miles field (convert meters to miles)
    edges['length_mi'] = edges['length'] / 1609.34
    total_miles = edges['length_mi'].sum()
    
    # Store in session state for persistent downloads
    st.session_state.edges = edges
    st.session_state.nodes = nodes
    
    # Display stats
    st.success("✅ Network extracted successfully!")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nodes", f"{len(nodes):,}")
    col2.metric("Edges", f"{len(edges):,}")
    col3.metric("Total Miles", f"{total_miles:.2f}")
    col4.metric("Total Length (km)", f"{edges['length'].sum()/1000:.2f}")
    
    # Perform clustering if enabled
    cluster_gdf = None
    points_gdf = None
    if enable_clustering:
        with st.spinner("Generating cluster analysis..."):
            try:
                # Calculate number of clusters
                n_clusters = max(1, int(np.ceil(total_miles / target_miles_per_cluster)))
                
                st.info(f"📊 Generating {n_clusters} clusters (Target: {target_miles_per_cluster} miles/cluster)")
                
                # Generate points along lines
                points_gdf = generate_points_along_lines(edges, spacing_miles=point_spacing)
                
                # Check if we have enough points
                if len(points_gdf) == 0:
                    st.warning(f"⚠️ No points generated with {point_spacing} mile spacing. Network may be too small or spacing too large. Try reducing point spacing.")
                elif len(points_gdf) < n_clusters:
                    st.warning(f"⚠️ Only {len(points_gdf)} points generated, but {n_clusters} clusters requested. Adjusting to {len(points_gdf)} clusters.")
                    n_clusters = len(points_gdf)
                
                if len(points_gdf) >= 2:  # Need at least 2 points to cluster
                    # Create cluster polygons
                    cluster_gdf, points_gdf = create_cluster_polygons(points_gdf, n_clusters, edges)
                    
                    # Store in session state
                    st.session_state.cluster_gdf = cluster_gdf
                    
                    # Display clustering stats
                    st.success(f"✅ Created {n_clusters} clusters")
                    
                    cluster_stats_display = st.expander("📈 View Cluster Statistics")
                    with cluster_stats_display:
                        st.dataframe(cluster_gdf[['cluster_id', 'total_miles']].sort_values('cluster_id'))
                else:
                    st.warning("⚠️ Not enough points for clustering. Continuing without clusters.")
                    st.session_state.cluster_gdf = None
                    
            except Exception as cluster_error:
                st.warning(f"⚠️ Clustering failed: {str(cluster_error)}. Continuing without clusters.")
                cluster_gdf = None
                st.session_state.cluster_gdf = None
    else:
        st.session_state.cluster_gdf = None
    
    # Create map
    st.subheader("Network Preview")
    map_center = [nodes.geometry.y.mean(), nodes.geometry.x.mean()]
    m = folium.Map(location=map_center, zoom_start=13)
    
    # Add cluster polygons if enabled
    if enable_clustering and cluster_gdf is not None:
        # Define color palette for clusters
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 
                 'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue', 
                 'darkpurple', 'pink', 'lightblue', 'lightgreen', 'gray', 
                 'black', 'lightgray']
        
        for idx, row in cluster_gdf.iterrows():
            color = colors[int(row['cluster_id']) % len(colors)]
            folium.GeoJson(
                row.geometry,
                style_function=lambda x, color=color: {
                    'fillColor': color,
                    'color': color,
                    'weight': 2,
                    'fillOpacity': 0.2
                },
                tooltip=f"Cluster {int(row['cluster_id'])}: {row['total_miles']:.1f} miles"
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
    
    # Use data from session state (persists across reruns)
    download_edges = st.session_state.edges if st.session_state.edges is not None else edges
    download_cluster_gdf = st.session_state.cluster_gdf
    
    with tempfile.TemporaryDirectory() as tmpdir:
        if output_format == "Shapefile":
            shp_path = os.path.join(tmpdir, "roads.shp")
            download_edges.to_file(shp_path, driver='ESRI Shapefile')
            
            # Zip the shapefile components
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                    file_path = os.path.join(tmpdir, f"roads{ext}")
                    if os.path.exists(file_path):
                        zipf.write(file_path, f"roads{ext}")
            
            zip_buffer.seek(0)
            st.download_button(
                label="📥 Download Roads Shapefile (ZIP)",
                data=zip_buffer,
                file_name="roads.zip",
                mime="application/zip",
                key="roads_shp"
            )
            
            # Add cluster download if enabled
            if enable_clustering and download_cluster_gdf is not None:
                cluster_shp_path = os.path.join(tmpdir, "clusters.shp")
                download_cluster_gdf.to_file(cluster_shp_path, driver='ESRI Shapefile')
                
                cluster_zip_buffer = io.BytesIO()
                with zipfile.ZipFile(cluster_zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                        file_path = os.path.join(tmpdir, f"clusters{ext}")
                        if os.path.exists(file_path):
                            zipf.write(file_path, f"clusters{ext}")
                
                cluster_zip_buffer.seek(0)
                st.download_button(
                    label="📥 Download Cluster Polygons Shapefile (ZIP)",
                    data=cluster_zip_buffer,
                    file_name="clusters.zip",
                    mime="application/zip",
                    key="clusters_shp"
                )
        
        elif output_format == "GeoJSON":
            geojson_str = download_edges.to_json()
            st.download_button(
                label="📥 Download Roads GeoJSON",
                data=geojson_str,
                file_name="roads.geojson",
                mime="application/json",
                key="roads_geojson"
            )
            
            # Add cluster download if enabled
            if enable_clustering and download_cluster_gdf is not None:
                cluster_geojson_str = download_cluster_gdf.to_json()
                st.download_button(
                    label="📥 Download Cluster Polygons GeoJSON",
                    data=cluster_geojson_str,
                    file_name="clusters.geojson",
                    mime="application/json",
                    key="clusters_geojson"
                )
        
        elif output_format == "GeoPackage":
            gpkg_path = os.path.join(tmpdir, "roads.gpkg")
            download_edges.to_file(gpkg_path, driver='GPKG', layer='roads')
            
            # Add clusters to same geopackage if enabled
            if enable_clustering and download_cluster_gdf is not None:
                download_cluster_gdf.to_file(gpkg_path, driver='GPKG', layer='clusters')
            
            with open(gpkg_path, 'rb') as f:
                gpkg_bytes = f.read()
            
            download_label = "📥 Download GeoPackage"
            if enable_clustering and download_cluster_gdf is not None:
                download_label += " (Roads + Clusters)"
            
            st.download_button(
                label=download_label,
                data=gpkg_bytes,
                file_name="roads.gpkg",
                mime="application/geopackage+sqlite3",
                key="roads_gpkg"
            )
    
    # Show attribute table sample
    with st.expander("📊 View Attribute Table (first 10 rows)"):
        display_cols = [col for col in edges.columns if col != 'geometry']
        st.dataframe(edges[display_cols].head(10))
    
    return edges, cluster_gdf

st.set_page_config(page_title="OSM Road Network Extractor", layout="wide")

# Configure OSMnx
ox.settings.use_cache = True
ox.settings.log_console = False

# Initialize session state for persistent data
if 'edges' not in st.session_state:
    st.session_state.edges = None
if 'nodes' not in st.session_state:
    st.session_state.nodes = None
if 'cluster_gdf' not in st.session_state:
    st.session_state.cluster_gdf = None

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

# Clustering options
st.sidebar.markdown("---")
st.sidebar.header("📊 Clustering Options")
enable_clustering = st.sidebar.checkbox("Enable Road Network Clustering", value=False, 
                                       help="Generate spatial clusters for dividing road networks")

if enable_clustering:
    point_spacing = st.sidebar.number_input("Point spacing (miles):", 
                                           min_value=0.1, max_value=5.0, 
                                           value=0.5, step=0.1,
                                           help="Distance between points along roads")
    
    target_miles_per_cluster = st.sidebar.number_input("Target miles per cluster:", 
                                                       min_value=1, max_value=1000, 
                                                       value=50, step=5,
                                                       help="Desired centerline miles in each cluster")

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
                    
                    # Process and display network
                    process_and_display_network(
                        edges, nodes, 
                        enable_clustering=enable_clustering,
                        target_miles_per_cluster=target_miles_per_cluster if enable_clustering else 50,
                        point_spacing=point_spacing if enable_clustering else 0.5,
                        output_format=output_format
                    )
                
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
                
                # Process and display network
                process_and_display_network(
                    edges, nodes,
                    enable_clustering=enable_clustering,
                    target_miles_per_cluster=target_miles_per_cluster if enable_clustering else 50,
                    point_spacing=point_spacing if enable_clustering else 0.5,
                    output_format=output_format
                )
            
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
                    
                    # Process and display network
                    process_and_display_network(
                        edges, nodes,
                        enable_clustering=enable_clustering,
                        target_miles_per_cluster=target_miles_per_cluster if enable_clustering else 50,
                        point_spacing=point_spacing if enable_clustering else 0.5,
                        output_format=output_format
                    )
                    
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