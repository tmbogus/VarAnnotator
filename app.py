from flask import Flask, jsonify, request
import pandas as pd
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load the annotated variants into a DataFrame
def load_variants(file_path):
    df = pd.read_csv(file_path, sep="\t", comment="#")

    # Parse the Frequency column
    def parse_frequency(freq_str):
        if pd.isnull(freq_str) or freq_str in ['N/A', 'NA']:
            return pd.NA, 'N/A'
        else:
            try:
                parts = freq_str.split(' (Population: ')
                freq_value = float(parts[0])
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

variants_df = load_variants("output/annotated_variants.tsv")

@app.route("/variants", methods=["GET"])
def get_variants():
    try:
        # Get query parameters for filtering
        frequency = request.args.get("frequency", type=float)
        depth = request.args.get("depth", type=int)
        page = request.args.get("page", type=int, default=1)
        per_page = request.args.get("per_page", type=int, default=20)

        # Start with the full dataset
        filtered_variants = variants_df.copy()

        # Apply frequency filter if provided
        if frequency is not None:
            filtered_variants = filtered_variants[
                (filtered_variants["Frequency"].notna()) &
                (filtered_variants["Frequency"] <= frequency)
            ]

        # Apply depth filter if provided
        if depth is not None:
            filtered_variants = filtered_variants[
                (filtered_variants["DP"].notna()) &
                (filtered_variants["DP"] >= depth)
            ]

        # Pagination
        total_variants = len(filtered_variants)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_variants = filtered_variants.iloc[start:end]

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
        return jsonify({"message": "Internal server error"}), 500

@app.route("/variants/<string:variant_id>", methods=["GET"])
def get_variant(variant_id):
    try:
        variant = variants_df[variants_df["ID"] == variant_id]
        if not variant.empty:
            return jsonify(variant.to_dict(orient="records")[0])
        else:
            return jsonify({"message": "Variant not found"}), 404
    except Exception as e:
        logging.error(f"Error retrieving variant {variant_id}: {e}")
        return jsonify({"message": "Internal server error"}), 500

@app.route("/reload_data", methods=["POST"])
def reload_data():
    try:
        global variants_df
        variants_df = load_variants("output/annotated_variants.tsv")
        return jsonify({"message": "Data reloaded successfully"}), 200
    except Exception as e:
        logging.error(f"Error reloading data: {e}")
        return jsonify({"message": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(debug=True)
