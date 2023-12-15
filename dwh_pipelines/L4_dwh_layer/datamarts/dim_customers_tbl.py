import os 
import json
import time
import psycopg2
import pandas as pd
import configparser
from pathlib import Path
import logging, coloredlogs
from datetime import datetime

# ================================================ LOGGER ================================================


# Set up root root_logger 
root_logger     =   logging.getLogger(__name__)
root_logger.setLevel(logging.DEBUG)


# Set up formatter for logs 
file_handler_log_formatter      =   logging.Formatter('%(asctime)s  |  %(levelname)s  |  %(message)s  ')
console_handler_log_formatter   =   coloredlogs.ColoredFormatter(fmt    =   '%(message)s', level_styles=dict(
                                                                                                debug           =   dict    (color  =   'white'),
                                                                                                info            =   dict    (color  =   'green'),
                                                                                                warning         =   dict    (color  =   'cyan'),
                                                                                                error           =   dict    (color  =   'red',      bold    =   True,   bright      =   True),
                                                                                                critical        =   dict    (color  =   'black',    bold    =   True,   background  =   'red')
                                                                                            ),

                                                                                    field_styles=dict(
                                                                                        messages            =   dict    (color  =   'white')
                                                                                    )
                                                                                    )


# Set up file handler object for logging events to file
current_filepath    =   Path(__file__).stem
file_handler        =   logging.FileHandler('logs/L4_dwh_layer/live/' + current_filepath + '.log', mode='w')
file_handler.setFormatter(file_handler_log_formatter)


# Set up console handler object for writing event logs to console in real time (i.e. streams events to stderr)
console_handler     =   logging.StreamHandler()
console_handler.setFormatter(console_handler_log_formatter)


# Add the file handler 
root_logger.addHandler(file_handler)

# Only add the console handler if the script is running directly from this location 
if __name__=="__main__":
    root_logger.addHandler(console_handler)


# ================================================ CONFIG ================================================


# Create a config file for storing environment variables
config  =   configparser.ConfigParser()

path    =   os.path.abspath('dwh_pipelines/local_config.ini')

config.read(path)

JSONDATA = config['data_filepath']['JSONDATA']

host = config['data_filepath']['HOST']
port =  config['data_filepath']['PORT']
database = config['data_filepath']['DWH_DB']
username = config['data_filepath']['USERNAME']
password = config['data_filepath']['PASSWORD']

postgres_connection = None
cursor = None

root_logger.info("")
root_logger.info("---------------------------------------------")
root_logger.info("Beginning the data extraction process........")

postgres_connection = psycopg2.connect(
    host = host,
    port = port,
    dbname = database,
    user = username,
    password = password,
)
postgres_connection.set_session(autocommit=True)



def load_data_to_stg_customers_table(postgres_connection):
# LOGIC
    try:
        CURRENT_TIMESTAMP = datetime.now()
        fdw_extension = 'postgres_fdw'
        foreign_server = config['data_filepath']['HOST']
        fdw_user = username
        src_db_name = config['data_filepath']['STAGING_DB']
        src_schema_name = 'dev'
        active_schema_name = 'main'
        active_db_name = database

        src_table_1 = 'stg_customer_feedbacks_tbl' 
        src_table_2 = 'stg_tbl'

        table_name = 'stg_customers_tbl'
        data_warehouse_layer = 'DWH - DATAMART'
        source_system                   =   ['CRM', 'ERP', 'Mobile App', 'Website', 'Company database']
        row_counter                     =   0 
        column_index                    =   0 
        total_null_values_in_table      =   0 
        successful_rows_upload_count    =   0 
        failed_rows_upload_count        =   0 
 
        cursor = postgres_connection.cursor()

        # ================================================== VALIDATE CONNECTION ==================================================
        if postgres_connection.closed == 0:
            root_logger.info("=================================================================================")
            root_logger.info(f"CONNECTION SUCCESS: Managed to connect successfully to the {active_db_name} database!!")
            root_logger.info(f"Connection details: {postgres_connection.dsn} ")
            root_logger.info("=================================================================================")
        elif postgres_connection.closed != 0:
            raise ConnectionError("CONNECTION ERROR: Unable to connect to the demo_company database...") 


        # ================================================== ENABLING CROSS-DATABASE QUERYING VIA FDW ==================================================

# Set up SQL statements for schema creation and validation check 
        try:
            create_schema   =    f'''CREATE SCHEMA IF NOT EXISTS {active_schema_name};'''
            check_if_schema_exists  =   f'''SELECT schema_name from information_schema.schemata WHERE schema_name= '{active_schema_name}';'''

            # Create schema in Postgres
            CREATING_SCHEMA_PROCESSING_START_TIME   =   time.time()
            cursor.execute(create_schema)
            root_logger.info(f"Successfully created {active_schema_name} schema. ")
            CREATING_SCHEMA_PROCESSING_END_TIME     =   time.time()

            CREATING_SCHEMA_VAL_CHECK_START_TIME    =   time.time()
            cursor.execute(check_if_schema_exists)
            CREATING_SCHEMA_VAL_CHECK_END_TIME      =   time.time()

            sql_result = cursor.fetchone()[0]
            if sql_result:
                root_logger.debug(f"")
                root_logger.info(f"=================================================================================================")
                root_logger.info(f"SCHEMA CREATION SUCCESS: Managed to create {active_schema_name} schema in {active_db_name} ")
                root_logger.info(f"Schema name in Postgres: {sql_result} ")
                root_logger.info(f"SQL Query for validation check:  {check_if_schema_exists} ")
                root_logger.info(f"=================================================================================================")
                root_logger.debug(f"")
            else:
                root_logger.debug(f"")
                root_logger.error(f"=================================================================================================")
                root_logger.error(f"SCHEMA CREATION FAILURE: Unable to create schema for {active_db_name}...")
                root_logger.info(f"SQL Query for validation check:  {check_if_schema_exists} ")
                root_logger.error(f"=================================================================================================")
                root_logger.debug(f"")
            # postgres_connection.commit()
        except psycopg2.Error as e:
            print(e)


# Drop extension postgres_fdw if it exists 
        try:
            drop_postgres_fdw_extension = f'''DROP EXTENSION {fdw_extension} CASCADE;'''
            cursor.execute(drop_postgres_fdw_extension)
            # postgres_connection.commit()

            root_logger.info("")
            root_logger.info(f"Successfully DROPPED the '{fdw_extension}' extension. Now advancing to re-importing the extension...")
            root_logger.info("")
        except psycopg2.Error as e:
            print(e)

# Create the new postgres_fdw extension  
        try:
            import_postgres_fdw = f'''CREATE EXTENSION {fdw_extension};'''
            
            cursor.execute(import_postgres_fdw)
            # postgres_connection.commit()

            root_logger.info("")
            root_logger.info(f"Successfully IMPORTED the '{fdw_extension}' extension. Now advancing to creating the foreign server...")
            root_logger.info("")
        except psycopg2.Error as e:
            print(e)

# Create the foreign server
        try: 
            create_foreign_server = f'''CREATE SERVER {foreign_server}
                    FOREIGN DATA WRAPPER {fdw_extension}
                    OPTIONS (host '{host}', dbname '{src_db_name}', port '{port}');'''
            cursor.execute(create_foreign_server)
            # postgres_connection.commit()
            root_logger.info("")
            root_logger.info(f"Successfully CREATED the '{foreign_server}' foreign server. Now advancing to user mapping stage...")
            root_logger.info("")
        except psycopg2.Error as e:
            print(e)


# Create the user mapping between the fdw_user and local user 
        try:
            map_fdw_user_to_local_user = f'''       CREATE USER MAPPING FOR {username}
                                                        SERVER {foreign_server}
                                                        OPTIONS (user '{fdw_user}', password '{password}')
                                                        ;
            '''

            cursor.execute(map_fdw_user_to_local_user)
            # postgres_connection.commit()

            root_logger.info("")
            root_logger.info(f"Successfully mapped the '{fdw_user}' fdw user to the '{username}' local user. ")
            root_logger.info("")

            root_logger.info("")
            root_logger.info("-------------------------------------------------------------------------------------------------------------------------------------------")
            root_logger.info("")
            root_logger.info(f"You should now be able to create and interact with the virtual tables that mirror the actual tables from the '{src_db_name}' database. ")
            root_logger.info("")
            root_logger.info("-------------------------------------------------------------------------------------------------------------------------------------------")
            root_logger.info("")
        except psycopg2.Error as e:
            print(e)


# Import the foreign schema from the previous layer's source table 
        try:
            import_foreign_schema = f'''IMPORT FOREIGN SCHEMA "{src_schema_name}"
                                                LIMIT TO ({src_table_1}, {src_table_2})
                                                FROM SERVER {foreign_server}
                                                INTO {active_schema_name};'''

            cursor.execute(import_foreign_schema)
            # postgres_connection.commit()
            
            root_logger.info("")
            root_logger.info(f"Successfully imported the '{src_table_1}' and '{src_table_2}' tables into '{active_db_name}' database . ")
            root_logger.info("")
        except psycopg2.Error as e:
            print(e)
            root_logger.error("")
            root_logger.error(f"Unable to import the '{src_table_1}' and '{src_table_2}' tables into '{active_db_name}' database . ")
            root_logger.error("")

        # ================================================== LOAD MDM DATA TO DWH TABLE =======================================

# Set up SQL statements for table deletion and validation check  
        delete_stg_customers_tbl_if_exists = f'''DROP TABLE IF EXISTS {active_schema_name}.{table_name} CASCADE;'''

        check_if_stg_customers_tbl_is_deleted = f'''SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}' );'''

# Set up SQL statements for table creation and validation check 
        create_stg_customers_tbl = f'''                CREATE TABLE IF NOT EXISTS {active_schema_name}.{table_name} as 
                                                                SELECT
                                                                        i.customer_sk ,
                                                                        i.customer_id ,
                                                                        i.first_name,
                                                                        i.last_name,
                                                                        i.full_name,
                                                                        i.email,
                                                                        i.age,
                                                                        i.dob,
                                                                        i.phone_number,
                                                                        i.place_of_birth,
                                                                        i.address,
                                                                        i.city,
                                                                        i.created_date,
                                                                        i.last_updated_date,
                                                                        f.feedback_id,
                                                                        f.feedback_date,
                                                                        f.feedback_text
                                                                    FROM dev.stg_tbl i
                                                                    LEFT JOIN dev.stg_customer_feedbacks_tbl f ON i.customer_id = f.customer_id;
        '''

        check_if_stg_customers_tbl_exists = f'''SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}' );'''


# Set up SQL statements for adding data lineage and validation check 
        add_data_lineage_to_stg_customers_tbl  =   f'''ALTER TABLE {active_schema_name}.{table_name}
                                                                                ADD COLUMN  created_at                  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                                                                                ADD COLUMN  updated_at                  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                                                                                ADD COLUMN  source_system               VARCHAR(255),
                                                                                ADD COLUMN  source_file                 VARCHAR(255),
                                                                                ADD COLUMN  load_timestamp              TIMESTAMP,
                                                                                ADD COLUMN  dwh_layer                   VARCHAR(255)
                                                                        ;'''

        check_if_data_lineage_fields_are_added_to_tbl   =   f'''        
                                                                    SELECT * 
                                                                    FROM    information_schema.columns 
                                                                    WHERE   table_name      = '{table_name}' 
                                                                        AND table_schema = '{active_schema_name}'
                                                                        AND     (column_name    = 'created_at'
                                                                        OR      column_name     = 'updated_at' 
                                                                        OR      column_name     = 'source_system' 
                                                                        OR      column_name     = 'source_file' 
                                                                        OR      column_name     = 'load_timestamp' 
                                                                        OR      column_name     = 'dwh_layer');
                                                                              
        '''
        
        check_total_row_count_before_insert_statement = f'''SELECT COUNT(*) FROM {active_schema_name}.{table_name}'''

# Set up SQL statements for records insert and validation check
        insert_customers_data  =   f'''INSERT INTO {active_schema_name}.{table_name} (
                                                                                customer_id,                        
                                                                                first_name,                         
                                                                                last_name,
                                                                                full_name,
                                                                                email,    
                                                                                age,      
                                                                                dob,
                                                                                phone_number,                                      
                                                                                place_of_birth,                     
                                                                                address,  
                                                                                city,
                                                                                created_date,
                                                                                last_updated_date,
                                                                                created_at,
                                                                                updated_at
                                                                            )
                                                                            VALUES (
                                                                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                                                                            );
        '''

        check_total_row_count_after_insert_statement    =   f'''SELECT COUNT(*) FROM {active_schema_name}.{table_name}
        '''


        
        count_total_no_of_columns_in_table  =   f'''            SELECT          COUNT(column_name) 
                                                                FROM            information_schema.columns 
                                                                WHERE           table_name      =   '{table_name}'
                                                                AND             table_schema    =   '{active_schema_name}'
        '''

        count_total_no_of_unique_records_in_table   =   f'''        SELECT COUNT(*) FROM 
                                                                            (SELECT DISTINCT * FROM {active_schema_name}.{table_name}) as unique_records   
        '''
        get_list_of_column_names    =   f'''                SELECT column_name FROM information_schema.columns 
                                                            WHERE   table_name = '{table_name}'
                                                            ORDER BY ordinal_position 
        '''


# Delete table if it exists in Postgres
        # DELETING_SCHEMA_PROCESSING_START_TIME   =   time.time()
        # cursor.execute(delete_stg_customers_tbl_if_exists)
        # DELETING_SCHEMA_PROCESSING_END_TIME     =   time.time()

        
        DELETING_SCHEMA_VAL_CHECK_PROCESSING_START_TIME     =   time.time()
        cursor.execute(check_if_stg_customers_tbl_is_deleted)
        DELETING_SCHEMA_VAL_CHECK_PROCESSING_END_TIME       =   time.time()


        sql_result = cursor.fetchone()[0]
        if sql_result:
            root_logger.debug(f"")
            root_logger.info(f"=============================================================================================================================================================================")
            root_logger.info(f"TABLE DELETION SUCCESS: Managed to drop {table_name} table in {active_db_name}. Now advancing to recreating table... ")
            root_logger.info(f"SQL Query for validation check:  {check_if_stg_customers_tbl_is_deleted} ")
            root_logger.info(f"=============================================================================================================================================================================")
            root_logger.debug(f"")
        else:
            root_logger.debug(f"")
            root_logger.error(f"==========================================================================================================================================================================")
            root_logger.error(f"TABLE DELETION FAILURE: Unable to delete {table_name}. This table may have objects that depend on it (use DROP TABLE ... CASCADE to resolve) or it doesn't exist. ")
            root_logger.error(f"SQL Query for validation check:  {check_if_stg_customers_tbl_is_deleted} ")
            root_logger.error(f"==========================================================================================================================================================================")
            root_logger.debug(f"")



        # Create table if it doesn't exist in Postgres  
        CREATING_TABLE_PROCESSING_START_TIME    =   time.time()
        cursor.execute(create_stg_customers_tbl)
        CREATING_TABLE_PROCESSING_END_TIME  =   time.time()

        
        CREATING_TABLE_VAL_CHECK_PROCESSING_START_TIME  =   time.time()
        cursor.execute(check_if_stg_customers_tbl_exists)
        CREATING_TABLE_VAL_CHECK_PROCESSING_END_TIME    =   time.time()


        sql_result = cursor.fetchone()[0]
        if sql_result:
            root_logger.debug(f"")
            root_logger.info(f"=============================================================================================================================================================================")
            root_logger.info(f"TABLE CREATION SUCCESS: Managed to create {table_name} table in {active_db_name}.  ")
            root_logger.info(f"SQL Query for validation check:  {check_if_stg_customers_tbl_exists} ")
            root_logger.info(f"=============================================================================================================================================================================")
            root_logger.debug(f"")
        else:
            root_logger.debug(f"")
            root_logger.error(f"==========================================================================================================================================================================")
            root_logger.error(f"TABLE CREATION FAILURE: Unable to create {table_name}... ")
            root_logger.error(f"SQL Query for validation check:  {check_if_stg_customers_tbl_exists} ")
            root_logger.error(f"==========================================================================================================================================================================")
            root_logger.debug(f"")



        # Add data lineage to table 
        ADDING_DATA_LINEAGE_PROCESSING_START_TIME   =   time.time()
        cursor.execute(add_data_lineage_to_stg_customers_tbl)
        ADDING_DATA_LINEAGE_PROCESSING_END_TIME     =   time.time()

        
        ADDING_DATA_LINEAGE_VAL_CHECK_PROCESSING_START_TIME  =  time.time()
        cursor.execute(check_if_data_lineage_fields_are_added_to_tbl)
        ADDING_DATA_LINEAGE_VAL_CHECK_PROCESSING_END_TIME    =  time.time()


        sql_results = cursor.fetchall()
        
        if len(sql_results) == 6:
            root_logger.debug(f"")
            root_logger.info(f"=============================================================================================================================================================================")
            root_logger.info(f"DATA LINEAGE FIELDS CREATION SUCCESS: Managed to create data lineage columns in {active_schema_name}.{table_name}.  ")
            root_logger.info(f"SQL Query for validation check:  {check_if_data_lineage_fields_are_added_to_tbl} ")
            root_logger.info(f"=============================================================================================================================================================================")
            root_logger.debug(f"")
        else:
            root_logger.debug(f"")
            root_logger.error(f"==========================================================================================================================================================================")
            root_logger.error(f"DATA LINEAGE FIELDS CREATION FAILURE: Unable to create data lineage columns in {active_schema_name}.{table_name}.... ")
            root_logger.error(f"SQL Query for validation check:  {check_if_data_lineage_fields_are_added_to_tbl} ")
            root_logger.error(f"==========================================================================================================================================================================")
            root_logger.debug(f"")


        # ======================================= DATA PROFILING METRICS =======================================
# Prepare data profiling metrics 
        # --------- A. Table statistics 
        cursor.execute(count_total_no_of_columns_in_table)
        total_columns_in_table = cursor.fetchone()[0]

        cursor.execute(count_total_no_of_unique_records_in_table)
        total_unique_records_in_table = cursor.fetchone()[0]
        

        cursor.execute(get_list_of_column_names)
        list_of_column_names = cursor.fetchall()
        column_names = [sql_result[0] for sql_result in list_of_column_names]
                
        # --------- B. Performance statistics (Python)
        EXECUTION_TIME_FOR_CREATING_SCHEMA                   =   (CREATING_SCHEMA_PROCESSING_END_TIME                -       CREATING_SCHEMA_PROCESSING_START_TIME                   )   * 1000

        # eliminate execution time threshold         =   (CREATING_SCHEMA_VAL_CHECK_END_TIME                 -       CREATING_SCHEMA_VAL_CHECK_START_TIME                    )   * 1000

        EXECUTION_TIME_FOR_DROPPING_SCHEMA                   =   (DELETING_SCHEMA_PROCESSING_END_TIME                -       DELETING_SCHEMA_PROCESSING_START_TIME                   )   * 1000

        EXECUTION_TIME_FOR_DROPPING_SCHEMA_VAL_CHECK         =   (DELETING_SCHEMA_VAL_CHECK_PROCESSING_END_TIME      -       DELETING_SCHEMA_VAL_CHECK_PROCESSING_START_TIME         )   * 1000

        EXECUTION_TIME_FOR_CREATING_TABLE                    =   (CREATING_TABLE_PROCESSING_END_TIME                 -       CREATING_TABLE_PROCESSING_START_TIME                    )   * 1000

        EXECUTION_TIME_FOR_CREATING_TABLE_VAL_CHECK          =   (CREATING_TABLE_VAL_CHECK_PROCESSING_END_TIME       -       CREATING_TABLE_VAL_CHECK_PROCESSING_START_TIME          )   * 1000

        EXECUTION_TIME_FOR_ADDING_DATA_LINEAGE               =   (ADDING_DATA_LINEAGE_PROCESSING_END_TIME            -       ADDING_DATA_LINEAGE_PROCESSING_START_TIME               )   * 1000

        EXECUTION_TIME_FOR_ADDING_DATA_LINEAGE_VAL_CHECK     =   (ADDING_DATA_LINEAGE_VAL_CHECK_PROCESSING_END_TIME  -       ADDING_DATA_LINEAGE_VAL_CHECK_PROCESSING_START_TIME     )   * 1000


        # Display data profiling metrics
        
        root_logger.info(f'')
        root_logger.info(f'')
        root_logger.info('================================================')
        root_logger.info('              DATA PROFILING METRICS              ')
        root_logger.info('================================================')
        root_logger.info(f'')
        root_logger.info(f'Now calculating table statistics...')
        root_logger.info(f'')
        root_logger.info(f'')
        root_logger.info(f'Table name:                                  {table_name} ')
        root_logger.info(f'Schema name:                                 {active_schema_name} ')
        root_logger.info(f'Database name:                               {database} ')
        root_logger.info(f'Data warehouse layer:                        {data_warehouse_layer} ')
        root_logger.info(f'')
        root_logger.info(f'')
        root_logger.info(f'Number of columns in table:                  {total_columns_in_table} ')
        root_logger.info(f'')


        
        for column_name in column_names:
            cursor.execute(f'''
                    SELECT COUNT(*)
                    FROM {active_schema_name}.{table_name}
                    WHERE {column_name} is NULL
            ''')
            sql_result = cursor.fetchone()[0]
            total_null_values_in_table += sql_result
            column_index += 1
            if sql_result == 0:
                root_logger.info(f'Column name: {column_name},  Column no: {column_index},  Number of NULL values: {sql_result} ')
            else:
                root_logger.warning(f'Column name: {column_name},  Column no: {column_index},  Number of NULL values: {sql_result} ')
        

        root_logger.info(f'')
        root_logger.info('================================================')
        root_logger.info(f'')
        root_logger.info(f'Now calculating performance statistics for Python...')
        root_logger.info(f'')


        if (EXECUTION_TIME_FOR_CREATING_SCHEMA > 1000) and (EXECUTION_TIME_FOR_CREATING_SCHEMA < 60000):
            root_logger.info(f'1. Execution time for CREATING schema: {EXECUTION_TIME_FOR_CREATING_SCHEMA} ms ({    round   (EXECUTION_TIME_FOR_CREATING_SCHEMA  /   1000, 2)   } secs) ')
            root_logger.info(f'')
            root_logger.info(f'')
        elif (EXECUTION_TIME_FOR_CREATING_SCHEMA >= 60000):
            root_logger.info(f'1. Execution time for CREATING schema: {EXECUTION_TIME_FOR_CREATING_SCHEMA} ms  ({    round   (EXECUTION_TIME_FOR_CREATING_SCHEMA  /   1000, 2)   } secs)  ({   round  ((EXECUTION_TIME_FOR_CREATING_SCHEMA  /   1000) / 60, 4)     } mins)   ')
            root_logger.info(f'')
            root_logger.info(f'')
        else:
            root_logger.info(f'1. Execution time for CREATING schema: {EXECUTION_TIME_FOR_CREATING_SCHEMA} ms ')
            root_logger.info(f'')
            root_logger.info(f'')


        if (# eliminate execution time threshold > 1000) and (# eliminate execution time threshold < 60000):
            root_logger.info(f'2. Execution time for CREATING schema (VAL CHECK): {# eliminate execution time threshold} ms ({  round   (# eliminate execution time threshold  /   1000, 2)} secs)      ')
            root_logger.info(f'')
            root_logger.info(f'')
        elif (# eliminate execution time threshold >= 60000):
            root_logger.info(f'2. Execution time for CREATING schema (VAL CHECK): {# eliminate execution time threshold} ms ({  round   (# eliminate execution time threshold  /   1000, 2)} secs)    ({  round ((# eliminate execution time threshold  /   1000) / 60,  4)   } min)      ')
            root_logger.info(f'')
            root_logger.info(f'')
        else:
            root_logger.info(f'2. Execution time for CREATING schema (VAL CHECK): {# eliminate execution time threshold} ms ')
            root_logger.info(f'')
            root_logger.info(f'')
        

        if (EXECUTION_TIME_FOR_DROPPING_SCHEMA > 1000) and (EXECUTION_TIME_FOR_DROPPING_SCHEMA < 60000):
            root_logger.info(f'3. Execution time for DELETING schema:  {EXECUTION_TIME_FOR_DROPPING_SCHEMA} ms ({  round   (EXECUTION_TIME_FOR_DROPPING_SCHEMA  /   1000, 2)} secs)      ')
            root_logger.info(f'')
            root_logger.info(f'')
        elif (EXECUTION_TIME_FOR_DROPPING_SCHEMA >= 60000):
            root_logger.info(f'3. Execution time for DELETING schema:  {EXECUTION_TIME_FOR_DROPPING_SCHEMA} ms ({  round   (EXECUTION_TIME_FOR_DROPPING_SCHEMA  /   1000, 2)} secs)    ({  round ((EXECUTION_TIME_FOR_DROPPING_SCHEMA  /   1000) / 60,  4)   } min)      ')
            root_logger.info(f'')
            root_logger.info(f'')
        else:
            root_logger.info(f'3. Execution time for DELETING schema:  {EXECUTION_TIME_FOR_DROPPING_SCHEMA} ms ')
            root_logger.info(f'')
            root_logger.info(f'')



        if (EXECUTION_TIME_FOR_DROPPING_SCHEMA_VAL_CHECK > 1000) and (EXECUTION_TIME_FOR_DROPPING_SCHEMA_VAL_CHECK < 60000):
            root_logger.info(f'4. Execution time for DELETING schema (VAL CHECK):  {EXECUTION_TIME_FOR_DROPPING_SCHEMA_VAL_CHECK} ms ({  round   (EXECUTION_TIME_FOR_DROPPING_SCHEMA_VAL_CHECK  /   1000, 2)} secs)      ')
            root_logger.info(f'')
            root_logger.info(f'')
        elif (EXECUTION_TIME_FOR_DROPPING_SCHEMA_VAL_CHECK >= 60000):
            root_logger.info(f'4. Execution time for DELETING schema (VAL CHECK):  {EXECUTION_TIME_FOR_DROPPING_SCHEMA_VAL_CHECK} ms ({  round   (EXECUTION_TIME_FOR_DROPPING_SCHEMA_VAL_CHECK  /   1000, 2)} secs)    ({  round ((EXECUTION_TIME_FOR_DROPPING_SCHEMA_VAL_CHECK  /   1000) / 60,  4)   } min)      ')
            root_logger.info(f'')
            root_logger.info(f'')
        else:
            root_logger.info(f'4. Execution time for DELETING schema (VAL CHECK):  {EXECUTION_TIME_FOR_DROPPING_SCHEMA_VAL_CHECK} ms ')
            root_logger.info(f'')
            root_logger.info(f'')

        

# delete timming on excutuion


        root_logger.info(f'')
        root_logger.info('================================================')


        # Add conditional statements for data profile metrics 


        if failed_rows_upload_count > 0:
            root_logger.error(f"ERROR: A total of {failed_rows_upload_count} records failed to upload to '{table_name}' table....")
            raise ImportError("Trace filepath to highlight the root cause of the missing rows...")
        else:
            root_logger.debug("")
            root_logger.info("DATA VALIDATION SUCCESS: All general DQ checks passed! ")
            root_logger.debug("")
        # Commit the changes made in Postgres 
        root_logger.info("Now saving changes made by SQL statements to Postgres DB....")
        # postgres_connection.commit()
        root_logger.info("Saved successfully, now terminating cursor and current session....")
    except psycopg2.Error as e:
            root_logger.info(e)
        
    finally:
        if cursor is not None:
            cursor.close()
            root_logger.debug("")
            root_logger.debug("Cursor closed successfully.")

        if postgres_connection is not None:
            postgres_connection.close()
            # root_logger.debug("")
            root_logger.debug("Session connected to Postgres database closed.")

load_data_to_stg_customers_table(postgres_connection)

