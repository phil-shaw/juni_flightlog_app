from controllers import FlightController

def main():
    try:
        app = FlightController()
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()
