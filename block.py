"""
This module contains the blocking_intercept function.
It is used to reduce the bandwidth usage when loading Facebook Marketplace pages.
"""

from playwright.sync_api import Route

BLOCK_RESOURCE_TYPES = [
    "beacon",
    "csp_report",
    "font",
    "image",
    "imageset",
    "media",
    "object",
    "texttrack",
    "xhr",
    "eventsource",
]


BLOCK_RESOURCE_NAMES = [
    "adzerk",
    "analytics",
    "cdn.api.twitter",
    "doubleclick",
    "exelator",
    "fontawesome",
    "google",
    "google-analytics",
    "googletagmanager",
]


def blocking_intercept(route: Route) -> None:
    """Abort blocked routes

    Args:
        route (Route): The intercepted route.
    """
    if route.request.resource_type in BLOCK_RESOURCE_TYPES:
        return route.abort()
    if any(key in route.request.url for key in BLOCK_RESOURCE_NAMES):
        return route.abort()
    return route.continue_()
