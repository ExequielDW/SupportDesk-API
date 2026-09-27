from pymongo import MongoClient
from decouple import config

DB_CLIENT = MongoClient(config("URI")).suport
