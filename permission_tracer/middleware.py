"""
Middleware to trace permission checks during request processing
"""
import json
import time
import inspect
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache


class PermissionTracerMiddleware(MiddlewareMixin):
    """
    Middleware that traces permission checks for each request.
    Django middleware for tracing permission checks during request processing.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.config = getattr(settings, 'PERMISSION_TRACER', {})
        self.enabled = self.config.get('ENABLED', True)
        self.storage_backend = self.config.get('STORAGE_BACKEND', 'memory')
        self.max_traces = self.config.get('MAX_TRACES', 100)
        self.exclude_paths = self.config.get('EXCLUDE_PATHS', ['/_permission-tracer/', '/admin/'])
        super().__init__(get_response)
    
    def process_request(self, request):
        """Initialize tracing for this request"""
        if not self.enabled:
            return None
        
        # Skip excluded paths
        if any(request.path.startswith(path) for path in self.exclude_paths):
            return None
        
        # Skip tracing for permission tracer's own views to avoid recursion
        if request.path.startswith('/_permission-tracer/'):
            return None
        
        # Initialize trace data
        request._permission_trace = {
            'path': request.path,
            'method': request.method,
            'timestamp': time.time(),
            'permissions_checked': [],
            'permission_results': {},
            'view_class': None,
            'permission_classes': [],
        }
        
        return None
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """Capture view and permission information"""
        if not self.enabled or not hasattr(request, '_permission_trace'):
            return None
        
        # Skip tracing for permission tracer's own views to avoid recursion
        if request.path.startswith('/_permission-tracer/'):
            return None
        
        # Ensure permissions are patched (in case they were imported after our module)
        ensure_permission_patching()
        
        # Get view class - handle different view types
        view_class = None
        
        # Method 1: DRF viewset (most common)
        if hasattr(view_func, 'view_class'):
            view_class = view_func.view_class
        # Method 2: Direct class-based view
        elif inspect.isclass(view_func):
            view_class = view_func
        # Method 3: Function-based view with cls attribute
        elif hasattr(view_func, 'cls'):
            view_class = view_func.cls
        # Method 4: Try to get from closure (for DRF viewsets)
        elif hasattr(view_func, '__closure__') and view_func.__closure__:
            try:
                for cell in view_func.__closure__:
                    if hasattr(cell.cell_contents, 'permission_classes'):
                        view_class = cell.cell_contents
                        break
            except (AttributeError, TypeError):
                pass
        
        if view_class:
            request._permission_trace['view_class'] = {
                'name': view_class.__name__,
                'module': view_class.__module__,
                'full_path': f"{view_class.__module__}.{view_class.__name__}",
            }
            
            # Get permission classes
            if hasattr(view_class, 'permission_classes'):
                permission_classes = view_class.permission_classes
                if permission_classes:
                    request._permission_trace['permission_classes'] = [
                        {
                            'name': perm.__name__,
                            'module': perm.__module__,
                            'full_path': f"{perm.__module__}.{perm.__name__}",
                        }
                        for perm in permission_classes
                    ]
            
            # Patch the view's permission checking to track permission checks
            self._patch_view_permission_checking(view_class, request)
        
        return None
    
    def _patch_view_permission_checking(self, view_class, request):
        """Patch a view's permission checking methods to track permission calls"""
        try:
            from rest_framework.views import APIView
            if not issubclass(view_class, APIView):
                return
            
            # Use a unique identifier for this view class
            view_key = f"{view_class.__module__}.{view_class.__name__}"
            
            # Check if we've already patched this view class for this request
            if not hasattr(request, '_patched_views'):
                request._patched_views = set()
            
            if view_key in request._patched_views:
                return
            
            # Store original methods if not already stored
            if not hasattr(view_class, '_original_get_permissions'):
                view_class._original_get_permissions = view_class.get_permissions
            
            # Patch get_permissions to track when permissions are retrieved
            def tracked_get_permissions(self):
                """Track when permissions are retrieved"""
                permissions = view_class._original_get_permissions(self)
                
                # Track each permission instance that will be checked
                for perm in permissions:
                    permission_name = f"{perm.__class__.__module__}.{perm.__class__.__name__}"
                    if hasattr(request, '_permission_trace'):
                        if permission_name not in request._permission_trace['permissions_checked']:
                            request._permission_trace['permissions_checked'].append(permission_name)
                
                return permissions
            
            # Replace the method on the class
            view_class.get_permissions = tracked_get_permissions
            
            # Also patch check_permissions if it exists
            if hasattr(view_class, 'check_permissions'):
                if not hasattr(view_class, '_original_check_permissions'):
                    view_class._original_check_permissions = view_class.check_permissions
                
                def tracked_check_permissions(self, request):
                    """Track permission checks"""
                    # Get permissions before checking (this will trigger get_permissions)
                    if hasattr(self, 'get_permissions'):
                        permissions = self.get_permissions()
                        # Track each permission
                        for perm in permissions:
                            permission_name = f"{perm.__class__.__module__}.{perm.__class__.__name__}"
                            if hasattr(request, '_permission_trace'):
                                if permission_name not in request._permission_trace['permissions_checked']:
                                    request._permission_trace['permissions_checked'].append(permission_name)
                    
                    # Now call the original check
                    return view_class._original_check_permissions(self, request)
                
                view_class.check_permissions = tracked_check_permissions
            
            request._patched_views.add(view_key)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error patching view permission checking: {e}")
    
    def process_response(self, request, response):
        """Store trace data after request completes"""
        if not self.enabled or not hasattr(request, '_permission_trace'):
            return response
        
        trace = request._permission_trace
        trace['status_code'] = response.status_code
        trace['duration'] = time.time() - trace['timestamp']
        
        # Store trace
        self._store_trace(trace)
        
        return response
    
    def _store_trace(self, trace: Dict[str, Any]):
        """Store trace data using configured storage backend"""
        if self.storage_backend == 'memory':
            self._store_in_memory(trace)
        elif self.storage_backend == 'database':
            self._store_in_database(trace)
        elif self.storage_backend == 'cache':
            self._store_in_cache(trace)
    
    def _store_in_memory(self, trace: Dict[str, Any]):
        """Store trace in process memory (thread-safe with cache)"""
        cache_key = 'permission_tracer:traces'
        traces = cache.get(cache_key, [])
        traces.insert(0, trace)
        
        # Limit number of traces
        if len(traces) > self.max_traces:
            traces = traces[:self.max_traces]
        
        cache.set(cache_key, traces, timeout=3600)  # 1 hour
    
    def _store_in_database(self, trace: Dict[str, Any]):
        """Store trace in database"""
        # This would use models - we'll implement this later
        # For now, fall back to memory
        self._store_in_memory(trace)
    
    def _store_in_cache(self, trace: Dict[str, Any]):
        """Store trace in cache"""
        self._store_in_memory(trace)


# Monkey patch permission classes to track checks
def patch_permission_classes():
    """Patch DRF permission classes to track permission checks"""
    try:
        from rest_framework.permissions import BasePermission
        from rest_framework.views import APIView
        
        # Check if already patched
        if hasattr(BasePermission.has_permission, '_permission_tracer_patched'):
            return
        
        original_has_permission = BasePermission.has_permission
        
        def tracked_has_permission(self, request, view):
            """Wrapper that tracks permission checks"""
            # Initialize trace if it doesn't exist (might happen if permission is checked early)
            if not hasattr(request, '_permission_trace'):
                request._permission_trace = {
                    'path': getattr(request, 'path', ''),
                    'method': getattr(request, 'method', ''),
                    'timestamp': time.time(),
                    'permissions_checked': [],
                    'permission_results': {},
                    'view_class': None,
                    'permission_classes': [],
                }
            
            permission_name = f"{self.__class__.__module__}.{self.__class__.__name__}"
            
            # Record that this permission is being checked
            if permission_name not in request._permission_trace['permissions_checked']:
                request._permission_trace['permissions_checked'].append(permission_name)
            
            # Execute permission check
            try:
                result = original_has_permission(self, request, view)
                request._permission_trace['permission_results'][permission_name] = {
                    'allowed': result,
                    'error': None,
                }
                return result
            except Exception as e:
                request._permission_trace['permission_results'][permission_name] = {
                    'allowed': False,
                    'error': str(e),
                }
                raise
        
        # Mark as patched to avoid double-patching
        tracked_has_permission._permission_tracer_patched = True
        BasePermission.has_permission = tracked_has_permission
        
        # Also patch APIView.check_permissions to catch all permission checks
        if hasattr(APIView, 'check_permissions'):
            original_check_permissions = APIView.check_permissions
            
            def tracked_check_permissions(self, request):
                """Track when permissions are checked on a view"""
                if hasattr(request, '_permission_trace'):
                    # This will be called before individual permission checks
                    pass
                return original_check_permissions(self, request)
            
            if not hasattr(APIView.check_permissions, '_permission_tracer_patched'):
                tracked_check_permissions._permission_tracer_patched = True
                APIView.check_permissions = tracked_check_permissions
                
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to patch permission classes: {e}")


# Auto-patch when module is imported (only if DRF is available)
def _try_patch():
    try:
        from rest_framework.permissions import BasePermission
        patch_permission_classes()
    except ImportError:
        # DRF not installed, skip patching
        pass
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Permission patching skipped: {e}")

# Patch on import
_try_patch()

# Also patch in process_view to catch late imports
def ensure_permission_patching():
    """Ensure permissions are patched even if imported late"""
    try:
        from rest_framework.permissions import BasePermission
        # Only patch if not already patched
        if not hasattr(BasePermission.has_permission, '_permission_tracer_patched'):
            patch_permission_classes()
    except Exception:
        pass

