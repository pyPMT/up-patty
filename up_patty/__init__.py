import unified_planning as up
from .up_patty import PattyPlanner

# Register the planner to the UP framework
# This is done once the package is imported so its transparent to the user.
env = up.environment.get_environment()
env.factory.add_engine('up_patty', 'up_patty', 'PattyPlanner')