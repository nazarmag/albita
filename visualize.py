import pandas as pd
import geopandas as gpd
import json
from sqlalchemy import inspect, text
from database.connection import engine
from utils.helpers import extract_table_name
import re

def visualize_data(user_input):
    try:
        table_name = extract_table_name(user_input)
        if not table_name:
            return "Could not determine the table name. Please specify the table name."

        column_match = re.search(r"of\s+the\s+(\w+)\s+values", user_input, re.IGNORECASE)
        if not column_match:
            return "Could not determine the column name. Please specify the column name."

        column_name = column_match.group(1)

        # Extract filter conditions if any
        filter_condition = None
        filter_match = re.search(r"where\s+(.+)", user_input, re.IGNORECASE)
        if filter_match:
            filter_condition = filter_match.group(1)

        # Build the query
        query = f"SELECT * FROM {table_name}"
        if filter_condition:
            query += f" WHERE {filter_condition}"

        print(f"Executing query: {query}")  # Debug output

        try:
            # Try to read as GeoDataFrame
            gdf = gpd.read_postgis(query, engine, geom_col=column_name, crs='EPSG:4326')

            # DEBUG CHECK 1: Check if GeoDataFrame is loaded correctly
            print(f"\n--- DEBUG CHECK 1: GeoDataFrame Info ---")
            print(f"Number of features: {len(gdf)}")
            print(f"Columns: {gdf.columns.tolist()}")
            print(f"CRS: {gdf.crs}")
            if len(gdf) > 0:
                print(f"First geometry type: {gdf.geometry.iloc[0].geom_type}")
                print(f"First geometry: {gdf.geometry.iloc[0]}")
            else:
                print("No geometries found in the result")

            if not gdf.empty and hasattr(gdf, 'geometry') and not gdf.geometry.isna().all():
                # Convert to GeoJSON
                geojson_data = json.loads(gdf.to_json())

                # DEBUG CHECK 2: Check GeoJSON output
                print(f"\n--- DEBUG CHECK 2: GeoJSON Sample ---")
                print(f"GeoJSON type: {type(geojson_data)}")
                if 'features' in geojson_data and len(geojson_data['features']) > 0:
                    print(f"Number of features in GeoJSON: {len(geojson_data['features'])}")
                    print(f"First feature geometry: {geojson_data['features'][0]['geometry']}")
                else:
                    print("No features found in GeoJSON")

                # Create HTML with Leaflet map
                map_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
                    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
                    <style>
                        #map {{ height: 500px; width: 100%; }}
                        .map-container {{ margin: 10px 0; }}
                    </style>
                </head>
                <body>
                    <h3>Visualization of {column_name} in {table_name}</h3>
                    {f"<p>Filtered by: {filter_condition}</p>" if filter_condition else ""}
                    <div class="map-container">
                        <div id="map"></div>
                    </div>
                    <script>
                        // Initialize the map
                        var map = L.map('map').setView([0, 0], 2);

                        // Add OpenStreetMap tiles
                        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        }}).addTo(map);

                        // Add GeoJSON layer
                        var geoJsonData = {json.dumps(geojson_data)};
                        console.log("GeoJSON data loaded:", geoJsonData); // Debug console log

                        var geoJsonLayer = L.geoJSON(geoJsonData, {{
                            style: function(feature) {{
                                return {{
                                    color: '#3388ff',
                                    weight: 2,
                                    opacity: 0.7,
                                    fillOpacity: 0.4
                                }};
                            }},
                            onEachFeature: function(feature, layer) {{
                                if (feature.properties) {{
                                    var popupContent = "<div style='max-width: 200px;'>";
                                    for (var key in feature.properties) {{
                                        if (key !== 'geom' && key !== 'geometry') {{
                                            popupContent += "<b>" + key + ":</b> " + feature.properties[key] + "<br>";
                                        }}
                                    }}
                                    popupContent += "</div>";
                                    layer.bindPopup(popupContent);
                                }}
                            }}
                        }}).addTo(map);

                        // Fit the map to the GeoJSON bounds
                        if (geoJsonLayer.getBounds && geoJsonLayer.getBounds().isValid()) {{
                            map.fitBounds(geoJsonLayer.getBounds());
                            console.log("Map bounds fitted to GeoJSON"); // Debug console log
                        }} else {{
                            // Default view if bounds are not valid
                            map.setView([0, 0], 2);
                            console.log("Using default map view"); // Debug console log
                        }}
                    </script>
                </body>
                </html>
                """
                return map_html
            else:
                return f"No geometries found in {table_name} for column {column_name}."
        except Exception as e:
            print(f"Error checking geometry column: {str(e)}")
            # If it's not a geometry column, proceed with regular data visualization
            pass

        # If not a geometry column, fetch data normally
        df = pd.read_sql(f"SELECT {column_name} FROM {table_name} LIMIT 1", engine)
        if df.empty:
            return f"No data found in {table_name} for column {column_name}."
        # Determine the column type based on the data
        column_type = str(df.dtypes[column_name]).lower()
        print(f"Column type detected: {column_type}")  # Debug output
        if 'object' in column_type or 'str' in column_type or 'text' in column_type:
            # For text data
            df_full = pd.read_sql(f"SELECT {column_name} FROM {table_name}", engine)
            values = df_full[column_name].dropna().unique()
            if len(values) > 20:
                values_list = "<ul>" + "".join(f"<li>{value}</li>" for value in values[:20]) + f"<li>... and {len(values) - 20} more</li>" + "</ul>"
            else:
                values_list = "<ul>" + "".join(f"<li>{value}</li>" for value in values) + "</ul>"
            return f"Unique values in {column_name} column of {table_name}: {values_list}"
        elif 'float' in column_type or 'double' in column_type or 'int' in column_type or 'numeric' in column_type:
            # For numeric data, show values
            df_full = pd.read_sql(f"SELECT {column_name} FROM {table_name}", engine)
            values = df_full[column_name].dropna().head(20)  # Show first 20 values
            values_list = "<ul>" + "".join(f"<li>{value:.4f}</li>" for value in values) + "</ul>"
            # Also show statistics
            stats = df_full[column_name].describe()
            stats_html = f"""
            <h4>Statistics:</h4>
            <ul>
                <li>Count: {stats['count']}</li>
                <li>Mean: {stats['mean']:.4f}</li>
                <li>Standard Deviation: {stats['std']:.4f}</li>
                <li>Minimum: {stats['min']:.4f}</li>
                <li>25%: {stats['25%']:.4f}</li>
                <li>50%: {stats['50%']:.4f}</li>
                <li>75%: {stats['75%']:.4f}</li>
                <li>Maximum: {stats['max']:.4f}</li>
            </ul>
            """
            return f"First 20 values in {column_name} column of {table_name}: {values_list}{stats_html}"
        else:
            # For other types, show sample values
            df_full = pd.read_sql(f"SELECT {column_name} FROM {table_name} LIMIT 10", engine)
            values_list = "<ul>" + "".join(f"<li>{str(value)}</li>" for value in df_full[column_name].dropna().values) + "</ul>"
            return f"Sample values in {column_name} column of {table_name}: {values_list}"
    except Exception as e:
        return f"Error visualizing data: {str(e)}"
