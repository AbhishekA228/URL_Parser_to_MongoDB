from pymongo import MongoClient
import hashlib
import datetime

# MongoDB Configuration
client = MongoClient("mongodb://localhost:27017/")  # Update with your MongoDB URI if needed
db = client["WebCrawlerDB"]  # Database name
collection = db["WebContent"]  # Collection for individual URL records
master_collection = db["MasterRecord"]  # Collection for the master record

def generate_content_hash(content):
    """
    Generate a hash value for the content to detect changes.
    """
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def insert_web_content(url, content):
    """
    Insert the content into the WebContent collection and return the inserted ID.
    """
    content_hash = generate_content_hash(content)
    record = {
        "URL": url,
        "Content": content,
        "ContentHash": content_hash,
        "LastCrawled": datetime.datetime.utcnow()
    }

    result = collection.insert_one(record)
    return result.inserted_id

def insert_master_record(url, all_data, sublinks):
    """
    Insert the master record into the MasterRecord collection.
    """
    content_hash = generate_content_hash(all_data)
    record = {
        "url": url,
        "all_data": all_data,
        "hash": content_hash,
        "sublinks": sublinks,
        "LastUpdated": datetime.datetime.utcnow()
    }
    
    result = master_collection.insert_one(record)
    return result.inserted_id

def update_master_record(master_record_id, all_data, sublinks, content_hash):
    """
    Update the master record in the MasterRecord collection.
    """
    record = {
        "all_data": all_data,
        "sublinks": sublinks,
        "hash": content_hash,
        "LastUpdated": datetime.datetime.utcnow()
    }

    master_collection.update_one({"_id": master_record_id}, {"$set": record})
