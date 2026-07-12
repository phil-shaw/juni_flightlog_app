import csv
import math
import json
import os
import time
import random

# Constants
FLIGHT_LOG = "flight_log.csv"
ACTIVE_FLIGHT = "active_flight.json"
AIRCRAFT_FILE = "aircraft.csv"
AIRPORTS_FILE = "airports.csv"
CONFIG_FILE = "config.json"
TOUR_FILE = "route.json"
JOBS_FILE = "jobs.csv"

class ConfigModel:
    @staticmethod
    def load_config():
        default_config = {
            "active_pilot": "Keira US",
            "pilots": {
                "Keira US": {
                    "home_location": "KJFK",
                    "current_location": "KJFK",
                    "max_distance": 400
                },
                "Keira UK": {
                    "home_location": "EGNH",
                    "current_location": "EGNH",
                    "max_distance": 400
                }
            }
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    # Support legacy format
                    if 'pilot_name' in config:
                        name = config['pilot_name']
                        return {
                            "active_pilot": name,
                            "pilots": {
                                name: {
                                    "home_location": config.get('home_location', 'EGNH'),
                                    "current_location": config.get('current_location', config.get('home_location', 'EGNH')),
                                    "max_distance": config.get('max_distance', 400)
                                }
                            }
                        }
                    return {**default_config, **config}
            except (json.JSONDecodeError, IOError):
                return default_config
        return default_config

    @staticmethod
    def save_config(config):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)

    @staticmethod
    def get_active_pilot_data(config):
        active_pilot = config.get('active_pilot')
        if not active_pilot or active_pilot not in config.get('pilots', {}):
            # Fallback to first available pilot
            if config.get('pilots'):
                active_pilot = list(config['pilots'].keys())[0]
                config['active_pilot'] = active_pilot
            else:
                return None
        
        data = config['pilots'][active_pilot]
        data['pilot_name'] = active_pilot
        return data

class AirportModel:
    def __init__(self, filename=AIRPORTS_FILE):
        self.airports = self.load_airports(filename)

    def load_airports(self, filename):
        airports = {}
        if not os.path.exists(filename):
            return airports
        with open(filename, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                airports[row['ICAO']] = {
                    'name': row['Name'],
                    'lat': float(row['Latitude']),
                    'lon': float(row['Longitude'])
                }
        return airports

    def get_airport(self, icao):
        return self.airports.get(icao)

    def exists(self, icao):
        return icao in self.airports

class AircraftModel:
    def __init__(self, filename=AIRCRAFT_FILE):
        self.filename = filename
        self.aircraft_list = self.load_aircraft(filename)

    def load_aircraft(self, filename):
        aircraft_list = []
        if not os.path.exists(filename):
            return aircraft_list
        with open(filename, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row['Reg'] or not row['Type']:
                    continue
                try:
                    aircraft_list.append({
                        'type': row['Type'],
                        'reg': row['Reg'],
                        'pax': int(row['PAX']),
                        'cargo': int(row['cargo']),
                        'speed': int(row['Speed']),
                        'range': int(row['Range']),
                        'location': row['icao']
                    })
                except (ValueError, KeyError):
                    continue
        return aircraft_list

    def save_aircraft(self):
        if not self.aircraft_list:
            return
        fieldnames = ['Type', 'Reg', 'PAX', 'cargo', 'Speed', 'GPH', 'Fuel', 'Range', 'icao']
        original_data = {}
        if os.path.exists(self.filename):
            with open(self.filename, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    original_data[row['Reg']] = row

        with open(self.filename, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for ac in self.aircraft_list:
                row = original_data.get(ac['reg'], {}).copy()
                row['icao'] = ac['location']
                writer.writerow(row)

    def get_aircraft_at(self, location):
        return [ac for ac in self.aircraft_list if ac['location'] == location]

    def get_by_reg(self, reg):
        for ac in self.aircraft_list:
            if ac['reg'] == reg:
                return ac
        return None

class JobModel:
    @staticmethod
    def load_jobs():
        jobs = []
        if not os.path.exists(JOBS_FILE):
            return jobs
        with open(JOBS_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    jobs.append({
                        'id': row['id'],
                        'origin': row['origin'],
                        'destination': row['destination'],
                        'distance': int(row['distance']),
                        'type': row['type'],
                        'amount': int(row['amount']),
                        'unit': row['unit'],
                        'dest_name': row['dest_name'],
                        'expiry': int(row.get('expiry', 0))
                    })
                except (ValueError, KeyError):
                    continue
        return jobs

    @staticmethod
    def save_jobs(jobs):
        fieldnames = ['id', 'origin', 'destination', 'distance', 'type', 'amount', 'unit', 'dest_name', 'expiry']
        with open(JOBS_FILE, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for job in jobs:
                writer.writerow(job)

    @staticmethod
    def get_jobs_at(icao):
        all_jobs = JobModel.load_jobs()
        return [j for j in all_jobs if j['origin'] == icao]

    @staticmethod
    def ensure_jobs_for_airport(icao, airports_dict, aircraft_list=None, max_distance=None):
        all_jobs = JobModel.load_jobs()
        existing_jobs = [j for j in all_jobs if j['origin'] == icao]
        
        if len(existing_jobs) < 2:
            num_to_create = random.randint(2, 6) - len(existing_jobs)
            if num_to_create > 0:
                # Use available aircraft at this location to determine capacity
                available_here = []
                if aircraft_list:
                    available_here = [ac for ac in aircraft_list if ac['location'] == icao]
                
                new_jobs = FlightModel.generate_jobs(icao, airports_dict, count=num_to_create, max_distance=max_distance, available_aircraft=available_here)
                current_time = int(time.time())
                for nj in new_jobs:
                    nj['id'] = f"{icao}-{current_time}-{random.randint(1000, 9999)}"
                    # Random expiry 1 to 5 days (in seconds)
                    nj['expiry'] = current_time + random.randint(1, 5) * 24 * 3600
                    all_jobs.append(nj)
                JobModel.save_jobs(all_jobs)
                return True
        return False

    @staticmethod
    def cleanup_expired_jobs(airports_dict, aircraft_list=None, max_distance=None):
        all_jobs = JobModel.load_jobs()
        current_time = int(time.time())
        
        # Filter out expired jobs
        fresh_jobs = [j for j in all_jobs if j.get('expiry', 0) > current_time or j.get('expiry', 0) == 0]
        
        if len(fresh_jobs) < len(all_jobs):
            # Identify which airports lost jobs
            affected_airports = set(j['origin'] for j in all_jobs if j not in fresh_jobs)
            
            # Save the filtered list first so ensure_jobs_for_airport sees the reduction
            JobModel.save_jobs(fresh_jobs)
            
            # Replenish jobs for affected airports
            for icao in affected_airports:
                JobModel.ensure_jobs_for_airport(icao, airports_dict, aircraft_list, max_distance)
            return True
        return False

    @staticmethod
    def remove_job(job_id):
        all_jobs = JobModel.load_jobs()
        all_jobs = [j for j in all_jobs if j['id'] != job_id]
        JobModel.save_jobs(all_jobs)

class FlightModel:
    @staticmethod
    def get_logs(count=15):
        if not os.path.exists(FLIGHT_LOG):
            return []
        with open(FLIGHT_LOG, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Normalize headers by stripping and converting to lowercase for internal check
            # but we need to map them back to what the template expects.
            logs = []
            for row in reader:
                # Handle both old and new formats by mapping keys
                normalized_row = {}
                
                # Possible keys for each field
                mapping = {
                    'Timestamp': ['Timestamp', 'timestamp'],
                    'Pilot': ['Pilot', 'pilot'],
                    'Aircraft': ['Aircraft', 'aircraft_reg', 'aircraft'],
                    'Type': ['Type', 'type'],
                    'Origin': ['Origin', 'origin'],
                    'Destination': ['Destination', 'destination'],
                    'Distance': ['Distance', 'distance'],
                    'Payload': ['Payload', 'amount', 'payload'],
                    'Unit': ['Unit', 'unit'],
                    'Status': ['Status', 'status']
                }
                
                for target_key, possible_keys in mapping.items():
                    value = None
                    for pk in possible_keys:
                        if pk in row:
                            value = row[pk]
                            break
                    normalized_row[target_key] = value if value is not None else ""
                
                # Special handling for Type/Payload/Unit mapping if fields were ambiguous in old format
                if not normalized_row['Unit'] and 'passengers' in str(row).lower():
                    normalized_row['Unit'] = 'passengers'
                if not normalized_row['Unit'] and 'kg' in str(row).lower():
                    normalized_row['Unit'] = 'kg cargo'
                
                if normalized_row['Timestamp']:
                    logs.append(normalized_row)
            
            return logs[-count:][::-1] # Last count logs, reversed to show newest first

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        R = 3440.065 # Earth radius in nautical miles
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def generate_jobs(origin_icao, airports_dict, count=15, max_distance=None, available_aircraft=None):
        jobs = []
        if origin_icao not in airports_dict:
            return []
        
        origin = airports_dict[origin_icao]
        all_icao = list(airports_dict.keys())

        # Determine max capacities from available aircraft
        max_pax = 0
        max_cargo = 0
        if available_aircraft:
            max_pax = max((ac['pax'] for ac in available_aircraft), default=0)
            max_cargo = max((ac['cargo'] for ac in available_aircraft), default=0)
        else:
            # Fallback to some defaults if no aircraft info provided
            max_pax = 10
            max_cargo = 1000
        
        attempts = 0
        while len(jobs) < count and attempts < 1000:
            attempts += 1
            dest_icao = random.choice(all_icao)
            if dest_icao == origin_icao:
                continue
                
            dest = airports_dict[dest_icao]
            distance = FlightModel.haversine(origin['lat'], origin['lon'], dest['lat'], dest['lon'])
            
            # Apply config max distance limit if set
            if max_distance is not None and distance > max_distance:
                continue

            job_type = random.choice(['PAX', 'CARGO', 'PLEASURE'])
            if job_type == 'PAX':
                if max_pax < 1: continue
                amount = random.randint(1, max_pax)
                unit = "passengers"
            elif job_type == 'CARGO':
                if max_cargo < 50: continue
                amount = random.randint(50, max_cargo)
                unit = "kg cargo"
            else: # PLEASURE
                dest_icao = origin_icao
                dest = origin
                distance = 0
                if max_pax < 1: continue
                amount = random.randint(1, min(4, max_pax))
                unit = "passengers"
            
            jobs.append({
                'origin': origin_icao,
                'destination': dest_icao,
                'distance': round(distance),
                'type': job_type,
                'amount': amount,
                'unit': unit,
                'dest_name': dest['name']
            })
        return jobs

    @staticmethod
    def load_active_flight():
        if os.path.exists(ACTIVE_FLIGHT):
            with open(ACTIVE_FLIGHT, 'r') as f:
                return json.load(f)
        return None

    @staticmethod
    def save_active_flight(job):
        with open(ACTIVE_FLIGHT, 'w') as f:
            json.dump(job, f)

    @staticmethod
    def clear_active_flight():
        if os.path.exists(ACTIVE_FLIGHT):
            os.remove(ACTIVE_FLIGHT)

    @staticmethod
    def log_flight(aircraft, job, pilot_name, status="COMPLETED"):
        file_exists = os.path.isfile(FLIGHT_LOG)
        with open(FLIGHT_LOG, mode='a', encoding='utf-8', newline='') as f:
            fieldnames = ['Timestamp', 'Pilot', 'Aircraft', 'Type', 'Origin', 'Destination', 'Distance', 'Payload', 'Unit', 'Status']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                'Timestamp': time.strftime("%d-%m-%Y"),
                'Pilot': pilot_name,
                'Aircraft': aircraft['reg'],
                'Type': aircraft['type'],
                'Origin': job['origin'],
                'Destination': job['destination'],
                'Distance': job['distance'],
                'Payload': job['amount'],
                'Unit': job['unit'],
                'Status': status
            })

class TourModel:
    @staticmethod
    def load_tour():
        if os.path.exists(TOUR_FILE):
            try:
                with open(TOUR_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    @staticmethod
    def save_tour(tour_data):
        with open(TOUR_FILE, 'w') as f:
            json.dump(tour_data, f, indent=4)

    @staticmethod
    def delete_tour():
        if os.path.exists(TOUR_FILE):
            os.remove(TOUR_FILE)
