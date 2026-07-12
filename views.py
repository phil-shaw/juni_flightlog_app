import time

# Colors
CYAN = "36"
GREEN = "32"
YELLOW = "33"
WHITE = "37"
MAGENTA = "35"
BLUE = "34"
RED = "31"

class TerminalView:
    @staticmethod
    def clear_screen():
        print("\033[H\033[J", end="")

    @staticmethod
    def move_cursor(y, x):
        print(f"\033[{y};{x}H", end="")

    @staticmethod
    def color_text(text, color_code):
        return f"\033[{color_code}m{text}\033[0m"

    @staticmethod
    def draw_box(y, x, w, h, title=""):
        TerminalView.move_cursor(y, x)
        print("┏" + "━" * (w - 2) + "┓")
        for i in range(1, h - 1):
            TerminalView.move_cursor(y + i, x)
            print("┃" + " " * (w - 2) + "┃")
        TerminalView.move_cursor(y + h - 1, x)
        print("┗" + "━" * (w - 2) + "┛")
        if title:
            TerminalView.move_cursor(y, x + 2)
            print(f" {title} ")

    @staticmethod
    def show_main_menu(pilot_name, pilot_location, selected_aircraft, active_job, tour_active=False, max_distance=None):
        TerminalView.clear_screen()
        TerminalView.draw_box(1, 1, 80, 20, "MAIN MENU")
        TerminalView.move_cursor(3, 4)
        pilot_str = TerminalView.color_text(pilot_name, YELLOW)
        loc_str = TerminalView.color_text(pilot_location, GREEN)
        
        info_line = f"Pilot: {pilot_str} | Location: {loc_str}"
        if max_distance:
            info_line += f" | Max Job Dist: {max_distance} nm"
            
        print(TerminalView.color_text(info_line, WHITE))
        
        TerminalView.move_cursor(4, 4)
        ac_type = TerminalView.color_text(selected_aircraft['type'], CYAN)
        print(TerminalView.color_text(f"Aircraft: {ac_type} ({selected_aircraft['reg']})", WHITE))
        
        if active_job:
            TerminalView.move_cursor(6, 4)
            job_str = f"{active_job['origin']} -> {active_job['destination']} ({active_job['distance']} nm, {active_job['amount']} {active_job['unit']})"
            color = RED
            if tour_active:
                job_str = "[TOUR] " + job_str
                color = MAGENTA
            print(TerminalView.color_text(f"ACTIVE JOB: {job_str}", color))
        
        menu_items = [
            "1. Show Available Jobs",
            "2. Show Flight Log",
            "3. Show Aircraft & Locations",
            "4. Mark Job Completed",
            "5. Cancel Active Job",
            "6. Ferry Flight",
            "7. Start Flight Tour",
            "Q. Quit Program"
        ]
        
        for i, item in enumerate(menu_items):
            TerminalView.move_cursor(8 + i, 6)
            print(TerminalView.color_text(item, WHITE))
            
        TerminalView.move_cursor(19, 4)
        return input(TerminalView.color_text("Select an option: ", YELLOW)).lower()

    @staticmethod
    def show_available_jobs(jobs, origin_icao, origin_name):
        TerminalView.clear_screen()
        TerminalView.draw_box(1, 1, 120, 25, "AVAILABLE JOBS")
        TerminalView.move_cursor(3, 4)
        print(TerminalView.color_text(f"Available jobs at : {origin_icao} {origin_name}", WHITE))
        
        TerminalView.move_cursor(5, 4)
        header = f"{'#':<3} {'Dest':<25} {'Dist':<10} {'Type':<12} {'Payload':<15}"
        print(TerminalView.color_text(header, MAGENTA))
        TerminalView.move_cursor(6, 4)
        print("─" * 104)
        
        for i, job in enumerate(jobs):
            if i >= 15: break
            TerminalView.move_cursor(7 + i, 4)
            dest_str = f"{job['destination']} ({job['dest_name'][:15]})"
            payload_str = f"{job['amount']} {job['unit']}"
            jtype = job.get('type', 'PAX')
            
            # Color coding based on job type
            color = WHITE
            if jtype == 'PAX':
                color = CYAN
            elif jtype == 'CARGO':
                color = GREEN
            elif jtype == 'PLEASURE':
                color = BLUE
            
            line = f"{i+1:<3} {dest_str:<25} {job['distance']:>4} nm    {jtype:<12} {payload_str:<15}"
            print(TerminalView.color_text(line, color))
        
        TerminalView.move_cursor(23, 4)
        return input(TerminalView.color_text("Select a job (1-15) or 'b' for back: ", YELLOW)).lower()

    @staticmethod
    def select_aircraft_for_job(available_aircraft, job):
        TerminalView.clear_screen()
        TerminalView.draw_box(1, 1, 80, 20, "SELECT AIRCRAFT FOR JOB")
        TerminalView.move_cursor(3, 4)
        print(TerminalView.color_text(f"Job: {job['origin']} -> {job['destination']} ({job['amount']} {job['unit']})", WHITE))
        
        TerminalView.move_cursor(5, 4)
        header = f"{'#':<3} {'Type':<25} {'Reg':<10} {'Capacity':<15}"
        print(TerminalView.color_text(header, MAGENTA))
        
        for i, ac in enumerate(available_aircraft):
            suitable = False
            capacity_str = ""
            if job['type'] in ['PAX', 'PLEASURE']:
                suitable = ac['pax'] >= job['amount']
                capacity_str = f"{ac['pax']} PAX"
            elif job['type'] == 'CARGO':
                suitable = ac['cargo'] >= job['amount']
                capacity_str = f"{ac['cargo']} kg"
            
            TerminalView.move_cursor(6 + i, 4)
            line = f"{i+1:<3} {ac['type']:<25} {ac['reg']:<10} {capacity_str:<15}"
            
            if suitable:
                print(TerminalView.color_text(line, GREEN))
            else:
                print(TerminalView.color_text(line + " (TOO SMALL)", RED))
        
        TerminalView.move_cursor(18, 4)
        return input(TerminalView.color_text("Select aircraft or 'b' for back: ", YELLOW)).lower()

    @staticmethod
    def show_flight_log(logs):
        TerminalView.clear_screen()
        TerminalView.draw_box(1, 1, 100, 25, "FLIGHT LOG")
        if logs:
            TerminalView.move_cursor(3, 4)
            header = f"{'Date':<18} {'AC':<8} {'Route':<15} {'Dist':<8} {'Payload':<15} {'Status':<10}"
            print(TerminalView.color_text(header, MAGENTA))
            for i, log in enumerate(logs):
                TerminalView.move_cursor(4 + i, 4)
                route = f"{log.get('Origin', '')}->{log.get('Destination', '')}"
                dist = f"{log.get('Distance', '0')} nm"
                payload = f"{log.get('Payload', '')} {log.get('Unit', '')}"
                status = log.get('Status', 'COMPLETED')
                timestamp = log.get('Timestamp', '')
                if len(timestamp) > 16: # Format was YYYY-MM-DD HH:MM:SS
                    timestamp = timestamp[:16]
                print(f"{timestamp:<18} {log.get('Aircraft', ''):<8} {route:<15} {dist:<8} {payload:<15} {status:<10}")
        else:
            TerminalView.move_cursor(4, 4)
            print("No flight logs found.")
        TerminalView.move_cursor(23, 4)
        input("Press Enter to go back...")

    @staticmethod
    def show_aircraft_locations(pilot_location, aircraft_list):
        TerminalView.clear_screen()
        TerminalView.draw_box(1, 1, 80, 25, "AIRCRAFT LOCATIONS")
        TerminalView.move_cursor(3, 4)
        loc_str = TerminalView.color_text(pilot_location, GREEN)
        print(TerminalView.color_text(f"Pilot Current Location: {loc_str}", WHITE))
        TerminalView.move_cursor(5, 4)
        header = f"{'Type':<25} {'Reg':<10} {'Location':<10}"
        print(TerminalView.color_text(header, MAGENTA))
        
        for i, ac in enumerate(aircraft_list):
            if i >= 18: break
            TerminalView.move_cursor(6 + i, 4)
            ac_line = f"{ac['type']:<25} {ac['reg']:<10} {ac['location']:<10}"
            if ac['location'] == pilot_location:
                print(TerminalView.color_text(ac_line, GREEN))
            else:
                print(ac_line)
        TerminalView.move_cursor(23, 4)
        input("Press Enter to go back...")

    @staticmethod
    def show_flight_progress(origin, destination, distance):
        TerminalView.clear_screen()
        TerminalView.draw_box(5, 10, 60, 10, "FLIGHT IN PROGRESS")
        TerminalView.move_cursor(7, 15)
        print(f"Flying from {origin} to {destination}")
        TerminalView.move_cursor(8, 15)
        print(f"Distance: {distance} nm")
        
        bar_len = 30
        for p in range(bar_len + 1):
            TerminalView.move_cursor(10, 15)
            progress = "#" * p + "-" * (bar_len - p)
            print(f"[{progress}] {int(p/bar_len*100)}%")
            time.sleep(0.05)

    @staticmethod
    def get_ferry_aircraft(available_aircraft):
        TerminalView.clear_screen()
        TerminalView.draw_box(1, 1, 60, 20, "SELECT AIRCRAFT FOR FERRY")
        TerminalView.move_cursor(3, 4)
        print(TerminalView.color_text(f"{'#':<3} {'Type':<25} {'Reg':<10}", MAGENTA))
        for i, ac in enumerate(available_aircraft):
            TerminalView.move_cursor(4 + i, 4)
            print(f"{i+1:<3} {ac['type']:<25} {ac['reg']:<10}")
        
        TerminalView.move_cursor(18, 4)
        return input(TerminalView.color_text("Select aircraft (or 'b'): ", YELLOW)).lower()

    @staticmethod
    def get_input(prompt, y=19, x=4):
        TerminalView.move_cursor(y, x)
        # Clear line first
        print(" " * 70, end="")
        TerminalView.move_cursor(y, x)
        return input(TerminalView.color_text(prompt, YELLOW))

    @staticmethod
    def show_message(message, color=WHITE, duration=2):
        TerminalView.move_cursor(19, 4)
        # Clear line
        print(" " * 70, end="")
        TerminalView.move_cursor(19, 4)
        print(TerminalView.color_text(message, color))
        if duration > 0:
            time.sleep(duration)
