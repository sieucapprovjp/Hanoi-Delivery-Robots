import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from delivery_robots.utils.geo import haversine_distance

lat1, lon1 = 21.0285, 105.8542
lat2, lon2 = 21.0385, 105.8642

dist = haversine_distance(lat1, lon1, lat2, lon2)
print(f"Distance: {dist} meters")
