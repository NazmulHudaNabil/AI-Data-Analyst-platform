import os
import requests
import pandas as pd


class ETLTools:

    def __init__(self):
        pass

    def extract_load(self, url:str, output_folder:str, format:str):
        """
        This tool extracts the data from the API (url) and loads it into the
        the desired location (output_folder).

        Args:
            url (str): The API endpoint from which to extract data.
            output_folder (str): The folder where the extracted data will be saved.
        
        Returns:
            str: A message indicating the success or failure of the operation.

        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        output_folder = os.path.join(project_root, output_folder) 

        try:
            # Extract data from the API
            response = requests.get(url)
            response.raise_for_status() # Raise an error for bad responses
            data = response.json()

            file_name = os.path.join(output_folder, f"extracted_data.{format}")
            os.makedirs(output_folder, exist_ok=True)  # Create the output folder if it doesn't exist

            df = pd.json_normalize(data["results"])  # Normalize the JSON data into a flat table
            if format == "csv":
                df.to_csv(file_name, index=False)
            elif format == "json":
                df.to_json(file_name, orient='records', lines=True)
            elif format == "parquet":
                df.to_parquet(file_name, index=False)
            else:
                return f"Unsupported format: {format}. Please choose 'csv', 'json', or 'parquet'."

            return f"Data Sucessfully extracted and Saved to {file_name} in {format} format."

        except requests.exceptions.RequestException as e:
            return f"Error extracting data from API: {e}"


    def transform_load_context(self, file_paht:str):
        """
        This tool transforms the data from the extracted file and loads it into a context string.

        Args:
            file_path (str): The path to the extracted data file.
        Returns:
            str: A string representation of the transformed data suitable for use as context in a prompt.
        """

        file_extension = os.path.splitext(file_paht)[1].lower()

        if file_extension == ".csv":
            df = pd.read_csv(file_paht)
        elif file_extension == ".json":
            df = pd.read_json(file_paht, lines=True)
        elif file_extension == ".parquet":
            df = pd.read_parquet(file_paht)
        else:
            return f"Unsupported file format: {file_extension}. Please provide a CSV, JSON, or Parquet file."

        # Convert the DataFrame to a string representation
        top_3_rows = str(df.head(5))
        return top_3_rows


    def execute_code(self, code:str):
        """
        This tool executes the provided code and returns the output.

        Args:
            code (str): The code to be executed.
        Returns:
            str: The output of the executed code or an error message if execution fails.
        """
        try:
            exec(code)  # Execute on the my local environment
            return "Code executed successfully."
        except Exception as e:
            return f"Error executing code: {e}"




if __name__ == "__main__":
    etl_tool = ETLTools()
    url = "https://pokeapi.co/api/v2/pokemon?limit=10"
    output_folder = "data/extracted"
    format = "csv"

    # Extract and load data
    # result = etl_tool.extract_load(url, output_folder, format)
    # print(result)

    # Transform and load context
    # file_path = os.path.join(output_folder, f"extracted_data.{format}")
    # context = etl_tool.transform_load_context(file_path)
    # print("Transformed Context:")
    # print(context)

    # Execute some code
    code = "print('Hello, World!')"
    output = etl_tool.execute_code(code)
    print("Code Output:")
    print(output)