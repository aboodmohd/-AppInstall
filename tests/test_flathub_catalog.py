"""Flathub Discover: no real network or packages are touched in these tests."""
import io
import unittest
from unittest.mock import patch, Mock

import flathub_catalog as cat


class CatalogValidationTests(unittest.TestCase):
    def test_install_urls_accept_only_reverse_dns_flatpak_app_ids(self):
        self.assertEqual(
            cat.flathub_ref_url('org.gimp.GIMP'),
            'https://dl.flathub.org/repo/appstream/org.gimp.GIMP.flatpakref')
        for bad in ('', 'gimp', 'org.gimp', 'https://bad.invalid/e',
                    '../evil', 'org/evil.Test', 'org.gimp.Test;rm',
                    'org.gimp.Test?query', 'org.gimp.Test\\nX',
                    'org..Broken', 'org.example.' + 'x' * 240, None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    cat.flathub_ref_url(bad)

    def test_untrusted_and_non_flathub_icons_are_discarded(self):
        self.assertEqual(cat._icon_url('https://evil.invalid/preview.png'), '')
        self.assertEqual(cat._icon_url('https://dl.flathub.org.evil.invalid/media/x.png'), '')
        self.assertEqual(cat._icon_url('http://dl.flathub.org/media/x.png'), '')
        self.assertEqual(cat._icon_url('https://dl.flathub.org/private/a.png'), '')
        self.assertEqual(cat._icon_url('https://dl.flathub.org/media/a.png?token=1'), '')
        self.assertEqual(cat._icon_url('file:///etc/passwd'), '')
        self.assertEqual(cat._icon_url('https://dl.flathub.org/media/app/icon.png'),
                         'https://dl.flathub.org/media/app/icon.png')

    def test_untrusted_catalog_ids_and_duplicates_are_dropped(self):
        entries = cat._base_entries({'hits': [
            {'app_id': 'org.gimp.GIMP', 'name': 'GIMP'},
            {'app_id': 'org.gimp.GIMP', 'name': 'duplicate'},
            {'app_id': '../../../evil'},
            {'app_id': 'com.example.Game', 'summary': '<script>unsafe</script>'},
            {'app_id': 'http://evil.test/SomeApp'},
            {},
        ]})
        self.assertEqual([a['appId'] for a in entries],
                         ['org.gimp.GIMP', 'com.example.Game'])

    def test_malformed_search_response_rejected(self):
        with self.assertRaises(cat.CatalogError):
            cat._base_entries('not-an-array')
        self.assertEqual(cat._base_entries({'hits': 'not an array'}), [])

    def test_short_queries_do_not_touch_network(self):
        with patch.object(cat, '_json_request') as http:
            for query in ('', 'g', ' '):
                with self.assertRaises(ValueError):
                    cat.search(query)
        http.assert_not_called()


class CatalogApiTests(unittest.TestCase):
    def test_search_sends_json_to_fixed_flathub_endpoint(self):
        seen = []
        def response(url, payload=None):
            seen.append((url, payload))
            if url == cat.SEARCH_URL:
                return {'hits': [{'app_id': 'org.gimp.GIMP', 'name': 'GIMP'}]}
            return {
                'id': 'org.gimp.GIMP', 'name': 'GNU Image Manipulation Program',
                'summary': 'Image editor', 'categories': ['Graphics'],
                'icon': 'https://dl.flathub.org/media/org/gimp/GIMP/icons/gimp.png',
            }
        with patch.object(cat, '_json_request', side_effect=response):
            rows = cat.search('gimp')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['appId'], 'org.gimp.GIMP')
        self.assertEqual(rows[0]['category'], 'Graphics')
        self.assertEqual(rows[0]['summary'], 'Image editor')
        self.assertIn('/media/', rows[0]['iconUrl'])
        self.assertEqual(seen[0],
                         (cat.SEARCH_URL, {'query': 'gimp', 'filters': []}))

    def test_popular_catalog_is_dynamic_and_enriched(self):
        def response(url, payload=None):
            if url == cat.FEATURED_URL:
                return ['org.example.Painter', 'org.example.Video']
            return {'name': url.split('/')[-1], 'summary': 'Available on Flathub'}
        with patch.object(cat, '_json_request', side_effect=response):
            rows = cat.popular()
        self.assertEqual([row['appId'] for row in rows],
                         ['org.example.Painter', 'org.example.Video'])

    def test_eol_apps_are_not_shown(self):
        def response(url, payload=None):
            if url == cat.SEARCH_URL:
                return [{'app_id': 'org.example.Old'}]
            return {'is_eol': True}
        with patch.object(cat, '_json_request', side_effect=response):
            self.assertEqual(cat.search('old'), [])

    def test_failed_metadata_retains_search_results(self):
        def response(url, payload=None):
            if url == cat.SEARCH_URL:
                return [{'app_id': 'org.example.Tool', 'name': 'Tool',
                         'summary': 'Does things'}]
            raise cat.CatalogError('offline')
        with patch.object(cat, '_json_request', side_effect=response):
            rows = cat.search('tool')
        self.assertEqual(rows[0]['name'], 'Tool')
        self.assertEqual(rows[0]['iconUrl'], '')

    def test_search_results_bounded_to_24(self):
        hits=[{'app_id': f'org.example.App{i}'} for i in range(75)]
        self.assertEqual(len(cat._base_entries(hits)), cat.MAX_SEARCH_RESULTS)

    def test_refuse_network_request_to_non_flathub_host(self):
        with patch.object(cat.urllib.request, 'build_opener') as build:
            with self.assertRaises(cat.CatalogError):
                cat._json_request('https://localhost/api/v2/search')
            with self.assertRaises(cat.CatalogError):
                cat._json_request('http://flathub.org/api/v2/search')
            with self.assertRaises(cat.CatalogError):
                cat._json_request('https://flathub.org.evil.invalid/api/v2/search')
        build.assert_not_called()

    def test_oversized_or_invalid_json_response_rejected(self):
        class FakeResponse:
            def __init__(self, body, url):
                self.content = io.BytesIO(body)
                self.url = url
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return None
            def geturl(self):
                return self.url
            def read(self, n):
                return self.content.read(n)
        def mockopener(content):
            opener=Mock()
            opener.open.return_value=FakeResponse(content, cat.FEATURED_URL)
            return opener
        with patch.object(cat.urllib.request, 'build_opener',
                          return_value=mockopener(b'x' * (cat.MAX_RESPONSE_BYTES + 1))):
            with self.assertRaises(cat.CatalogError):
                cat._json_request(cat.FEATURED_URL)
        with patch.object(cat.urllib.request, 'build_opener',
                          return_value=mockopener(b'invalid json')):
            with self.assertRaises(cat.CatalogError):
                cat._json_request(cat.FEATURED_URL)

    def test_redirects_are_rejected(self):
        blocker = cat._RejectRedirects()
        with self.assertRaises(cat.CatalogError):
            blocker.redirect_request(None, None, 302, 'redirect', {},
                                     'https://169.254.169.254/latest/meta-data/')


if __name__ == '__main__':
    unittest.main()
