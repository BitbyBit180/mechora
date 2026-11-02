import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.roles import assign_user_role

from .models import Product


class ProductPermissionTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user("product-admin", password="StrongPass123!")
        assign_user_role(self.admin, "Admin")
        self.engineer = get_user_model().objects.create_user("product-engineer", password="StrongPass123!")
        assign_user_role(self.engineer, "Engineer")

    def test_seed_product_exists(self):
        self.assertTrue(Product.objects.filter(product_code="P-PLATE01", is_active=True).exists())

    def test_only_admin_can_create_product(self):
        self.client.force_login(self.engineer)
        response = self.client.post("/api/products/", data=json.dumps({"product_code": "P-NEW", "name": "New plate"}), content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.post("/api/products/", data=json.dumps({"product_code": "P-NEW", "name": "New plate"}), content_type="application/json")
        self.assertEqual(response.status_code, 201)
