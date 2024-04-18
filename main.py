"""
This is a proof of concept script that fetches listings from Facebook Marketplace for a given city and search query.
It uses Playwright to automate the browser and fetch the listings, and BeautifulSoup to parse the HTML content of each listing.

The end goal is to automatically parse listings into specified data classes and save them to a DB.
"""

import logging
import json
import os
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Browser, Page
from block import blocking_intercept

from dataclasses import dataclass
from exceptions import CredentialsError, ParseError

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


# Load environment variables from .env file
load_dotenv()
email = os.getenv("FB_EMAIL")
password = os.getenv("FB_PASSWORD")

if not email or not password:
    raise CredentialsError(
        "Facebook email and password must be set as environment variables."
    )
logger.info("Environment variables loaded successfully.")


LOGIN_URL = "https://www.facebook.com/login/device-based/regular/login/"


@dataclass
class Listing:
    """
    Data class representing a Facebook Marketplace listing.

    Listings correspond to a specific page on Facebook Marketplace not necessarily to a single item.
    """

    image_url: str
    title: str
    price: int
    post_url: str
    location: str
    description: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.title} for ${self.price} at ({self.location})" + (
            f"\n{self.description}" if self.description else ""
        )


def open_browser(pw, headless: bool = True) -> Tuple[Page, Browser]:
    """
    Opens a browser and returns the Playwright page object.

    Args:
        pw (SyncPlaywright): The Playwright instance.
        headless (bool): Whether to launch the browser in headless mode.

    Returns:
        Page: The Playwright page object.


    """
    browser = pw.firefox.launch(headless=headless)
    context = browser.new_context(geolocation=None, permissions=["geolocation"])
    page = context.new_page()
    page.route("**/*", blocking_intercept)
    logger.info("Browser opened successfully.")
    return page, browser


def login_to_facebook(page: Page) -> None:
    """
    Log into Facebook using the provided credentials.

    Args:
        page (Page): The Playwright page object.
    """
    EMAIL_SELECTOR = "input[name='email']"
    PASSWORD_SELECTOR = "input[name='pass']"
    LOGIN_BUTTON_SELECTOR = "button[name='login']"

    logger.info("Logging in to Facebook at %s.", LOGIN_URL)
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    page.fill(EMAIL_SELECTOR, email)
    page.fill(PASSWORD_SELECTOR, password)
    page.click(LOGIN_BUTTON_SELECTOR)
    logger.info("Logged in successfully.")


def get_descriptions(listings: List[Listing]) -> None:
    """
    Fetches the descriptions for a list of listings.

    Args:
        listings (List[Listing]): The listings for which to fetch descriptions.
    """
    DESCRIPTION_SELECTOR = "div.xz9dl7a.x4uap5.xsag5q8.xkhd6sd.x126k92a"

    logger.info("Fetching descriptions for %s listings.", len(listings))
    with sync_playwright() as pw:
        # Open browser
        page, browser = open_browser(pw)

        # Login process
        login_to_facebook(page)

        for listing in listings:
            # Navigate to listing
            logger.info("Fetching description for listing %s.", listing.title)
            logger.info("Navigating to listing at %s.", listing.post_url)
            page.goto(listing.post_url, wait_until="domcontentloaded")
            logger.info("Navigated to listing successfully.")

            # Extract description
            description = page.locator(DESCRIPTION_SELECTOR).inner_text()
            logger.debug("Description: %s", description)

            # Update the description
            listing.description = description
            logger.info("Description fetched successfully.")

        # Close the browser
        browser.close()
        logger.info("Browser closed successfully.")


def clean_listing_url(url: str) -> str:
    """
    Cleans a Facebook Marketplace listing URL to remove tracking parameters and add the base URL.

    Args:
        url (str): The URL to clean.

    Returns:
        str: The cleaned URL.
    """
    return f"https://www.facebook.com{url.split('?', 1)[0]}"


def convert_price_to_int(price: str) -> int:
    """
    Converts a price string to an integer.

    "$CA1,000" -> 1000

    Args:
        price (str): The price string to convert.

    Returns:
        int: The price as an integer.
    """
    price = "".join(filter(str.isdigit, price))
    return int(price)


def create_marketplace_url(
    city: str,
    query: str,
    max_price: Optional[int] = None,
    min_price: Optional[int] = None,
    exact: bool = False,
) -> str:
    """
    Creates a Facebook Marketplace URL based on the provided search criteria.

    Args:
        city (str): The city in which to search for listings.
        query (str): The search query or item type to look for.
        max_price (int): The maximum price of the items to fetch.
        min_price (int): The minimum price of the items to fetch.
        exact (bool): Whether to search for exact matches only.

    Returns:
        str: The generated Facebook Marketplace URL.
    """
    url = f"https://www.facebook.com/marketplace/{city}/search?query={query}"
    if max_price is not None:
        url += f"&maxPrice={max_price}"
    if min_price is not None:
        url += f"&minPrice={min_price}"
    if not exact:
        url += "&exact=false"
    return url


def fetch_marketplace_listings(
    city: str,
    query: str,
    max_price: Optional[int] = None,
    min_price: Optional[int] = None,
    max_listings: int = 0,
) -> List[Listing]:
    """
    Fetches listings from Facebook Marketplace based on provided search criteria.

    Args:
        city (str): The city in which to search for listings.
        query (str): The search query or item type to look for.
        max_price (int): The maximum price of the items to fetch.
        min_price (int): The minimum price of the items to fetch.
        max_listings (int): The maximum number of listings to fetch. If 0, all listings are fetched.

    Returns:
        List[Listing]: A list of Listing objects representing the fetched listings.
    """
    PAGE_OPEN_SELECTOR = 'text="Marketplace"'
    LISTINGS_SELECTOR = "div.x8gbvx8 > div"

    logger.info(
        "Fetching Facebook Marketplace listings for %s in %s with max price %s and min price %s.",
        query,
        city,
        max_price,
        min_price,
    )

    # URLs setup
    marketplace_url = create_marketplace_url(city, query, max_price, min_price)

    # Launch browser and fetch listings
    logger.info("Launching browser and fetching listings.")
    with sync_playwright() as pw:
        # Open browser
        page, browser = open_browser(pw)

        # Login process
        login_to_facebook(page)

        # Navigate to marketplace
        logger.info("Navigating to marketplace at %s.", marketplace_url)
        page.goto(marketplace_url, wait_until="domcontentloaded")
        logger.info("Navigated to marketplace successfully.")

        # Highlight the listings for debugging
        listings = page.locator(LISTINGS_SELECTOR)
        num_listings = (
            listings.count()
            if not max_listings
            else min(listings.count(), max_listings)
        )
        logger.info("Found %s listings on the page.", num_listings)

        # Extract and parse
        parsed = []
        for i in range(num_listings):
            logger.info("Parsing listing %s/%s.", i + 1, num_listings)
            listing_html = listings.nth(i).inner_html()
            try:
                parsed_listing = parse_listing_with_soup(listing_html)
                parsed.append(parsed_listing)
            except ParseError:
                logger.warning("Failed to parse listing %s.", listing_html)
        logger.info("Listings parsed successfully.")

        # Close the browser
        browser.close()
        logger.info("Browser closed successfully.")

    logger.info("Listings fetched successfully.")
    return parsed


def parse_listing_with_soup(html_content: str) -> Listing:
    """
    Parses a single listing's HTML content using BeautifulSoup.

    Args:
        html_content (str): The HTML content of a listing.

    Returns:
        Listing: A dataclass representing the parsed listing.

    Raises:
        ParseError: If the listing cannot be parsed.
    """
    # Selectors
    IMAGE_SELECTOR = "img.xt7dq6l.xl1xv1r.x6ikm8r.x10wlt62.xh8yej3"
    TITLE_SELECTOR = "span.x1lliihq.x6ikm8r.x10wlt62.x1n2onr6"
    PRICE_SELECTOR = "span.x193iq5w"
    URL_SELECTOR = "a.x1i10hfl"
    LOCATION_SELECTOR = "span.x1lliihq.x6ikm8r.x10wlt62.x1n2onr6.xlyipyv.xuxw1ft"

    soup = BeautifulSoup(html_content, "html.parser")
    logger.debug("Parsing listing with BeautifulSoup: %s", soup)

    image_locator = soup.select_one(IMAGE_SELECTOR)
    image = image_locator.get("src", None) if image_locator else None
    if isinstance(image, list):
        logger.debug("Multiple images found. Selecting the first one.")
        image = image[0]
    image = image[0] if isinstance(image, list) else image
    logger.debug("Image: %s", image)

    title_locator = soup.select_one(TITLE_SELECTOR)
    title = title_locator.text.strip() if title_locator else None
    logger.debug("Title: %s", title)

    price_locator = soup.select_one(PRICE_SELECTOR)
    price = price_locator.text.strip() if price_locator else None
    price = convert_price_to_int(price) if price else None
    logger.debug("Price: %s", price)

    link_locator = soup.select_one(URL_SELECTOR)
    link = link_locator.get("href", None) if link_locator else None
    if isinstance(link, list):
        logger.debug("Multiple links found. Selecting the first one.")
        link = link[0]
    link = clean_listing_url(link) if link else None
    logger.debug("Link: %s", link)

    location_locator = soup.select_one(LOCATION_SELECTOR)
    location = location_locator.text.strip() if location_locator else None
    logger.debug("Location: %s", location)

    if not all([image, title, price, link, location]):
        raise ParseError("Failed to parse listing.")

    return Listing(image, title, price, link, location)  # type: ignore


def listings_to_json(listings: List[Listing]) -> str:
    """
    Converts a list of Listing objects to a JSON string.

    Args:
        listings (List[Listing]): The list of Listing objects to convert.

    Returns:
        str: The JSON string representing the listings.
    """
    return json.dumps([listing.__dict__ for listing in listings], indent=4)


if __name__ == "__main__":
    logger.setLevel(logging.INFO)
    logger.info("Fetching listings.")
    scraped_listings = fetch_marketplace_listings(
        "toronto", "mountain bike", max_listings=15, max_price=500
    )
    get_descriptions(scraped_listings)

    logger.info("Listings fetched successfully.")
    # Save listings to JSON file
    with open("mtb_bikes.json", "w", encoding="utf-8") as f:
        f.write(listings_to_json(scraped_listings))
        logger.info("Listings saved to listings.json.")
