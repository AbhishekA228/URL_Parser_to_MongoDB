from crawler import get_content_from_url_async, print_sublink_stats  # Corrected import

async def main():
    url = "https://www.un.org/en"  # Starting URL
    depth = 2  # Depth of crawl
    print("Starting crawl...")
    await get_content_from_url_async(url, depth)  # Await the asynchronous function
    print_sublink_stats()  # Print the crawl statistics

if __name__ == "__main__":
    # Run the main async function
    import asyncio
    asyncio.run(main())  # Use asyncio.run to start the async main function
