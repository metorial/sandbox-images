from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(args=['--disable-dev-shm-usage'])
    try:
        page = browser.new_page()
        page.set_content('<title>Sandbox Browser</title><h1>Ready</h1>')
        assert page.title() == 'Sandbox Browser'
        page.screenshot(path='/tmp/browser.png')
        print('Chromium launched, rendered HTML and captured a screenshot')
    finally:
        browser.close()
