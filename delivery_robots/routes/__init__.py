def register_routes(app):
    """Register all modular blueprints to the Flask app."""
    from .views import views_bp
    from .system import system_bp
    from .traffic import traffic_bp
    from .weather import weather_bp
    from .obstacles import obstacles_bp
    from .routing import routing_bp
    from .algorithms import algorithms_bp
    from .metrics import metrics_bp

    app.register_blueprint(views_bp)
    app.register_blueprint(system_bp, url_prefix='/api')
    app.register_blueprint(traffic_bp, url_prefix='/api/traffic')
    app.register_blueprint(weather_bp, url_prefix='/api/weather')
    app.register_blueprint(obstacles_bp, url_prefix='/api/obstacles')
    app.register_blueprint(routing_bp, url_prefix='/api/route')
    app.register_blueprint(algorithms_bp, url_prefix='/api/algorithms')
    app.register_blueprint(metrics_bp, url_prefix='/api/metrics')
