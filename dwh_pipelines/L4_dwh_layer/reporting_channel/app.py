import os 
import dash 
import psycopg2
import configparser
import pandas as pd
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc
from pathlib import Path
import logging, coloredlogs
import plotly.express as px 
from sqlalchemy import create_engine


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
file_handler        =   logging.FileHandler('logs/L4_dwh_layer/user_access_layer/' + current_filepath + '.log', mode='w')
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


def render_dash_visualizations(postgres_connection):
    try:
        
        # Set up constants
        
        active_schema_name                  =      'reporting'
        active_db_name                      =       database
        sql_query_1                         =      f'''SELECT * FROM {active_schema_name}.avg_ticket_prices_by_year ;   '''
        sql_query_2                         =      f'''SELECT * FROM {active_schema_name}.flight_bookings_by_age   ;   '''
        sql_query_3                         =      f'''SELECT * FROM {active_schema_name}.top_destinations ;    '''
        sql_query_4                         =      f'''SELECT * FROM {active_schema_name}.total_sales_by_destination ;  '''
        sql_query_5                         =      f'''SELECT * FROM {active_schema_name}.customer_booking_trend ;  '''
        sql_query_6                         =      f'''SELECT * FROM {active_schema_name}.total_sales_by_payment_method ;  '''
        sql_query_7                         =      f'''SELECT * FROM {active_schema_name}.total_sales_by_year ;  '''
        sql_alchemy_engine                  =       create_engine(f'postgresql://{username}:{password}@{host}:{port}/{database}')
        data_warehouse_layer                =      'DWH - UAL'
        

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
        


        # ================================================== CREATE DASHBOARD VIA PLOTLY-DASH =======================================
        

        avg_ticket_prices_by_year_df                =       pd.read_sql(sql_query_1, con=sql_alchemy_engine)
        flight_bookings_by_age_df                      =       pd.read_sql(sql_query_2, con=sql_alchemy_engine)
        top_destinations_df                         =       pd.read_sql(sql_query_3, con=sql_alchemy_engine)
        total_sales_by_destination_df               =       pd.read_sql(sql_query_4, con=sql_alchemy_engine)

        # Commit the changes made in Postgres 
        # postgres_connection.commit()


        # Create Dash app 
        app = dash.Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])


        # Create graphs for dashboard
        graph_1 = dcc.Graph(
                    figure=px.scatter(avg_ticket_prices_by_year_df, x="booking_year", y="arrival_city", size="avg_ticket_price", color="arrival_city", title="Average Ticket Prices by Destination and Year")
                    )
        
        graph_2 = dcc.Graph(
                    figure=px.bar(flight_bookings_by_age_df, x="age", y="no_of_bookings")
                    )
        
        graph_3 = dcc.Graph(
                    figure=px.treemap(top_destinations_df, path=['destination'], values="no_of_bookings", color="no_of_bookings", color_continuous_scale="Blues")
                    )  

        graph_4 = dcc.Graph(
                    figure=px.bar(top_destinations_df, x="destination", y="no_of_bookings", title="Top 10 Most Booked Destinations")
                    )
        
        graph_5 = dcc.Graph(
                    figure=px.scatter(total_sales_by_destination_df, x="booking_year", y="arrival_city", size="total_sales", color="arrival_city", title="Total Sales by Destination and Year")
                    )
        
        graph_6 = dcc.Graph(
                    figure=px.bar(top_destinations_df, x="destination", y="no_of_bookings")
                    )

        # Create the layout for the Dash app
        app.layout = html.Div(
             [
             
             dbc.Row(
                dbc.Col(
             html.H1("Flight Booking Data")
                )
             ),
             dbc.Row(
                dbc.Col(
             html.H1("")
                )
             ),
             
             dbc.Row(
                dbc.Col(
             html.H1("")
                )
             ),
             dbc.Row(
             [
               dbc.Col(
             [html.H2("Number of Bookings by Age"),
                    graph_2],
                ),
                dbc.Col(
             [html.H2("Top Destinations"),
                    graph_3],
                ),
             ]
             ),

             dbc.Row(
                dbc.Col(
             [html.H2("Top 10 Most Booked Destinations"),
                graph_6]
                ),
             ),
             dbc.Row([
                dbc.Col(
             html.Div(""), align="start"
                ),
                
                dbc.Col(
             html.Div(""), align="middle"
                ),
                
                dbc.Col(
             html.H2("DW & DSS HK231"), align="end"
                )]
                
             ),

            ]
        )


        root_logger.info(f'')
        root_logger.info('================================================')


        # Run the app  
        app.run_server(debug=True)
        root_logger.info("Now rendering Dash app....")


    except psycopg2.Error as e:
            root_logger.info(e)
        

render_dash_visualizations(postgres_connection)

