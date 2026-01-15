"""
Management command to analyze permissions in the Django project
"""
from django.core.management.base import BaseCommand
from permission_tracer.analyzer import PermissionAnalyzer
import json


class Command(BaseCommand):
    help = 'Analyze Django project to discover permission-to-endpoint mappings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path for JSON results',
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'text'],
            default='text',
            help='Output format',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Analyzing permissions...'))
        
        analyzer = PermissionAnalyzer()
        analysis = analyzer.analyze()
        
        if options['format'] == 'json':
            output = json.dumps(analysis, indent=2)
            if options['output']:
                with open(options['output'], 'w') as f:
                    f.write(output)
                self.stdout.write(self.style.SUCCESS(f'Results saved to {options["output"]}'))
            else:
                self.stdout.write(output)
        else:
            # Text output
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.SUCCESS('PERMISSION ANALYSIS RESULTS'))
            self.stdout.write('=' * 80 + '\n')
            
            self.stdout.write(f"Total Endpoints: {analysis['total_endpoints']}")
            self.stdout.write(f"Total Permissions: {analysis['total_permissions']}\n")
            
            self.stdout.write('\n' + '-' * 80)
            self.stdout.write('PERMISSIONS AND THEIR USAGE')
            self.stdout.write('-' * 80 + '\n')
            
            for perm_name, endpoints in sorted(analysis['permission_endpoints'].items()):
                self.stdout.write(self.style.WARNING(f"\n{perm_name}"))
                self.stdout.write(f"  Used in {len(endpoints)} endpoint(s):")
                for endpoint in endpoints[:5]:  # Show first 5
                    self.stdout.write(f"    - {endpoint['path']}")
                if len(endpoints) > 5:
                    self.stdout.write(f"    ... and {len(endpoints) - 5} more")
            
            self.stdout.write('\n' + '-' * 80)
            self.stdout.write('ENDPOINTS AND THEIR PERMISSIONS')
            self.stdout.write('-' * 80 + '\n')
            
            for endpoint_key, info in list(analysis['endpoint_permissions'].items())[:10]:  # Show first 10
                self.stdout.write(self.style.SUCCESS(f"\n{info['path']}"))
                self.stdout.write(f"  View: {info['view_class']}")
                self.stdout.write(f"  Permissions ({len(info['permissions'])}):")
                for perm in info['permissions']:
                    self.stdout.write(f"    - {perm}")
            
            if len(analysis['endpoint_permissions']) > 10:
                self.stdout.write(f"\n... and {len(analysis['endpoint_permissions']) - 10} more endpoints")
            
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.SUCCESS('Analysis complete!'))
            self.stdout.write('=' * 80 + '\n')

