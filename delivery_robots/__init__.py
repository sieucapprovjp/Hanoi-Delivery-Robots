from flask import Flask
from .core.map_manager import MapManager
from .core.environment import EnvironmentManager
from .utils.metrics_utils import create_metrics

# Global singletons
map_manager = MapManager()
env_manager = EnvironmentManager(map_manager)
_metrics = create_metrics()

def create_app():
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object('delivery_robots.config.Config')

    with app.app_context():
        # Import routes down here to avoid circular imports
        from . import routes
        routes.register_routes(app)
        
    return app
