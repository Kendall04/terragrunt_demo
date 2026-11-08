"""Source/lock contract checks only; no restore, network or SDK invocation."""
import base64
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
SOLUTION = ROOT / 'demo-api/terragrunt-demo.sln'


class DotnetLockTests(unittest.TestCase):
    def projects(self):
        names = re.findall(r'^Project\([^\n]+?= "[^"]+", "([^"]+\.csproj)"',
                           SOLUTION.read_text(encoding='utf-8-sig'), flags=re.M)
        self.assertEqual(len(names), 4)
        return [(SOLUTION.parent / n.replace('\\', '/')).resolve() for n in names]

    def test_all_solution_projects_have_content_bound_locks(self):
        for project in self.projects():
            with self.subTest(project=project.name):
                data = json.loads(project.with_name('packages.lock.json').read_text())
                self.assertEqual(data['version'], 1)
                self.assertIn('net10.0', data['dependencies'])
                for package in data['dependencies']['net10.0'].values():
                    if package['type'] != 'Project':
                        self.assertEqual(len(base64.b64decode(package['contentHash'], validate=True)), 64)
                        self.assertTrue(package['resolved'])

    def test_direct_project_dependencies_match_locked_requested_and_resolved_versions(self):
        for project in self.projects():
            lock = json.loads(project.with_name('packages.lock.json').read_text())['dependencies']['net10.0']
            by_name = {name.lower(): value for name, value in lock.items()}
            for reference in ET.parse(project).getroot().iter('PackageReference'):
                name, version = reference.attrib['Include'], reference.attrib['Version']
                with self.subTest(project=project.name, package=name):
                    entry = by_name[name.lower()]
                    self.assertEqual(entry['type'], 'Direct')
                    self.assertEqual(entry['requested'], '[' + version + ', )')
                    self.assertEqual(entry['resolved'], version)

    def test_ci_and_docker_use_locks_without_publish_reresolution(self):
        ci = (ROOT / '.github/workflows/ci-dotnet.yml').read_text(encoding='utf-8')
        docker = (ROOT / 'demo-api/Dockerfile').read_text()
        self.assertIn('run: dotnet restore ./demo-api/terragrunt-demo.sln --locked-mode', ci)
        self.assertIn("hashFiles('**/*.csproj', '**/packages.lock.json', 'global.json')", ci)
        self.assertIn('test_dotnet_locks.py', ci)
        self.assertIn('COPY terragrunt-demo/terragrunt-demo.csproj terragrunt-demo/packages.lock.json terragrunt-demo/', docker)
        self.assertIn('RUN dotnet restore terragrunt-demo/terragrunt-demo.csproj --locked-mode', docker)
        publish = docker.split('RUN dotnet publish', 1)[1].split('FROM base AS final', 1)[0]
        self.assertIn('--no-restore', publish)
        self.assertNotIn('NuGetAudit=false', ci + docker)
        self.assertNotIn('id-token:', ci)


if __name__ == '__main__': unittest.main()
