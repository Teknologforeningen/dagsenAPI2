from app import create_app
from flasgger import Swagger
import logging
import os

app = create_app()
swagger = Swagger(app, template_file="static/swagger.yml")


if __name__ == "__main__":
    print("Running app")
    api_debug = os.getenv('API_DEBUG', '0').lower() in ('1', 'true', 'yes')
    if api_debug:
        print("API_DEBUG enabled: running in debug mode and verbose logging")
        # In debug mode we want Werkzeug's normal logging and the Flask debugger.
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        # Reduce noisy per-request access logs from Werkzeug in Docker logs
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        # Run without Flask debug mode in production
        app.run(debug=False, host='0.0.0.0', port=5000)
