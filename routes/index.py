import logging
import plotly.graph_objs as go
import plotly.io as pio
from quart import Blueprint, render_template, jsonify
from datetime import datetime, timedelta
from utils.weather_data import fetch_QuestWeatherStation_data, generate_timestamps
from database import fetch_all_rows
import aiohttp
import asyncio

bp = Blueprint('index', __name__)

logger = logging.getLogger(__name__)

html_template = "index.html"  # Use template file

@bp.route('/')
async def index():
    try:
        traces_celsius = []
        traces_fahrenheit = []
        traces_windspeed = []

        # Calculate the timestamp for 21 days ago
        days_ago = datetime.now() - timedelta(days=21)
        days_ago_str = days_ago.strftime('%Y-%m-%d %H:%M:%S')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Loop through sensors Sensor1 to Sensor30
        for i in range(1, 31):
            sensorid = f'Sensor{i}'
            query = f"""
            SELECT t1.timestamp, t1.temperature, t2.owners_first_name
            FROM sensor_data t1
            INNER JOIN latest_sensor_meta_data t2 ON t1.sensorid = t2.sensor_name
            WHERE t1.sensorid = '{sensorid}' AND t1.timestamp >= '{days_ago_str}'
            ORDER BY t1.timestamp ASC;
            """
            rows = fetch_all_rows(query)

            logger.info(f"query for {sensorid}: {query}")

            if rows:
                # Extract data into lists
                timestamps = [row['timestamp'] for row in rows]
                temperatures_celsius = [row['temperature'] for row in rows]
                temperatures_fahrenheit = [c * 9/5 + 32 for c in temperatures_celsius]
                extended_name = sensorid + " (" + rows[0]['owners_first_name'] + ")"

                # Create a trace for the temperature data in Celsius
                trace_celsius = go.Scatter(
                    x=timestamps,
                    y=temperatures_celsius,
                    mode='lines',
                    name=extended_name
                )
                traces_celsius.append(trace_celsius)

                # Create a trace for the temperature data in Fahrenheit
                trace_fahrenheit = go.Scatter(
                    x=timestamps,
                    y=temperatures_fahrenheit,
                    mode='lines',
                    name=extended_name
                )
                traces_fahrenheit.append(trace_fahrenheit)
            else:
                logger.warning(f'No temperature data found for {sensorid}')

        # Fetch Quest Weather Station data asynchronously
        async with aiohttp.ClientSession() as session:
            tasks = []
            for start_timestamp, end_timestamp in generate_timestamps(days_ago, datetime.now()):
                tasks.append(fetch_QuestWeatherStation_data(session, start_timestamp, end_timestamp))

            responses = await asyncio.gather(*tasks)

        # Process Quest Weather Station data
        temperatures_api = []
        timestamps_api = []
        windspeed_api = []
        for data in responses:
            if data and 'sensors' in data:
                for sensor in data['sensors']:
                    for record in sensor['data']:
                        if 'temp_out' in record and 'ts' in record:
                            temperatures_api.append((record['temp_out'] - 32) / 1.8)
                            windspeed_api.append(record['wind_speed_avg'])
                            timestamps_api.append(datetime.fromtimestamp(record['ts']))

        # Debug output
        logger.debug(f"First few timestamps_api: {timestamps_api[:5]}")
        logger.debug(f"First few temperatures_api: {temperatures_api[:5]}")
        logger.debug(f"First few windspeed_api: {windspeed_api[:5]}")

        if not temperatures_api or not timestamps_api:
            logger.warning("No Quest Weather Station data found.")
        else:
            logger.debug(f"Quest Weather Station data: {len(temperatures_api)} records found.")

        # Add Quest Weather Station data to the traces
        if temperatures_api and timestamps_api:
            trace_quest_celsius = go.Scatter(
                x=timestamps_api,
                y=temperatures_api,
                mode='lines',
                name='Sensor51 (Quest Weather Station)'
            )
            traces_celsius.append(trace_quest_celsius)

            trace_quest_fahrenheit = go.Scatter(
                x=timestamps_api,
                y=[temp * 9/5 + 32 for temp in temperatures_api],
                mode='lines',
                name='Quest Weather Station'
            )
            traces_fahrenheit.append(trace_quest_fahrenheit)

            # Make the windspeed trace not visible on load
            trace_quest_windspeed = go.Scatter(
                x=timestamps_api,
                y=windspeed_api,
                mode='lines',
                name='Sensor51 (Quest Wind Speed)',
                yaxis='y2',  # Use secondary y-axis
                visible='legendonly'  # Start as hidden
            )
            traces_windspeed.append(trace_quest_windspeed)

            logger.debug("Quest Weather Station data added to traces.")
        else:
            logger.warning("Quest Weather Station data not added to traces due to missing data.")

        # Verify traces length
        logger.debug(f"Total sensor traces (Celsius): {len(traces_celsius)}")
        logger.debug(f"Total sensor traces (Fahrenheit): {len(traces_fahrenheit)}")
        logger.debug(f"Total sensor traces (Windspeed): {len(traces_windspeed)}")

        # Combine traces into a single figure for Celsius
        fig_celsius = go.Figure(data=traces_celsius + traces_windspeed)  # Add windspeed traces here
        fig_celsius.update_layout(
            title='Default Date Range is last 21 days (°C)',
            xaxis_title='Date/Time',
            yaxis=dict(
                title='Temperature (°C)',
                titlefont=dict(size=24, family='Arial', color='black', weight='bold'),
                tickfont=dict(size=12, family='Arial', color='black'),
            ),
            yaxis2=dict(
                title='Wind Speed (m/s)',  # Secondary y-axis
                titlefont=dict(size=24, family='Arial', color='black', weight='bold'),
                tickfont=dict(size=12, family='Arial', color='black'),
                overlaying='y',
                side='right'
            ),
            margin=dict(l=80, r=180, t=50, b=50),  # Adjust margins
            legend=dict(
                x=1.05,  # Move the legend outside the plot area
                y=0.5,
                xanchor='left',
                yanchor='middle',
                orientation='v',  # Vertical legend
                font=dict(size=10),
            ),
            legend_title='Sensors - click toggles visibility',
            showlegend=True,
            xaxis_range=[days_ago_str, now]
        )

        # Combine traces into a single figure for Fahrenheit
        fig_fahrenheit = go.Figure(data=traces_fahrenheit + traces_windspeed)  # Add windspeed traces here
        fig_fahrenheit.update_layout(
            title='Default Date Range is last 21 days (°F)',
            xaxis_title='Date/Time',
            yaxis=dict(
                title='Temperature (°F)',
                titlefont=dict(size=24, family='Arial', color='black', weight='bold'),
                tickfont=dict(size=12, family='Arial', color='black'),
            ),
            yaxis2=dict(
                title='Wind Speed (m/s)',  # Secondary y-axis
                titlefont=dict(size=24, family='Arial', color='black', weight='bold'),
                tickfont=dict(size=12, family='Arial', color='black'),
                overlaying='y',
                side='right'
            ),
            margin=dict(l=80, r=180, t=50, b=50),  # Adjust margins
            legend=dict(
                x=1.05,  # Move the legend outside the plot area
                y=0.5,
                xanchor='left',
                yanchor='middle',
                orientation='v',  # Vertical legend
                font=dict(size=10),
            ),
            legend_title='Sensors - click toggles visibility',
            showlegend=True,
            xaxis_range=[days_ago_str, now]
        )

        # Convert the figures to JSON for Plotly
        plot_data_celsius = pio.to_json(fig_celsius)
        plot_data_fahrenheit = pio.to_json(fig_fahrenheit)

        return await render_template(html_template, plot_data_celsius=plot_data_celsius, plot_data_fahrenheit=plot_data_fahrenheit)

    except Exception as e:
        logger.exception("Exception occurred in index route")
        return jsonify({"error": "Internal Server Error"}), 500
