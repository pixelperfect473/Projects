import pyodbc
import requests
import logging
import credentials
import time  
from datetime import datetime
import pandas as pd
import auth0 as ao
import time
from zoneinfo import ZoneInfo

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

logger = logging.getLogger(__name__)

def update_add_new_vins():
    logger.info('Beginning first step of adding new apps.')
    cursor.execute(""" SELECT 
    gi.dealid,
    gi.dcappno,
    gi.createddate,
    c.VehicleID,
    c.VIN,
    v.[Year],
    v.Make,
    v.Model,
    c.Mileage
FROM prodsnapshot.nlc_ss.deal.GeneralInfo gi
LEFT JOIN prodsnapshot.nlc_ss.deal.Collateral c 
    ON gi.dealid = c.dealid
LEFT JOIN (
    SELECT vehicleid, MAX(valuationid) AS maxvalid
    FROM prodsnapshot.nlc_ss.collateral.valuations
    GROUP BY vehicleid
) v2 
    ON v2.VehicleID = c.VehicleID
LEFT JOIN prodsnapshot.nlc_ss.Collateral.Valuations v 
    ON v.valuationid = v2.maxvalid
LEFT JOIN Carfax_auto_valuation cav on cav.dealid =gi.dealid and cav.VIN = c.VIN
WHERE 
    c.LastUpdatedDate >= '2026-03-01' and gi.createddate >getdate()-300
    AND c.vin IS NOT NULL and cav.dealid is null""")
    rows = cursor.fetchall()
    logger.info('Pulled new apps.')
    insert_query = '''INSERT INTO Carfax_auto_valuation (DealID, DCAppNO, AppSubmissionDate, VehicleID, VIN, Year, Make , Model, Mileage ) 
                    VALUES (?,?,?,?,?,?,?,?,?)'''
    for row in rows:
        cursor.execute(insert_query, (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]))  # Insert 
    conn.commit()
    logger.info('Inserted new apps into base table.')


def prep_vins():
    cursor.execute("""
        SELECT   DCAppNO, VIN, Mileage
        FROM NLC_CACRSvc.dbo.Carfax_auto_valuation
        WHERE Trim IS NULL and notes is null
    """)
    data = cursor.fetchall()
    labeled_data = [
        {'DCAppNO': app_no, 'VIN': vin, 'Mileage': mileage}
        for app_no, vin, mileage in data
    ]
    logger.info("Found %d records needing a trim, getting trims.", len(labeled_data))
    return labeled_data


def get_trim(app_no, vin, mileage, token):
    url = 'https://api.carfax.ca/vindecode/api/v2/SingleVin/SingleVinDecode'
    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {token}',
        'Auth0CarfaxCanadaJWTBearer': f'{token}'
    }
    params = {
        'Vin': vin,
        'Odometer': str(mileage)
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            trims = response.json().get("ResponseData", {}).get("Trims", [])
            trim = trims[0] if trims else 'ERROR'
            return trim
        else:
            logger.info(f'API CALL FAILED for {app_no} with status code {response.status_code}.')
    except Exception as e:
        logger.error(f'Error extracting trim for {app_no}: {e}')
    finally:
        time.sleep(0.05)  # 20 calls per second max
    

def update_trims_in_db(trim_data):
    # Prepare the update query
    update_query = """
    UPDATE Carfax_auto_valuation
    SET Trim = ?
    WHERE DCAppNO = ?
    """
    if not trim_data:
        logger.warning("No trim data provided — skipping database update.")
        return
    # Execute the query for all trims
    cursor.executemany(update_query, trim_data)

    # Commit the transaction
    conn.commit()
    logger.info(f"Database updated for {len(trim_data)} records.")
    


def prep_trim():
    cursor.execute("""
        SELECT  DCAPPNO, VIN, Mileage, Trim
        FROM NLC_CACRSvc.dbo.Carfax_auto_valuation
        WHERE Trim IS NOT NULL and Trim <>'ERROR' and transmission is null and Notes is null
    """)
    data = cursor.fetchall()
    labeled_data2 = [
        {'DCAPPNO': app_no, 'VIN': vin, 'Mileage': mileage, 'Trim': trim}
        for app_no, vin, mileage, trim in data
    ]
    logger.info('Found %d records needing vehicle details, getting details.',len(labeled_data2))
    return labeled_data2

def fetch_vehicle_details(labeled_data2, token):
    url = 'https://api.carfax.ca/vindecode/api/v2/SingleVin/SingleVinDecode'
    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {token}',
        'Auth0CarfaxCanadaJWTBearer': f'{token}'
    }

    results = []

    for record in labeled_data2:
        # Safely get values with defaults
        vin = record.get('VIN')
        mileage = record.get('Mileage')
        trim = record.get('Trim')
        app_no = record.get('DCAPPNO', 'UNKNOWN')

        if not vin or not mileage:
            logger.warning(f"Skipping record {app_no}: missing VIN or mileage.")
            continue  # skip records with missing essential data

        params = {'Vin': vin, 'Odometer': str(mileage)}
        if trim:
            params['Trim'] = trim

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code != 200:
                logger.warning(f'API call failed for {app_no} - status: {response.status_code}.')
                continue

            data = response.json().get("ResponseData", {})
            vi = data.get("VehicleInformation", {})
            eo = data.get("EngineOptions", [{}])[0]
            do = eo.get("DrivetrainOptions", [{}])[0]

            result = {
                'app_no': app_no,
                'vin': vi.get("Vin"),
                'year': vi.get("Year"),
                'make': vi.get("Make"),
                'model': vi.get("Model"),
                'engine': eo.get("EngineLabel"),
                'fuel_type': eo.get("FuelType"),
                'drivetrain': do.get("DriveTrain"),
                'transmission': 'Automatic'  # default placeholder
            }

            results.append(result)
            time.sleep(0.05)
        except Exception as e:
            logger.warning(f'Error processing record {app_no}: {e}')
            continue
    logger.info('Found vehicle details for %d records.', len(results))        
    return results
    


def update_vehicle_details_in_db( vehicle_data):
    #cursor = conn.cursor()
    update_query = """
        UPDATE NLC_CACRSvc.dbo.Carfax_auto_valuation
        SET 
            engine = ?,
            transmission = ?,
            fuelType = ?,
            driveTrain = ?
        WHERE DCAPPNO = ?
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
            logger.warning(f"Failed to update AppNo {record.get('app_no')}: {e}")
            continue

    conn.commit()
    logging.info(f"Update complete. {updated_count} rows were updated for vehicle details.")
    #print(f"Update complete. {updated_count} rows were updated.")


def prep_valu():
    cursor.execute("""
        SELECT DCAPPNO, VIN, Mileage, Trim, engine, transmission, fuelType, driveTrain
        FROM NLC_CACRSvc.dbo.Carfax_auto_valuation
        WHERE Retail is null and trim is not null and transmission is not null and trim <>'ERROR' and notes is null
    """)
    data = cursor.fetchall()
    labeled_data3 = [
        {'DCAPPNO': app_no, 'VIN': vin, 'Mileage': mileage, 'Trim': trim, 'engine': engine, 'transmission': transmission, 'fuelType': fuelType, 'driveTrain': driveTrain}
        for app_no, vin, mileage, trim, engine, transmission, fuelType, driveTrain in data
    ]
    logger.info('Found %d needing valuation, pulling valuation.',len(labeled_data3))
    return labeled_data3



def fetch_valu(labeled_data3, token):
    url = 'https://valuationapi.carfax.ca/api/v2/SingleVinValuation/SingleVinValuation'
    headers = {
        'accept': 'text/plain',
        'Authorization': f'Bearer {token}',
        'Auth0CarfaxCanadaJWTBearer': f'{token}',
        'Content-Type': 'application/json'
    }
    logging.info(f"Retrieving vins for value pull...")
    Toronto_tz = ZoneInfo("America/Toronto")
    results = []

    for record in labeled_data3:
        vin = record['VIN']
        mileage = record['Mileage']
        trim = record['Trim']
        app_no = record['DCAPPNO']
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
            logger.warning(f'API call failed for {app_no} - status: {response.status_code}')
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
                'valuation_5': valuation_dict.get(5),
                'valuation_pulled': datetime.now(Toronto_tz)
            }

            results.append(result)
            logging.info(f"Added value data for ID {app_no}")
        except Exception as e:
            logging.info(f"Error processing record {app_no}: {e}")
            time.sleep(0.05)
            continue
    logger.info('Pulled valuations for %d records.',len(results))
    return results


def update_valu_details_in_db(valu_data):
    #cursor = conn.cursor()
    update_query = """
        UPDATE NLC_CACRSvc.dbo.Carfax_auto_valuation
        SET 
            Retail =?,
            Wholesale =?,
            Private=?,
            Listing=?,
            TradeIn=?,
            ValuationPullDate=?
        WHERE DCAPPNO = ?
    """
    updated_count = 0  

    for record in valu_data:
        values = (
            record.get('valuation_1'),
            record.get('valuation_2'),
            record.get('valuation_3'),
            record.get('valuation_4'),
            record.get('valuation_5'),   
            record.get('valuation_pulled'),      
            record.get('app_no')

        )

        try:
            cursor.execute(update_query, values)
            if cursor.rowcount > 0:  # If the row was updated
                updated_count += 1  # Increment the counter
        except Exception as e:
            logger.warning(f"Failed to update AppNo {record.get('app_no')}: {e}")
            continue

    conn.commit()
    conn.close()
    logger.info(f"Update complete. {updated_count} rows were updated.")