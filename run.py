from app import create_app

app = create_app()

if __name__ == "__main__":
    print("Running app")
    app.run(debug=True, host='0.0.0.0', port=5000)
