import os
import databases
from dotenv import load_dotenv

load_dotenv()

# Get the URL from .env
DATABASE_URL = os.getenv("DATABASE_URL")

# Quick fix for standard async postgres driver compatibility
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Initialize the database object
database = databases.Database(DATABASE_URL)