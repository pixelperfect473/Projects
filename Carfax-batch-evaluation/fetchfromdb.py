import pyodbc
import requests
import logging
import json  
import credentials
import time  
from datetime import datetime
import os
import pandas as pd

#FETCH THE VINS I WANT TO LOOK UP
# Database connection details
server = 'Wagas.hankeyinvestments.com' #'prodsnapshot'  
database = 'NLC_CACRSvc' #'CACRSvc_20240808'
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

#update new originations
def update_add_new_vins():
    cursor.execute('''select gi.DaybreakAppNo, bp.VehicleVIN, bp.VehicleMileage
    from prodsnapshot.nlc_ss.deal.GeneralInfo gi 
    left join prodsnapshot.nlc_ss.bp.BuyProgram bp on gi.DealID =bp.DealID and finalized=1
    left join NLC_CACRSvc.dbo.VINDecode b on b.daybreakappno = gi.daybreakappno
    where gi.daybreakappno is not null and b.daybreakappno is null and gi.createddate >= GETDATE()-7''')
    rows = cursor.fetchall()
    insert_query = '''INSERT INTO VINDecode (DaybreakAppNo, VehicleVIN, VehicleMileage)
                    VALUES (?,?,?)'''
    for row in rows:
        cursor.execute(insert_query, (row[0], row[1], row[2]))  # Insert 
    conn.commit()

def prep_vins():
    cursor.execute("""
        SELECT top 100 DaybreakAppNo, VehicleVin, VehicleMileage
        FROM NLC_CACRSvc.dbo.VINDecode
        WHERE Trim IS NULL 
    """)
    data = cursor.fetchall()
    labeled_data = [
        {'DaybreakAppNo': app_no, 'Vin': vin, 'Mileage': mileage}
        for app_no, vin, mileage in data
    ]
    return labeled_data

def prep_MMY():
    cursor.execute("""
        SELECT top 100 DaybreakAppNo, Year, Make, Model, VehicleMileage
        FROM NLC_CACRSvc.dbo.VINDecode
        WHERE Trim IS NULL 
    """)
    data = cursor.fetchall()
    labeled_data = [
        {'DaybreakAppNo': app_no, 'Year': Year, 'Make': Make, 'Model':Model, 'Mileage': Mileage}
        for app_no, Year, Make, Model,Mileage in data
    ]
    return labeled_data

def prep_trim():
    cursor.execute("""
        SELECT top 100 DaybreakAppNo, VehicleVin, VehicleMileage, Trim
        FROM NLC_CACRSvc.dbo.VINDecode
        WHERE Trim IS NOT NULL and transmission is null  
    """)
    data = cursor.fetchall()
    labeled_data2 = [
        {'DaybreakAppNo': app_no, 'Vin': vin, 'Mileage': mileage, 'Trim': trim}
        for app_no, vin, mileage, trim in data
    ]
    return labeled_data2


def prep_trim_MMY():
    cursor.execute("""
        SELECT top 100 DaybreakAppNo, Make, Year, Model, VehicleMileage, Trim
        FROM NLC_CACRSvc.dbo.VINDecode
        WHERE Trim IS NOT NULL and transmission is null 
    """)
    data = cursor.fetchall()
    labeled_data2 = [
        {'DaybreakAppNo': app_no, 'Make': Make, 'Year':Year, 'Model':Model, 'Mileage': mileage, 'Trim': trim}
        for app_no, Make, Model, Year, mileage, trim in data
    ]
    return labeled_data2

def prep_valu():
    cursor.execute("""
        SELECT top 100 DaybreakAppNo, VehicleVin, VehicleMileage, Trim, engine, transmission, fuelType, driveTrain
        FROM NLC_CACRSvc.dbo.VINDecode
        WHERE Retail is null and trim is not null and transmission is not null 
    """)
    data = cursor.fetchall()
    labeled_data3 = [
        {'DaybreakAppNo': app_no, 'Vin': vin, 'Mileage': mileage, 'Trim': trim, 'engine': engine, 'transmission': transmission, 'fuelType': fuelType, 'driveTrain': driveTrain}
        for app_no, vin, mileage, trim, engine, transmission, fuelType, driveTrain in data
    ]
    return labeled_data3

def prep_valu_MMY():
    cursor.execute("""
        SELECT top 100 DaybreakAppNo, Make, Year, Model, VehicleMileage, Trim, engine, transmission, fuelType, driveTrain
        FROM NLC_CACRSvc.dbo.VINDecode
        WHERE Retail is null and trim is not null and transmission is not null 
    """)
    data = cursor.fetchall()
    labeled_data3 = [
        {'DaybreakAppNo': app_no, 'Make': Make, 'Year':Year, 'Model':Model, 'Mileage': mileage, 'Trim': trim, 'engine': engine, 'transmission': transmission, 'fuelType': fuelType, 'driveTrain': driveTrain}
        for app_no, Make, Year, Model, mileage, trim, engine, transmission, fuelType, driveTrain in data
    ]
    return labeled_data3

def update_trims_in_db(trim_data):
    # Prepare the update query
    update_query = """
    UPDATE VINDecode
    SET Trim = ?
    WHERE DaybreakAppNo = ?
    """

    # Execute the query for all trims
    cursor.executemany(update_query, trim_data)

    # Commit the transaction
    conn.commit()
    print(f"Database updated for {len(trim_data)} records.")

def get_trim(app_no,vin,mileage,token):
    url = 'https://api.carfax.ca/vindecode/api/v2/SingleVin/SingleVinDecode'
    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {token}',
        'Auth0CarfaxCanadaJWTBearer': f'{token}'
    }
    params ={
        'Vin': vin,
        'Odometer': str(mileage)
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code==200:
        try:
            trims = response.json().get("ResponseData", {}).get("Trims", [])
            trim = trims[0] if trims else None
            return trim
        except Exception as e:
            print(f'Error extracting trim for {app_no}')
            return None
    else: 
        print(f'API CALL FAILED for {app_no} with status code {response.status_code}.')
        return None
    
def get_trim_MMY(app_no,Year,Make,Model,Mileage, token):
    url = 'https://api.carfax.ca/vindecode/api/v2/SingleVin/SingleVinDecode'
    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {token}',
        'Auth0CarfaxCanadaJWTBearer': f'{token}'
    }
    params ={
        'Year': Year,
        'Odometer': str(Mileage),
        'Year': Year,
        'Make': Make,
        'Model': Model
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code==200:
        try:
            trims = response.json().get("ResponseData", {}).get("Trims", [])
            trim = trims[0] if trims else None
            return trim
        except Exception as e:
            print(f'Error extracting trim for {app_no}')
            return None
    else: 
        print(f'API CALL FAILED for {app_no} with status code {response.status_code}.')
        return None

def fetch_vehicle_details(labeled_data2, token):
    url = 'https://api.carfax.ca/vindecode/api/v2/SingleVin/SingleVinDecode'
    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {token}',
        'Auth0CarfaxCanadaJWTBearer': f'{token}'
    }

    results = []

    for record in labeled_data2:
        vin = record['Vin']
        mileage = record['Mileage']
        trim = record['Trim']
        app_no = record['DaybreakAppNo']

        params = {'Vin': vin, 'Odometer': str(mileage), 'Trim': trim}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            print(f'API call failed for {app_no} - status: {response.status_code}')
            continue

        try:
            data = response.json().get("ResponseData", {})
            vi = data.get("VehicleInformation", {})
            eo = data.get("EngineOptions", [{}])[0]
            do = eo.get("DrivetrainOptions", [{}])[0]
            #bs = do.get("BodyStyleOptions", [{}])[0]

            result = {
                'app_no': app_no,
                'vin': vi.get("Vin"),
                'year': vi.get("Year"),
                'make': vi.get("Make"),
                'model': vi.get("Model"),
                'engine': eo.get("EngineLabel"),
                'fuel_type': eo.get("FuelType"),
                'drivetrain': do.get("DriveTrain"),
                'transmission': 'Automatic' #do.get("TransmissionOptions", [None])[0]
                # Uncomment below if needed:
                # 'body_style': bs.get("BodyStyle"),
                # 'box_length': bs.get("BoxLengthOptions", [None])[0]
            }

            results.append(result)

        except Exception as e:
            print(f'Error processing record {app_no}: {e}')
            continue

    return results

def fetch_vehicle_details_MMY(labeled_data2, token):
    url = 'https://api.carfax.ca/vindecode/api/v2/SingleVin/SingleVinDecode'
    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {token}',
        'Auth0CarfaxCanadaJWTBearer': f'{token}'
    }

    results = []

    for record in labeled_data2:
        #vin = record['Vin']
        mileage = record['Mileage']
        trim = record['Trim']
        app_no = record['DaybreakAppNo']
        Make = record['Make']
        Model = record['Model']
        Year = record['Year']

        params = {'Year':Year,'Make':Make,'Model':Model, 'Odometer': str(mileage), 'Trim': trim}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            print(f'API call failed for {app_no} - status: {response.status_code}')
            continue

        try:
            data = response.json().get("ResponseData", {})
            vi = data.get("VehicleInformation", {})
            eo = data.get("EngineOptions", [{}])[0]
            do = eo.get("DrivetrainOptions", [{}])[0]
            #bs = do.get("BodyStyleOptions", [{}])[0]

            result = {
                'app_no': app_no,
                'vin': vi.get("Vin"),
                'year': vi.get("Year"),
                'make': vi.get("Make"),
                'model': vi.get("Model"),
                'engine': eo.get("EngineLabel"),
                'fuel_type': eo.get("FuelType"),
                'drivetrain': do.get("DriveTrain"),
                'transmission': 'Automatic' #do.get("TransmissionOptions", [None])[0]
                # Uncomment below if needed:
                # 'body_style': bs.get("BodyStyle"),
                # 'box_length': bs.get("BoxLengthOptions", [None])[0]
            }

            results.append(result)

        except Exception as e:
            print(f'Error processing record {app_no}: {e}')
            continue

    return results

def update_vehicle_details_in_db(conn, vehicle_data):
    cursor = conn.cursor()
    update_query = """
        UPDATE NLC_CACRSvc.dbo.VINDecode
        SET 
            engine = ?,
            transmission = ?,
            fuelType = ?,
            driveTrain = ?
        WHERE DaybreakAppNo = ?
    """
    
    updated_count = 0  # Initialize a counter for updated rows

    for record in vehicle_data:
        values = (
            record.get('engine'),         # Engine
            record.get('transmission'),   # Transmission
            record.get('fuel_type'),      # FuelType
            record.get('drivetrain'),     # DriveTrain
            record.get('app_no')          # DaybreakAppNo
        )

        try:
            cursor.execute(update_query, values)
            if cursor.rowcount > 0:  # If the row was updated
                updated_count += 1  # Increment the counter
        except Exception as e:
            print(f"Failed to update AppNo {record.get('app_no')}: {e}")
            continue

    conn.commit()
    logging.info(f"Update complete. {updated_count} rows were updated for vehicle details.")
    print(f"Update complete. {updated_count} rows were updated.")

def fetch_valu(labeled_data3, token):
    url = 'https://valuationapi.carfax.ca/api/v2/SingleVinValuation/SingleVinValuation'
    headers = {
        'accept': 'text/plain',
        'Authorization': f'Bearer {token}',
        'Auth0CarfaxCanadaJWTBearer': f'{token}',
        'Content-Type': 'application/json'
    }
    logging.info(f"Retrieving vins for value pull...")

    results = []

    for record in labeled_data3:
        vin = record['Vin']
        mileage = record['Mileage']
        trim = record['Trim']
        app_no = record['DaybreakAppNo']
        engine = record['engine']
        fuelType = record['fuelType']
        driveTrain = record['driveTrain']
        transmission = record['transmission']

        payload = {
            'valuationTypeRequest': 1,
            'vin': vin,
            'odometer': str(mileage),
            'trim': trim,
            'engine': engine,
            'transmission': transmission,
            'driveTrain': driveTrain,
            'fuelType': fuelType
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            print(f'API call failed for {app_no} - status: {response.status_code}')
            continue

        try:
            data = response.json().get("responseData", {})
            valuations = data.get("marketValuations", [])

            # Map valuations by type for clarity
            valuation_dict = {v["valuationType"]: v["valuation"] for v in valuations if "valuationType" in v}

            result = {
                'app_no': app_no,
                'valuation_1': valuation_dict.get(1),
                'valuation_2': valuation_dict.get(2),
                'valuation_3': valuation_dict.get(3),
                'valuation_4': valuation_dict.get(4),
                'valuation_5': valuation_dict.get(5)
            }

            results.append(result)
            logging.info(f"Added value data for ID {app_no}")
        except Exception as e:
            print(f'Error processing record {app_no}: {e}')
            logging.info(f"Error processing record {app_no}: {e}")
            continue

    return results

def fetch_valu_MMY(labeled_data3, token):
    url = 'https://valuationapi.carfax.ca/api/v2/SingleVinValuation/SingleVinValuation'
    headers = {
        'accept': 'text/plain',
        'Authorization': f'Bearer {token}',
        'Auth0CarfaxCanadaJWTBearer': f'{token}',
        'Content-Type': 'application/json'
    }
    logging.info(f"Retrieving vins for value pull...")

    results = []

    for record in labeled_data3:
        Year = record['Year']
        Make = record['Make']
        Model = record['Model']
        mileage = record['Mileage']
        trim = record['Trim']
        app_no = record['DaybreakAppNo']
        engine = record['engine']
        fuelType = record['fuelType']
        driveTrain = record['driveTrain']
        transmission = record['transmission']

        payload = {
            'valuationTypeRequest': 1,
            #'vin': vin,
            'odometer': str(mileage),
            'trim': trim,
            'engine': engine,
            'transmission': transmission,
            'driveTrain': driveTrain,
            'fuelType': fuelType,
            'Year': Year,
            'Make': Make,
            'Model': Model
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            print(f'API call failed for {app_no} - status: {response.status_code}')
            continue

        try:
            data = response.json().get("responseData", {})
            valuations = data.get("marketValuations", [])

            # Map valuations by type for clarity
            valuation_dict = {v["valuationType"]: v["valuation"] for v in valuations if "valuationType" in v}

            result = {
                'app_no': app_no,
                'valuation_1': valuation_dict.get(1),
                'valuation_2': valuation_dict.get(2),
                'valuation_3': valuation_dict.get(3),
                'valuation_4': valuation_dict.get(4),
                'valuation_5': valuation_dict.get(5)
            }

            results.append(result)
            logging.info(f"Added value data for ID {app_no}")
        except Exception as e:
            print(f'Error processing record {app_no}: {e}')
            logging.info(f"Error processing record {app_no}: {e}")
            continue

    return results

def update_valu_details_in_db(conn, valu_data):
    cursor = conn.cursor()
    update_query = """
        UPDATE NLC_CACRSvc.dbo.VINDecode
        SET 
            Retail =?,
            Wholesale =?,
            Private=?,
            Listing=?,
            TradeIn=?
        WHERE DaybreakAppNo = ?
    """
    updated_count = 0  # Initialize a counter for updated rows

    for record in valu_data:
        values = (
            record.get('valuation_1'),
            record.get('valuation_2'),
            record.get('valuation_3'),
            record.get('valuation_4'),
            record.get('valuation_5'),         
            record.get('app_no')          
        )

        try:
            cursor.execute(update_query, values)
            if cursor.rowcount > 0:  # If the row was updated
                updated_count += 1  # Increment the counter
        except Exception as e:
            print(f"Failed to update AppNo {record.get('app_no')}: {e}")
            continue

    conn.commit()

    print(f"Update complete. {updated_count} rows were updated.")

