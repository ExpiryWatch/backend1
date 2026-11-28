"""Optional browser check: python -m tests.browser_smoke (requires Playwright Chromium)."""
import socket
import threading

import uvicorn
from playwright.sync_api import expect, sync_playwright

from app.main import app
from tests.test_integration import ApiTests


def main():
    fixture = ApiTests(methodName="runTest")
    fixture.setUp()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route('**/stats/', lambda route: route.fulfill(
                status=503, json={"detail": "Проверка повторной загрузки"}))
            page.goto(f"http://127.0.0.1:{port}/ui/")
            expect(page.locator('#stock-retry')).to_be_visible()
            expect(page.locator('#stock-loading')).not_to_be_visible()
            expect(page.locator('#stock-add')).to_be_disabled()
            page.unroute('**/stats/')
            page.locator('#stock-retry').click()
            expect(page.locator('#stock-add')).to_be_enabled()
            expect(page.locator('#stock-retry')).not_to_be_visible()
            expect(page.locator('#empty-stock')).to_be_visible()
            page.locator('#stock-add').click()
            expect(page.locator('[name="name"]')).to_be_focused()
            page.locator('[name="name"]').fill('Молоко интеграция')
            page.locator('[name="quantity"]').fill('0')
            page.locator('#stock-save').click()
            expect(page.locator('#error-quantity')).to_contain_text('больше нуля')
            page.locator('[name="quantity"]').fill('0.001')
            page.locator('#stock-save').click()
            expect(page.locator('#error-quantity')).to_contain_text('двух знаков')
            page.locator('[name="quantity"]').fill('100000000')
            page.locator('#stock-save').click()
            expect(page.locator('#error-quantity')).to_contain_text('99999999.99')
            page.locator('[name="quantity"]').fill('0.5')
            page.locator('[name="category_id"]').evaluate("select => select.add(new Option('Удалённая категория', '9999'))")
            page.locator('[name="category_id"]').select_option('9999')
            page.locator('#stock-save').click()
            expect(page.locator('#stock-form-error')).to_contain_text('Категория с ID 9999 не найдена')
            page.locator('[name="category_id"]').select_option('11')
            page.locator('[name="storage_location_id"]').select_option('21')
            page.locator('[name="purchase_date"]').fill('2027-01-01')
            page.locator('[name="expiry_date"]').fill('2026-12-31')
            page.locator('#stock-save').click()
            cards = page.locator('.product-card')
            expect(cards).to_have_count(1)
            expect(cards).to_contain_text('Скоро истекает')
            expect(cards).to_contain_text('Холодильник')
            page.reload()
            expect(cards).to_have_count(1)
            expect(cards).to_contain_text('0.5')
            page.locator('.products__search').fill('нет такого продукта')
            expect(page.locator('#empty-search')).to_be_visible()
            page.locator('.products__search').fill('МОЛОКО')
            expect(cards).to_have_count(1)
            page.locator('.products__category').select_option('11')
            page.locator('.products__location').select_option('21')
            page.locator('.products__filter').select_option('expiring_soon')
            page.locator('.products__sort').select_option('expiry')
            page.locator('.products__order').select_option('desc')
            expect(cards).to_have_count(1)
            cards.locator('.product-card__edit').click()
            expect(page.locator('[name="category_id"]')).to_have_value('11')
            expect(page.locator('[name="purchase_date"]')).to_have_value('2027-01-01')
            item_id = cards.get_attribute('data-id')
            item_url = f"http://127.0.0.1:{port}/inventory/{item_id}"
            external = page.request.patch(item_url, data={"comment": "Изменено другим запросом"})
            assert external.ok, external.text()
            page.locator('[name="purchase_date"]').fill('2027-02-01')
            name = 'Кефир <img src=x onerror=alert(1)> ' + 'ДлинноеНазвание' * 10
            page.locator('[name="name"]').fill(name)
            page.locator('[name="quantity"]').fill('1.25')
            patch_bodies = []
            def check_save(route):
                if route.request.method == 'PATCH':
                    assert page.locator('#stock-form').get_attribute('aria-busy') == 'true'
                    assert page.locator('#stock-form :is(input, select, textarea, button):enabled').count() == 0
                    assert page.locator('#stock-close').is_disabled()
                    assert page.locator('#stock-save').text_content() == 'Сохранение…'
                    patch_bodies.append(route.request.post_data_json)
                route.continue_()
            page.route('**/inventory/' + item_id, check_save)
            page.locator('#stock-save').click()
            expect(page.locator('#stock-panel')).not_to_be_visible()
            page.unroute('**/inventory/' + item_id, check_save)
            assert patch_bodies == [{"name": name, "quantity": 1.25, "purchase_date": "2027-02-01"}], patch_bodies
            assert page.request.get(item_url).json()['comment'] == 'Изменено другим запросом'
            page.locator('.products__search').fill('Кефир')
            expect(cards).to_contain_text(name)
            expect(cards.locator('img')).to_have_count(0)
            page.set_viewport_size({"width": 360, "height": 800})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile page overflows'
            assert cards.first.bounding_box()['width'] >= page.locator('.products__list').bounding_box()['width'] - 1, 'Mobile card does not fill the row'
            cards.locator('.product-card__edit').click()
            expect(page.locator('[name="purchase_date"]')).to_have_value('2027-02-01')
            expect(page.locator('[name="comment"]')).to_have_value('Изменено другим запросом')
            page.locator('[name="comment"]').fill('')
            page.locator('#stock-save').scroll_into_view_if_needed()
            expect(page.locator('#stock-save')).to_be_in_viewport()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile form overflows'
            page.screenshot(path=str(fixture.directory.name + '/mobile.png'), full_page=True)
            def reject_save(route):
                if route.request.method == 'PATCH':
                    route.fulfill(status=422, json={
                        "detail": "body.comment: Проверка ошибки поля",
                        "errors": [{"loc": ["body", "comment"], "msg": "Проверка ошибки поля"}]
                    })
                else:
                    route.continue_()
            page.route('**/inventory/' + item_id, reject_save)
            page.locator('#stock-save').click()
            expect(page.locator('#error-comment')).to_have_text('Проверка ошибки поля')
            expect(page.locator('[name="comment"]')).to_be_enabled()
            expect(page.locator('[name="comment"]')).to_be_focused()
            expect(page.locator('[name="comment"]')).to_have_value('')
            page.unroute('**/inventory/' + item_id, reject_save)
            with page.expect_request(lambda request: request.method == 'PATCH') as clear_request:
                page.locator('#stock-save').click()
            assert clear_request.value.post_data_json == {"comment": None}
            expect(page.locator('#stock-panel')).not_to_be_visible()
            assert page.request.get(item_url).json()['comment'] is None
            cards.locator('.product-card__delete').click()
            page.locator('#stock-delete-cancel').click()
            expect(cards).to_have_count(1)
            cards.locator('.product-card__delete').click()
            page.locator('#stock-delete-confirm').click()
            expect(page.locator('#empty-stock')).to_be_visible()
            expect(page.locator('[data-stat="total"]')).to_have_text('0')
            page.reload()
            expect(page.locator('#empty-stock')).to_be_visible()
            assert not errors, errors
            browser.close()
        print('Browser smoke passed: CRUD, validation, search, filters, reload, safe text and 360px layout.')
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        fixture.doCleanups()


if __name__ == "__main__":
    main()
