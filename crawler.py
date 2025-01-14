import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from langdetect import detect
from pymongo import MongoClient
import hashlib
import datetime

# MongoDB Configuration
client = MongoClient("mongodb://localhost:27017/")  # Update with your MongoDB URI if needed
db = client["WebCrawlerDB"]  # Database name
collection = db["WebContent"]  # Collection for individual URL records
master_collection = db["MasterRecord"]  # Collection for the master record

# Track sublinks and errors
total_sublinks = 0
fetched_sublinks = 0
error_count = 0  # Track number of URLs that caused errors
saved_count = 0  # Track number of URLs saved to the database

async def fetch(session, url):
    """
    Fetch the content of a URL asynchronously with User-Agent header.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                print(f"Failed to retrieve {url}. Status code: {response.status}")
                return None
            return await response.text()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def is_english(text):
    """
    Check if the given text is in English using langdetect.
    """
    try:
        return detect(text) == 'en'
    except:
        return False

def generate_content_hash(content):
    """
    Generate a hash value for the content to detect changes.
    """
    return hashlib.md5(content.encode('utf-8')).hexdigest()

async def get_content_from_url_async(url, depth=1, visited=None, master_record=None):
    """
    Crawl a webpage and optionally follow links up to a specified depth.
    Only extracts content in English and saves it to MongoDB.
    """
    global total_sublinks, fetched_sublinks, error_count, saved_count

    if visited is None:
        visited = set()

    if url in visited or depth <= 0:
        return

    visited.add(url)

    async with aiohttp.ClientSession() as session:
        html = await fetch(session, url)
        if not html:
            error_count += 1  # Increment error count if fetching fails
            return

        soup = BeautifulSoup(html, 'html.parser')

        # Extract the main content under each header
        content_sections = []
        
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            heading_text = heading.get_text(strip=True)
            if heading_text and is_english(heading_text):
                section_text = []
                sibling = heading.find_next_sibling()

                while sibling and sibling.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    if sibling.name == 'p':
                        paragraph_text = sibling.get_text(strip=True)
                        if is_english(paragraph_text):
                            section_text.append(paragraph_text)
                    elif sibling.name in ['ul', 'ol']:
                        list_items = [
                            li.get_text(strip=True) for li in sibling.find_all('li') if is_english(li.get_text(strip=True))
                        ]
                        section_text.append("\n".join(list_items))
                    sibling = sibling.find_next_sibling()

                if section_text:
                    content_sections.append(f"{heading_text}\n{'-' * len(heading_text)}\n" + "\n".join(section_text))

        if not content_sections:
            paragraphs = soup.find_all('p')
            content_sections = [
                p.get_text(strip=True) for p in paragraphs if is_english(p.get_text(strip=True))
            ]

        combined_content = "\n\n".join(content_sections)

        # Save to MongoDB if there's new content
        if combined_content.strip():
            content_hash = generate_content_hash(combined_content)
            record = {
                "URL": url,
                "Content": combined_content,
                "ContentHash": content_hash,
                "LastCrawled": datetime.datetime.utcnow()  # Using datetime here
            }

            # Insert the individual URL record in WebContent
            web_content_record = collection.insert_one(record)
            saved_count += 1  # Increment saved count when data is saved
            print(f"Stored content for {url} in individual record")

            # Check if the master record exists, if not create it
            if master_record:
                if content_hash != master_record.get('hash'):
                    # Add sublink record to the sublinks array in master record
                    sublink_obj = {
                        "Id": web_content_record.inserted_id,
                        "url": url,
                        "data": combined_content,
                        "hash": content_hash
                    }
                    master_record["all_data"] += f"\n\n{combined_content}"
                    master_record["sublinks"].append(sublink_obj)
                    master_record["hash"] = content_hash
                    master_record["LastUpdated"] = datetime.datetime.utcnow()
                    master_collection.update_one({"_id": master_record["_id"]}, {"$set": master_record})
                    print(f"Updated master record with new content for {url}")
                else:
                    print(f"No new content for: {url}")
            else:
                # Create a master record if it doesn't exist
                master_record = {
                    "url": url,
                    "all_data": combined_content,
                    "hash": content_hash,
                    "sublinks": [{
                        "Id": web_content_record.inserted_id,
                        "url": url,
                        "data": combined_content,
                        "hash": content_hash
                    }],
                    "LastUpdated": datetime.datetime.utcnow()
                }
                master_collection.insert_one(master_record)
                print(f"Created master record with content for {url}")

        # Extract and crawl links recursively, only if depth is 2
        links = []
        if depth == 2:  # Only consider sublinks at depth 2
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)
                if full_url.startswith('http') and full_url not in visited:
                    links.append(full_url)
                    total_sublinks += 1  # Increment total sublinks count

        if depth > 1 and links:
            tasks = [get_content_from_url_async(link, depth - 1, visited, master_record) for link in links]
            await asyncio.gather(*tasks)

        # Count fetched sublinks only for depth 2
        if depth == 2 and links:
            fetched_sublinks += len(links)

def get_async_results(url, depth=2):
    """
    Wrapper to collect results using an event loop.
    """
    return asyncio.run(get_content_from_url_async(url, depth))

def print_sublink_stats():
    """
    Print the total number of sublinks, the number of fetched sublinks, 
    the number of URLs causing errors, and the number of saved URLs.
    """
    print(f"\nTotal number of sublinks: {total_sublinks}")
    print(f"Number of URLs that caused errors: {error_count}")
    print(f"Number of URLs saved to the database: {saved_count}")
