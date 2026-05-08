import argparse
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep Streamlit app warm using Selenium")
    parser.add_argument("--url", required=True, help="Target Streamlit app URL")
    parser.add_argument("--wait-seconds", type=int, default=12, help="Wait time for page load")
    args = parser.parse_args()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1365,1024")

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)
        driver.get(args.url)

        # Allow Streamlit hydration and network calls to settle.
        time.sleep(max(3, args.wait_seconds))

        title = (driver.title or "").strip()
        body = driver.find_element(By.TAG_NAME, "body").text[:500]

        print(f"URL: {args.url}")
        print(f"Title: {title}")

        if not title and not body:
            print("ERROR: Page appears empty.")
            return 1

        print("Keep-alive ping succeeded.")
        return 0
    except Exception as exc:
        print(f"ERROR: Keep-alive failed: {exc}")
        return 1
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    sys.exit(main())
