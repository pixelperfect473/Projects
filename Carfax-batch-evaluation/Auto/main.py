import pyodbc
# import requests
import logging
import credentials
from datetime import datetime
import auth0 as ao
import os
import db_ops as ops
import tokens

# server = 'Wagas.hankeyinvestments.com' #'prodsnapshot'  
# database = 'NLC_CACRSvc' #'CACRSvc_20240808'
# username = credentials.prodsnapshotUser
# password = credentials.prodsnapshotPass


# # Setup connection to SQL Server
# conn = pyodbc.connect(f'DRIVER={{ODBC Driver 18 for SQL Server}};'
#                       f'SERVER={server};'
#                       f'DATABASE={database};'
#                       f'UID={username};'
#                       f'PWD={password};'
#                     #   f'Trusted_Connection=Yes;'
#                       f'TrustServerCertificate=yes')
# cursor = conn.cursor()

ao.get_auth()
token = tokens.TOKEN
email=credentials.carfax_email
Tpk =credentials.tpk
portfolio=credentials.portfolioid

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
os.makedirs('logs', exist_ok=True)
# make the log 
log_filename = f"logs/output_{timestamp}.log"
logging.basicConfig(filename=log_filename, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

logging.basicConfig(filename='Output.txt', level=logging.INFO)

ops.update_add_new_vins()

FirstStepData = ops.prep_vins()


TrimsResponse=[]
for vin in FirstStepData:
        AppNo = vin['DCAppNO']
        VinCode = vin['VIN']
        Miles = vin['Mileage']
        trim = ops.get_trim(AppNo, VinCode, Miles, tokens.TOKEN)
        if trim:
            TrimsResponse.append((trim, AppNo))


ops.update_trims_in_db(TrimsResponse)

ops.update_vehicle_details_in_db(ops.fetch_vehicle_details(ops.prep_trim(), tokens.TOKEN))

ops.update_valu_details_in_db(ops.fetch_valu(ops.prep_valu(),tokens.TOKEN))

print('COMPLETED -- CHECK LOGS.')




    