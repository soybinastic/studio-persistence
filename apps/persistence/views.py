from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.persistence.exceptions import (
    ActiveSceneDeleteError,
    DestinationNotFoundError,
    InvalidCountdownTargetError,
    SceneNotFoundError,
    TenantNotFoundError,
)
from apps.persistence.serializers import (
    CreateDestinationSerializer,
    CreateSceneSerializer,
    DestinationSerializer,
    SceneSerializer,
    TenantBootstrapSerializer,
    UpdateConfigurationSerializer,
    UpdateDestinationSerializer,
    UpdateSceneSerializer,
)
from apps.persistence.services import TenantService


def _tenant_service() -> TenantService:
    return TenantService()


def _serialize_scene(scene, tenant) -> dict:
    active_scene_id = tenant.configuration.active_scene_id
    return SceneSerializer(
        scene,
        context={'active_scene_id': active_scene_id},
    ).data


class TenantBootstrapView(APIView):
    """Get or create a tenant and return its full persisted configuration."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = TenantBootstrapSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = _tenant_service()
        tenant, created = service.get_or_create_tenant(
            tenant_id=data['tenant_id'],
            tenant_name=data['tenant_name'],
        )
        tenant = service.get_tenant(tenant.id)

        return Response(
            {
                'tenant_id': str(tenant.id),
                'tenant_name': tenant.name,
                'created': created,
                'configuration': service.build_configuration_payload(tenant),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class TenantConfigurationView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, tenant_id):
        try:
            tenant = _tenant_service().get_tenant(tenant_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(_tenant_service().build_configuration_payload(tenant))

    def patch(self, request, tenant_id):
        serializer = UpdateConfigurationSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            _tenant_service().update_configuration(
                tenant_id,
                layout=data.get('layout'),
                tile_order_config=data.get('tile_order_config'),
                devices=data.get('devices'),
                graphics_config=data.get('graphics_config'),
                active_scene_id=data.get('active_scene_id', ...),
            )
            tenant = _tenant_service().get_tenant(tenant_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except SceneNotFoundError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(_tenant_service().build_configuration_payload(tenant))


class TenantSceneListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, tenant_id):
        try:
            tenant = _tenant_service().get_tenant(tenant_id)
            scenes = _tenant_service().list_scenes(tenant_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            SceneSerializer(
                scenes,
                many=True,
                context={'active_scene_id': tenant.configuration.active_scene_id},
            ).data
        )

    def post(self, request, tenant_id):
        serializer = CreateSceneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            scene = _tenant_service().create_scene(
                tenant_id,
                scene_type=data['type'],
                name=data.get('name'),
                devices=data.get('devices'),
                layout=data.get('layout'),
                graphics_config=data.get('graphics_config'),
                duration_seconds=data.get('duration_seconds'),
                target_scene_id=data.get('target_scene_id'),
            )
            tenant = _tenant_service().get_tenant(tenant_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except InvalidCountdownTargetError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            _serialize_scene(scene, tenant),
            status=status.HTTP_201_CREATED,
        )


class TenantSceneDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, tenant_id, scene_id):
        serializer = UpdateSceneSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            tenant = _tenant_service().get_tenant(tenant_id)
            scene = _tenant_service().update_scene(
                tenant_id,
                scene_id,
                name=data.get('name'),
                layout=data.get('layout'),
                graphics_config=data.get('graphics_config'),
                devices=data.get('devices'),
                sources=data.get('sources'),
                background_music=data.get('background_music'),
                sort_order=data.get('sort_order'),
            )
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except SceneNotFoundError:
            return Response({'detail': 'Scene not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(_serialize_scene(scene, tenant))

    def delete(self, request, tenant_id, scene_id):
        try:
            _tenant_service().delete_scene(tenant_id, scene_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except SceneNotFoundError:
            return Response({'detail': 'Scene not found'}, status=status.HTTP_404_NOT_FOUND)
        except ActiveSceneDeleteError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except InvalidCountdownTargetError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(status=status.HTTP_204_NO_CONTENT)


class TenantDestinationListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, tenant_id):
        try:
            destinations = _tenant_service().list_destinations(tenant_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(DestinationSerializer(destinations, many=True).data)

    def post(self, request, tenant_id):
        serializer = CreateDestinationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            destination = _tenant_service().create_destination(
                tenant_id,
                url=data['url'],
                label=data.get('label', ''),
                platform=data.get('platform', ''),
            )
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            DestinationSerializer(destination).data,
            status=status.HTTP_201_CREATED,
        )


class TenantDestinationDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, tenant_id, destination_id):
        serializer = UpdateDestinationSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            destination = _tenant_service().update_destination(
                tenant_id,
                destination_id,
                url=data.get('url'),
                label=data.get('label'),
                platform=data.get('platform'),
                sort_order=data.get('sort_order'),
            )
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except DestinationNotFoundError:
            return Response(
                {'detail': 'Destination not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(DestinationSerializer(destination).data)

    def delete(self, request, tenant_id, destination_id):
        try:
            _tenant_service().delete_destination(tenant_id, destination_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except DestinationNotFoundError:
            return Response(
                {'detail': 'Destination not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
