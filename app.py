from flask import Flask, render_template, request, redirect, url_for, flash
from models import AirportModel, AircraftModel, FlightModel, ConfigModel, TourModel, JobModel
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Helper to get the application state
def get_state():
    config = ConfigModel.load_config()
    pilot_data = ConfigModel.get_active_pilot_data(config)
    
    airports = AirportModel()
    aircraft = AircraftModel()
    pilot_name = pilot_data['pilot_name']
    pilot_location = pilot_data.get('current_location', pilot_data['home_location'])
    active_job = FlightModel.load_active_flight()
    tour_data = TourModel.load_tour()
    
    # Cleanup expired jobs
    JobModel.cleanup_expired_jobs(airports.airports, aircraft.aircraft_list, pilot_data.get('max_distance'))
    
    selected_aircraft = None
    if active_job:
        selected_aircraft = aircraft.get_by_reg(active_job['aircraft_reg'])
        if selected_aircraft:
            pilot_location = selected_aircraft['location']
    
    # Initialize jobs for airports with aircraft if jobs file doesn't exist
    from models import JOBS_FILE
    if not os.path.exists(JOBS_FILE):
        max_dist = pilot_data.get('max_distance')
        for ac in aircraft.aircraft_list:
            JobModel.ensure_jobs_for_airport(ac['location'], airports.airports, aircraft.aircraft_list, max_dist)

    return {
        'config': config,
        'pilot_data': pilot_data,
        'airports': airports,
        'aircraft': aircraft,
        'pilot_name': pilot_name,
        'pilot_location': pilot_location,
        'active_job': active_job,
        'tour_data': tour_data,
        'selected_aircraft': selected_aircraft
    }

@app.route('/')
def index():
    state = get_state()
    tour_active = state['active_job'] and state['active_job'].get('type') == 'TOUR'
    return render_template('index.html', 
                           pilot_name=state['pilot_name'],
                           pilot_location=state['pilot_location'],
                           selected_aircraft=state['selected_aircraft'],
                           active_job=state['active_job'],
                           tour_active=tour_active,
                           max_distance=state['pilot_data'].get('max_distance'))

@app.route('/jobs')
def available_jobs():
    state = get_state()
    if state['active_job']:
        flash("You have an active job! Complete or cancel it first.", "danger")
        return redirect(url_for('index'))
    
    JobModel.ensure_jobs_for_airport(state['pilot_location'], state['airports'].airports, state['aircraft'].aircraft_list, state['pilot_data'].get('max_distance'))
    jobs = JobModel.get_jobs_at(state['pilot_location'])
    
    available_aircraft = state['aircraft'].get_aircraft_at(state['pilot_location'])
    
    import time
    return render_template('jobs.html', 
                           jobs=jobs, 
                           pilot_location=state['pilot_location'],
                           available_aircraft=available_aircraft,
                           now_ts=int(time.time()))

@app.route('/accept_job', methods=['POST'])
def accept_job():
    # In a real app we'd pass an ID, here we might need to regenerate or pass all data
    # For simplicity, let's assume the form passes all job data
    aircraft_reg = request.form.get('aircraft_reg')
    state = get_state()
    aircraft = state['aircraft'].get_by_reg(aircraft_reg)
    
    if not aircraft:
        flash("Selected aircraft not found!", "danger")
        return redirect(url_for('available_jobs'))

    job_data = {
        'origin': request.form.get('origin'),
        'destination': request.form.get('destination'),
        'distance': int(request.form.get('distance') or 0),
        'type': request.form.get('type'),
        'amount': int(request.form.get('amount') or 0),
        'unit': request.form.get('unit'),
        'dest_name': request.form.get('dest_name'),
        'aircraft_reg': aircraft['reg'],
        'aircraft_type': aircraft['type']
    }
    
    # Final validation of capacity
    if job_data['type'] in ['PAX', 'PLEASURE']:
        if job_data['amount'] > aircraft['pax']:
            flash(f"Selected aircraft {aircraft['reg']} does not have enough passenger capacity!", "danger")
            return redirect(url_for('available_jobs'))
    elif job_data['type'] == 'CARGO':
        if job_data['amount'] > aircraft['cargo']:
            flash(f"Selected aircraft {aircraft['reg']} does not have enough cargo capacity!", "danger")
            return redirect(url_for('available_jobs'))

    FlightModel.save_active_flight(job_data)
    
    job_id = request.form.get('job_id')
    if job_id:
        JobModel.remove_job(job_id)

    flash(f"Job to {job_data['destination']} accepted with {aircraft['reg']}!", "success")
    return redirect(url_for('index'))

@app.route('/complete_job')
def complete_job():
    state = get_state()
    active_job = state['active_job']
    if not active_job:
        flash("No active job to complete!", "danger")
        return redirect(url_for('index'))
        
    FlightModel.log_flight(state['selected_aircraft'], active_job, state['pilot_name'], "COMPLETED")
    job_type = active_job.get('type')
    pilot_location = active_job['destination']
    
    # Update aircraft location
    state['selected_aircraft']['location'] = pilot_location
    state['aircraft'].save_aircraft()
    
    # Update pilot location in config
    state['pilot_data']['current_location'] = pilot_location
    ConfigModel.save_config(state['config'])
    
    FlightModel.clear_active_flight()
    
    flash(f"Flight to {pilot_location} completed!", "success")
    
    if job_type == 'TOUR':
        tour_data = TourModel.load_tour()
        if tour_data and len(tour_data.get('airports', [])) > 1:
            tour_data['airports'].pop(0)
            if len(tour_data['airports']) > 1:
                TourModel.save_tour(tour_data)
                # In terminal it automatically called handle_flight_tour
                # In web we can redirect to a route that handles the next leg
                return redirect(url_for('flight_tour'))
            else:
                TourModel.delete_tour()
                flash("Flight Tour completed!", "success")
                
    return redirect(url_for('index'))

@app.route('/cancel_job')
def cancel_job():
    state = get_state()
    if not state['active_job']:
        flash("No active job to cancel!", "danger")
        return redirect(url_for('index'))
        
    FlightModel.log_flight(state['selected_aircraft'], state['active_job'], state['pilot_name'], "CANCELLED")
    FlightModel.clear_active_flight()
    flash("Job cancelled.", "warning")
    return redirect(url_for('index'))

@app.route('/log')
def flight_log():
    logs = FlightModel.get_logs(20)
    return render_template('log.html', logs=logs)

@app.route('/aircraft')
def aircraft_locations():
    state = get_state()
    return render_template('aircraft.html', 
                           pilot_location=state['pilot_location'], 
                           aircraft_list=state['aircraft'].aircraft_list)

@app.route('/ferry', methods=['GET', 'POST'])
def ferry_flight():
    state = get_state()
    if state['active_job']:
        flash("You have an active job!", "danger")
        return redirect(url_for('index'))
        
    available_aircraft = state['aircraft'].get_aircraft_at(state['pilot_location'])
    if not available_aircraft:
        flash("No aircraft available here!", "danger")
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        reg = request.form.get('aircraft_reg')
        dest_icao = request.form.get('destination').upper()
        
        ferry_ac = next((ac for ac in available_aircraft if ac['reg'] == reg), None)
        if not ferry_ac:
            flash("Selected aircraft not found!", "danger")
            return redirect(url_for('ferry_flight'))
            
        if not state['airports'].exists(dest_icao):
            flash(f"Airport {dest_icao} not found!", "danger")
            return redirect(url_for('ferry_flight'))
            
        dest_info = state['airports'].get_airport(dest_icao)
        origin_info = state['airports'].get_airport(ferry_ac['location'])
        
        dist = FlightModel.haversine(
            origin_info['lat'], origin_info['lon'],
            dest_info['lat'], dest_info['lon']
        )
        
        # Ignore range check as requested
        # if dist > ferry_ac['range']:
        #     flash(f"Destination out of range ({round(dist)} nm)!", "danger")
        #     return redirect(url_for('ferry_flight'))
            
        job = {
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
        FlightModel.save_active_flight(job)
        flash(f"Ferry flight to {dest_icao} ready.", "success")
        return redirect(url_for('index'))
        
    return render_template('ferry.html', aircraft_list=available_aircraft)

@app.route('/tour', methods=['GET', 'POST'])
def flight_tour():
    state = get_state()
    if state['active_job']:
        flash("You have an active job!", "danger")
        return redirect(url_for('index'))
        
    tour_data = TourModel.load_tour()
    
    if request.method == 'POST' and not tour_data:
        # Create new tour
        icao_list = request.form.get('airports').upper().split()
        if len(icao_list) < 2:
            flash("Need at least 2 airports for a tour!", "danger")
            return redirect(url_for('flight_tour'))
            
        valid_airports = []
        for icao in icao_list:
            if state['airports'].exists(icao):
                valid_airports.append(icao)
            else:
                flash(f"Airport {icao} not found!", "warning")
        
        if len(valid_airports) < 2:
            flash("Not enough valid airports!", "danger")
            return redirect(url_for('flight_tour'))
            
        tour_data = {'airports': valid_airports}
        TourModel.save_tour(tour_data)
        flash("Tour created!", "success")
        
    if tour_data:
        # Check if we are at the start of the next leg
        current_leg_origin = tour_data['airports'][0]
        if state['pilot_location'] != current_leg_origin:
            flash(f"You are at {state['pilot_location']}, but the tour next leg starts at {current_leg_origin}. Fly there first!", "warning")
            return render_template('tour.html', tour_data=tour_data, pilot_location=state['pilot_location'])
            
        # Get available aircraft
        available_aircraft = state['aircraft'].get_aircraft_at(state['pilot_location'])
            
        # If user selected an aircraft for the leg
        if request.method == 'POST' and request.form.get('aircraft_reg'):
            reg = request.form.get('aircraft_reg')
            ac = next((a for a in available_aircraft if a['reg'] == reg), None)
            if ac:
                dest_icao = tour_data['airports'][1]
                dest_info = state['airports'].get_airport(dest_icao)
                origin_info = state['airports'].get_airport(ac['location'])
                
                dist = FlightModel.haversine(
                    origin_info['lat'], origin_info['lon'],
                    dest_info['lat'], dest_info['lon']
                )
                
                # Ignore range check as requested
                # if dist > ac['range']:
                #     flash(f"Destination out of range ({round(dist)} nm)!", "danger")
                #     return render_template('tour.html', tour_data=tour_data, aircraft_list=available_aircraft, pilot_location=state['pilot_location'])
                
                job = {
                    'origin': ac['location'],
                    'destination': dest_icao,
                    'distance': round(dist),
                    'type': 'TOUR',
                    'amount': 0,
                    'unit': 'passengers',
                    'dest_name': dest_info['name'],
                    'aircraft_reg': ac['reg'],
                    'aircraft_type': ac['type']
                }
                FlightModel.save_active_flight(job)
                flash(f"Tour leg to {dest_icao} ready.", "success")
                return redirect(url_for('index'))

        return render_template('tour.html', tour_data=tour_data, aircraft_list=available_aircraft, pilot_location=state['pilot_location'])

    return render_template('tour.html', tour_data=None)

@app.route('/delete_tour')
def delete_tour():
    TourModel.delete_tour()
    flash("Tour deleted.", "info")
    return redirect(url_for('flight_tour'))

@app.route('/airport/<icao>')
def airport_page(icao):
    state = get_state()
    airport = state['airports'].get_airport(icao)
    if not airport:
        flash(f"Airport {icao} not found!", "danger")
        return redirect(url_for('index'))
    
    # Create jobs if they don't exist
    JobModel.ensure_jobs_for_airport(icao, state['airports'].airports, state['aircraft'].aircraft_list, state['pilot_data'].get('max_distance'))
    
    jobs = JobModel.get_jobs_at(icao)
    aircraft_at_airport = state['aircraft'].get_aircraft_at(icao)
    
    return render_template('airport.html', 
                           airport=airport, 
                           icao=icao,
                           jobs=jobs, 
                           aircraft_list=aircraft_at_airport,
                           pilot_location=state['pilot_location'])

@app.route('/pilots')
def pilot_selection():
    state = get_state()
    return render_template('pilots.html', 
                           pilots=state['config'].get('pilots', {}), 
                           active_pilot=state['config'].get('active_pilot'),
                           pilot_name=state['pilot_name'])

@app.route('/select_pilot/<name>')
def select_pilot(name):
    config = ConfigModel.load_config()
    if name in config.get('pilots', {}):
        config['active_pilot'] = name
        ConfigModel.save_config(config)
        flash(f"Switched to pilot {name}", "success")
    else:
        flash(f"Pilot {name} not found", "danger")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
