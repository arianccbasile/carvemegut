import os
import urllib.request
import zipfile
import shutil
from configparser import ConfigParser
from reframed import set_default_solver
from reframed.solvers.solver import default_parameters, Parameter

__version__ = '0.3.9'

# Project directory
project_dir = os.path.abspath(os.path.dirname(__file__)) + '/'
config = ConfigParser()
config.read(os.path.join(project_dir, 'config.cfg'))

# Set solver parameters
set_default_solver(config.get('solver', 'default_solver'))
default_parameters[Parameter.FEASIBILITY_TOL] = config.getfloat('solver', 'feas_tol')
default_parameters[Parameter.OPTIMALITY_TOL] = config.getfloat('solver', 'opt_tol')
default_parameters[Parameter.INT_FEASIBILITY_TOL] = config.getfloat('solver', 'int_feas_tol')

# Define subfolders as package modules
__all__ = ["cli", "reconstruction", "universe"]

# Configuration paths
CONFIG_PATH = os.path.join(project_dir, "config.cfg")
DATA_URL = "https://zenodo.org/records/14882984/files/data.zip"  # Replace with the correct URL
DATA_PATH = os.path.join(project_dir, "data")

# Function to load configuration
def load_config():
    """Loads the configuration file if it exists."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            config_data = f.read()
        return config_data
    return None

# Function to download data
def download_data():
    """Downloads data from an online repository if it does not exist."""
    zip_path = os.path.join(DATA_PATH, "data.zip")
    if not os.path.exists(DATA_PATH):
        os.makedirs(DATA_PATH, exist_ok=True)
    if not os.path.exists(zip_path):
        print("Downloading data...")
        urllib.request.urlretrieve(DATA_URL, zip_path)
        print("Data successfully downloaded to", zip_path)

# Function to extract data and fix nested structure

def extract_data():
    """Extracts data and removes nested directory if needed."""
    zip_path = os.path.join(DATA_PATH, "data.zip")
    if os.path.exists(zip_path):
        print("Extracting data...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(DATA_PATH)
        os.remove(zip_path)  # Cleanup
        print("Data extraction complete.")
       

# Import submodules
from . import cli
from . import reconstruction
from . import universe

# Optional: Initialization
CONFIG = load_config()
if CONFIG:
    print("Configuration successfully loaded.")

# Automatically download and extract data
download_data()
extract_data()
