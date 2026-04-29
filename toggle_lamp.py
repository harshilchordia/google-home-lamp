"""
Google Home Lamp Toggle Script
-------------------------------
First run: opens a visible browser so you can log in with Google.
           Session is saved to ./session/cookies.pkl for future runs.
After that: runs headlessly using the saved session.

Usage:
    python3 toggle_lamp.py              # auto-detect mode
    python3 toggle_lamp.py --login      # force headed login
    python3 toggle_lamp.py --headless   # force headless (needs saved session)
"""

import argparse
import pickle
import sys
import time
from pathlib import Path

import undetected_chromedriver as uc
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SESSION_DIR = Path(__file__).parent / "session"
COOKIES_FILE = SESSION_DIR / "cookies.pkl"
GOOGLE_HOME_URL = "https://home.google.com/"

LAMP_SELECTOR = "button.on-off-tile p.title[aria-label='Lamp tile']"


def save_cookies(driver):
    SESSION_DIR.mkdir(exist_ok=True)
    with open(COOKIES_FILE, "wb") as f:
        pickle.dump(driver.get_cookies(), f)
    print("[+] Session saved.")


def load_cookies(driver):
    driver.get("https://home.google.com/")
    with open(COOKIES_FILE, "rb") as f:
        for cookie in pickle.load(f):
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass


def is_logged_in(driver, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button.on-off-tile"))
        )
        return True
    except Exception:
        return False


def dismiss_modal(driver):
    try:
        ok = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='OK']"))
        )
        ok.click()
        print("[*] Dismissed modal.")
        time.sleep(1)
    except Exception:
        pass  # no modal, that's fine


def click_lamp(driver):
    try:
        print(f"[*] Current URL: {driver.current_url}")

        dismiss_modal(driver)

        driver.save_screenshot(str(Path(__file__).parent / "before_click.png"))
        print("[*] Screenshot saved → before_click.png")

        # List every on-off-tile to debug
        all_btns = driver.find_elements(By.CSS_SELECTOR, "button.on-off-tile")
        print(f"[*] Found {len(all_btns)} device tile(s):")
        for i, b in enumerate(all_btns):
            label_els = b.find_elements(By.CSS_SELECTOR, "p.title")
            label_text = label_els[0].text if label_els else "?"
            print(f"    [{i}] '{label_text}' — title='{b.get_attribute('title')}'")

        label = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, LAMP_SELECTOR))
        )
        btn = label.find_element(By.XPATH, "./ancestor::button")
        title = btn.get_attribute("title") or "unknown state"
        print(f"[+] Clicking Lamp — action will be: '{title}'")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        time.sleep(0.5)
        # Dispatch the full pointer event sequence Angular Material expects
        driver.execute_script("""
            var el = arguments[0];
            ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(type) {
                el.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
            });
        """, btn)
        time.sleep(1.5)

        driver.save_screenshot(str(Path(__file__).parent / "after_click.png"))
        print("[*] Screenshot saved → after_click.png")
        print("[+] Done.")
    except Exception as e:
        print(f"[-] Could not find the Lamp button: {e}")
        sys.exit(1)


def make_driver(headless: bool):
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return uc.Chrome(options=options, version_main=147)


def run(headless: bool):
    driver = make_driver(headless)

    try:
        if COOKIES_FILE.exists():
            print("[*] Loading saved session...")
            load_cookies(driver)
            driver.get(GOOGLE_HOME_URL)
            if is_logged_in(driver):
                print("[+] Session valid.")
                click_lamp(driver)
                return
            else:
                print("[!] Saved session expired, need to log in again.")
                if headless:
                    print("    Run without --headless to re-authenticate.")
                    sys.exit(1)

        if headless:
            print("[-] No saved session found. Run without --headless first to authenticate.")
            sys.exit(1)

        print(f"[*] Opening Google Home — please sign in with your Google account...")
        driver.get(GOOGLE_HOME_URL)

        print("[*] Waiting for you to log in (up to 2 minutes)...")
        try:
            WebDriverWait(driver, 120).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.on-off-tile"))
            )
        except Exception:
            print("[-] Timed out waiting for login.")
            sys.exit(1)

        print("[+] Logged in!")
        save_cookies(driver)
        click_lamp(driver)

    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser(description="Toggle the Lamp on Google Home.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--login", action="store_true", help="Force headed browser (re-authenticate)")
    group.add_argument("--headless", action="store_true", help="Force headless mode")
    args = parser.parse_args()

    if args.login:
        headless = False
    elif args.headless:
        headless = True
    else:
        headless = COOKIES_FILE.exists()
        print(f"[*] Session {'found' if headless else 'not found'} — running {'headless' if headless else 'headed'}.")

    run(headless)


if __name__ == "__main__":
    main()
