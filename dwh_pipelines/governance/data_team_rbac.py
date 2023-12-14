import os 
import psycopg2
from psycopg2 import errors
import configparser
from pathlib import Path
import logging, coloredlogs


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
file_handler        =   logging.FileHandler('logs/governance/' + current_filepath + '.log', mode='w')
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
    database                =   config['postgres_airflow_config']['DWH_DB']
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
    database                =   config['data_filepath']['DWH_DB']
    username                =   config['data_filepath']['USERNAME']
    password                =   config['data_filepath']['PASSWORD']

    postgres_connection     =   None
    cursor                  =   None


# Begin the data extraction process
root_logger.info("")
root_logger.info("---------------------------------------------")
root_logger.info("Beginning the dwh process...")


postgres_connection = psycopg2.connect(
                host        =   host,
                port        =   port,
                dbname      =   database,
                user        =   username,
                password    =   password,
        )
postgres_connection.set_session(autocommit=True)


def set_up_access_controls(postgres_connection):
    try:
        
        # Set up constants
        
        cursor                                                  =          postgres_connection.cursor()
        active_db_name                                          =          database
        raw_db                                                  =          config['data_filepath']['RAW_DB']
        staging_db                                              =          config['data_filepath']['STAGING_DB']
        semantic_db                                             =          config['data_filepath']['SEMANTIC_DB']
        dwh_db                                                  =          config['data_filepath']['DWH_DB']
        custom_roles                                            =          ['junior_data_analyst',
                                                                          'senior_data_analyst',  
                                                                          'junior_data_engineer',   
                                                                          'senior_data_engineer', 
                                                                          'junior_data_scientist',
                                                                          'senior_data_scientist'
                                                                          ]
        
        raw_main_schema                                         =           'main'
        
        staging_dev_schema                                      =           'dev'
        staging_prod_schema                                     =           'prod'

        semantic_dev_schema                                     =           'dev'
        semantic_prod_schema                                    =           'prod'

        dwh_reporting_schema                                    =           'reporting'
        dwh_live_schema                                         =           'live'

        db_schemas = {
            "raw_db"            :   [raw_main_schema],
            "staging_db"        :   [staging_dev_schema, staging_prod_schema],
            "semantic_db"       :   [semantic_dev_schema, semantic_prod_schema],
            "dwh_db"            :   [dwh_live_schema, dwh_reporting_schema],

        }
        role_databases = {

            "junior_data_analyst"       : [dwh_db],
            "senior_data_analyst"       : [dwh_db],
            "junior_data_engineer"      : [raw_db, staging_db, semantic_db, dwh_db],
            "senior_data_engineer"      : [raw_db, staging_db, semantic_db, dwh_db],
            "junior_data_scientist"     : [staging_db, semantic_db, dwh_db],
            "senior_data_scientist"     : [staging_db, semantic_db, dwh_db],

        }


        
        # For granting access to the DWH databases 

        
        ## A. Data analysts
        grant_jda_access_to_database_sql_query                  =           f''' GRANT CONNECT ON DATABASE {dwh_db} TO junior_data_analyst; '''
        grant_sda_access_to_database_sql_query                  =           f''' GRANT CONNECT ON DATABASE {dwh_db} TO senior_data_analyst; '''


        ## B. Data engineers
        grant_jde_access_to_database_sql_query_1                =           f''' GRANT CONNECT ON DATABASE {raw_db} TO junior_data_engineer; '''
        grant_jde_access_to_database_sql_query_2                =           f''' GRANT CONNECT ON DATABASE {staging_db} TO junior_data_engineer; '''
        grant_jde_access_to_database_sql_query_3                =           f''' GRANT CONNECT ON DATABASE {semantic_db} TO junior_data_engineer; '''
        grant_jde_access_to_database_sql_query_4                =           f''' GRANT CONNECT ON DATABASE {dwh_db} TO junior_data_engineer; '''
        
        grant_sde_access_to_database_sql_query_1                =           f''' GRANT CONNECT ON DATABASE {raw_db} TO senior_data_engineer; '''
        grant_sde_access_to_database_sql_query_2                =           f''' GRANT CONNECT ON DATABASE {staging_db} TO senior_data_engineer; '''
        grant_sde_access_to_database_sql_query_3                =           f''' GRANT CONNECT ON DATABASE {semantic_db} TO senior_data_engineer; '''
        grant_sde_access_to_database_sql_query_4                =           f''' GRANT CONNECT ON DATABASE {dwh_db} TO senior_data_engineer; '''


        ## C. Data scientists 
        grant_jds_access_to_database_sql_query_1                =           f''' GRANT CONNECT ON DATABASE {staging_db} TO junior_data_scientist; '''
        grant_jds_access_to_database_sql_query_2                =           f''' GRANT CONNECT ON DATABASE {semantic_db} TO junior_data_scientist; '''
        grant_jds_access_to_database_sql_query_3                =           f''' GRANT CONNECT ON DATABASE {dwh_db} TO junior_data_scientist; '''

        grant_sds_access_to_database_sql_query_1                =           f''' GRANT CONNECT ON DATABASE {staging_db} TO senior_data_scientist; '''
        grant_sds_access_to_database_sql_query_2                =           f''' GRANT CONNECT ON DATABASE {semantic_db} TO senior_data_scientist; '''
        grant_sds_access_to_database_sql_query_3                =           f''' GRANT CONNECT ON DATABASE {dwh_db} TO senior_data_scientist; '''




        # For granting access to viewing metadata on objects within the specified schema 

        ## A. Data analysts
        grant_jda_access_to_schema_info_sql_query               =           f''' GRANT USAGE ON SCHEMA {dwh_reporting_schema} TO junior_data_analyst   ; '''
        grant_sda_access_to_schema_info_sql_query               =           f''' GRANT USAGE ON SCHEMA {dwh_reporting_schema} TO senior_data_analyst   ; '''


        ## B. Data engineers
        grant_jde_access_to_schema_info_sql_query_1               =           f''' GRANT USAGE ON SCHEMA {raw_main_schema} TO junior_data_engineer        ;  '''
        grant_jde_access_to_schema_info_sql_query_2               =           f''' GRANT USAGE ON SCHEMA {staging_dev_schema} TO junior_data_engineer     ;  '''
        grant_jde_access_to_schema_info_sql_query_3               =           f''' GRANT USAGE ON SCHEMA {staging_prod_schema} TO junior_data_engineer     ; '''
        grant_jde_access_to_schema_info_sql_query_4               =           f''' GRANT USAGE ON SCHEMA {semantic_dev_schema} TO junior_data_engineer     ; '''
        grant_jde_access_to_schema_info_sql_query_5               =           f''' GRANT USAGE ON SCHEMA {semantic_prod_schema} TO junior_data_engineer    ; '''
        grant_jde_access_to_schema_info_sql_query_6               =           f''' GRANT USAGE ON SCHEMA {dwh_live_schema} TO junior_data_engineer         ; '''
        grant_jde_access_to_schema_info_sql_query_7               =           f''' GRANT USAGE ON SCHEMA {dwh_reporting_schema} TO junior_data_engineer    ; '''


        grant_sde_access_to_schema_info_sql_query_1               =           f''' GRANT USAGE ON SCHEMA {raw_main_schema} TO senior_data_engineer         ; '''
        grant_sde_access_to_schema_info_sql_query_2               =           f''' GRANT USAGE ON SCHEMA {staging_dev_schema} TO senior_data_engineer     ;  '''
        grant_sde_access_to_schema_info_sql_query_3               =           f''' GRANT USAGE ON SCHEMA {staging_prod_schema} TO senior_data_engineer    ;  '''
        grant_sde_access_to_schema_info_sql_query_4               =           f''' GRANT USAGE ON SCHEMA {semantic_dev_schema} TO senior_data_engineer    ;  '''
        grant_sde_access_to_schema_info_sql_query_5               =           f''' GRANT USAGE ON SCHEMA {semantic_prod_schema} TO senior_data_engineer   ;  '''
        grant_sde_access_to_schema_info_sql_query_6               =           f''' GRANT USAGE ON SCHEMA {dwh_live_schema} TO senior_data_engineer        ;  '''
        grant_sde_access_to_schema_info_sql_query_7               =           f''' GRANT USAGE ON SCHEMA {dwh_reporting_schema} TO senior_data_engineer   ;  '''



        ## C. Data scientists 
        grant_jds_access_to_schema_info_sql_query_1               =           f''' GRANT USAGE ON SCHEMA {staging_dev_schema} TO junior_data_scientist     ;  '''
        grant_jds_access_to_schema_info_sql_query_2               =           f''' GRANT USAGE ON SCHEMA {staging_prod_schema} TO junior_data_scientist    ;  '''
        grant_jds_access_to_schema_info_sql_query_3               =           f''' GRANT USAGE ON SCHEMA {semantic_dev_schema} TO junior_data_scientist    ;  '''
        grant_jds_access_to_schema_info_sql_query_4               =           f''' GRANT USAGE ON SCHEMA {semantic_prod_schema} TO junior_data_scientist  ;   '''
        grant_jds_access_to_schema_info_sql_query_5               =           f''' GRANT USAGE ON SCHEMA {dwh_live_schema} TO junior_data_scientist        ;  '''
        grant_jds_access_to_schema_info_sql_query_6               =           f''' GRANT USAGE ON SCHEMA {dwh_reporting_schema} TO junior_data_scientist   ;  '''



        grant_sds_access_to_schema_info_sql_query_1               =           f''' GRANT USAGE ON SCHEMA {staging_dev_schema} TO senior_data_scientist      ; '''
        grant_sds_access_to_schema_info_sql_query_2               =           f''' GRANT USAGE ON SCHEMA {staging_prod_schema} TO senior_data_scientist    ;  '''
        grant_sds_access_to_schema_info_sql_query_3               =           f''' GRANT USAGE ON SCHEMA {semantic_dev_schema} TO senior_data_scientist    ;  '''
        grant_sds_access_to_schema_info_sql_query_4               =           f''' GRANT USAGE ON SCHEMA {semantic_prod_schema} TO senior_data_scientist    ; '''
        grant_sds_access_to_schema_info_sql_query_5               =           f''' GRANT USAGE ON SCHEMA {dwh_live_schema} TO senior_data_scientist         ; '''
        grant_sds_access_to_schema_info_sql_query_6               =           f''' GRANT USAGE ON SCHEMA {dwh_reporting_schema} TO senior_data_scientist   ;  '''




        # For granting table ownership to specific roles
        table_1                             =           'avg_ticket_prices_by_year'
        table_2                             =           'flight_bookings_by_age'
        table_3                             =           'top_destination'
        table_4                             =           'total_sales_by_destination'
        grant_ownership_rights_to_sde       =           f''' ALTER TABLE {dwh_reporting_schema}.{table_1} OWNER TO senior_data_analyst ; '''
        
    


        # For granting privileges to roles

        grant_privileges_for_jda_sql_query = f'GRANT SELECT ON ALL TABLES IN SCHEMA {dwh_reporting_schema} TO junior_data_analyst'
        grant_privileges_for_sda_sql_query = f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {dwh_reporting_schema} TO senior_data_analyst'

        

        # For creating row security policies 
        table_with_restricted_field_1   =   'total_sales_by_destination'
        restricted_field                =   'total_sales'

        set_row_security_policies_for_jda = f'''    CREATE POLICY restrict_jda_policy ON {dwh_reporting_schema}.{table_with_restricted_field_1}
                                                    FOR SELECT 
                                                    TO junior_data_analyst
                                                    USING ({restricted_field} != 0 );
        '''



        # Validate the Postgres database connection
        if postgres_connection.closed == 0:
            root_logger.debug(f"")
            root_logger.info("=================================================================================")
            root_logger.info(f"CONNECTION SUCCESS: Managed to connect successfully to the {active_db_name} database!!")
            root_logger.info(f"Connection details: {postgres_connection.dsn} ")
            root_logger.info("=================================================================================")
            root_logger.debug("")
        
        elif postgres_connection.closed != 0:
            raise ConnectionError("CONNECTION ERROR: Unable to connect to the demo_company database...") 
        


        # ================================================== CREATE CUSTOM ROLES =======================================

        try:
            root_logger.info(f'=========================================== CREATE CUSTOM ROLES =======================================')
            root_logger.info(f'======================================================================================================')
            root_logger.info(f'')
            root_logger.info(f'')
             
            for data_role in role_databases:
                checking_if_roles_exist_sql_query                   =       f'''SELECT 1 FROM pg_roles WHERE rolname = '{data_role}' ;'''
                cursor.execute(checking_if_roles_exist_sql_query)
                # postgres_connection.commit()

                role_exists = cursor.fetchone()

                if role_exists:
                    for data_role, databases in role_databases.items():
                        for db in databases:
                            if db in db_schemas:
                                schemas = db_schemas[db]
                                for schema in schemas:
                                    try:
                                        revoke_all_privileges_from_database = f'''   REVOKE ALL PRIVILEGES ON DATABASE {db} FROM {data_role} ;  '''
                                        cursor.execute(revoke_all_privileges_from_database)
                                        # postgres_connection.commit()
                                        root_logger.debug(f''' Revoking all privileges for all tables in '{db}' database for '{data_role}' role... ''')


                                        revoke_all_privileges_from_all_tables = f''' REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {schema} from {data_role} ;'''
                                        cursor.execute(revoke_all_privileges_from_all_tables)

                                        revoke_all_privileges_from_schema =     f''' REVOKE ALL PRIVILEGES ON SCHEMA {schema} FROM {data_role}  ; '''
                                        cursor.execute(revoke_all_privileges_from_schema)

                                        root_logger.debug(f''' Revoking all privileges for all tables in '{schema}' schema for '{data_role}' role... ''')
                                    
                                        drop_role_sql_query  = f''' DROP ROLE {data_role}; '''
                                        cursor.execute(drop_role_sql_query)
                                        # postgres_connection.commit()
                                        root_logger.info(f'Dropped "{data_role}" successfully ... Now re-creating "{data_role}" role...')

                                        creating_roles_sql_query                =       f'''CREATE ROLE {data_role} NOLOGIN;'''
                                        cursor.execute(creating_roles_sql_query)
                                        # postgres_connection.commit()
                                        root_logger.info(f'''Successfully created '{data_role}' role''')
                                            
                                        root_logger.info(f'===========================================')
                                        root_logger.info(f'')
                                        root_logger.info(f'')

                                    except psycopg2.Error as e:
                                        postgres_connection.rollback()
                                        continue
                            else:
                                root_logger.error(f"Database '{db}' not found in 'db_schema' dictionary ")

                else:
                    creating_roles_sql_query                =       f'''CREATE ROLE {data_role} NOLOGIN;'''
                    cursor.execute(creating_roles_sql_query)
                    # postgres_connection.commit()

                    root_logger.info(f'''Successfully created '{data_role}' role''')
                    root_logger.info(f'===========================================')
                    root_logger.info(f'')
                    root_logger.info(f'')


        except psycopg2.Error as e:
            root_logger.error(e)
             


            
        # ================================================== GRANT DATABASE AND INFO SCHEMA ACCESS =======================================

        try:
            root_logger.info(f'=========================================== GRANT DATABASE AND INFO SCHEMA ACCESS =======================================')
            root_logger.info(f'======================================================================================================')
            root_logger.info(f'')
            root_logger.info(f'')


            ## A. Data analysts
            cursor.execute(grant_jda_access_to_database_sql_query)
            root_logger.info(f'''Granted 'junior_data_analyst' role access to connecting to '{dwh_db}' database ''')
            cursor.execute(grant_jda_access_to_schema_info_sql_query)
            root_logger.info(f'''Granted 'junior_data_analyst' role access to viewing the information on '{dwh_reporting_schema}' schema's objects ''')
            root_logger.info(f'===========================================')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')

            cursor.execute(grant_sda_access_to_database_sql_query)
            root_logger.info(f'''Granted 'senior_data_analyst' role access to connecting to '{dwh_db}' database ''')
            cursor.execute(grant_sda_access_to_schema_info_sql_query)
            root_logger.info(f'''Granted 'senior_data_analyst' role access to viewing the information on '{dwh_reporting_schema}' schema's objects ''')
            root_logger.info(f'===========================================')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')



            # ## B. Data engineers
            # cursor.execute(grant_jde_access_to_database_sql_query_1)
            # root_logger.info(f'''Granted 'junior_data_engineer' role access to connecting to '{raw_db}' database ''')
            # cursor.execute(grant_jde_access_to_schema_info_sql_query_1)
            # root_logger.info(f'''Granted 'junior_data_engineer' role access to viewing the information on '{raw_main_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')

            # cursor.execute(grant_jde_access_to_database_sql_query_2)
            # root_logger.info(f'''Granted 'junior_data_engineer' role access to connecting to '{staging_db}' database ''')
            # cursor.execute(grant_jde_access_to_schema_info_sql_query_2)
            # cursor.execute(grant_jde_access_to_schema_info_sql_query_3)
            # root_logger.info(f'''Granted 'junior_data_engineer' role access to viewing the information on '{staging_dev_schema}' schema's objects ''')
            # root_logger.info(f'''Granted 'junior_data_engineer' role access to viewing the information on '{staging_prod_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')

            # cursor.execute(grant_jde_access_to_database_sql_query_3)
            # root_logger.info(f'''Granted 'junior_data_engineer' role access to connecting to '{semantic_db}' database ''')
            # cursor.execute(grant_jde_access_to_schema_info_sql_query_4)
            # cursor.execute(grant_jde_access_to_schema_info_sql_query_5)
            # root_logger.info(f'''Granted 'junior_data_engineer' role access to viewing the information on '{semantic_dev_schema}' schema's objects ''')
            # root_logger.info(f'''Granted 'junior_data_engineer' role access to viewing the information on '{semantic_prod_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')

            # cursor.execute(grant_jde_access_to_database_sql_query_4)
            # root_logger.info(f'''Granted 'junior_data_engineer' role access to connecting to '{dwh_db}' database ''')
            # cursor.execute(grant_jde_access_to_schema_info_sql_query_6)
            # cursor.execute(grant_jde_access_to_schema_info_sql_query_7)
            # root_logger.info(f'''Granted 'junior_data_engineer' role access to viewing the information on '{dwh_live_schema}' schema's objects ''')
            # root_logger.info(f'''Granted 'junior_data_engineer' role access to viewing the information on '{dwh_reporting_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')

            
            # cursor.execute(grant_sde_access_to_database_sql_query_1)
            # root_logger.info(f'''Granted 'senior_data_engineer' role access to connecting to '{raw_db}' database ''')
            # cursor.execute(grant_sde_access_to_schema_info_sql_query_1)
            # root_logger.info(f'''Granted 'senior_data_engineer' role access to viewing the information on '{raw_main_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')

            # cursor.execute(grant_sde_access_to_database_sql_query_2)
            # root_logger.info(f'''Granted 'senior_data_engineer' role access to connecting to '{staging_db}' database ''')
            # cursor.execute(grant_sde_access_to_schema_info_sql_query_2)
            # cursor.execute(grant_sde_access_to_schema_info_sql_query_3)
            # root_logger.info(f'''Granted 'senior_data_engineer' role access to viewing the information on '{staging_dev_schema}' schema's objects ''')
            # root_logger.info(f'''Granted 'senior_data_engineer' role access to viewing the information on '{staging_prod_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')

            # cursor.execute(grant_sde_access_to_database_sql_query_3)
            # root_logger.info(f'''Granted 'senior_data_engineer' role access to connecting to '{semantic_db}' database ''')
            # cursor.execute(grant_sde_access_to_schema_info_sql_query_4)
            # cursor.execute(grant_sde_access_to_schema_info_sql_query_5)
            # root_logger.info(f'''Granted 'senior_data_engineer' role access to viewing the information on '{semantic_dev_schema}' schema's objects ''')
            # root_logger.info(f'''Granted 'senior_data_engineer' role access to viewing the information on '{semantic_prod_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')

            # cursor.execute(grant_sde_access_to_database_sql_query_4)
            # root_logger.info(f'''Granted 'senior_data_engineer' role access to connecting to '{dwh_db}' database ''')
            # cursor.execute(grant_sde_access_to_schema_info_sql_query_6)
            # cursor.execute(grant_sde_access_to_schema_info_sql_query_7)
            # root_logger.info(f'''Granted 'senior_data_engineer' role access to viewing the information on '{dwh_live_schema}' schema's objects ''')
            # root_logger.info(f'''Granted 'senior_data_engineer' role access to viewing the information on '{dwh_reporting_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')






            # ## C. Data scientists 
            # cursor.execute(grant_jds_access_to_database_sql_query_1)
            # root_logger.info(f'''Granted 'junior_data_scientist' role access to connecting to '{raw_db}' database ''')
            # cursor.execute(grant_jds_access_to_schema_info_sql_query_1)
            # cursor.execute(grant_jds_access_to_schema_info_sql_query_2)
            # root_logger.info(f'''Granted 'junior_data_scientist' role access to viewing the information on '{raw_main_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')

            # cursor.execute(grant_jds_access_to_database_sql_query_2)
            # root_logger.info(f'''Granted 'junior_data_scientist' role access to connecting to '{staging_db}' database ''')
            # cursor.execute(grant_jds_access_to_schema_info_sql_query_3)
            # cursor.execute(grant_jds_access_to_schema_info_sql_query_4)
            # root_logger.info(f'''Granted 'junior_data_scientist' role access to viewing the information on '{staging_dev_schema}' schema's objects ''')
            # root_logger.info(f'''Granted 'junior_data_scientist' role access to viewing the information on '{staging_prod_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')

            # cursor.execute(grant_jds_access_to_database_sql_query_3)
            # root_logger.info(f'''Granted 'junior_data_scientist' role access to connecting to '{semantic_db}' database ''')
            # cursor.execute(grant_jds_access_to_schema_info_sql_query_5)
            # cursor.execute(grant_jds_access_to_schema_info_sql_query_6)
            # root_logger.info(f'''Granted 'junior_data_scientist' role access to viewing the information on '{semantic_dev_schema}' schema's objects ''')
            # root_logger.info(f'''Granted 'junior_data_scientist' role access to viewing the information on '{semantic_prod_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')




            # cursor.execute(grant_sds_access_to_database_sql_query_1)
            # root_logger.info(f'''Granted 'senior_data_scientist' role access to connecting to '{raw_db}' database ''')
            # cursor.execute(grant_sds_access_to_schema_info_sql_query_1)
            # cursor.execute(grant_sds_access_to_schema_info_sql_query_2)
            # root_logger.info(f'''Granted 'senior_data_scientist' role access to viewing the information on '{raw_main_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')

            # cursor.execute(grant_sds_access_to_database_sql_query_2)
            # root_logger.info(f'''Granted 'senior_data_scientist' role access to connecting to '{staging_db}' database ''')
            # cursor.execute(grant_sds_access_to_schema_info_sql_query_3)
            # cursor.execute(grant_sds_access_to_schema_info_sql_query_4)
            # root_logger.info(f'''Granted 'senior_data_scientist' role access to viewing the information on '{staging_dev_schema}' schema's objects ''')
            # root_logger.info(f'''Granted 'senior_data_scientist' role access to viewing the information on '{staging_prod_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')

            # cursor.execute(grant_sds_access_to_database_sql_query_3)
            # root_logger.info(f'''Granted 'senior_data_scientist' role access to connecting to '{semantic_db}' database ''')
            # cursor.execute(grant_sds_access_to_schema_info_sql_query_5)
            # cursor.execute(grant_sds_access_to_schema_info_sql_query_6)
            # root_logger.info(f'''Granted 'senior_data_scientist' role access to viewing the information on '{semantic_dev_schema}' schema's objects ''')
            # root_logger.info(f'''Granted 'senior_data_scientist' role access to viewing the information on '{semantic_prod_schema}' schema's objects ''')
            # root_logger.info(f'===========================================')
            # root_logger.info(f'')
            # root_logger.info(f'')


        
        except psycopg2.Error as e:
            root_logger.error(e)


        
        # ================================================== GRANT TABLE OWNERSHIP RIGHTS TO ROLES =======================================

        try:
            root_logger.info(f'=========================================== GRANT TABLE OWNERSHIP RIGHTS TO ROLES =======================================')
            root_logger.info(f'======================================================================================================')
            root_logger.info(f'')
            root_logger.info(f'')

            cursor.execute(grant_ownership_rights_to_sde)
            # postgres_connection.commit()
            root_logger.info(f'''Successfully granted 'senior_data_analyst' ownership of '{table_1}' table in '{dwh_db}.{dwh_reporting_schema}' schema  ''')
            root_logger.info(f'''Successfully granted 'senior_data_analyst' ownership of '{table_2}' table in '{dwh_db}.{dwh_reporting_schema}' schema  ''')
            root_logger.info(f'''Successfully granted 'senior_data_analyst' ownership of '{table_3}' table in '{dwh_db}.{dwh_reporting_schema}' schema  ''')
            root_logger.info(f'''Successfully granted 'senior_data_analyst' ownership of '{table_4}' table in '{dwh_db}.{dwh_reporting_schema}' schema  ''')
            root_logger.info(f'===========================================')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')
        
        
        except psycopg2.Error as e:
            root_logger.error(e)






        # ================================================== GRANT PRIVILEGES TO ROLES =======================================

        try:
            root_logger.info(f'=========================================== GRANT PRIVILEGES TO ROLES =======================================')
            root_logger.info(f'======================================================================================================')
            root_logger.info(f'')
            root_logger.info(f'')

            cursor.execute(grant_privileges_for_jda_sql_query)
            # postgres_connection.commit()
            root_logger.info(f'''Successfully granted privileges to 'junior_data_analyst' on all tables in '{dwh_db}.{dwh_reporting_schema}' schema.  ''')
            root_logger.info(f'===========================================')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')
        
            cursor.execute(grant_privileges_for_sda_sql_query)
            # postgres_connection.commit()
            root_logger.info(f'''Successfully granted privileges to 'senior_data_analyst' on all tables in '{dwh_db}.{dwh_reporting_schema}' schema.  ''')
            root_logger.info(f'===========================================')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')
        
        except psycopg2.Error as e:
            root_logger.error(e)


        # ================================================== SET ROW SECURITY POLICIES =======================================


        try:
            root_logger.info(f'=========================================== SET ROW SECURITY POLICIES =======================================')
            root_logger.info(f'======================================================================================================')
            root_logger.info(f'')
            root_logger.info(f'')

            cursor.execute(set_row_security_policies_for_jda)
            # postgres_connection.commit()
            root_logger.info(f'''Successfully created row security policy for '{table_with_restricted_field_1}' table to regulate the data the 'junior_data_analyst' role views in the '{restricted_field}' field .  ''')
            root_logger.info(f'===========================================')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')
            root_logger.info(f'')
        
        except psycopg2.Error as e:
            root_logger.error(e)


    except psycopg2.Error as e:
            root_logger.error(e)
        

set_up_access_controls(postgres_connection)





# Miscellaneous scripts

'''

-- For creating the roles
CREATE ROLE junior_data_analyst NOLOGIN ;
CREATE ROLE senior_data_analyst NOLOGIN ;

CREATE ROLE junior_data_engineer NOLOGIN ;
CREATE ROLE senior_data_engineer NOLOGIN ;

CREATE ROLE junior_data_scientist NOLOGIN ;
CREATE ROLE senior_data_scientist NOLOGIN ;



-- For deleting the roles 
DROP ROLE junior_data_analyst;
DROP ROLE senior_data_analyst;

DROP ROLE junior_data_engineer;
DROP ROLE senior_data_engineer;

DROP ROLE junior_data_scientist;
DROP ROLE senior_data_scientist;



# SECURITY ROLES TEST

-- Check table ownership
SELECT tableowner FROM pg_tables WHERE schemaname = 'reporting' AND tablename = 'avg_ticket_prices_by_year';



-- Check if delegated privileges work for 'junior_data_analyst'
SET ROLE junior_data_analyst;
SELECT * FROM reporting.avg_ticket_prices_by_year; 


SET ROLE senior_data_analyst;
SELECT * FROM reporting.avg_ticket_prices_by_year; 


-- Check if row security policy is set up correctly
SELECT * FROM pg_policy WHERE polname = 'restrict_jda_policy'

'''