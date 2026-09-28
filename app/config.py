# Contains application figuration such as: 
# database location, maximum upload size, secret key, 
# allowed file extensions, and application settings. 

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key") # Secret key to use

    SQLALCHEMY_DATABASE_URI = os.getenv( # where the SQLite database is
        "DATABASE_URL",
        "sqlite:///epadata.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False # SQLAlchemy modification tracking

    MAX_CONTENT_LENGTH = 50 * 1024 * 1024 # Maximum upload size 

    ALLOWED_UPLOAD_EXTENSIONS = { # File types we accept
        "csv",
        "xlsx",
        "xls"
    }
