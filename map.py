import requests
import pandas as pd
import geopandas as gpd
from flask import Flask, render_template_string, jsonify, request
import threading
import time
import json
import logging

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)

api_key = 'e7a66c45669665ed6335c299f5e2a461e658737e'

census_url = f'https://api.census.gov/data/2020/dec/pl?get=P1_001N,NAME&for=county:*&key={api_key}'

live_number_url = 'https://nia-statistics.com/api/get?platform=youtube&type=channel&id=UCX6OQ3DkcsbYNE6H8uQQuVA'

html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>US Population by County</title>
    <style>
        body, html { margin: 0; padding: 0; height: 100%; font-family: Arial, sans-serif; }
        #map { height: 100%; }
        #controls { position: absolute; top: 10px; right: 10px; z-index: 1000; }
        .tooltip-content {
            font-size: 14px;
            line-height: 1.5;
        }
        .legend {
            line-height: 18px;
            color: #555;
            background: white;
            padding: 10px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
            border-radius: 5px;
            margin-bottom: 10px;
        }
        .legend i {
            width: 18px;
            height: 18px;
            float: left;
            margin-right: 8px;
            opacity: 0.7;
        }
        #sort-button, #toggle-map-button {
            padding: 10px 20px;
            font-size: 16px;
            cursor: pointer;
            border: none;
            border-radius: 5px;
            background-color: #007bff;
            color: white;
            margin-bottom: 10px;
            width: 150px;
        }
        #info-container {
            background: white;
            padding: 10px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
            border-radius: 5px;
            margin-bottom: 10px;
            width: auto;
        }
        .button-container {
            display: flex;
            justify-content: flex-end;
            gap: 10px; /* optional, for spacing between buttons */
        }
    </style>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <script>
        function formatNumber(num) {
            return num ? num.toLocaleString() : 'N/A';
        }

        var map;
        var geoJsonLayer;
        var ascending = false;
        var liveNumber = 0;
        var tileLayer;

        function initMap() {
            map = L.map('map').setView([37.8, -96], 4);
            tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }).addTo(map);

            fetchData();
            setInterval(fetchData, 10000);

            var legend = L.control({position: 'bottomright'});

            legend.onAdd = function (map) {
                var div = L.DomUtil.create('div', 'legend'),
                    grades = ["Population < Sub Count", "Population >= Sub Count", "Next County to Pass"],
                    colors = ["rgb(226, 69, 124)", "rgb(5, 166, 200)", "rgb(255, 165, 0)"];

                div.innerHTML = '<b>Legend</b><br>';
                for (var i = 0; i < grades.length; i++) {
                    div.innerHTML +=
                        '<i style="background:' + colors[i] + '"></i> ' +
                        grades[i] + '<br>';
                }
                return div;
            };

            legend.addTo(map);

            var infoContainer = L.control({position: 'bottomright'});

            infoContainer.onAdd = function (map) {
                var div = L.DomUtil.create('div', 'info-container');
                div.innerHTML = `
                    <div id="info-container"></div>
                    <div class="button-container">
                        <button id="sort-button" onclick="toggleSortOrder()">Toggle Sort Order</button>
                        <button id="toggle-map-button" onclick="toggleMapBackground()">Toggle Map Background</button>
                    </div>
                `;
                return div;
            };

            infoContainer.addTo(map);
        }

        function updateMap(data) {
            if (geoJsonLayer) {
                geoJsonLayer.eachLayer(function (layer) {
                    var props = layer.feature.properties;
                    var newProps = data.features.find(f => f.properties.County === props.County && f.properties.State === props.State).properties;
                    layer.setStyle({ fillColor: newProps.color });
                    layer.feature.properties.color = newProps.color; // Update the property in the layer's data
                    var stateName = newProps.StateName.split(', ')[1];
                    layer.bindTooltip(
                        '<div class="tooltip-content">' +
                        '<b>County:</b> ' + props.County + '<br>' +
                        '<b>State:</b> ' + stateName + '<br>' +
                        '<b>Population:</b> ' + formatNumber(props.P1_001N) + '<br>' +
                        '<b>Rank:</b> ' + formatNumber(props.rank) +
                        '</div>'
                    );
                });
            } else {
                geoJsonLayer = L.geoJSON(data, {
                    style: function (feature) {
                        return {
                            fillColor: feature.properties.color,
                            color: 'black',
                            weight: 0.5,
                            fillOpacity: 0.7
                        };
                    },
                    onEachFeature: function (feature, layer) {
                        var stateName = feature.properties.StateName.split(', ')[1];
                        layer.bindTooltip(
                            '<div class="tooltip-content">' +
                            '<b>County:</b> ' + feature.properties.County + '<br>' +
                            '<b>State:</b> ' + stateName + '<br>' +
                            '<b>Population:</b> ' + formatNumber(feature.properties.P1_001N) + '<br>' +
                            '<b>Rank:</b> ' + formatNumber(feature.properties.rank) +
                            '</div>'
                        );
                    }
                }).addTo(map);
            }
        }

        function fetchData() {
            fetch(`/data?ascending=${ascending}`)
                .then(response => response.json())
                .then(data => {
                    liveNumber = data.live_number;
                    updateMap(data.geojson_data);
                    updateInfoContainer(data);
                })
                .catch(error => console.error('Error fetching data:', error));
        }

        function updateInfoContainer(data) {
            const infoContainer = document.getElementById('info-container');
            const nextCounty = data.next_county;
            const percentPassed = ((data.counties_passed / data.total_counties) * 100).toFixed(2);
            infoContainer.innerHTML = `
                <b>Current Subscriber Count:</b> ${formatNumber(data.live_number)}<br>
                <b>Total Population Count:</b> ${formatNumber(data.total_population)}<br>
                <b>Current Counties Passed:</b> ${data.counties_passed} of ${data.total_counties} (${percentPassed}%)<br>
                <b>Next County to Pass:</b> ${nextCounty ? nextCounty.name : 'N/A'} (${formatNumber(nextCounty ? nextCounty.remaining_population : null )} remaining)<br>
                <b>Subscribers Left Until Map is Complete:</b> ${formatNumber(data.population_left)}
            `;
        }

        function toggleSortOrder() {
            ascending = !ascending;
            fetchData();
        }

        function toggleMapBackground() {
            if (map.hasLayer(tileLayer)) {
                map.removeLayer(tileLayer);
            } else {
                map.addLayer(tileLayer);
            }
        }

        window.onload = initMap;
    </script>
</head>
<body>
    <div id="map"></div>
</body>
</html>
"""

def fetch_live_number():
    response = requests.get(live_number_url)
    data = response.json()
    est_sub_count = data.get('estSubCount', 303500000)
    return est_sub_count

def fetch_population_data(ascending=False):
    response = requests.get(census_url)
    data = response.json()

    columns = data[0]
    data_rows = data[1:]
    df = pd.DataFrame(data_rows, columns=columns)
    df['P1_001N'] = pd.to_numeric(df['P1_001N'])
    df = df.sort_values(by='P1_001N', ascending=ascending)
    return df

def generate_map(df, live_number):
    df['cumulative_population'] = df['P1_001N'].cumsum()
    df['color'] = df['cumulative_population'].apply(lambda x: 'rgb(226, 69, 124)' if x < live_number else 'rgb(5, 166, 200)')
    
    next_county = df[df['cumulative_population'] >= live_number].iloc[0]
    next_county_index = df.index[df['cumulative_population'] >= live_number][0]
    df.at[next_county_index, 'color'] = 'rgb(255, 165, 0)'  # Highlight next county to pass

    df['rank'] = df['P1_001N'].rank(method='min', ascending=True)

    shapefile_path = 'cb_2020_us_county_20m/cb_2020_us_county_20m.shp'
    gdf = gpd.read_file(shapefile_path)
    gdf = gdf.merge(df, left_on=['STATEFP', 'COUNTYFP'], right_on=['state', 'county'], how='left')
    gdf = gdf.rename(columns={"NAME_x": "County", "state": "State", "NAME_y": "StateName"})

    geojson = json.loads(gdf.to_json())
    return geojson

@app.route('/')
def index():
    return render_template_string(html_template)

@app.route('/data')
def data():
    try:
        ascending = request.args.get('ascending', 'true').lower() == 'true'
        live_number = fetch_live_number()
        df = fetch_population_data(ascending=ascending)
        geojson_data = generate_map(df, live_number)
        
        counties_passed = df[df['cumulative_population'] < live_number].shape[0]
        next_county_row = df[df['cumulative_population'] >= live_number].iloc[0]
        remaining_population = next_county_row['P1_001N'] - (live_number - df[df['cumulative_population'] < live_number]['P1_001N'].sum())
        next_county = {'name': next_county_row['NAME'], 'remaining_population': int(remaining_population)}
        population_left = df['P1_001N'].sum() - live_number
        total_population = df['P1_001N'].sum()
        total_counties = len(df)
        
        response_data = {
            'live_number': int(live_number),
            'total_population': int(total_population),
            'counties_passed': int(counties_passed),
            'total_counties': total_counties,
            'next_county': next_county,
            'population_left': int(population_left),
            'geojson_data': geojson_data
        }
        
        return jsonify(response_data)
    except Exception as e:
        app.logger.error(f"Error generating data: {e}")
        print(f"Error generating data: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

def update_map_periodically():
    while True:
        with app.test_request_context():
            app.preprocess_request()
        time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=update_map_periodically).start()
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
