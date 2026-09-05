import sys
import os

# Add root repository directory to sys.path so 'src' imports resolve properly on Vercel Serverless
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.api.app import app

# Export app instance for Vercel Python runtime
handler = app
