from sqlalchemy import MetaData
from sqlmodel import SQLModel

# Import all models here for Alembic to detect them
from app.models import *

# Get metadata from SQLModel (it auto-creates tables in it)
meta = SQLModel.metadata

# Set schema for all tables in metadata
meta.schema = 'gepvi_reports'
