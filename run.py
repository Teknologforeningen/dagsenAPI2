from app import create_app
from flasgger import Swagger

app = create_app()
swagger = Swagger(app, template_file="static/swagger.yml")

if __name__ == "__main__":
    print("Running app")
    app.run(debug=True, host='0.0.0.0', port=5000)
