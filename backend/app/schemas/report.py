from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    todays_sales: Decimal
    todays_collections: Decimal
    total_outstanding_amount: Decimal
    partially_paid_invoice_amount: Decimal
    fully_unpaid_invoice_amount: Decimal
    customer_advances: Decimal
    total_customers: int
    todays_orders: int
    monthly_revenue: Decimal
    top_selling_materials: list[dict]
    recent_invoices: list[dict]
    recent_payments: list[dict]


class AgeingBucket(BaseModel):
    customer_id: int
    customer_name: str
    bucket_0_30: Decimal
    bucket_31_60: Decimal
    bucket_61_90: Decimal
    bucket_91_180: Decimal
    bucket_over_180: Decimal
    total: Decimal


class ReportFilter(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    customer_id: int | None = None


class AnalyticsTrendPoint(BaseModel):
    date: date
    sales: Decimal
    collections: Decimal
    invoice_count: int
    new_customers: int
    outstanding: Decimal


class AnalyticsSummary(BaseModel):
    total_sales: Decimal
    total_collections: Decimal
    invoice_count: int
    new_customers: int
    customers_served: int
    current_outstanding: Decimal


class AnalyticsMaterial(BaseModel):
    material: str
    unit: str
    quantity: Decimal
    sales: Decimal


class AnalyticsReport(BaseModel):
    start_date: date
    end_date: date
    summary: AnalyticsSummary
    daily: list[AnalyticsTrendPoint]
    top_materials: list[AnalyticsMaterial]
