1. The user opens the dashboard in a browser.
2. The Streamlit app loads and accepts a DM CSV upload.
3. The app calls the ingestion pipeline to read, clean, and validate the file.
4. The pipeline writes a Parquet file to the results staging directory when validation succeeds.
5. The app reports the output path and displays the uploaded data.
