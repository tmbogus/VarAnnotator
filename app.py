# app.py

from flask import Flask, jsonify, request, send_from_directory
import pandas as pd
import logging
import json
import os

app = Flask(__name__, static_folder='static')

# Configure logging
logging.basicConfig(level=logging.INFO)

# Path to the pipeline status file
STATUS_FILE_PATH = "/shared/pipeline_status.json"

# Path to the annotated variants file
VARIANTS_FILE_PATH = "output/annotated_variants.tsv"

# Allowed columns for sorting
ALLOWED_SORT_COLUMNS = ["CHROM", "POS", "ID", "REF", "ALT", "Gene", "Frequency", "Population", "DP"]
ALLOWED_SORT_ORDERS = ["asc", "desc"]

# Load the annotated variants into a DataFrame
def load_variants(file_path):
    if not os.path.exists(file_path):
        return pd.DataFrame()  # Return empty DataFrame if file doesn't exist

    df = pd.read_csv(file_path, sep="\t", comment="#")

    # Parse the Frequency column
    def parse_frequency(freq_str):
        if pd.isnull(freq_str) or freq_str in ['N/A', 'NA']:
            return pd.NA, 'N/A'
        else:
            try:
                # Split by ' (' to separate frequency value and population
                parts = freq_str.split(' (')
                freq_value = float(parts[0].strip())
                population = parts[1].rstrip(')') if len(parts) > 1 else 'N/A'
                return freq_value, population
            except Exception as e:
                logging.error(f"Error parsing frequency '{freq_str}': {e}")
                return pd.NA, 'N/A'

    freq_parsed = df['Frequency'].apply(parse_frequency)
    df['Frequency'], df['Population'] = zip(*freq_parsed)
    df['Frequency'] = pd.to_numeric(df['Frequency'], errors='coerce')

    # Parse the DP column
    def parse_dp(dp_str):
        if pd.isnull(dp_str) or dp_str in ['N/A', 'NA']:
            return pd.NA
        else:
            try:
                dp_str = dp_str.strip('[]')
                dp_value = int(dp_str)
                return dp_value
            except Exception as e:
                logging.error(f"Error parsing DP '{dp_str}': {e}")
                return pd.NA

    df['DP'] = df['DP'].apply(parse_dp)

    return df

# Load variants data
variants_df = load_variants(VARIANTS_FILE_PATH)

# Helper function for parameter validation
def validate_query_param(param_value, param_name, expected_type, positive=False, min_value=None, max_value=None):
    if param_value is not None:
        try:
            value = expected_type(param_value)
            if positive and value < 1:
                raise ValueError
            if min_value is not None and value < min_value:
                raise ValueError
            if max_value is not None and value > max_value:
                raise ValueError
            return value
        except ValueError:
            if expected_type == float:
                type_name = 'float'
            elif expected_type == int:
                type_name = 'integer'
            else:
                type_name = expected_type.__name__
            message = f"Invalid query parameter: '{param_name}' must be a "
            if positive:
                message += f"positive {type_name}."
            elif min_value is not None and max_value is not None:
                message += f"{type_name} between {min_value} and {max_value}."
            elif min_value is not None:
                message += f"{type_name} greater than or equal to {min_value}."
            elif max_value is not None:
                message += f"{type_name} less than or equal to {max_value}."
            else:
                message += f"{type_name}."
            raise ValueError(message)
    return None

def validate_operator_param(param_value, param_name):
    allowed_values = ['le', 'ge', 'eq']
    if param_value not in allowed_values:
        raise ValueError(f"Invalid query parameter: '{param_name}' must be one of {allowed_values}.")
    return param_value

def apply_operator(series, operator, value):
    if operator == 'le':
        return series <= value
    elif operator == 'ge':
        return series >= value
    elif operator == 'eq':
        return series == value
    else:
        # Should not reach here if validation is correct
        raise ValueError(f"Invalid operator: {operator}")

@app.route("/variants", methods=["GET"])
def get_variants():
    try:
        # Get query parameters as strings
        frequency_str = request.args.get("frequency")
        frequency_operator = request.args.get("frequency_operator", default='le')
        depth_str = request.args.get("depth")
        depth_operator = request.args.get("depth_operator", default='ge')
        page_str = request.args.get("page", default='1')
        per_page_str = request.args.get("per_page", default='20')
        sort_column = request.args.get("sort_column")
        sort_order = request.args.get("sort_order", default='asc')

        # Validate operator parameters
        try:
            frequency_operator = validate_operator_param(frequency_operator, 'frequency_operator')
            depth_operator = validate_operator_param(depth_operator, 'depth_operator')
        except ValueError as ve:
            return jsonify({"message": str(ve)}), 400

        # Validate sort parameters
        if sort_column:
            if sort_column not in ALLOWED_SORT_COLUMNS:
                return jsonify({"message": f"Invalid sort_column. Allowed columns are: {ALLOWED_SORT_COLUMNS}."}), 400
        if sort_order:
            if sort_order not in ALLOWED_SORT_ORDERS:
                return jsonify({"message": f"Invalid sort_order. Allowed values are: {ALLOWED_SORT_ORDERS}."}), 400

        # Validate other parameters
        try:
            frequency = validate_query_param(
                frequency_str, 'frequency', float, min_value=0.0, max_value=1.0)
            depth = validate_query_param(
                depth_str, 'depth', int, min_value=0)
            page = validate_query_param(
                page_str, 'page', int, positive=True)
            per_page = validate_query_param(
                per_page_str, 'per_page', int, positive=True)
        except ValueError as ve:
            return jsonify({"message": str(ve)}), 400

        # Check pipeline status
        if os.path.exists(STATUS_FILE_PATH):
            with open(STATUS_FILE_PATH, 'r') as status_file:
                status_data = json.load(status_file)
            if status_data['status'] == 'running':
                return jsonify({"message": status_data['message']}), 202  # 202 Accepted
            elif status_data['status'] == 'failed':
                return jsonify({"message": status_data['message']}), 500  # 500 Internal Server Error
        else:
            # If status file doesn't exist, assume idle or no data
            if variants_df.empty:
                return jsonify({"message": "Pipeline has not been run yet."}), 503  # 503 Service Unavailable

        # Start with the full dataset
        filtered_variants = variants_df.copy()

        # Apply frequency filter if provided
        if frequency is not None:
            frequency_series = filtered_variants["Frequency"]
            frequency_mask = frequency_series.notna() & apply_operator(frequency_series, frequency_operator, frequency)
            filtered_variants = filtered_variants[frequency_mask]

        # Apply depth filter if provided
        if depth is not None:
            depth_series = filtered_variants["DP"]
            depth_mask = depth_series.notna() & apply_operator(depth_series, depth_operator, depth)
            filtered_variants = filtered_variants[depth_mask]

        # Apply sorting if provided
        if sort_column:
            ascending = True if sort_order == 'asc' else False
            filtered_variants = filtered_variants.sort_values(by=sort_column, ascending=ascending)

        # Pagination
        total_variants = len(filtered_variants)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_variants = filtered_variants.iloc[start:end].replace({pd.NA: None, float('nan'): None})

        # Prepare the response
        response = {
            "page": page,
            "per_page": per_page,
            "total_variants": total_variants,
            "variants": paginated_variants.to_dict(orient="records")
        }

        return jsonify(response)

    except Exception as e:
        logging.error(f"Error retrieving variants: {e}")
        return jsonify({"message": "Internal server error."}), 500

@app.route("/variants/<string:variant_id>", methods=["GET"])
def get_variant(variant_id):
    try:
        variant = variants_df[variants_df["ID"] == variant_id]
        if not variant.empty:
            # Replace NaN with None
            variant_dict = variant.to_dict(orient="records")[0]
            for key, value in variant_dict.items():
                if pd.isna(value):
                    variant_dict[key] = None
            return jsonify(variant_dict)
        else:
            return jsonify({"message": "Variant not found."}), 404
    except Exception as e:
        logging.error(f"Error retrieving variant {variant_id}: {e}")
        return jsonify({"message": "Internal server error."}), 500

@app.route("/status", methods=["GET"])
def get_status():
    try:
        if os.path.exists(STATUS_FILE_PATH):
            with open(STATUS_FILE_PATH, 'r') as status_file:
                status_data = json.load(status_file)
            return jsonify(status_data), 200
        else:
            if variants_df.empty:
                return jsonify({"status": "idle", "message": "Pipeline has not been run yet."}), 200
            else:
                return jsonify({"status": "completed", "message": "Pipeline has completed."}), 200
    except Exception as e:
        logging.error(f"Error retrieving pipeline status: {e}")
        return jsonify({"message": "Internal server error."}), 500

@app.route("/", methods=["GET"])
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')

@app.route("/<path:path>", methods=["GET"])
def serve_static_files(path):
    return send_from_directory(app.static_folder, path)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
