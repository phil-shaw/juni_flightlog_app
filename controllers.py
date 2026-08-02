import sys
from models import AirportModel, AircraftModel, FlightModel, ConfigModel, TourModel
from views import TerminalView, RED, GREEN, YELLOW

class FlightController:
    def __init__(self):
        self.config = ConfigModel.load_config()
        self.airports = AirportModel()
        self.aircraft = AircraftModel()
        self.view = TerminalView()
        
        # Initial State
        self.pilot_name = self.config['pilot_name']
        self.pilot_location = self.config.get('current_location', self.config['home_location'])
        self.active_job = FlightModel.load_active_flight()
        self.selected_aircraft = None
        self.tour_data = TourModel.load_tour()
        self._sync_state_with_active_job()

    def _sync_state_with_active_job(self):
        if self.active_job:
            ac = self.aircraft.get_by_reg(self.active_job['aircraft_reg'])
            if ac:
                self.selected_aircraft = ac
                self.pilot_location = ac['location']
        
        if not self.selected_aircraft:
            available = self.aircraft.get_aircraft_at(self.pilot_location)
            if available:
                self.selected_aircraft = available[0]
            elif self.aircraft.aircraft_list:
                # Use the first aircraft in database as selected, 
                # but DO NOT move the pilot to its location.
                self.selected_aircraft = self.aircraft.aircraft_list[0]
            else:
                self.view.show_message("No aircraft found in database!", RED)
                sys.exit(1)

    def run(self):
        while True:
            self.active_job = FlightModel.load_active_flight()
            # If tour is active, we might want to check if the current active job is the tour job
            tour_active = self.active_job and self.active_job.get('type') == 'TOUR'
            
            choice = self.view.show_main_menu(
                self.pilot_name, 
                self.pilot_location, 
                self.selected_aircraft, 
                self.active_job,
                tour_active=tour_active,
                max_distance=self.config.get('max_distance')
            )

            if choice == '1':
                self.handle_available_jobs()
            elif choice == '2':
                self.handle_flight_log()
            elif choice == '3':
                self.handle_aircraft_locations()
            elif choice == '4':
                self.handle_complete_job()
            elif choice == '5':
                self.handle_cancel_job()
            elif choice == '6':
                self.handle_ferry_flight()
            elif choice == '7':
                self.handle_flight_tour()
            elif choice == 'q':
                break

    def handle_available_jobs(self):
        if self.active_job:
            self.view.show_message("You have an active job! Complete or cancel it first.", RED)
            return

        available_aircraft = self.aircraft.get_aircraft_at(self.pilot_location)

        max_dist = self.config.get('max_distance')
        jobs = FlightModel.generate_jobs(self.pilot_location, self.airports.airports, 15, max_dist, available_aircraft)
        
        while True:
            origin_info = self.airports.get_airport(self.pilot_location)
            origin_name = origin_info['name'] if origin_info else "Unknown"
            job_choice = self.view.show_available_jobs(jobs, self.pilot_location, origin_name)
            if job_choice == 'b':
                break
            try:
                idx = int(job_choice) - 1
                if 0 <= idx < len(jobs):
                    selected_job = jobs[idx]
                    
                    if not available_aircraft:
                        self.view.show_message("No aircraft available at your location to accept this job!", RED)
                        continue

                    # Now let user select aircraft
                    ac_choice = self.view.select_aircraft_for_job(available_aircraft, selected_job)
                    if ac_choice == 'b':
                        continue
                        
                    ac_idx = int(ac_choice) - 1
                    if 0 <= ac_idx < len(available_aircraft):
                        ac = available_aircraft[ac_idx]
                        
                        # Validate capacity
                        if selected_job['type'] in ['PAX', 'PLEASURE'] and ac['pax'] < selected_job['amount']:
                            self.view.show_message("Aircraft too small for this many passengers!", RED)
                            continue
                        elif selected_job['type'] == 'CARGO' and ac['cargo'] < selected_job['amount']:
                            self.view.show_message("Aircraft does not have enough cargo capacity!", RED)
                            continue
                            
                        self.active_job = selected_job
                        self.active_job['aircraft_reg'] = ac['reg']
                        self.active_job['aircraft_type'] = ac['type']
                        self.selected_aircraft = ac
                        FlightModel.save_active_flight(self.active_job)
                        break
            except (ValueError, IndexError):
                continue

    def handle_flight_log(self):
        logs = FlightModel.get_logs(15)
        self.view.show_flight_log(logs)

    def handle_aircraft_locations(self):
        self.view.show_aircraft_locations(self.pilot_location, self.aircraft.aircraft_list)

    def handle_complete_job(self):
        if not self.active_job:
            self.view.show_message("No active job to complete!", RED)
            return
        
        self.view.show_flight_progress(
            self.active_job['origin'], 
            self.active_job['destination'], 
            self.active_job['distance']
        )
        
        FlightModel.log_flight(self.selected_aircraft, self.active_job, self.pilot_name, "COMPLETED")
        job_type = self.active_job.get('type')
        self.pilot_location = self.active_job['destination']
        self.selected_aircraft['location'] = self.pilot_location
        self.aircraft.save_aircraft()
        
        # Save new pilot location to config
        self.config['current_location'] = self.pilot_location
        ConfigModel.save_config(self.config)
        
        FlightModel.clear_active_flight()
        self.active_job = None
        
        # If it was a tour flight, we need to update the tour data
        if job_type == 'TOUR':
            self.tour_data = TourModel.load_tour()
            if self.tour_data and len(self.tour_data.get('airports', [])) > 1:
                self.tour_data['airports'].pop(0)
                if len(self.tour_data['airports']) > 1:
                    TourModel.save_tour(self.tour_data)
                    # Automatically start next leg
                    self.handle_flight_tour()
                else:
                    # Only one airport remains, tour is finished
                    TourModel.delete_tour()
                    self.tour_data = None
                    self.view.show_message("Flight Tour completed!", GREEN)

        self.view.show_message("Flight completed and aircraft location updated!", GREEN)

    def handle_cancel_job(self):
        if not self.active_job:
            self.view.show_message("No active job to cancel!", RED)
            return
            
        FlightModel.log_flight(self.selected_aircraft, self.active_job, self.pilot_name, "CANCELLED")
        FlightModel.clear_active_flight()
        self.active_job = None
        self.view.show_message("Job cancelled.", YELLOW)

    def handle_ferry_flight(self):
        if self.active_job:
            self.view.show_message("You have an active job!", RED)
            return

        available_aircraft = self.aircraft.get_aircraft_at(self.pilot_location)
        if not available_aircraft:
            self.view.show_message("No aircraft available here!", RED)
            return

        ac_choice = self.view.get_ferry_aircraft(available_aircraft)
        if ac_choice == 'b':
            return
            
        try:
            idx = int(ac_choice) - 1
            if 0 <= idx < len(available_aircraft):
                ferry_ac = available_aircraft[idx]
                dest_icao = self.view.get_input("Enter destination ICAO: ").upper()
                
                if not self.airports.exists(dest_icao):
                    self.view.show_message(f"Airport {dest_icao} not found!", RED)
                    return
                
                dest_info = self.airports.get_airport(dest_icao)
                origin_info = self.airports.get_airport(ferry_ac['location'])
                
                dist = FlightModel.haversine(
                    origin_info['lat'], origin_info['lon'],
                    dest_info['lat'], dest_info['lon']
                )
                
                # Ignore range check as requested
                # if dist > ferry_ac['range']:
                #     self.view.show_message(f"Destination out of range ({round(dist)} nm)!", RED)
                #     return
                
                self.selected_aircraft = ferry_ac
                self.active_job = {
                    'origin': ferry_ac['location'],
                    'destination': dest_icao,
                    'distance': round(dist),
                    'type': 'FERRY',
                    'amount': 0,
                    'unit': 'payload',
                    'dest_name': dest_info['name'],
                    'aircraft_reg': ferry_ac['reg'],
                    'aircraft_type': ferry_ac['type']
                }
                FlightModel.save_active_flight(self.active_job)
                self.view.show_message(f"Ferry flight to {dest_icao} ready.", GREEN)
        except (ValueError, IndexError):
            pass

    def handle_flight_tour(self):
        if self.active_job:
            self.view.show_message("You have an active job!", RED)
            return

        self.tour_data = TourModel.load_tour()
        if not self.tour_data:
            self.view.show_message("No tour (route.json) found!", RED)
            return

        airports = self.tour_data.get('airports', [])
        if len(airports) < 2:
            self.view.show_message("Tour finished or invalid (needs at least 2 airports)!", YELLOW)
            TourModel.delete_tour()
            self.tour_data = None
            return

        origin_icao = airports[0]
        dest_icao = airports[1]

        if not self.airports.exists(origin_icao) or not self.airports.exists(dest_icao):
            self.view.show_message(f"One of the tour airports ({origin_icao} or {dest_icao}) not found!", RED)
            return

        # Setup pilot and aircraft
        self.pilot_name = self.tour_data.get('pilot_name', self.pilot_name)
        self.config['pilot_name'] = self.pilot_name
        
        # Check if aircraft exists, if not create it or find it
        ac_reg = self.tour_data.get('aircraft_name', "TOUR-1") # use aircraft_name as reg for simplicity or look it up
        ac = self.aircraft.get_by_reg(ac_reg)
        
        if not ac:
            # Create a temporary aircraft for the tour if it doesn't exist
            ac = {
                'type': self.tour_data.get('aircraft_model', 'Cessna 172'),
                'reg': ac_reg,
                'pax': 4,
                'cargo': 100,
                'speed': 120,
                'range': 600,
                'location': origin_icao
            }
            self.aircraft.aircraft_list.append(ac)
            self.aircraft.save_aircraft()
        else:
            # Move aircraft to tour start
            ac['location'] = origin_icao
            self.aircraft.save_aircraft()

        self.selected_aircraft = ac
        self.pilot_location = origin_icao
        self.config['current_location'] = self.pilot_location
        ConfigModel.save_config(self.config)

        origin_info = self.airports.get_airport(origin_icao)
        dest_info = self.airports.get_airport(dest_icao)
        
        dist = FlightModel.haversine(
            origin_info['lat'], origin_info['lon'],
            dest_info['lat'], dest_info['lon']
        )

        self.active_job = {
            'origin': origin_icao,
            'destination': dest_icao,
            'distance': round(dist),
            'type': 'TOUR',
            'amount': 0,
            'unit': 'tourists',
            'dest_name': dest_info['name'],
            'aircraft_reg': ac['reg'],
            'aircraft_type': ac['type']
        }
        FlightModel.save_active_flight(self.active_job)
        self.view.show_message(f"Tour flight to {dest_icao} ready.", GREEN)
