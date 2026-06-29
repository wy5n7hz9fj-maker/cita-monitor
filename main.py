import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from config import (
    CHECK_INTERVAL_SECONDS,
    FULL_NAME,
    HEADLESS,
    HEARTBEAT_EVERY_HOURS,
    NIE,
    OFFICE,
    PROCEDURE,
    PROVINCE,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)

URL = "https://icp.administracionelectronica.gob.es/icpco/index"
SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id

    def send_message(self, text: str) -> None:
        try:
            requests.post(
                f"{self.base_url}/sendMessage",
                data={"chat_id": self.chat_id, "text": text},
                timeout=20,
            )
        except Exception as exc:
            print(f"Telegram message error: {exc}", flush=True)

    def send_photo(self, path: Path, caption: str = "") -> None:
        try:
            with path.open("rb") as photo:
                requests.post(
                    f"{self.base_url}/sendPhoto",
                    data={"chat_id": self.chat_id, "caption": caption},
                    files={"photo": photo},
                    timeout=30,
                )
        except Exception as exc:
            print(f"Telegram photo error: {exc}", flush=True)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sleep_random(base_seconds: int = 2, extra_seconds: int = 3) -> None:
    time.sleep(base_seconds + random.random() * extra_seconds)


def make_driver() -> webdriver.Chrome:
    chrome_options = Options()

    if HEADLESS:
        chrome_options.add_argument("--headless=new")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-features=RendererCodeIntegrity")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument("--no-zygote")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    chromedriver_bin = os.getenv("CHROMEDRIVER_BIN", "/usr/bin/chromedriver")

    if Path(chrome_bin).exists():
        chrome_options.binary_location = chrome_bin

    service = Service(chromedriver_bin)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(90)
    driver.set_script_timeout(90)
    return driver


def select_by_text_contains(driver, locator: tuple[str, str], expected_text: str, timeout: int = 25) -> None:
    element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))
    select = Select(element)
    expected_norm = expected_text.strip().lower()

    for option in select.options:
        option_text = option.text.strip()
        if expected_norm in option_text.lower() or option_text.lower() in expected_norm:
            select.select_by_visible_text(option.text)
            return

    available = [option.text.strip() for option in select.options if option.text.strip()]
    raise RuntimeError(f"Option not found: {expected_text}. Available options: {available[:20]}")


def click_when_ready(driver, locator: tuple[str, str], timeout: int = 25) -> None:
    WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator)).click()


def send_keys_when_ready(driver, locator: tuple[str, str], value: str, timeout: int = 25) -> None:
    element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))
    element.clear()
    element.send_keys(value)


def save_page_screenshot(driver, prefix: str) -> Path:
    path = SCREENSHOT_DIR / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    driver.save_screenshot(str(path))
    return path


def check_once(bot: Telegram) -> bool:
    driver = make_driver()
    try:
        print(f"[{now_text()}] Opening site...", flush=True)
        driver.get(URL)

        select_by_text_contains(driver, (By.NAME, "form"), PROVINCE)
        sleep_random()
        click_when_ready(driver, (By.ID, "btnAceptar"))

        select_by_text_contains(driver, (By.NAME, "sede"), OFFICE)
        sleep_random(1, 2)
        select_by_text_contains(driver, (By.NAME, "tramiteGrupo[0]"), PROCEDURE)
        sleep_random()
        driver.execute_script("envia()")

        sleep_random()
        driver.execute_script("document.forms[0].submit()")

        send_keys_when_ready(driver, (By.NAME, "txtIdCitado"), NIE)
        sleep_random(1, 2)
        send_keys_when_ready(driver, (By.NAME, "txtDesCitado"), FULL_NAME)
        sleep_random()
        driver.execute_script("envia()")

        sleep_random()
        driver.execute_script("enviar('solicitud')")
        sleep_random(4, 4)

        page_text = driver.find_element(By.TAG_NAME, "body").text
        screenshot = save_page_screenshot(driver, "check")

        no_slots_phrases = [
            "En este momento no hay citas disponibles",
            "no hay citas disponibles",
            "no existen citas disponibles",
        ]

        if any(phrase.lower() in page_text.lower() for phrase in no_slots_phrases):
            print(f"[{now_text()}] No appointment slots available.", flush=True)
            return False

        message = (
            "🚨 POSIBLE CITA ENCONTRADA\n\n"
            f"Provincia: {PROVINCE}\n"
            f"Oficina: {OFFICE}\n"
            f"Trámite: {PROCEDURE}\n"
            f"Hora: {now_text()}\n\n"
            "Revisa la web inmediatamente. Te envío captura."
        )
        bot.send_message(message)
        bot.send_photo(screenshot, "Captura de la posible cita")
        print(f"[{now_text()}] Possible appointment found!", flush=True)
        return True

    finally:
        driver.quit()


def main() -> None:
    bot = Telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    bot.send_message("✅ Cita monitor iniciado en Railway.")
    print(f"[{now_text()}] Monitor started.", flush=True)

    next_heartbeat = datetime.now() + timedelta(hours=HEARTBEAT_EVERY_HOURS)

    while True:
        try:
            found = check_once(bot)
            if found:
                time.sleep(300)

            if datetime.now() >= next_heartbeat:
                bot.send_message(f"✅ Monitor работает. Последняя проверка: {now_text()}")
                next_heartbeat = datetime.now() + timedelta(hours=HEARTBEAT_EVERY_HOURS)

        except TimeoutException as exc:
            print(f"[{now_text()}] Timeout error: {exc}", flush=True)
        except WebDriverException as exc:
            print(f"[{now_text()}] WebDriver error: {exc}", flush=True)
        except Exception as exc:
            print(f"[{now_text()}] Unexpected error: {exc}", flush=True)
            bot.send_message(f"⚠️ Ошибка монитора: {exc}")

        delay = CHECK_INTERVAL_SECONDS + random.randint(10, 45)
        print(f"[{now_text()}] Sleeping {delay} seconds...", flush=True)
        time.sleep(delay)


if __name__ == "__main__":
    main()
