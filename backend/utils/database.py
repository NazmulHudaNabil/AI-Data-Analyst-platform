import psycopg2


class DatabaseUtils:
    def __init__(self, db_config_or_url):
        try:
            if isinstance(db_config_or_url, dict):
                self.connection = psycopg2.connect(**db_config_or_url)
            elif isinstance(db_config_or_url, str):
                self.connection = psycopg2.connect(db_config_or_url)
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            self.connection = None

    def schema_details(self, schema_name):
        schema_info_context = ""

        connetion = self.connection
        cursor = connetion.cursor()

        schema_info_context = f"Schema: {schema_name}\n\n"

        try:
            cursor.execute("SELECT table_name from information_schema.tables where table_schema = %s;", (schema_name,))
            table_list = cursor.fetchall()

            for table in table_list:
                table_name = table[0]
                schema_info_context = f"{schema_info_context}\nTable: {table_name}\n"

                # Adding Columns & Data Types
                cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s;", (table_name,))
                curlumns = cursor.fetchall()

                for column in curlumns:
                    column_name = column[0]
                    data_type = column[1]
                    schema_info_context = f"{schema_info_context}  - Column: {column_name}, Data Type: {data_type}\n"

                # Adding Sample Data
                cursor.execute(f"SELECT * FROM {schema_name}.{table_name} LIMIT 5;")
                sample_data = cursor.fetchall()
                schema_info_context = f"{schema_info_context}  - Sample Data:\n"
                for row in sample_data:
                    schema_info_context = f"{schema_info_context}    {row}\n"

        except Exception as e:
            print(f"Error retrieving schema details: {e}")
            schema_info_context = f"Error retrieving schema details: {e}\n"

        finally:
            if cursor:
                cursor.close()
            if connetion:
                connetion.close()

        return schema_info_context

    def execute_sql(self, sql_query):
        connetion = self.connection
        cursor = connetion.cursor()

        try:
            cursor.execute(sql_query)
            result = cursor.fetchall()
            connetion.commit()
            return str(result)
        except Exception as e:
            print(f"Error executing SQL query: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if connetion:
                connetion.close()




if __name__ == "__main__":

    obj = DatabaseUtils({
        "host": "localhost",
        "port": 5432,
        "user": "mdnazmulhudanabil",
        "password": "",
        "database": "ai_data_analyst_platform"
    })

    result = obj.schema_details("public")


    with open("test_schema_details.txt", "w") as file:
        file.write(result)
