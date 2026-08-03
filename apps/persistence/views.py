from django.conf import settings
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.persistence.exceptions import (
    ActiveSceneDeleteError,
    BannerMaterialNotFoundError,
    DestinationNotFoundError,
    InvalidCountdownTargetError,
    OAuthStateError,
    PlatformConnectionNotFoundError,
    PlatformIntegrationError,
    SceneNotFoundError,
    TenantNotFoundError,
    TickerMaterialNotFoundError,
)
from apps.persistence.serializers import (
    CreateBannerMaterialSerializer,
    CreateDestinationSerializer,
    CreateSceneSerializer,
    CreateTickerMaterialSerializer,
    DestinationSerializer,
    SceneSerializer,
    TenantBootstrapSerializer,
    UpdateBannerMaterialSerializer,
    UpdateConfigurationSerializer,
    UpdateDestinationSerializer,
    UpdateSceneSerializer,
    UpdateTickerMaterialSerializer,
    PlatformConnectionEmbedImportSerializer,
    PlatformConnectionSerializer,
    TwitchAuthorizeQuerySerializer,
)
from apps.persistence.asset_service import AssetCatalogService
from apps.persistence.platform_connection_service import PlatformConnectionService
from apps.persistence.services import TenantService
from apps.persistence.text_material_service import TextMaterialService


def _tenant_service() -> TenantService:
    return TenantService()


def _text_material_service() -> TextMaterialService:
    return TextMaterialService()


def _platform_connection_service() -> PlatformConnectionService:
    return PlatformConnectionService()


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


class TenantAssetCatalogView(APIView):
    """List studio media assets available to a tenant (system defaults + tenant uploads)."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, tenant_id):
        try:
            catalog = AssetCatalogService().build_asset_catalog(tenant_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(catalog)


class TenantTextMaterialCatalogView(APIView):
    """List banner and ticker materials available to a tenant."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, tenant_id):
        try:
            catalog = _text_material_service().build_text_material_catalog(tenant_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(catalog)


class TenantBannerMaterialListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, tenant_id):
        try:
            banners = _text_material_service().list_banners_for_tenant(tenant_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            [
                _text_material_service().serialize_banner_material(banner)
                for banner in banners
            ]
        )

    def post(self, request, tenant_id):
        serializer = CreateBannerMaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            banner = _text_material_service().create_banner_material(
                tenant_id,
                label=data.get('label', ''),
                title=data['title'],
                description=data.get('description', ''),
                theme=data.get('theme', 'classic'),
                primary=data.get('primary', '#111111'),
                secondary=data.get('secondary', '#374151'),
                accent=data.get('accent', '#38bdf8'),
                font_size=data.get('font_size', 32),
                is_display_names=data.get('is_display_names', True),
            )
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            _text_material_service().serialize_banner_material(banner),
            status=status.HTTP_201_CREATED,
        )


class TenantBannerMaterialDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, tenant_id, banner_id):
        serializer = UpdateBannerMaterialSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            banner = _text_material_service().update_banner_material(
                tenant_id,
                banner_id,
                **serializer.validated_data,
            )
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except BannerMaterialNotFoundError:
            return Response(
                {'detail': 'Banner material not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(_text_material_service().serialize_banner_material(banner))

    def delete(self, request, tenant_id, banner_id):
        try:
            _text_material_service().delete_banner_material(tenant_id, banner_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except BannerMaterialNotFoundError:
            return Response(
                {'detail': 'Banner material not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class TenantTickerMaterialListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, tenant_id):
        try:
            tickers = _text_material_service().list_tickers_for_tenant(tenant_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            [
                _text_material_service().serialize_ticker_material(ticker)
                for ticker in tickers
            ]
        )

    def post(self, request, tenant_id):
        serializer = CreateTickerMaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            ticker = _text_material_service().create_ticker_material(
                tenant_id,
                label=data.get('label', ''),
                ticker_text=data['ticker_text'],
                ticker_position=data.get('ticker_position', 'bottom'),
                ticker_direction=data.get('ticker_direction', 'rtl'),
                ticker_speed=data.get('ticker_speed', 2.0),
                primary=data.get('primary', '#111827'),
                secondary=data.get('secondary', '#ffffff'),
            )
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            _text_material_service().serialize_ticker_material(ticker),
            status=status.HTTP_201_CREATED,
        )


class TenantTickerMaterialDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, tenant_id, ticker_id):
        serializer = UpdateTickerMaterialSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            ticker = _text_material_service().update_ticker_material(
                tenant_id,
                ticker_id,
                **serializer.validated_data,
            )
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except TickerMaterialNotFoundError:
            return Response(
                {'detail': 'Ticker material not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(_text_material_service().serialize_ticker_material(ticker))

    def delete(self, request, tenant_id, ticker_id):
        try:
            _text_material_service().delete_ticker_material(tenant_id, ticker_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except TickerMaterialNotFoundError:
            return Response(
                {'detail': 'Ticker material not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class TenantPlatformConnectionListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, tenant_id):
        try:
            connections = _platform_connection_service().list_connections(tenant_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(PlatformConnectionSerializer(connections, many=True).data)


class TenantPlatformConnectionDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def delete(self, request, tenant_id, connection_id):
        try:
            _platform_connection_service().delete_connection(tenant_id, connection_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except PlatformConnectionNotFoundError:
            return Response(
                {'detail': 'Platform connection not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class TenantPlatformConnectionDisconnectView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, tenant_id, connection_id):
        try:
            connection = _platform_connection_service().disconnect_connection(
                tenant_id,
                connection_id,
            )
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except PlatformConnectionNotFoundError:
            return Response(
                {'detail': 'Platform connection not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(PlatformConnectionSerializer(connection).data)


class TenantPlatformConnectionRefreshView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, tenant_id, connection_id):
        try:
            connection = _platform_connection_service().refresh_twitch_stream_key(
                tenant_id,
                connection_id,
            )
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except PlatformConnectionNotFoundError:
            return Response(
                {'detail': 'Platform connection not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PlatformIntegrationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PlatformConnectionSerializer(connection).data)


class TenantPlatformConnectionImportView(APIView):
    """Import OAuth credentials from CMS embed postMessage (studio-frontend persists on behalf of parent)."""

    authentication_classes = []
    permission_classes = []

    def post(self, request, tenant_id):
        serializer = PlatformConnectionEmbedImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            connection = _platform_connection_service().import_platform_connection_from_embed(
                tenant_id,
                data['platform'],
                name=data['name'],
                platform_login=data['platform_login'],
                platform_user_id=data.get('platform_user_id') or '',
                access_token=data.get('access_token') or '',
                refresh_token=data.get('refresh_token') or '',
                stream_key=data.get('stream_key') or '',
                rtmp_url=data.get('rtmp_url') or '',
                token_expires_at=data.get('token_expires_at'),
                metadata=data.get('metadata') or {},
            )
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except PlatformIntegrationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PlatformConnectionSerializer(connection).data, status=status.HTTP_200_OK)


class TwitchChatCredentialsView(APIView):
    """Internal endpoint for compositor to fetch Twitch IRC credentials."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, tenant_id):
        try:
            credentials = _platform_connection_service().get_twitch_chat_credentials(tenant_id)
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except PlatformConnectionNotFoundError:
            return Response(
                {'detail': 'Twitch connection not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PlatformIntegrationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(credentials)


class TwitchAuthorizeView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        serializer = TwitchAuthorizeQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            authorize_url = _platform_connection_service().build_twitch_authorize_url(
                data['tenant_id'],
                return_url=data.get('return_url') or '',
            )
        except TenantNotFoundError:
            return Response({'detail': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)
        except PlatformIntegrationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({'authorize_url': authorize_url})


class TwitchOAuthCallbackView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        error = request.query_params.get('error')
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')

        if error:
            description = request.query_params.get('error_description', error)
            return redirect(f'{frontend_url}?twitch=error&message={description}')

        code = request.query_params.get('code')
        state = request.query_params.get('state')
        if not code or not state:
            return redirect(f'{frontend_url}?twitch=error&message=Missing+OAuth+parameters')

        try:
            connection, return_url = _platform_connection_service().complete_twitch_oauth(
                code=code,
                state=state,
            )
        except OAuthStateError as exc:
            return redirect(f'{frontend_url}?twitch=error&message={exc}')
        except PlatformIntegrationError as exc:
            return redirect(f'{frontend_url}?twitch=error&message={exc}')

        target = return_url or frontend_url
        separator = '&' if '?' in target else '?'
        return redirect(
            f'{target}{separator}twitch=connected&connection_id={connection.id}&platform=twitch',
        )
