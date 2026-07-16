import pyodbc
import requests
import logging
import credentials
from datetime import datetime
import os
import fetchfromdb as ffdb

# Database connection details
server = credentials.server
database = credentials.database
username = credentials.prodsnapshotUser
password = credentials.prodsnapshotPass


# Setup connection to SQL Server
conn = pyodbc.connect(f'DRIVER={{ODBC Driver 18 for SQL Server}};'
                      f'SERVER={server};'
                      f'DATABASE={database};'
                      f'UID={username};'
                      f'PWD={password};'
                    #   f'Trusted_Connection=Yes;'
                      f'TrustServerCertificate=yes')
cursor = conn.cursor()

# ffdb.update_add_new_vins() # adding new vins to the list of possible updates - NEW ORIGINATINS

# -------------------------------------------------------------------------------------------------------- #

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
os.makedirs('logs', exist_ok=True)
# Create the log 
log_filename = f"logs/output_{timestamp}.log"
logging.basicConfig(filename=log_filename, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Configure logging
logging.basicConfig(filename='Output.txt', level=logging.INFO)


# ffdb.update_add_new_vins()

url = OathEndpoint

headers = {
    'Content-Type': 'application/x-www-form-urlencoded'
}

data = {    
    'audience': credentials.audience,
    'grant_type':credentials.grant_type,
    'client_id': credentials.client_id,
    'client_secret': credentials.client_secret
}

response = requests.post(url, headers=headers, data=data)

# print(response.status_code)
# print(response.json())
# vin = 'KMHGC4DDXDU249474'
token = response.json().get('access_token')
email=credentials.carfax_email
Tpk =credentials.tpk
portfolio=credentials.portfolioid

import time

for i in range(1):
    print(f"\n🌀 Starting run {i + 1}")

    # Step 1: Fetch unlabeled VINs
    labeled_data = ffdb.prep_MMY()
    print(labeled_data)
    trim_data = []
    for item in labeled_data:
        app_no = item['DaybreakAppNo']
        # vin = item['Vin']
        mileage = item['Mileage']
        year = item['Year']
        make = item['Make']
        model = item['Model']
        # Get trim from API
        # trim = ffdb.get_trim(app_no, vin, mileage, token)
        trim = ffdb.get_trim_MMY(app_no,model,year,make, mileage, token)
        if trim:
            trim_data.append((trim, app_no))

    # Step 2: Update DB with found trims
    if trim_data:
        ffdb.update_trims_in_db(trim_data)

    # Step 3: Fetch vehicle details for trimmed records
    labeled_data2 = ffdb.prep_trim_MMY()
    vehicle_data = ffdb.fetch_vehicle_details_MMY(labeled_data2, token)

    if vehicle_data:
        ffdb.update_vehicle_details_in_db(conn, vehicle_data)

    # Step 4: Get valuation data
    labeled_data3 = ffdb.prep_valu_MMY()
    valu_data = ffdb.fetch_valu_MMY(labeled_data3, token)
    ffdb.update_valu_details_in_db(conn, valu_data)

    print(f"✅ Finished run {i + 1}")
    time.sleep(1)  # Optional delay between runs
