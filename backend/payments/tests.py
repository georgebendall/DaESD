from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import ProducerProfile, User
from orders.models import Order

from .models import PaymentTransaction, WeeklySettlement


class ProducerSettlementPageTests(TestCase):
    def setUp(self):
        self.producer = User.objects.create_user(
            username="settlementproducer",
            email="settlementproducer@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(
            user=self.producer,
            business_name="Settlement Farm",
            postcode="BS1 4DJ",
        )
        self.customer = User.objects.create_user(
            username="settlementcustomer",
            email="settlementcustomer@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        WeeklySettlement.objects.create(
            producer=self.producer,
            period_start=date(2026, 4, 21),
            period_end=date(2026, 4, 28),
            gross_sales=Decimal("250.00"),
            commission_total=Decimal("25.00"),
            payout_total=Decimal("225.00"),
            status=WeeklySettlement.Status.DRAFT,
        )
        WeeklySettlement.objects.create(
            producer=self.producer,
            period_start=date(2026, 4, 14),
            period_end=date(2026, 4, 20),
            gross_sales=Decimal("120.00"),
            commission_total=Decimal("12.00"),
            payout_total=Decimal("108.00"),
            status=WeeklySettlement.Status.PAID,
        )

    def test_producer_can_view_weekly_settlements_page(self):
        self.client.force_login(self.producer)
        response = self.client.get(reverse("producer_settlements"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Weekly Payment Settlements")
        self.assertContains(response, "Settlement Farm")
        self.assertContains(response, "250.00")
        self.assertContains(response, "225.00")
        self.assertContains(response, "370.00")
        self.assertContains(response, "333.00")
        self.assertContains(response, "Draft")
        self.assertContains(response, "Paid")

    def test_non_producer_is_redirected_away_from_settlements_page(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("producer_settlements"))

        self.assertRedirects(
            response,
            reverse("after_login"),
            fetch_redirect_response=False,
        )

    def test_producer_dashboard_shows_latest_settlement_summary(self):
        self.client.force_login(self.producer)
        response = self.client.get(reverse("producer_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Weekly Payment Settlement")
        self.assertContains(response, "April 21, 2026 to April 28, 2026")
        self.assertContains(response, "225.00")


class AdminFinanceReportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="adminfinance",
            email="adminfinance@example.com",
            password="StrongPass123!",
        )
        self.producer = User.objects.create_user(
            username="financeproducer",
            email="financeproducer@example.com",
            password="StrongPass123!",
            role=User.Role.PRODUCER,
        )
        ProducerProfile.objects.create(
            user=self.producer,
            business_name="Finance Farm",
            postcode="BS1 2AB",
        )
        self.customer = User.objects.create_user(
            username="financecustomer",
            email="financecustomer@example.com",
            password="StrongPass123!",
            role=User.Role.CUSTOMER,
        )
        self.order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.PAID,
            subtotal=Decimal("100.00"),
            commission_total=Decimal("10.00"),
            total=Decimal("110.00"),
        )
        PaymentTransaction.objects.create(
            order=self.order,
            status=PaymentTransaction.Status.SUCCEEDED,
            provider="manual",
            amount=Decimal("110.00"),
            currency="GBP",
            provider_reference="demo-finance-001",
        )
        WeeklySettlement.objects.create(
            producer=self.producer,
            period_start=date(2026, 4, 21),
            period_end=date(2026, 4, 28),
            gross_sales=Decimal("100.00"),
            commission_total=Decimal("10.00"),
            payout_total=Decimal("90.00"),
            status=WeeklySettlement.Status.FINAL,
        )

    def test_admin_can_view_finance_report(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_finance_report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commission Monitoring Report")
        self.assertContains(response, "Finance Farm")
        self.assertContains(response, "100.00")
        self.assertContains(response, "10.00")
        self.assertContains(response, "90.00")
        self.assertContains(response, "demo-finance-001")

    def test_non_admin_cannot_view_finance_report(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("admin_finance_report"))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_download_finance_report_csv(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"{reverse('admin_finance_report')}?format=csv")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("brfn-commission-report.csv", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("Producer,Period Start,Period End,Gross Sales,Commission,Payout,Status", content)
        self.assertIn("Finance Farm,2026-04-21,2026-04-28,100.00,10.00,90.00,Final", content)
