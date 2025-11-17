
import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, inspect
from geoalchemy2 import Geometry, WKTElement
from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon
from shapely.geometry import mapping, shape

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import tempfile
import re


from flask import Flask, request, jsonify, send_from_directory
import spacy
from database.connection import engine, check_db_connection
from tables.create import create_table
from tables.list import list_tables
from data.upload import upload_data
from data.update import update_data
from data.visualize import visualize_data
from utils.nlp import process_query
from utils.helpers import extract_table_name, extract_columns, extract_file_name
from classification.ranges import create_ranges

app = Flask(__name__)

# Load NLP model
nlp = spacy.load("en_core_web_sm")

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/query', methods=['POST'])
def handle_query():
    user_input = request.json.get('query')
    doc = nlp(user_input.lower())

    response = process_query(doc, user_input, check_db_connection, create_table, list_tables,
                            upload_data, update_data, visualize_data, create_ranges,
                               extract_table_name, extract_columns, extract_file_name)
    return jsonify({"response": response})

if __name__ == '__main__':
    app.run(debug=True)
