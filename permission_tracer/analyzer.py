"""
Static analyzer to discover permission-to-endpoint mappings
"""
import inspect
from typing import Dict, List, Any, Optional
from django.urls import get_resolver

try:
    from rest_framework.routers import DefaultRouter
    DRF_AVAILABLE = True
except ImportError:
    DRF_AVAILABLE = False


class PermissionAnalyzer:
    """
    Analyzes Django project to discover permission-to-endpoint mappings
    """
    
    def __init__(self):
        self.permission_mappings = {}
        self.endpoint_permissions = {}
        self.permission_endpoints = {}
    
    def analyze(self) -> Dict[str, Any]:
        """
        Perform full analysis of the project
        Returns a dictionary with all discovered mappings
        """
        try:
            # Discover all URLs and their views
            url_patterns = self._discover_url_patterns()
            
            # If no patterns found via URL resolver, try router discovery
            if not url_patterns:
                import logging
                logger = logging.getLogger(__name__)
                logger.info("No patterns found via URL resolver, trying router discovery...")
                url_patterns = self._discover_from_routers()
            
            # Analyze each view for permissions
            for pattern_info in url_patterns:
                try:
                    self._analyze_view(pattern_info)
                except Exception as e:
                    # Skip views that cause errors
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Error analyzing view {pattern_info.get('path', 'unknown')}: {e}")
                    continue
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error during analysis: {e}")
            # Return empty results rather than crashing
            pass
        
        return {
            'endpoint_permissions': self.endpoint_permissions,
            'permission_endpoints': self.permission_endpoints,
            'total_endpoints': len(self.endpoint_permissions),
            'total_permissions': len(self.permission_endpoints),
        }
    
    def _discover_url_patterns(self) -> List[Dict[str, Any]]:
        """Discover all URL patterns in the project"""
        patterns = []
        
        try:
            resolver = get_resolver()
        except Exception as e:
            # If resolver fails (e.g., database issues), try alternative method
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to get URL resolver: {e}")
            # Try to discover from router directly
            return self._discover_from_routers()
        
        def extract_patterns(url_patterns, prefix=''):
            for pattern in url_patterns:
                try:
                    if hasattr(pattern, 'url_patterns'):
                        # Include pattern
                        new_prefix = prefix + str(pattern.pattern)
                        extract_patterns(pattern.url_patterns, new_prefix)
                    elif hasattr(pattern, 'callback'):
                        # View pattern
                        callback = pattern.callback
                        patterns.append({
                            'path': prefix + str(pattern.pattern),
                            'callback': callback,
                            'name': getattr(pattern, 'name', None),
                        })
                except Exception as e:
                    # Skip patterns that cause errors (e.g., reverse URL lookups that need DB)
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Skipping pattern due to error: {e}")
                    continue
        
        try:
            extract_patterns(resolver.url_patterns)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error extracting URL patterns: {e}, trying alternative method")
            # Fallback to router discovery
            router_patterns = self._discover_from_routers()
            if router_patterns:
                patterns.extend(router_patterns)
        
        return patterns
    
    def _discover_from_routers(self) -> List[Dict[str, Any]]:
        """Alternative method: Discover viewsets from Django routers directly - Generic approach"""
        patterns = []
        
        try:
            # Try to import and inspect the main urls module
            from django.conf import settings
            root_urlconf = settings.ROOT_URLCONF
            
            import importlib
            
            # Try to import from ROOT_URLCONF (generic - works with any project)
            urls_module = None
            try:
                urls_module = importlib.import_module(root_urlconf)
            except ImportError:
                # If that fails, try to discover by walking URL patterns
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Could not import {root_urlconf}")
                return patterns
            
            # Look for router registrations (generic - works with any router)
            if urls_module and hasattr(urls_module, 'router'):
                router = urls_module.router
                if hasattr(router, 'registry'):
                    for prefix, viewset, basename in router.registry:
                        # The prefix from router.registry is a Pattern object or string
                        # Convert it to a simple URL path
                        if hasattr(prefix, 'pattern'):
                            # It's a Pattern object
                            url_prefix = str(prefix.pattern)
                        else:
                            # It's already a string
                            url_prefix = str(prefix)
                        
                        # Remove regex special characters and anchors
                        url_prefix = url_prefix.replace('^', '').replace('$', '')
                        # Remove named groups like (?P<slug>...) but keep the path
                        import re
                        url_prefix = re.sub(r'\(\?P<[^>]+>[^)]+\)', '{pk}', url_prefix)
                        
                        # Create patterns for standard CRUD operations
                        # DRF routers create these standard routes:
                        # - list: GET /prefix/
                        # - create: POST /prefix/
                        # - retrieve: GET /prefix/{pk}/
                        # - update: PUT /prefix/{pk}/
                        # - partial_update: PATCH /prefix/{pk}/
                        # - destroy: DELETE /prefix/{pk}/
                        
                        # List and create share the same path
                        patterns.append({
                            'path': f"/{url_prefix}/",
                            'callback': None,
                            'viewset': viewset,
                            'action': 'list',
                            'name': f"{basename}-list" if basename else None,
                        })
                        
                        # Detail operations
                        patterns.append({
                            'path': f"/{url_prefix}/{{pk}}/",
                            'callback': None,
                            'viewset': viewset,
                            'action': 'retrieve',
                            'name': f"{basename}-detail" if basename else None,
                        })
            
            # Also check for direct URL patterns in the module (generic discovery)
            if urls_module and hasattr(urls_module, 'urlpatterns'):
                for pattern in urls_module.urlpatterns:
                    try:
                        if hasattr(pattern, 'callback') and hasattr(pattern, 'pattern'):
                            patterns.append({
                                'path': str(pattern.pattern),
                                'callback': pattern.callback,
                                'name': getattr(pattern, 'name', None),
                            })
                    except Exception:
                        continue
                        
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Alternative discovery method failed: {e}")
        
        return patterns
    
    def _analyze_view(self, pattern_info: Dict[str, Any]):
        """Analyze a single view for its permission classes"""
        try:
            callback = pattern_info.get('callback')
            path = pattern_info.get('path', '')
            viewset = pattern_info.get('viewset')  # For router-discovered viewsets
            
            # Get view class
            view_class = None
            
            # Method 1: Direct viewset from router
            if viewset:
                view_class = viewset
            # Method 2: From callback
            elif callback:
                if hasattr(callback, 'view_class'):
                    view_class = callback.view_class
                elif inspect.isclass(callback):
                    view_class = callback
                elif hasattr(callback, 'cls'):
                    view_class = callback.cls
                elif hasattr(callback, '__self__') and hasattr(callback.__self__, 'view_class'):
                    view_class = callback.__self__.view_class
            
            if not view_class:
                return
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error getting view class: {e}")
            return
        
        # Get permission classes
        permission_classes = []
        if hasattr(view_class, 'permission_classes'):
            perm_classes = view_class.permission_classes
            if perm_classes:
                # Handle both tuple and list
                if isinstance(perm_classes, (tuple, list)):
                    permission_classes = list(perm_classes)
                else:
                    permission_classes = [perm_classes]
        
        # Also check for get_permissions method which might return permissions dynamically
        if not permission_classes and hasattr(view_class, 'get_permissions'):
            try:
                # Create a mock request to call get_permissions
                # We can't actually call it without a request, but we can check the method
                # For now, we'll rely on permission_classes attribute
                pass
            except Exception:
                pass
        
        # Fallback to default DRF permissions if none specified
        if not permission_classes and DRF_AVAILABLE:
            try:
                from rest_framework.views import APIView
                if inspect.isclass(view_class) and issubclass(view_class, APIView):
                    # Use default permission classes from settings or APIView default
                    from django.conf import settings
                    rest_framework_settings = getattr(settings, 'REST_FRAMEWORK', {})
                    default_perms = rest_framework_settings.get('DEFAULT_PERMISSION_CLASSES', [])
                    if default_perms:
                        # Convert string paths to actual classes if needed
                        import importlib
                        resolved_perms = []
                        for perm in default_perms:
                            if isinstance(perm, str):
                                try:
                                    module_path, class_name = perm.rsplit('.', 1)
                                    module = importlib.import_module(module_path)
                                    resolved_perms.append(getattr(module, class_name))
                                except (ImportError, AttributeError):
                                    # Keep as string if can't resolve
                                    pass
                            else:
                                resolved_perms.append(perm)
                        permission_classes = resolved_perms if resolved_perms else default_perms
            except (ImportError, TypeError) as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"Error getting default permissions: {e}")
                pass
        
        # Also check for permission_classes in view actions
        actions_permissions = {}
        if hasattr(view_class, 'get_permissions'):
            # This is a DRF viewset
            for action in ['list', 'create', 'retrieve', 'update', 'partial_update', 'destroy']:
                if hasattr(view_class, action):
                    # Check if action has specific permissions
                    action_method = getattr(view_class, action)
                    if hasattr(action_method, 'kwargs') and 'permission_classes' in action_method.kwargs:
                        actions_permissions[action] = action_method.kwargs['permission_classes']
        
        # Store mappings
        try:
            permission_names = [
                f"{perm.__module__}.{perm.__name__}"
                for perm in permission_classes
            ]
            
            endpoint_key = f"{pattern_info.get('method', 'ALL')} {path}"
            
            self.endpoint_permissions[endpoint_key] = {
                'path': path,
                'view_class': f"{view_class.__module__}.{view_class.__name__}",
                'permissions': permission_names,
                'actions_permissions': actions_permissions,
            }
            
            # Reverse mapping: permission -> endpoints
            for perm_name in permission_names:
                if perm_name not in self.permission_endpoints:
                    self.permission_endpoints[perm_name] = []
                self.permission_endpoints[perm_name].append({
                    'path': path,
                    'view_class': f"{view_class.__module__}.{view_class.__name__}",
                })
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error storing mappings for {path}: {e}")
            # Continue with other views
    
    def find_permission_usage(self, permission_name: str) -> List[Dict[str, Any]]:
        """Find all endpoints using a specific permission"""
        return self.permission_endpoints.get(permission_name, [])
    
    def find_endpoint_permissions(self, endpoint_path: str) -> List[str]:
        """Find all permissions for a specific endpoint"""
        for key, info in self.endpoint_permissions.items():
            if info['path'] == endpoint_path:
                return info['permissions']
        return []
    
    def get_permission_graph(self) -> Dict[str, Any]:
        """Get graph data for visualization"""
        nodes = []
        edges = []
        
        # Add permission nodes
        permission_nodes = {}
        for perm_name in self.permission_endpoints.keys():
            node_id = f"perm_{len(permission_nodes)}"
            permission_nodes[perm_name] = node_id
            nodes.append({
                'id': node_id,
                'label': perm_name.split('.')[-1],  # Just the class name
                'type': 'permission',
                'full_name': perm_name,
            })
        
        # Add endpoint nodes - use endpoint_key to preserve all entries (including duplicates)
        endpoint_nodes = {}
        
        for endpoint_key, info in self.endpoint_permissions.items():
            # Use endpoint_key as identifier to preserve all entries
            if endpoint_key not in endpoint_nodes:
                node_id = f"endpoint_{len(endpoint_nodes)}"
                endpoint_nodes[endpoint_key] = node_id
                nodes.append({
                    'id': node_id,
                    'label': info['path'],
                    'type': 'endpoint',
                    'full_path': info['path'],
                })
        
        # Add edges - count all connections to match permission_endpoints count
        edge_count_by_permission = {}
        for endpoint_key, info in self.endpoint_permissions.items():
            endpoint_node = endpoint_nodes[endpoint_key]
            for perm_name in info['permissions']:
                if perm_name in permission_nodes:
                    perm_node = permission_nodes[perm_name]
                    # Count edges per permission (this matches permission_endpoints count)
                    if perm_name not in edge_count_by_permission:
                        edge_count_by_permission[perm_name] = 0
                    edge_count_by_permission[perm_name] += 1
                    # Add edge
                    edges.append({
                        'from': perm_node,
                        'to': endpoint_node,
                    })
        
        # Store edge counts in permission nodes for display
        for perm_name, node_id in permission_nodes.items():
            for node in nodes:
                if node['id'] == node_id:
                    # Use the count from permission_endpoints to ensure consistency
                    node['edge_count'] = len(self.permission_endpoints.get(perm_name, []))
                    break
        
        return {
            'nodes': nodes,
            'edges': edges,
            'stats': {
                'total_permissions': len(permission_nodes),
                'total_endpoints': len(endpoint_nodes),
                'total_edges': len(edges),
                'permission_edge_counts': edge_count_by_permission,
            }
        }

