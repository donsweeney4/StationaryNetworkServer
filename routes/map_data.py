from quart import Blueprint, jsonify
from database import fetch_all_rows

bp = Blueprint('map_data', __name__)

@bp.route('/get_map_data')
async def get_map_data():
    try:
        query = "SELECT * FROM latest_sensor_meta_data;"
        rows = fetch_all_rows(query)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": "Internal Server Error"}), 500
