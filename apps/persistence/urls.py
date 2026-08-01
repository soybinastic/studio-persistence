from django.urls import path

from apps.persistence.views import (
    TenantBootstrapView,
    TenantConfigurationView,
    TenantDestinationDetailView,
    TenantDestinationListCreateView,
    TenantSceneDetailView,
    TenantSceneListCreateView,
)

urlpatterns = [
    path('tenant', TenantBootstrapView.as_view(), name='tenant-bootstrap'),
    path(
        'tenant/<uuid:tenant_id>/configuration/',
        TenantConfigurationView.as_view(),
        name='tenant-configuration',
    ),
    path(
        'tenant/<uuid:tenant_id>/scenes/',
        TenantSceneListCreateView.as_view(),
        name='tenant-scenes',
    ),
    path(
        'tenant/<uuid:tenant_id>/scenes/<uuid:scene_id>/',
        TenantSceneDetailView.as_view(),
        name='tenant-scene-detail',
    ),
    path(
        'tenant/<uuid:tenant_id>/destinations/',
        TenantDestinationListCreateView.as_view(),
        name='tenant-destinations',
    ),
    path(
        'tenant/<uuid:tenant_id>/destinations/<uuid:destination_id>/',
        TenantDestinationDetailView.as_view(),
        name='tenant-destination-detail',
    ),
]
