import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker

from app.database import Base, make_engine
from app.main import app
from app.models import Category, StorageLocation, calc_days_left, calc_status
from app.schemas.inventory import InventoryCreate, InventoryPatch
from app.seed import seed_bulk


class RulesTests(unittest.TestCase):
    def test_expiry_boundaries_and_day_change(self):
        today = date(2026, 12, 31)
        for days, expected in [(-1, "expired"), (0, "expiring_soon"), (1, "expiring_soon"),
                               (3, "expiring_soon"), (4, "fresh")]:
            expiry = today + timedelta(days=days)
            with self.subTest(days=days):
                self.assertEqual(calc_days_left(expiry, today), days)
                self.assertEqual(calc_status(expiry, today), expected)
        self.assertIsNone(calc_days_left(None, today))
        self.assertEqual(calc_status(None, today), "no_date")
        self.assertEqual(calc_status(today + timedelta(days=4), today + timedelta(days=1)), "expiring_soon")
        self.assertEqual(calc_days_left(date(2024, 3, 1), date(2024, 2, 28)), 2)

    def test_strict_input_and_null_patch(self):
        for changes in [{"quantity": float("nan")}, {"quantity": float("inf")},
                        {"quantity": True}, {"quantity": "2"}, {"quantity": 0.001},
                        {"quantity": 100000000}, {"name": " "}, {"unit": " "},
                        {"purchase_date": 0}, {"expiry_date": "2026-11-20T00:00:00"},
                        {"category_id": True}, {"storage_location_id": -1}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                InventoryCreate.model_validate({"name": "Молоко", "quantity": 2} | changes)
        for field in ("name", "quantity", "unit"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                InventoryPatch(**{field: None})
        self.assertEqual(InventoryPatch().model_dump(exclude_unset=True), {})


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.url = f"sqlite:///{(Path(self.directory.name) / 'test.db').as_posix()}"
        self.engine = make_engine(self.url)
        self.addCleanup(lambda: self.engine.dispose())
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.enterContext(patch("app.database.SessionLocal", side_effect=lambda: self.factory()))
        self.today = date(2026, 12, 31)
        self.clock = self.enterContext(patch("app.models.stock_item.date"))
        self.clock.today.return_value = self.today
        self.client = self.enterContext(TestClient(app))
        with self.factory() as db:
            db.add_all([Category(id=11, name="Молочные"), StorageLocation(id=21, name="Холодильник")])
            db.commit()

    def create(self, **changes):
        response = self.client.post("/inventory/", json={
            "name": "Молоко", "quantity": 2, "unit": "л", "category_id": 11,
            "storage_location_id": 21, "purchase_date": "2026-12-01", "expiry_date": "2026-12-31",
        } | changes)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def assert_invalid(self, response):
        self.assertEqual(response.status_code, 422, response.text)
        detail = response.json()["detail"]
        self.assertIsInstance(detail, str)
        self.assertTrue(detail)
        self.assertNotIn("Некорректное значение", detail)

    def test_create_patch_put_delete_and_restart(self):
        first, other = self.create(name=" Молоко "), self.create(name="Хлеб")
        self.assertEqual(first["name"], "Молоко")
        url = f"/inventory/{first['id']}"
        self.assertEqual(self.client.patch(url, json={}).json(), first)
        changed = self.client.patch(url, json={"quantity": 0.5, "expiry_date": None}).json()
        self.assertEqual(changed["status"], "no_date")
        self.assertIsNone(changed["days_left"])
        self.assertEqual(changed["purchase_date"], first["purchase_date"])
        cleared = self.client.patch(url, json={"category_id": None, "storage_location_id": None,
                                               "purchase_date": None, "comment": None})
        self.assertEqual(cleared.status_code, 200, cleared.text)
        changed = cleared.json()
        self.assertTrue(all(changed[key] is None for key in
                            ("category_id", "storage_location_id", "purchase_date", "comment", "expiry_date")))
        self.engine.dispose()
        self.engine = make_engine(self.url)
        self.factory.configure(bind=self.engine)
        with TestClient(app) as restarted:
            self.assertEqual(restarted.get(url).json()["quantity"], 0.5)
            body = {key: changed[key] for key in InventoryCreate.model_fields}
            body.update(name="Кефир", purchase_date="2026-12-01", expiry_date="2026-12-01")
            replaced = restarted.put(url, json=body)
            self.assertEqual(replaced.status_code, 200, replaced.text)
            self.assertEqual(replaced.json()["status"], "expired")
            self.assertEqual(restarted.delete(url).json(), {"id": first["id"]})
            self.assertEqual(restarted.get(url).status_code, 404)
        self.assertEqual(self.client.get(f"/inventory/{other['id']}").json(), other)

    def test_invalid_create_and_update_preserve_all_data(self):
        first, other = self.create(), self.create(name="Хлеб")
        url = f"/inventory/{first['id']}"
        invalid = [{"name": " "}, {"quantity": 0}, {"quantity": -1}, {"quantity": "2"},
                   {"quantity": True}, {"quantity": 0.001}, {"quantity": 100000000},
                   {"quantity": None}, {"unit": None},
                   {"unit": " "}, {"name": None}, {"category_id": 9999},
                   {"storage_location_id": 9999}, {"category_id": True},
                   {"purchase_date": "2027-01-01"}, {"expiry_date": "2026-11-30"},
                   {"expiry_date": "2026-02-30"}, {"purchase_date": 0},
                   {"expiry_date": "2026-12-31T00:00:00"}, {"status": "fresh"},
                   {"storage_id": 21}, {"expiration_date": "2026-12-31"}]
        original = {key: first[key] for key in InventoryCreate.model_fields}
        for changes in invalid:
            with self.subTest(changes=changes):
                self.assert_invalid(self.client.post("/inventory/", json=original | changes))
                self.assert_invalid(self.client.patch(url, json=changes))
                self.assert_invalid(self.client.put(url, json=original | changes))
                self.assertEqual(self.client.get(url).json(), first)
                self.assertEqual(self.client.get(f"/inventory/{other['id']}").json(), other)
        self.assert_invalid(self.client.put(url, json={"name": "Кефир", "quantity": 1}))
        self.assertEqual(len(self.client.get("/inventory/").json()), 2)

    def test_errors_are_russian_and_located(self):
        for body in [{}, {"name": "Молоко"}, {"quantity": 2}, {"name": "Молоко", "quantity": 0}]:
            response = self.client.post("/inventory/", json=body)
            self.assert_invalid(response)
            error = response.json()["errors"][0]
            self.assertEqual(error["loc"][0], "body")
            self.assertRegex(error["msg"], "[А-Яа-я]")
        self.assert_invalid(self.client.post("/inventory/", content="{", headers={"Content-Type": "application/json"}))
        self.assert_invalid(self.client.post("/inventory/", json=[]))
        for token in ("NaN", "Infinity", "-Infinity"):
            self.assert_invalid(self.client.post("/inventory/", content='{"name":"X","quantity":' + token + '}',
                                                 headers={"Content-Type": "application/json"}))
        self.assert_invalid(self.client.get("/inventory/?status=unknown"))
        self.assert_invalid(self.client.get("/inventory/?limit=0"))
        self.assert_invalid(self.client.get("/inventory/abc"))
        for method in (self.client.get, self.client.delete):
            self.assertEqual(method("/inventory/999").status_code, 404)
        self.assertEqual(self.client.patch("/inventory/999", json={"quantity": 1}).status_code, 404)

    def test_expiry_read_filter_stats_and_day_change(self):
        for days, expected in [(-1, "expired"), (0, "expiring_soon"), (3, "expiring_soon"), (4, "fresh"), (None, "no_date")]:
            expiry = (self.today + timedelta(days=days)).isoformat() if days is not None else None
            item = self.create(expiry_date=expiry)
            self.assertEqual((item["days_left"], item["status"]), (days, expected))
            read = self.client.get(f"/inventory/{item['id']}").json()
            self.assertEqual((read["days_left"], read["status"]), (days, expected))
        stats = self.client.get("/stats/").json()
        self.assertEqual(stats, {"total": 5, "fresh": 1, "expiring_soon": 2, "expired": 1, "no_date": 1})
        for status in ("fresh", "expiring_soon", "expired", "no_date"):
            items = self.client.get("/inventory/", params={"status": status}).json()
            self.assertEqual(len(items), stats[status])
            self.assertTrue(all(item["status"] == status for item in items))
        self.clock.today.return_value = self.today + timedelta(days=1)
        self.assertEqual(self.client.get("/stats/").json()["fresh"], 0)
        self.assertEqual(self.client.get("/stats/").json()["expired"], 2)

    def test_shared_search_filters_sort_and_references(self):
        for name, days, category_id in [("Яблоки", 4, None), ("Мёд", None, 11), ("молоко", 0, 11), ("Молоко кокосовое", 3, None)]:
            self.create(name=name, category_id=category_id,
                        expiry_date=(self.today + timedelta(days=days)).isoformat() if days is not None else None)
        def names(**params):
            response = self.client.get("/inventory/", params=params)
            self.assertEqual(response.status_code, 200)
            return [item["name"] for item in response.json()]
        self.assertEqual(names(q="МОЛ", category_id=11, storage_location_id=21, status="expiring_soon"), ["молоко"])
        self.assertEqual(names(q="мед"), ["Мёд"])
        self.assertEqual(names(sort="name"), ["Мёд", "молоко", "Молоко кокосовое", "Яблоки"])
        self.assertEqual(names(sort="expiry"), ["молоко", "Молоко кокосовое", "Яблоки", "Мёд"])
        self.assertEqual(names(sort="expiry", order="desc"), ["Яблоки", "Молоко кокосовое", "молоко", "Мёд"])
        self.assertEqual(names(limit=1, offset=1), ["молоко"])
        self.assertEqual(names(q="нет такого продукта"), [])
        self.assertEqual(self.client.get("/categories/").json(), [{"id": 11, "name": "Молочные", "items_count": 2}])
        self.assertEqual(self.client.get("/storage-locations/").json()[0]["items_count"], 4)

    def test_parallel_patches_preserve_changes_and_date_order(self):
        item = self.create(expiry_date="2027-01-10")
        url = f"/inventory/{item['id']}"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda body: self.client.patch(url, json=body), [{"quantity": 0.5}, {"name": "Кефир"}]))
        self.assertEqual([r.status_code for r in results], [200, 200])
        changed = self.client.get(url).json()
        self.assertEqual((changed["name"], changed["quantity"]), ("Кефир", 0.5))
        # Каждая дата допустима относительно исходной записи, вместе они несовместимы.
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda body: self.client.patch(url, json=body),
                                    [{"purchase_date": "2027-01-05"}, {"expiry_date": "2026-12-20"}]))
        self.assertEqual(sorted(r.status_code for r in results), [200, 422])
        changed = self.client.get(url).json()
        self.assertLessEqual(changed["purchase_date"], changed["expiry_date"])

    def test_1000_items_search_filter_sort_and_stats_under_two_seconds(self):
        with self.factory() as db:
            seed_bulk(db, 1000, today=self.today)
            db.commit()
        for params in [{}, {"q": "ПРОДУКТ", "status": "fresh", "sort": "expiry", "order": "desc"}]:
            start = time.perf_counter()
            response = self.client.get("/inventory/", params=params)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertLess(time.perf_counter() - start, 2)
        self.assertEqual(len(self.client.get("/inventory/").json()), 1000)
        self.assertEqual(self.client.get("/stats/").json()["total"], 1000)

    def test_frontend_and_existing_api_are_served(self):
        self.assertEqual(self.client.get("/").json(), {"message": "Backend is running"})
        response = self.client.get("/ui/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="stock-form"', response.text)
        for path in ("script.js", "stock-form.js", "style.css", "stock-form.css"):
            self.assertEqual(self.client.get("/ui/" + path).status_code, 200)
        self.assertEqual(self.client.get("/openapi.json").status_code, 200)


if __name__ == "__main__":
    unittest.main()
