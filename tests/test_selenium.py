"""
Selenium test suite for Task Manager (multi-page app).

Run:
    pip install -r tests/requirements.txt
    APP_URL=http://<load-balancer-dns-or-ec2-ip> python tests/test_selenium.py

Optional: HEADLESS=0 to watch the browser.
"""
import os
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

APP_URL = os.getenv("APP_URL", "http://localhost").rstrip("/")
HEADLESS = os.getenv("HEADLESS", "1") == "1"

STAMP = int(time.time())
USERNAME = f"user{STAMP}"
EMAIL = f"user{STAMP}@example.com"
PASSWORD = "secret123"
TASK_TITLE = f"Selenium task {STAMP}"


def make_driver():
    opts = Options()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,900")
    return webdriver.Chrome(options=opts)


driver = make_driver()
wait = WebDriverWait(driver, 10)


def open_page(path):
    driver.get(APP_URL + path)


def page_title_text():
    return wait.until(EC.presence_of_element_located((By.ID, "page-title"))).text


def type_into(element_id, text):
    el = wait.until(EC.presence_of_element_located((By.ID, element_id)))
    el.clear()
    el.send_keys(text)


def click(element_id):
    wait.until(EC.element_to_be_clickable((By.ID, element_id))).click()


def flash_text():
    return wait.until(EC.presence_of_element_located((By.CLASS_NAME, "flash"))).text


def login(username, password):
    open_page("/login")
    type_into("login-username", username)
    type_into("login-password", password)
    click("login-submit")


# ------------------------------------------------------------------ tests
def test_home_page():
    open_page("/")
    hero = wait.until(EC.presence_of_element_located((By.ID, "hero-title"))).text
    assert "Organise your work" in hero, f"Unexpected hero text: {hero}"
    assert "Task Manager" in driver.title, f"Unexpected title: {driver.title}"


def test_register():
    open_page("/register")
    type_into("reg-username", USERNAME)
    type_into("reg-email", EMAIL)
    type_into("reg-password", PASSWORD)
    type_into("reg-confirm", PASSWORD)
    click("reg-submit")
    assert "Registration successful" in flash_text()
    assert page_title_text() == "Login"


def test_login_wrong_password():
    login(USERNAME, "wrong-password")
    assert "Invalid username or password" in flash_text()


def test_login_success():
    login(USERNAME, PASSWORD)
    assert page_title_text() == "Dashboard"
    assert USERNAME in driver.find_element(By.ID, "nav-user").text


def test_create_task():
    click("nav-new")
    assert page_title_text() == "New Task"
    type_into("task-title", TASK_TITLE)
    type_into("task-description", "Created by the Selenium test")
    Select(driver.find_element(By.ID, "task-priority")).select_by_value("high")
    click("task-submit")
    assert page_title_text() == "My Tasks"
    titles = [e.text for e in driver.find_elements(By.CLASS_NAME, "task-title")]
    assert TASK_TITLE in titles, f"Task not in list: {titles}"


def test_search_task():
    type_into("search-q", TASK_TITLE)
    click("filter-btn")
    rows = driver.find_elements(By.CLASS_NAME, "task-row")
    assert len(rows) == 1, f"Expected 1 row, found {len(rows)}"


def test_mark_done_and_dashboard():
    driver.find_element(By.CLASS_NAME, "toggle-btn").click()
    assert "marked as done" in flash_text()
    status = driver.find_element(By.CLASS_NAME, "task-status").text
    assert status == "Done", f"Status is {status}"
    click("nav-dashboard")
    assert page_title_text() == "Dashboard"
    assert driver.find_element(By.ID, "stat-total").text == "1"
    assert driver.find_element(By.ID, "stat-done").text == "1"


def test_logout():
    click("logout-btn")
    assert page_title_text() == "Login"
    assert "logged out" in flash_text()


TESTS = [
    test_home_page,
    test_register,
    test_login_wrong_password,
    test_login_success,
    test_create_task,
    test_search_task,
    test_mark_done_and_dashboard,
    test_logout,
]


def main():
    passed = 0
    print(f"Testing {APP_URL}\n")
    try:
        for test in TESTS:
            try:
                test()
                print(f"PASS  {test.__name__}")
                passed += 1
            except Exception as err:  # noqa: BLE001
                print(f"FAIL  {test.__name__}: {err}")
    finally:
        driver.quit()
    print(f"\nResult: {passed}/{len(TESTS)} tests passed")
    sys.exit(0 if passed == len(TESTS) else 1)


if __name__ == "__main__":
    main()
