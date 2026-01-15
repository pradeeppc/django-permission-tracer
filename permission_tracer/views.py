"""
Views for the permission tracer web interface
"""
import json
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.cache import cache
from django.conf import settings
from .analyzer import PermissionAnalyzer


class PermissionTracerIndexView(View):
    """Main index view"""
    
    def get(self, request):
        from django.template.loader import render_to_string
        
        try:
            html = render_to_string('permission_tracer/index.html', {
                'title': 'Permission Tracer',
            })
            return HttpResponse(html)
        except Exception as e:
            import traceback
            return HttpResponse(f"Error loading template: {str(e)}<pre>{traceback.format_exc()}</pre>", status=500)


@method_decorator(csrf_exempt, name='dispatch')
class PermissionTracerDebugView(View):
    """Debug view to check if permission patching is working"""
    
    def get(self, request):
        try:
            from rest_framework.permissions import BasePermission
            is_patched = hasattr(BasePermission.has_permission, '_permission_tracer_patched')
            
            # Try to find any permission class in the project as a sample (generic approach)
            sample_permissions = []
            try:
                # Use the analyzer to find permissions
                from .analyzer import PermissionAnalyzer
                analyzer = PermissionAnalyzer()
                analysis = analyzer.analyze()
                
                # Get first few permissions as samples
                permission_names = list(analysis.get('permission_endpoints', {}).keys())[:3]
                
                for perm_name in permission_names:
                    try:
                        # Try to import the permission
                        parts = perm_name.rsplit('.', 1)
                        if len(parts) == 2:
                            module_path, class_name = parts
                            import importlib
                            module = importlib.import_module(module_path)
                            perm_class = getattr(module, class_name, None)
                            if perm_class:
                                perm_instance = perm_class()
                                perm_has_patched = hasattr(perm_instance.has_permission, '_permission_tracer_patched')
                                sample_permissions.append({
                                    'name': perm_name,
                                    'found': True,
                                    'patched': perm_has_patched,
                                })
                    except Exception:
                        # Skip if can't import
                        continue
            except Exception as e:
                pass
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'base_permission_patched': is_patched,
                    'sample_permissions': sample_permissions,
                    'note': 'If patched is False, permission tracking may not work',
                    'total_permissions_found': len(sample_permissions),
                },
            })
        except Exception as e:
            import traceback
            return JsonResponse({
                'status': 'error',
                'message': str(e),
                'traceback': traceback.format_exc(),
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class PermissionTracerAPIView(View):
    """API endpoint for permission tracer data"""
    
    def get(self, request):
        """Get permission mappings"""
        try:
            analyzer = PermissionAnalyzer()
            analysis = analyzer.analyze()
            
            return JsonResponse({
                'status': 'success',
                'data': analysis,
            })
        except Exception as e:
            import traceback
            error_msg = str(e)
            error_trace = traceback.format_exc()
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Permission Tracer API Error: {error_msg}\n{error_trace}")
            
            return JsonResponse({
                'status': 'error',
                'message': error_msg,
                'traceback': error_trace,
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class PermissionTraceView(View):
    """View to get traced request data"""
    
    def get(self, request):
        """Get latest traces"""
        try:
            traces = cache.get('permission_tracer:traces', [])
            
            # Get specific trace if ID provided
            trace_id = request.GET.get('id')
            if trace_id:
                try:
                    trace_id = int(trace_id)
                    if 0 <= trace_id < len(traces):
                        return JsonResponse({
                            'status': 'success',
                            'data': traces[trace_id],
                        })
                except (ValueError, IndexError):
                    pass
            
            # Return all traces (limited)
            return JsonResponse({
                'status': 'success',
                'data': traces[:20],  # Last 20 traces
                'total': len(traces),
            })
        except Exception as e:
            import traceback
            return JsonResponse({
                'status': 'error',
                'message': str(e),
                'traceback': traceback.format_exc(),
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class PermissionGraphView(View):
    """View to get permission graph data"""
    
    def get(self, request):
        """Get graph data for visualization"""
        try:
            analyzer = PermissionAnalyzer()
            # Run analysis first to populate the data
            analysis = analyzer.analyze()
            graph = analyzer.get_permission_graph()
            
            # Add debug info if graph is empty
            if not graph.get('nodes'):
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Empty graph - analysis found {analysis.get('total_endpoints', 0)} endpoints and {analysis.get('total_permissions', 0)} permissions")
            
            return JsonResponse({
                'status': 'success',
                'data': graph,
                'debug': {
                    'total_endpoints': analysis.get('total_endpoints', 0),
                    'total_permissions': analysis.get('total_permissions', 0),
                } if not graph.get('nodes') else None,
            })
        except Exception as e:
            import traceback
            return JsonResponse({
                'status': 'error',
                'message': str(e),
                'traceback': traceback.format_exc(),
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class PermissionSearchView(View):
    """View to search for permissions or endpoints"""
    
    def get(self, request):
        """Search permissions or endpoints"""
        query = request.GET.get('q', '').strip()
        search_type = request.GET.get('type', 'all')  # 'permission', 'endpoint', 'all'
        
        if not query:
            return JsonResponse({
                'status': 'error',
                'message': 'Query parameter required',
            }, status=400)
        
        analyzer = PermissionAnalyzer()
        analysis = analyzer.analyze()
        
        results = {
            'permissions': [],
            'endpoints': [],
        }
        
        # Search permissions
        if search_type in ['permission', 'all']:
            for perm_name, endpoints in analysis['permission_endpoints'].items():
                if query.lower() in perm_name.lower():
                    results['permissions'].append({
                        'name': perm_name,
                        'usage_count': len(endpoints),
                        'endpoints': endpoints,
                    })
        
        # Search endpoints
        if search_type in ['endpoint', 'all']:
            for endpoint_key, info in analysis['endpoint_permissions'].items():
                if query.lower() in info['path'].lower() or query.lower() in info['view_class'].lower():
                    results['endpoints'].append({
                        'path': info['path'],
                        'view_class': info['view_class'],
                        'permissions': info['permissions'],
                    })
        
        return JsonResponse({
            'status': 'success',
            'data': results,
            'query': query,
        })


@method_decorator(csrf_exempt, name='dispatch')
class PermissionDetailView(View):
    """View to get details about a specific permission"""
    
    def get(self, request, permission_name):
        """Get details about a permission including implementation"""
        analyzer = PermissionAnalyzer()
        analysis = analyzer.analyze()
        
        # Decode permission name (URL encoded)
        from urllib.parse import unquote
        permission_name = unquote(permission_name)
        
        endpoints = analysis['permission_endpoints'].get(permission_name, [])
        
        # Get permission class implementation details
        permission_details = self._get_permission_implementation(permission_name)
        
        return JsonResponse({
            'status': 'success',
            'data': {
                'permission': permission_name,
                'usage_count': len(endpoints),
                'endpoints': endpoints,
                'implementation': permission_details,
            },
        })
    
    def _get_permission_implementation(self, permission_path: str):
        """Extract permission class implementation details"""
        try:
            import importlib
            import inspect
            
            # Parse module path (e.g., 'core.permissions.user.UserPermission')
            parts = permission_path.rsplit('.', 1)
            if len(parts) != 2:
                return None
            
            module_path, class_name = parts
            
            # Import the module and class
            try:
                module = importlib.import_module(module_path)
                permission_class = getattr(module, class_name, None)
                
                if not permission_class:
                    return None
                
                # Get source code
                try:
                    source_code = inspect.getsource(permission_class)
                except (OSError, TypeError):
                    source_code = None
                
                # Get docstring
                docstring = inspect.getdoc(permission_class) or ""
                
                # Get has_permission method details
                has_permission_method = None
                has_permission_doc = None
                has_permission_source = None
                
                if hasattr(permission_class, 'has_permission'):
                    has_permission_method = getattr(permission_class, 'has_permission')
                    has_permission_doc = inspect.getdoc(has_permission_method) or ""
                    try:
                        has_permission_source = inspect.getsource(has_permission_method)
                    except (OSError, TypeError):
                        has_permission_source = None
                
                # Analyze method logic (extract key checks)
                logic_summary = self._analyze_permission_logic(permission_class)
                
                # Get additional metadata
                metadata = {}
                try:
                    # Get file path and line number
                    try:
                        file_path = inspect.getfile(permission_class)
                        lines = inspect.getsourcelines(permission_class)
                        metadata['file_path'] = file_path
                        metadata['line_number'] = lines[1]
                        metadata['total_lines'] = len(lines[0])
                    except (OSError, TypeError):
                        pass
                    
                    # Get all methods in the class
                    all_methods = [name for name, method in inspect.getmembers(permission_class, predicate=inspect.ismethod)
                                 if not name.startswith('_')]
                    metadata['methods'] = all_methods
                    
                    # Check if it's a built-in Django/DRF permission
                    try:
                        from rest_framework.permissions import BasePermission, IsAuthenticated, AllowAny, IsAdminUser
                        drf_permissions = [IsAuthenticated, AllowAny, IsAdminUser, BasePermission]
                        is_builtin = permission_class in drf_permissions or any(
                            issubclass(permission_class, perm) if inspect.isclass(permission_class) else False 
                            for perm in drf_permissions
                        )
                        metadata['is_builtin'] = is_builtin
                    except Exception:
                        metadata['is_builtin'] = False
                    
                    # Get module docstring
                    try:
                        module_docstring = inspect.getdoc(module) or ""
                        if module_docstring:
                            metadata['module_docstring'] = module_docstring[:500]  # Limit length
                    except Exception:
                        pass
                    
                except Exception:
                    pass
                
                return {
                    'class_name': class_name,
                    'module_path': module_path,
                    'full_path': permission_path,
                    'source_code': source_code,
                    'docstring': docstring,
                    'has_permission': {
                        'docstring': has_permission_doc,
                        'source_code': has_permission_source,
                    },
                    'logic_summary': logic_summary,
                    'metadata': metadata,
                }
            except (ImportError, AttributeError) as e:
                return {
                    'error': f"Could not import permission class: {str(e)}",
                    'permission_path': permission_path,
                }
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error getting permission implementation: {e}")
            return {
                'error': f"Error analyzing permission: {str(e)}",
                'permission_path': permission_path if 'permission_path' in locals() else 'unknown',
            }
    
    def _analyze_permission_logic(self, permission_class):
        """Analyze permission class to extract logic summary - Generic pattern detection"""
        try:
            import inspect
            import re
            from datetime import datetime
            
            logic_summary = {
                'checks_feature_flags': False,
                'checks_roles': False,
                'checks_permissions': False,
                'checks_user': False,
                'checks_groups': False,
                'checks_authentication': False,
                'checks_method': False,
                'checks_action': False,
                'raises_exceptions': False,
                'custom_conditions': [],
                'methods_called': [],
                'base_classes': [],
                'imports': [],
                'conditions': [],
                'class_attributes': {},
                'method_signatures': {},
                'decorators': [],
                'complexity_score': 0,
            }
            
            # Get has_permission source
            if hasattr(permission_class, 'has_permission'):
                try:
                    source = inspect.getsource(permission_class.has_permission)
                    source_lower = source.lower()
                    
                    # Generic pattern detection - don't assume specific class names
                    # Feature flags: Look for patterns like "feature", "is_enabled", "check_if_feature"
                    feature_patterns = [
                        r'\bfeature.*enabled',
                        r'\bcheck.*feature',
                        r'\bfeature.*flag',
                        r'\bis.*enabled',
                        r'\bfeature.*active',
                    ]
                    logic_summary['checks_feature_flags'] = any(
                        re.search(pattern, source_lower) for pattern in feature_patterns
                    )
                    
                    # Roles: Look for patterns like "role", "has_role", "check_role", "is_in_role"
                    role_patterns = [
                        r'\bhas.*role',
                        r'\bcheck.*role',
                        r'\bis.*role',
                        r'\brole.*permission',
                        r'\buser.*role',
                        r'\brole.*assign',
                    ]
                    logic_summary['checks_roles'] = any(
                        re.search(pattern, source_lower) for pattern in role_patterns
                    )
                    
                    # Permissions: Look for patterns like "has_perm", "check_permission", "permission.*code"
                    permission_patterns = [
                        r'\bhas.*perm',
                        r'\bcheck.*perm',
                        r'\bpermission.*code',
                        r'\bpermission.*assigned',
                        r'\bis.*permission',
                    ]
                    logic_summary['checks_permissions'] = any(
                        re.search(pattern, source_lower) for pattern in permission_patterns
                    )
                    
                    # User checks: Look for patterns like "request.user", "user.id", "authenticated"
                    user_patterns = [
                        r'request\.user',
                        r'\buser\.id',
                        r'\buser\.is_authenticated',
                        r'\bauthenticated',
                        r'\buser_id',
                        r'\bemp_id',  # Common but not required
                        r'\bcurrent_user',
                    ]
                    logic_summary['checks_user'] = any(
                        re.search(pattern, source_lower) for pattern in user_patterns
                    )
                    
                    # Groups: Look for Django groups patterns
                    group_patterns = [
                        r'\bgroup',
                        r'\buser\.groups',
                        r'\bis.*group',
                    ]
                    logic_summary['checks_groups'] = any(
                        re.search(pattern, source_lower) for pattern in group_patterns
                    )
                    
                    # Authentication: Look for auth checks
                    auth_patterns = [
                        r'\bauthenticated',
                        r'\bis_authenticated',
                        r'\bauthentication',
                        r'\bnot.*authenticated',
                    ]
                    logic_summary['checks_authentication'] = any(
                        re.search(pattern, source_lower) for pattern in auth_patterns
                    )
                    
                    # Check for action-specific checks
                    logic_summary['checks_action'] = bool(
                        re.search(r'\baction\b', source_lower) or
                        re.search(r'view\.action', source_lower) or
                        re.search(r'getattr.*action', source_lower)
                    )
                    
                    # Check for HTTP method checks
                    logic_summary['checks_method'] = bool(
                        re.search(r'request\.method', source_lower) or
                        re.search(r'method\s*==', source_lower) or
                        re.search(r'method\s*in', source_lower)
                    )
                    
                    # Check for exception raises
                    logic_summary['raises_exceptions'] = bool(
                        re.search(r'\braise\s+\w+', source_lower) or
                        re.search(r'permissiondenied', source_lower) or
                        re.search(r'authenticationfailed', source_lower)
                    )
                    
                    # Extract conditions (if statements, raises, asserts)
                    condition_patterns = [
                        r'if\s+.*:',
                        r'raise\s+\w+',
                        r'assert\s+',
                        r'return\s+(true|false|none)',
                    ]
                    conditions = []
                    for line in source.split('\n'):
                        for pattern in condition_patterns:
                            if re.search(pattern, line.lower()):
                                # Clean up the condition
                                clean_line = line.strip()[:100]  # Limit length
                                if clean_line and not clean_line.startswith('#'):
                                    conditions.append(clean_line)
                                    break
                    logic_summary['conditions'] = conditions[:10]  # Limit to 10
                    
                    # Calculate complexity (simple metric: number of branches, conditions)
                    complexity = 0
                    complexity += len(re.findall(r'\bif\s+', source_lower))
                    complexity += len(re.findall(r'\bfor\s+', source_lower))
                    complexity += len(re.findall(r'\bwhile\s+', source_lower))
                    complexity += len(re.findall(r'\braise\s+', source_lower))
                    logic_summary['complexity_score'] = complexity
                    
                    # Extract method calls (filter out common Python methods)
                    method_calls = re.findall(r'\b(\w+)\s*\(', source)
                    # Filter out common Python built-ins and keywords
                    common_excluded = {
                        'self', 'request', 'view', 'get', 'set', 'str', 'int', 'bool', 'list', 'dict',
                        'len', 'all', 'any', 'filter', 'map', 'print', 'return', 'if', 'elif', 'else',
                        'for', 'while', 'try', 'except', 'with', 'as', 'from', 'import', 'is', 'in',
                        'not', 'and', 'or', 'True', 'False', 'None', 'raise', 'assert', 'pass', 'break',
                        'continue', 'yield', 'lambda', 'def', 'class'
                    }
                    filtered_calls = [
                        m for m in method_calls 
                        if m not in common_excluded and not m[0].islower() or m in ['hasattr', 'getattr']
                    ]
                    # Keep both camelCase/method-like calls and imports
                    logic_summary['methods_called'] = list(set(filtered_calls))[:15]
                    
                    # Extract imports used in the method (look for class names)
                    class_name_pattern = r'\b([A-Z][a-zA-Z0-9_]*)\b'
                    class_names = re.findall(class_name_pattern, source)
                    # Filter out common Python classes
                    python_classes = {'True', 'False', 'None', 'Exception', 'BaseException', 'object', 'type'}
                    unique_classes = [c for c in set(class_names) if c not in python_classes and len(c) > 2]
                    logic_summary['imports'] = unique_classes[:10]
                    
                except (OSError, TypeError) as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Could not get source for permission: {e}")
                    pass
            
            # Check base classes
            try:
                bases = inspect.getmro(permission_class)
                logic_summary['base_classes'] = [
                    {
                        'name': cls.__name__,
                        'module': cls.__module__ if hasattr(cls, '__module__') else 'builtins',
                        'full_path': f"{cls.__module__}.{cls.__name__}" if hasattr(cls, '__module__') else cls.__name__
                    }
                    for cls in bases[:4] 
                    if cls.__name__ not in ['object', 'type', 'ABC', 'abc.ABCMeta']
                ]
            except Exception:
                pass
            
            # Extract class attributes (constants, config values)
            try:
                class_attrs = {}
                for attr_name in dir(permission_class):
                    if not attr_name.startswith('_') and not callable(getattr(permission_class, attr_name, None)):
                        try:
                            attr_value = getattr(permission_class, attr_name)
                            # Only include simple types (not methods)
                            if isinstance(attr_value, (str, int, float, bool, list, tuple, dict, type(None))):
                                # Limit value size for display
                                if isinstance(attr_value, str):
                                    attr_value = attr_value[:100] if len(attr_value) <= 100 else attr_value[:100] + '...'
                                class_attrs[attr_name] = {
                                    'value': str(attr_value)[:200],  # Limit display length
                                    'type': type(attr_value).__name__
                                }
                        except Exception:
                            pass
                logic_summary['class_attributes'] = class_attrs
            except Exception:
                pass
            
            # Extract method signatures (all methods, not just has_permission)
            try:
                methods = {}
                for name, method in inspect.getmembers(permission_class, predicate=inspect.ismethod):
                    if not name.startswith('_'):
                        try:
                            sig = inspect.signature(method)
                            methods[name] = {
                                'parameters': [str(param) for param in sig.parameters.values()],
                                'docstring': inspect.getdoc(method) or '',
                            }
                        except Exception:
                            pass
                logic_summary['method_signatures'] = methods
            except Exception:
                pass
            
            # Extract decorators from class and methods
            try:
                decorators = []
                # Check class decorators (less common, but possible)
                if hasattr(permission_class, '__dict__'):
                    for key, value in permission_class.__dict__.items():
                        if callable(value) and hasattr(value, '__wrapped__'):
                            decorators.append(f"@{key} (on {key})")
                
                # Check method decorators
                if hasattr(permission_class, 'has_permission'):
                    if hasattr(permission_class.has_permission, '__wrapped__'):
                        decorators.append("@decorator (on has_permission)")
                    if hasattr(permission_class.has_permission, '__decorated__'):
                        decorators.append("@decorated (on has_permission)")
                
                logic_summary['decorators'] = decorators
            except Exception:
                pass
            
            return logic_summary
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error analyzing permission logic: {e}")
            return {}


@method_decorator(csrf_exempt, name='dispatch')
class EndpointDetailView(View):
    """View to get details about a specific endpoint"""
    
    def get(self, request, endpoint_path):
        """Get details about an endpoint"""
        analyzer = PermissionAnalyzer()
        analysis = analyzer.analyze()
        
        # Decode endpoint path
        from urllib.parse import unquote
        endpoint_path = unquote(endpoint_path)
        
        # Find matching endpoint
        for endpoint_key, info in analysis['endpoint_permissions'].items():
            if info['path'] == endpoint_path:
                return JsonResponse({
                    'status': 'success',
                    'data': info,
                })
        
        return JsonResponse({
            'status': 'error',
            'message': 'Endpoint not found',
        }, status=404)

