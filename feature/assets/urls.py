from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    inventory_interface_page,
    inventory_overview_page,
    inventory_portal_page,
    inventory_dashboard_page,
    location_management_page,
    supplier_management_page,
    SupplierViewSet,
    StorageLocationViewSet,
    VaccineViewSet,
    StockImportViewSet,
    StockExportViewSet,
    StockAdjustmentViewSet,
    InventoryDashboardAPIView,
)

router = DefaultRouter()
router.register(r"suppliers", SupplierViewSet, basename="supplier")
router.register(r"locations", StorageLocationViewSet, basename="location")
router.register(r"vaccines", VaccineViewSet, basename="vaccine")
router.register(r"imports", StockImportViewSet, basename="stock-import")
router.register(r"exports", StockExportViewSet, basename="stock-export")
router.register(r"adjustments", StockAdjustmentViewSet, basename="stock-adjustment")

urlpatterns = [
    path("", inventory_dashboard_page, name="inventory-home-page"),
    path("interface/", inventory_interface_page, name="inventory-interface-page"),
    path("portal/", inventory_portal_page, name="inventory-portal-page"),
    path("overview/", inventory_overview_page, name="inventory-overview-page"),
    path("locations-page/", location_management_page, name="location-management-page"),
    path("suppliers-page/", supplier_management_page, name="supplier-management-page"),
    path("dashboard-page/", inventory_dashboard_page, name="inventory-dashboard-page"),
    path("dashboard/", InventoryDashboardAPIView.as_view(), name="inventory-dashboard"),
    path("", include(router.urls)),
]
