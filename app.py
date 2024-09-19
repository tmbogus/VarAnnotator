# app.py

from flask import Flask, jsonify, request
import pandas as pd

app = Flask(__name__)

# Load the annotated variants into a DataFrame
def load_variants(file_path):
    # Assuming the annotated variants are stored in a TSV file
    return pd.read_csv(file_path, sep="\t")

variants_df = load_variants("output/annotated_variants.tsv")

@app.route("/variants", methods=["GET"])
def get_variants():
    # Get query parameters for filtering
    frequency = request.args.get("frequency", type=float, default=None)
    depth = request.args.get("depth", type=int, default=None)

    # Filter variants by frequency and depth
    filtered_variants = variants_df
    if frequency is not None:
        filtered_variants = filtered_variants[filtered_variants["frequency"] <= frequency]
    if depth is not None:
        filtered_variants = filtered_variants[filtered_variants["DP"] >= depth]

    # Return the filtered variants as JSON
    return jsonify(filtered_variants.to_dict(orient="records"))

if __name__ == "__main__":
    app.run(debug=True)
