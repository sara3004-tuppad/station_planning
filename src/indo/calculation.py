"""Service for handling battery swap station calculations."""

import time
import logging
import math
import pandas as pd
import gspread
from typing import Dict, Any, List
from datetime import datetime
from google.oauth2.service_account import Credentials
import json
import traceback

logger = logging.getLogger(__name__)

class CalculationService:
    """Service for calculating battery swap station requirements for EV fleet planning."""
    
    def __init__(self, credentials_data):
        """Initialize the calculation service."""
        logger.info("Initializing CalculationService")
        # Authenticate with Google Sheets
        self.credentials_data = credentials_data
        self.gspread_client = self._google_sheets_auth(self.credentials_data)
     
    
    def _google_sheets_auth(self, credentials_data: str) -> gspread.Client:
        """
        Authenticate with Google Sheets using service account credentials.
        
        Args:
            credentials_path: Path to the service account JSON file.
        
        Returns:
            gspread.Client: Authenticated client for Google Sheets.
        """
        try:
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            
            creds = Credentials.from_service_account_info(
                credentials_data,
                scopes=scope
            )
            return gspread.authorize(creds)
        except Exception as e:
            logger.error(f"Error authenticating with Google Sheets: {e}")
            raise ValueError("Failed to authenticate with Google Sheets") from e
    
    def calculate_stations_required(
        self,
        sheet_url: str,
        entities: dict
    ) -> pd.DataFrame:
        """
        Computes stations required city-wise based on vehicle demand and battery/ops capacity mix.
        
        Args:
            sheet_url: URL of the Google Sheets containing vehicle data
            cities: List of cities to analyze (use ['all'] for all cities)
            station_utilization: Expected utilization rate (0.0 to 1.0)
            off_road_percent: Percentage of vehicles that are off-road (0.0 to 1.0)
        Returns:
            DataFrame with station requirements per city
        """
        logger.info(f"Starting detailed calculation for entities: {entities}")
        
        try:
            cities = list(entities.keys()) if entities else ['all']
            # Step 1: Setup Google Sheets connection
            df = self._get_vehicle_data_from_sheets(sheet_url, cities)
            swappable_energy_per_station, vehicle_specs = self._get_swappable_energy_per_station_and_vehicle_mix(sheet_url)
            swappable_energy_per_station = int(swappable_energy_per_station)
            # Step 3: Calculate for each city
            results = []
            for _, row in df.iterrows():
                
                city = row['City']
                if cities != ['all']:
                    off_road_vehicle_percentage = entities.get(city).get('off_road_vehicle_percentage')/100
                    station_utilization_percentage = entities.get(city).get('station_utilization_percentage') / 100.0
                else:
                    off_road_vehicle_percentage = entities.get('all').get('off_road_vehicle_percentage')/100
                    station_utilization_percentage = entities.get('all').get('station_utilization_percentage') / 100.0
                logger.info(f"Processing city: {city}")
                
                # Calculate total energy required for the city
                total_energy_required = self._calculate_city_energy_demand(
                    row, vehicle_specs, off_road_vehicle_percentage
                )
                
            
                # Calculate stations required
                if swappable_energy_per_station > 0 and (station_utilization_percentage) > 0:
                    stations_required = total_energy_required / (
                        swappable_energy_per_station * (station_utilization_percentage)
                    )
                else:
                    stations_required = 0

                total_vehicles = sum(value for value in row.to_dict().values() if isinstance(value, (int, float)))
                
                results.append({
                    "City": city,
                    "vehicles": row.to_dict(),
                    "total_vehicles": total_vehicles,
                    "operational_vehicles": total_vehicles * (1 - off_road_vehicle_percentage),
                    "energy_required": round(total_energy_required, 2),
                    "swappable_energy_per_station": round(swappable_energy_per_station, 0),
                    "stations_required": round(stations_required, 0)
                })
                
                logger.info(f"City {city}: {math.ceil(stations_required)} stations required")
            
            result_df = pd.DataFrame(results)
            
            logger.info(f"Calculation completed for {len(results)} cities")
            return result_df
            
        except Exception as e:
            logger.error(f"Error in detailed calculation: {e}")
            raise

    def _get_swappable_energy_per_station_and_vehicle_mix(self, sheet_url: str) -> float:
        """Retrieve swappable energy per station from Google Sheets."""
        try:
           
            # Open sheet and get data
            sheet = self.gspread_client.open_by_url(sheet_url)
            worksheet = sheet.get_worksheet(1)  # Assuming swappable energy is in the second sheet
    
            swapable_energy = worksheet.acell('H5').value
            vehicle_start = None
            for i, row in enumerate(worksheet.get_all_values()):
                if any('Vehicle Mix' in str(cell) for cell in row):
                    vehicle_start = i
                    break
            all_values = worksheet.get_all_values()
            # Extract Vehicle Mix DataFrame
            if vehicle_start:
                vehicle_data = all_values[vehicle_start:]
                # Filter out empty rows
                vehicle_rows = []
                for row in vehicle_data[1:]:  # Skip header
                    if row[0] and row[0] != '':
                        vehicle_rows.append(row[:3])  # Take first 3 columns
                
                if vehicle_rows:
                    vehicle_df = pd.DataFrame(vehicle_rows, columns=['Vehicle Mix', 'Avg. km per day (km/day)', 'Energy required per km (wh/km)'])
                    vehicle_df['Avg. km per day (km/day)'] = pd.to_numeric(vehicle_df['Avg. km per day (km/day)'], errors='coerce')
                    vehicle_df['Energy required per km (wh/km)'] = pd.to_numeric(vehicle_df['Energy required per km (wh/km)'], errors='coerce')
                else:
                    vehicle_df = pd.DataFrame(columns=['Vehicle Mix', 'Avg. km per day (km/day)', 'Energy required per km (wh/km)'])

            return swapable_energy, vehicle_df.set_index(vehicle_df.columns[0]).to_dict('index')
        
        except Exception as e:
            logger.error(f"Error retrieving swappable energy per station: {e}")
            raise ValueError("Failed to retrieve swappable energy per station from Google Sheets") from e

    def _get_vehicle_data_from_sheets(
        self, 
        sheet_url: str, 
        cities: List[str]
    ) -> pd.DataFrame:
        """Retrieve and process vehicle data from Google Sheets."""
    
        # Open sheet and get data
        sheet = self.gspread_client.open_by_url(sheet_url)
        worksheet = sheet.get_worksheet(0)
        data = worksheet.get_all_values()
        
        if not data or len(data) < 2:
            raise ValueError("Insufficient data in Google Sheets")
        
        # Create DataFrame
        headers = data[0]
        values = data[1:]
        df = pd.DataFrame(values, columns=headers)
        
        # Convert numeric columns
        for col in df.columns[1:]:  # Skip 'City' column
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)


        # Clean city names
        df['City'] = df['City'].str.strip()
        df['City'] = df['City'].str.lower()
        
        # Filter cities if not 'all'
        if cities!=['all']:
            print(f"Filtering cities: {cities}")
            df = df[df['City'].isin(cities)]
            if df.empty:
                raise ValueError(f"No matching cities found for: {cities}")
        
        logger.info(f"Retrieved data for {len(df)} cities from Google Sheets")
        return df
            
    def _calculate_city_energy_demand(
        self, 
        city_row: pd.Series, 
        vehicle_specs: Dict, 
        off_road_percent: float
    ) -> float:
        """Calculate total energy demand for a city."""
        total_energy_required = 0
        
        for vehicle_type in vehicle_specs:
            if vehicle_type not in city_row:
                continue
                
            count = city_row[vehicle_type]
            specs = vehicle_specs[vehicle_type]
            
            # Apply off-road factor
            effective_vehicles = count * (1 - off_road_percent)
            
            # Calculate energy requirement
            energy_required = (
                effective_vehicles * 
                specs['Avg. km per day (km/day)'] * 
                specs['Energy required per km (wh/km)']
            )/1000  # Convert Wh to kWh
            
            total_energy_required += energy_required
            
        return total_energy_required

    
    def calculate_swap_stations(
        self, 
        entities: dict = None,
        sheet_url: str = None,
    ) -> Dict[str, Any]:
        """
        Main calculation method for Streamlit integration.
        Wrapper around the detailed calculation function.
        """
        
        
        try:
            start_time = time.time()
            
            
            if sheet_url is None:
                sheet_url = "https://docs.google.com/spreadsheets/d/1demo-sheet-id/edit#gid=0"
            
           
            
            # Call the detailed calculation
            results_df = self.calculate_stations_required(
                sheet_url=sheet_url,
                entities=entities,
               
            )
            
            # Convert DataFrame to the expected format for Streamlit
            city_breakdown = {}
            total_stations = 0
            
            for _, row in results_df.iterrows():
                city = row['City']
                stations = row['stations_required']
                
                city_breakdown[city] = row.to_dict()
                total_stations += stations
            
            calculation_time = time.time() - start_time
            
            final_result = {
                "city_breakdown": city_breakdown,
                "total_stations_required": int(total_stations),
                # "parameters_used": {
                #     "station_utilization": station_utilization,
                #     "off_road_percentage": off_road_percentage
                # }
            }
            
            logger.info(f"Calculation completed: {int(total_stations)} total stations across {len(results_df)} cities (took {calculation_time:.2f}s)")
            return final_result
            
        except Exception as e:
            logger.error(f"Error in swap station calculation: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {"error": str(e)}

# Example usage:
if __name__ == "__main__":
    from config import SHEET_URL, CREDENTIALS_DATA
    # print(f"credentials_data: {CREDENTIALS_DATA}")
    service = CalculationService(CREDENTIALS_DATA)
    result = service.calculate_swap_stations(
        entities={
            "delhi": {
                "station_utilization_percentage": 80,
                "off_road_vehicle_percentage": 20
            },
            "mumbai": {
                "station_utilization_percentage": 75,
                "off_road_vehicle_percentage": 15
            }
        },
        sheet_url=SHEET_URL
    )
    print(result)
