import os
import re
import sys
import pytest 
import psycopg2
import configparser
from datetime import datetime




# ================================================ CONFIG ================================================

# Add a flag/switch indicating whether Airflow is in use or not 
USING_AIRFLOW   =   False



# Create a config file for storing environment variables
config  =   configparser.ConfigParser()
if USING_AIRFLOW:

    # Use the airflow config file from the airflow container 
    config.read('/usr/local/airflow/dags/etl_to_postgres/airflow_config.ini')
    JSONDATA = config['postgres_airflow_config']['DATASET_SOURCE_PATH'] 

    host                    =   config['postgres_airflow_config']['HOST']
    port                    =   config['postgres_airflow_config']['PORT']
    database                =   config['postgres_airflow_config']['SEMANTIC_DB']
    username                =   config['postgres_airflow_config']['USERNAME']
    password                =   config['postgres_airflow_config']['PASSWORD']
    
    postgres_connection     =   None
    cursor                  =   None

    
else:

    # Use the local config file from the local machine 
    path    =   os.path.abspath('dwh_pipelines/local_config.ini')
    config.read(path)
    JSONDATA     =   config['data_filepath']['JSONDATA']

    host                    =   config['data_filepath']['HOST']
    port                    =   config['data_filepath']['PORT']
    database                =   config['data_filepath']['SEMANTIC_DB']
    username                =   config['data_filepath']['USERNAME']
    password                =   config['data_filepath']['PASSWORD']

    postgres_connection     =   None
    cursor                  =   None



# Connect to the Postgres database
try:
    pgsql_connection = psycopg2.connect(
            host = host,
            port = port,
            dbname = database,
            user = username,
            password = password,
        )


    # Create a cursor object to execute the PG-SQL commands 
    cursor = pgsql_connection.cursor()


except psycopg2.Error:
    raise ConnectionError("CONNECTION ERROR: Unable to connect to the demo_company database...")



# Define the database, schema and table names

table_name                      =   'dim_accommodation_bookings_tbl'
schema_name                     =   'dev'
database_name                   =    database



# ====================================== DATA QUALITY CHECKS ======================================
# ================================================================================================= 



# ====================================== TEST 1: DATABASE CONNECTION CHECK ======================================


""" Test the connection to the Postgres database is successful or not """

def test_database_connection():

    # Assert the existence of a valid connection to the database (i.e. not None) 
    assert pgsql_connection is not None, f"CONNECTION ERROR: Unable to connect to the {database_name} database... " 






# ====================================== TEST 2: SCHEMA EXISTENCE CHECK ======================================


"""  Verify the semantic schema exists in the Postgres semantic database   """



def test_schema_existence():
    sql_query = f"""     SELECT schema_name FROM information_schema.schemata 
    """
    cursor.execute(sql_query)

    sql_results = cursor.fetchall()
    schemas = [schema[0] for schema in sql_results]

    assert schema_name in schemas, f"The '{schema_name}' schema should be found in the '{database_name}' database. "






# ====================================== TEST 3: COLUMNS EXISTENCE CHECK ======================================

"""  Verify the columns of this table exists in the Postgres semantic database   """



def test_columns_existence():
    sql_query = f"""     SELECT column_name FROM information_schema.columns WHERE table_name='{table_name}' 
    """
    cursor.execute(sql_query)

    sql_results = cursor.fetchall()
    actual_columns = [column[0] for column in sql_results]

    expected_columns = ['id', 
                        'booking_date', 
                        'check_in_date', 
                        'check_out_date', 
                        'checked_in',
                        'confirmation_code', 
                        'customer_id', 
                        'flight_booking_id', 
                        'location',
                        'no_of_adults', 
                        'no_of_children', 
                        'payment_method', 
                        'room_type',
                        'sales_agent_id', 
                        'status', 
                        'total_price',
                        'created_at',
                        'updated_at',
                        'source_system',
                        'source_file',
                        'load_timestamp',
                        'dwh_layer'
                        ]
    
    for expected_column in expected_columns:
        assert expected_column in actual_columns, f"The '{expected_column}' column should be in the '{table_name}' table. "





# ====================================== TEST 4: TABLE EXISTENCE CHECK ======================================


""" Check if the active table is in the Postgres semantic database  """


def test_table_existence():
    sql_query = f"""     SELECT * FROM information_schema.tables WHERE table_name = '{table_name}' AND table_schema = '{schema_name}'  ;  """
    cursor.execute(sql_query)
    sql_result  = cursor.fetchone()

    assert sql_result is not None, f"The '{table_name}' does not exist in the '{database}.{schema_name}' schema. "





# ====================================== TEST 5: DATA TYPES CHECK ======================================


""" Test if each column is mapped to the expected data type in Postgres  """


def test_column_data_types():

    # Create a dictionary that specifies the expected data types for each column  
    expected_data_types = {
        # "customer_sk":                          "integer",
        "flight_booking_sk":                          "integer",
        "sales_agent_sk":                          "integer",
        "accommodation_sk":                     "integer",
        "id":                                   "uuid",
        "booking_date":                         "date",
        "check_in_date":                        "date",
        "check_out_date":                       "date",
        "checked_in":                           "character varying",
        "confirmation_code":                    "character varying",
        "customer_id":                          "uuid",
        "flight_booking_id":                    "uuid",
        "location":                             "character varying",
        "no_of_adults":                         "integer",
        "no_of_children":                       "integer",
        "payment_method":                       "character varying",
        "room_type":                            "character varying",
        "sales_agent_id":                       "uuid",
        "status":                               "character varying",
        "total_price":                          "numeric",
        "created_at":                           "timestamp with time zone",
        "updated_at":                           "timestamp with time zone",
        "source_system":                        "character varying",
        "source_file":                          "character varying",
        "load_timestamp":                       "timestamp without time zone",
        "dwh_layer":                            "character varying"

    }   



    # Use SQL to extract the column names and their data types
    sql_query = f"""         SELECT column_name, data_type from information_schema.columns WHERE table_name = '{table_name}'
    """
    cursor.execute(sql_query)

    sql_results = cursor.fetchall()

    for column_name, actual_data_type in sql_results:
        assert actual_data_type.lower() == expected_data_types[column_name], f"The expected data type for column '{column_name}' was '{expected_data_types[column_name]}', but the actual data type was '{actual_data_type}'. "
    




# ====================================== TEST 6: EMPTY VALUES CHECK ======================================


""" Check if there are any empty values present in your table """

def test_empty_values_in_table():
    sql_query = f"""     SELECT * FROM   {schema_name}.{table_name}
    """
    cursor.execute(sql_query)
    sql_results = cursor.fetchall()

    row_no = 0 
    for record in sql_results:
        row_no +=1
        for cell_value in record:
            assert cell_value is not None, f" There is an empty value in the '{schema_name}.{table_name}' table on row '{row_no}' . "






# ====================================== TEST 7: NULL VALUES CHECK ======================================

""" Check if there are any NULL values present in your table """

def test_null_values_in_table():

    # Get list of columns from table 
    cursor.execute(f""" SELECT column_name from information_schema.columns WHERE table_name = '{table_name}' ;
    """)
    columns = cursor.fetchall()


    for column in columns:
        sql_query = f'SELECT COUNT(*) FROM {schema_name}.{table_name} WHERE {column[0]} is NULL'
        cursor.execute(sql_query)
        sql_result = cursor.fetchone()

        assert sql_result[0] == 0, f"The {column} column has NULL values. "







# ====================================== TEST 8: DATE FORMATTING CHECK ======================================


""" Check the date columns contain values in the 'yyyy-mm-dd' format """

def test_date_formatting_constraint():
    expected_date_format = r"^\d{4}-\d{2}-\d{2}$"
    data_type = 'date'

    sql_query_1 = f'''  SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}' AND data_type = '{data_type}'    '''
    cursor.execute(sql_query_1)

    sql_results_1 = cursor.fetchall()
    date_columns = [sql_result[0] for sql_result in sql_results_1]

    for date_column in date_columns:
        sql_query_2 = f"""     SELECT      {date_column} 
                                FROM        {schema_name}.{table_name}        
        """
        cursor.execute(sql_query_2)
        sql_results_2 = cursor.fetchall()
        for sql_result in sql_results_2:
            date_value = sql_result[0].strftime("%Y-%m-%d")
            assert re.match(expected_date_format, date_value) is not None, f"Invalid date detected - date values should be in 'yyyy-mm-dd' format."




# ====================================== TEST 9: DATE DOMAIN CHECKS ======================================

""" Check if the values in `check_in_date` field are before the values in the `check_out_date` field """


def test_check_in_date_before_check_out_date():
    sql_query = f"""    SELECT check_in_date, check_out_date FROM {schema_name}.{table_name}
    """

    cursor.execute(sql_query)

    sql_results = cursor.fetchall()

    record_counter = 0
    for record in sql_results:
        record_counter += 1
        check_in_date, check_out_date = record

        assert check_in_date < check_out_date, f" Row {record_counter} contains a 'check out' date that is before the 'check in' date"




# ====================================== TEST 10: CONFIRMATION CODE FORMAT CHECK ======================================

""" Test the sequence of characters in each confirmation code matches the regular expression specified """


def test_confirmation_code_formatting_constraint():
    expected_conf_code_pattern = r"^[A-Z0-9]{8,10}$"
    sql_column = "confirmation_code"

    sql_query = f"""         SELECT {sql_column} FROM {schema_name}.{table_name} ;
    """
    cursor.execute(sql_query)
    
    sql_results = cursor.fetchall()

    # Assert the character sequence for confirmation codes match the pattern specified 
    for sql_result in sql_results:
        confirmation_code = sql_result[0]
        assert re.match(expected_conf_code_pattern, confirmation_code), f"Invalid confirmation code in the {sql_column} column for {schema_name}.{table_name}. "





# ====================================== TEST 11: PAYMENT METHOD DOMAIN CONSTRAINT CHECK  ======================================

""" Check if the payment_method column only contains the "Debit card", "Credit card", "Paypal" and "Bank transfer" values """

def test_payment_method_col_values():
    valid_payment_methods = ["Debit card", "Credit card", "PayPal", "Bank transfer"]
    sql_column = "payment_method"

    sql_query = f"""         SELECT {sql_column}  FROM {schema_name}.{table_name} ;
    """
    cursor.execute(sql_query)
    
    sql_results = cursor.fetchall()

    # Assert the values in the column payment_method column contain the values specified
    for sql_result in sql_results: 
        payment_method = sql_result[0]
        assert payment_method in valid_payment_methods, f" Invalid payment method detected - payment methods must only be one of the following options: {valid_payment_methods}. "


# ====================================== TEST 12: STATUS DOMAIN CONSTRAINT CHECK  ======================================

""" Check if the status column only contains the "Pending", "Confirmed" and "Cancelled" values """

def test_status_col_values():
    valid_statuses = ["Pending", "Confirmed", "Cancelled"]
    sql_column = "status"

    sql_query = f"""         SELECT {sql_column} FROM {schema_name}.{table_name} ;
    """
    cursor.execute(sql_query)
    
    sql_results = cursor.fetchall()

    # Assert the values in the column status column contain the values specified
    for sql_result in sql_results:
        
        status = sql_result[0]
        assert status in valid_statuses, f"Invalid status detected - statuses must only be one of the following options: {valid_statuses}. "
        



# ====================================== TEST 13: ID CHARACTER LENGTH CONSTRAINT CHECK ======================================

""" Test all the ID columns in the table contain 36 characters in length  """

def test_id_char_length_constraint():
    expected_id_char_length = 36
    sql_results = cursor.fetchall()
    

    sql_query = f"""     SELECT column_name FROM information_schema.columns WHERE table_name='{table_name} AND column_name LIKE "%_id%" ' 
    """
    cursor.execute(sql_query)
    
    sql_results = cursor.fetchall()


     # Assert the number of characters for the id column is equal to 36
    for sql_result in sql_results:
        id_column = sql_result[0]
        actual_id_length = len(id_column)
        assert actual_id_length == expected_id_char_length, f"Invalid ID column found: All ID columns must be {expected_id_char_length} characters long. The ID column containing invalid IDs is '{id_column}' column"




# ====================================== TEST 14: DUPLICATES CHECK ======================================


""" Test the number of duplicate records appearing in the Postgres table  """

def test_duplicate_records_count():
    column_name = "id"
    sql_query   = f"""                 SELECT          {column_name}, 
                                                        COUNT (*)
                                        FROM            {schema_name}.{table_name}
                                        GROUP BY        {column_name}
                                        HAVING          COUNT(*) > 1
                                        ;
    """
    cursor.execute(sql_query)

    duplicates = cursor.fetchall()
    total_no_of_duplicates = len(duplicates)

    # Assert the number of uniqueness constraints for the table specified is at least 1
    assert total_no_of_duplicates == 0, f"Duplicate entries detected - {table_name} should contain no duplicate entries."





# ====================================== BUSINESS RULES ======================================
# ============================================================================================= 


# ====================================== TEST 15: DATE RANGE CHECK ======================================


""" Test the date value in each date column are within the expected date ranges """

def test_date_range_constraints():
    earliest_date       =       datetime(2012, 1, 1).date()
    latest_date         =       datetime(2022, 12, 31).date()

    sql_query_1 = f"""                 SELECT      column_name, 
                                                    data_type 
                                        FROM        information_schema.columns 
                                        WHERE       table_name = '{table_name}'  
                                        ;
    """
    cursor.execute(sql_query_1)

    sql_results = cursor.fetchall()

    for sql_result in sql_results:
        column_name = sql_result[0]
        actual_data_type = sql_result[1]
        if actual_data_type == 'date':
            sql_query_2 = f"""         SELECT {column_name} FROM {schema_name}.{table_name};
            """
            cursor.execute(sql_query_2)

            dates = cursor.fetchall()

            # Assert the selected date value in this column is between the earliest and latest date specified   
            for date in dates:
                date_value = date[0]

                assert earliest_date <= date_value <= latest_date, f" Date columns should only contain dates between {earliest_date} and {latest_date}. "


def run_tests():
    test_filepath =  os.path.abspath('dwh_pipelines/L3_semantic_layer/tests/test_dim_accommodation_bookings_tbl.py')
    test_result = pytest.main([test_filepath])
    return test_result



if __name__ == "__main__":
    # Run DQ tests
    test_result = run_tests()

    # Create DQ reports in HTML format
    from pathlib import Path
    import webbrowser
    file_path = os.path.abspath(__file__)
    current_filepath = Path(__file__).stem
    html_report_path = f"{current_filepath}.html"
    pytest.main(["-v", "-s", "--capture=tee-sys", file_path, f"--html={html_report_path}", "--self-contained-html"])

    # Open DQ reports in browser
    # dq_report_url = Path.cwd() / html_report_path
    # webbrowser.open(dq_report_url.as_uri())
    sys.exit()
