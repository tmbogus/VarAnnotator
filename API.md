# VarAnnotator API Documentation
==============================

## Overview
------------
The VarAnnotator API provides access to annotated genetic variants obtained from VCF files. It allows users to retrieve variants, apply advanced filtering based on population frequency and depth (DP) with customizable operators, sort the results, paginate through large datasets, and retrieve detailed information about specific variants. Additionally, it offers an endpoint to check the status of the data processing pipeline.

## Base URL
-----------
```
http://localhost:5000/
```

## Endpoints
------------

### 1. GET `/variants`

Retrieve a list of annotated variants with advanced filtering, sorting, and pagination options.

#### URL
```
GET /variants
```

#### Query Parameters

- **frequency** (float, optional):  
  Maximum population frequency to filter variants. Only variants with a frequency less than or equal to this value are returned. Variants with missing frequency data are excluded when this parameter is provided.

- **frequency_operator** (string, optional, default=`le`):  
  Operator to apply to the frequency filter.  
  - Allowed values: `le` (≤), `ge` (≥), `eq` (=)

- **depth** (integer, optional):  
  Minimum depth (DP) value to filter variants. Only variants with a DP greater than or equal to this value are returned. Variants with missing DP values are excluded when this parameter is provided.

- **depth_operator** (string, optional, default=`ge`):  
  Operator to apply to the depth filter.  
  - Allowed values: `le` (≤), `ge` (≥), `eq` (=)

- **sort_column** (string, optional):  
  Column name to sort the variants by.  
  - Allowed values: `CHROM`, `POS`, `ID`, `REF`, `ALT`, `Gene`, `Frequency`, `Population`, `DP`

- **sort_order** (string, optional, default=`asc`):  
  Order to sort the results.  
  - Allowed values: `asc` (ascending), `desc` (descending)

- **page** (integer, optional, default=`1`):  
  Page number for pagination. Must be a positive integer.

- **per_page** (integer, optional, default=`20`):  
  Number of variants per page. Must be a positive integer.

#### Response
- **Status Codes:**
  - `200 OK`: Successful retrieval of variants.
  - `202 Accepted`: Pipeline is currently running; variants are not yet available.
  - `400 Bad Request`: Invalid query parameters.
  - `503 Service Unavailable`: Pipeline has not been run or completed without generating data.
  - `500 Internal Server Error`: An unexpected server error occurred.

- **Content Type:** `application/json`

- **Body:**
  ```json
  {
    "page": 1,
    "per_page": 20,
    "total_variants": 8990,
    "total_pages": 450,
    "variants": [
      {
        "CHROM": 1,
        "POS": 324822,
        "ID": "rs576317820",
        "REF": "A",
        "ALT": "T",
        "Gene": "RP4-669L17.10",
        "Frequency": 0.09906,
        "Population": "gnomADe:nfe",
        "DP": 152
      },
      // ... other variants
    ]
  }
  ```

#### Example Requests
- **Retrieve All Variants:**
  ```bash
  curl "http://localhost:5000/variants"
  ```

- **Retrieve Variants with Frequency ≤ 0.01:**
  ```bash
  curl "http://localhost:5000/variants?frequency=0.01&frequency_operator=le"
  ```

- **Retrieve Variants with DP ≥ 10:**
  ```bash
  curl "http://localhost:5000/variants?depth=10&depth_operator=ge"
  ```

- **Retrieve Variants with Frequency ≤ 0.01 and DP ≥ 10:**
  ```bash
  curl "http://localhost:5000/variants?frequency=0.01&frequency_operator=le&depth=10&depth_operator=ge"
  ```

- **Retrieve Variants Sorted by Position in Descending Order:**
  ```bash
  curl "http://localhost:5000/variants?sort_column=POS&sort_order=desc"
  ```

- **Retrieve Specific Page with Custom Page Size:**
  ```bash
  curl "http://localhost:5000/variants?page=2&per_page=50"
  ```

### 2. GET `/variants/<variant_id>`

Retrieve detailed information about a specific variant by its ID.

#### URL
```
GET /variants/<variant_id>
```

#### URL Parameters
- **variant_id** (string, required):  
  The ID of the variant (e.g., `rs576317820`).

#### Response
- **Status Codes:**
  - `200 OK`: Variant found and returned.
  - `404 Not Found`: Variant with the specified ID does not exist.
  - `503 Service Unavailable`: Variants data is not available.
  - `500 Internal Server Error`: An unexpected server error occurred.

- **Content Type:** `application/json`

- **Body:**
  ```json
  {
    "CHROM": 1,
    "POS": 324822,
    "ID": "rs576317820",
    "REF": "A",
    "ALT": "T",
    "Gene": "RP4-669L17.10",
    "Frequency": 0.09906,
    "Population": "gnomADe:nfe",
    "DP": 152
  }
  ```

#### Example Request
```bash
curl "http://localhost:5000/variants/rs576317820"
```

### 3. GET `/status`

Retrieve the current status of the data processing pipeline.

#### URL
```
GET /status
```

#### Response
- **Status Codes:**
  - `200 OK`: Successfully retrieved pipeline status.
  - `500 Internal Server Error`: An unexpected server error occurred.

- **Content Type:** `application/json`

- **Body:**
  - **Possible Responses:**
    - **Pipeline Running:**
      ```json
      {
        "status": "running",
        "message": "Pipeline is currently processing data."
      }
      ```
    - **Pipeline Completed:**
      ```json
      {
        "status": "completed",
        "message": "Pipeline has completed successfully."
      }
      ```
    - **Pipeline Failed:**
      ```json
      {
        "status": "failed",
        "message": "Pipeline encountered an error."
      }
      ```
    - **Pipeline Idle or Not Run:**
      ```json
      {
        "status": "idle",
        "message": "Pipeline has not been run yet."
      }
      ```

#### Example Request
```bash
curl "http://localhost:5000/status"
```

## Query Parameters Details
---------------------------

### `frequency`
- **Type:** `float`
- **Description:**  
  Maximum population frequency to filter variants. Only variants with a frequency less than or equal to this value are returned. Variants with missing frequency data are excluded when this parameter is provided.

### `frequency_operator`
- **Type:** `string`
- **Allowed Values:** `le` (≤), `ge` (≥), `eq` (=)
- **Default:** `le`
- **Description:**  
  Operator to apply to the frequency filter.

### `depth`
- **Type:** `integer`
- **Description:**  
  Minimum depth (DP) value to filter variants. Only variants with a DP greater than or equal to this value are returned. Variants with missing DP values are excluded when this parameter is provided.

### `depth_operator`
- **Type:** `string`
- **Allowed Values:** `le` (≤), `ge` (≥), `eq` (=)
- **Default:** `ge`
- **Description:**  
  Operator to apply to the depth filter.

### `sort_column`
- **Type:** `string`
- **Allowed Values:** `CHROM`, `POS`, `ID`, `REF`, `ALT`, `Gene`, `Frequency`, `Population`, `DP`
- **Description:**  
  Column name to sort the variants by.

### `sort_order`
- **Type:** `string`
- **Allowed Values:** `asc` (ascending), `desc` (descending)
- **Default:** `asc`
- **Description:**  
  Order to sort the results.

### `page`
- **Type:** `integer`
- **Default:** `1`
- **Description:**  
  The page number for pagination. Must be a positive integer.

### `per_page`
- **Type:** `integer`
- **Default:** `20`
- **Description:**  
  The number of variants per page. Must be a positive integer.

## Error Handling
-----------------

- **400 Bad Request**
  - **Condition:** Returned when query parameters have invalid types or values.
  - **Response Body:**
    ```json
    {
      "message": "Invalid query parameter: 'frequency' must be a float."
    }
    ```
    *Example Messages:*
    - `"Invalid query parameter: 'frequency' must be a float."`
    - `"Invalid query parameter: 'page' must be a positive integer."`
    - `"Invalid sort_column. Allowed columns are: ['CHROM', 'POS', 'ID', 'REF', 'ALT', 'Gene', 'Frequency', 'Population', 'DP']."`

- **404 Not Found**
  - **Condition:** Returned when a variant with the specified ID does not exist.
  - **Response Body:**
    ```json
    {
      "message": "Variant not found."
    }
    ```

- **202 Accepted**
  - **Condition:** Returned when the pipeline is currently running and variants data is not yet available.
  - **Response Body:**
    ```json
    {
      "message": "Pipeline is currently processing data."
    }
    ```

- **503 Service Unavailable**
  - **Condition:**  
    - Returned when the pipeline has not been run yet.
    - Returned when the pipeline has completed but no variants data is found.
  - **Response Body:**
    ```json
    {
      "message": "Pipeline has not been run yet."
    }
    ```
    or
    ```json
    {
      "message": "Pipeline has completed but no data found."
    }
    ```

- **500 Internal Server Error**
  - **Condition:** Returned when an unexpected error occurs on the server.
  - **Response Body:**
    ```json
    {
      "message": "Internal server error."
    }
    ```

## Examples
-----------

### Retrieve All Variants
```bash
curl "http://localhost:5000/variants"
```

### Retrieve Variants with Frequency ≤ 0.01
```bash
curl "http://localhost:5000/variants?frequency=0.01&frequency_operator=le"
```

### Retrieve Variants with DP ≥ 10
```bash
curl "http://localhost:5000/variants?depth=10&depth_operator=ge"
```

### Retrieve Variants with Frequency ≤ 0.01 and DP ≥ 10
```bash
curl "http://localhost:5000/variants?frequency=0.01&frequency_operator=le&depth=10&depth_operator=ge"
```

### Retrieve Variants Sorted by Gene in Descending Order
```bash
curl "http://localhost:5000/variants?sort_column=Gene&sort_order=desc"
```

### Retrieve Specific Variant by ID
```bash
curl "http://localhost:5000/variants/rs576317820"
```

### Check Pipeline Status
```bash
curl "http://localhost:5000/status"
```

## Notes
---------

- **Combined Filters:** When both `frequency` and `depth` filters are applied, only variants meeting both criteria are returned.
  
- **Pagination:** Pagination parameters (`page`, `per_page`) can be adjusted to navigate through large sets of variants. The response includes `total_pages` to facilitate navigation.
  
- **Sorting:** Variants can be sorted based on any allowed column using the `sort_column` and `sort_order` parameters.
  
- **Missing Data:** Variants with missing frequency or depth data are included when their respective filters are not applied.
  
- **Pipeline Status:** The `/status` endpoint provides real-time information about the data processing pipeline, ensuring users are aware of the data availability.

## Contact
-----------
For any questions or issues regarding the API, please contact the project maintainer.

---

**End of Documentation**