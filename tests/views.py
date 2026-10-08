from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.views import View
from rest_framework import generics, serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, BasePermission, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class HasAllowHeader(BasePermission):
    message = "Missing X-Allow header."

    def has_permission(self, request, view):
        return request.headers.get("X-Allow") == "1"


class IsSelf(BasePermission):
    message = "You can only view yourself."

    def has_object_permission(self, request, view, obj):
        return obj == request.user


class ArticleViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated | HasAllowHeader]

    def list(self, request):
        return Response([])

    def create(self, request):
        return Response({}, status=201)

    def retrieve(self, request, pk=None):
        return Response({"pk": pk})

    @action(detail=False, permission_classes=[AllowAny])
    def public(self, request):
        return Response({"public": True})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def publish(self, request, pk=None):
        return Response({"published": pk})


class DynamicView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        return Response({})

    def post(self, request):
        return Response({})


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsSelf]


class NotAuthenticatedView(APIView):
    permission_classes = [~IsAuthenticated]

    def get(self, request):
        return Response({})


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_only(request):
    return Response({})


class SecretPage(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "auth.view_user"

    def get(self, request):
        return HttpResponse("secret")


class IsActiveMember(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active
