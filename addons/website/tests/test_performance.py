# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import HttpCase

EXTRA_REQUEST = 4 - 1
""" During tests, the query on 'base_registry_signaling, base_cache_signaling'
won't be executed on hot state, but new queries related to the test cursor
will be added::

    cr = Cursor() # SAVEPOINT
    cr.commit() # RELEASE
    cr.close()
    cr = Cursor()
    cr.execute(...) # SAVEPOINT
    cr.commit() # RELEASE
    cr.close()
"""


class UtilPerf(HttpCase):
    def _get_url_hot_query(self, url, cache=True):
        url += ('?' not in url and '?' or '')
        if not cache:
            url += '&nocache'

        # ensure worker is in hot state
        self.url_open(url)
        self.url_open(url)

        sql_count = self.registry.test_cr.sql_log_count
        self.url_open(url)
        return self.registry.test_cr.sql_log_count - sql_count - EXTRA_REQUEST


class TestStandardPerformance(UtilPerf):
    def test_10_perf_sql_img_controller(self):
        self.authenticate('demo', 'demo')
        # not published user, get the not found image placeholder
        self.assertEqual(self.env['res.users'].sudo().browse(2).website_published, False)
        url = '/web/image/res.users/2/image_256'
        self.assertEqual(self._get_url_hot_query(url), 6)
        self.assertEqual(self._get_url_hot_query(url, cache=False), 6)

    def test_11_perf_sql_img_controller(self):
        self.authenticate('demo', 'demo')
        self.env['res.users'].sudo().browse(2).website_published = True
        url = '/web/image/res.users/2/image_256'
        self.assertEqual(self._get_url_hot_query(url), 5)
        self.assertEqual(self._get_url_hot_query(url, cache=False), 5)

    def test_20_perf_sql_img_controller_bis(self):
        url = '/web/image/website/1/favicon'
        self.assertEqual(self._get_url_hot_query(url), 4)
        self.assertEqual(self._get_url_hot_query(url, cache=False), 4)
        self.authenticate('portal', 'portal')
        self.assertEqual(self._get_url_hot_query(url), 4)
        self.assertEqual(self._get_url_hot_query(url, cache=False), 4)


class TestWebsitePerformance(UtilPerf):

    def setUp(self):
        super().setUp()
        self.page, self.menu = self._create_page_with_menu('/sql_page')

    def _create_page_with_menu(self, url):
        name = url[1:]
        website = self.env['website'].browse(1)
        page = self.env['website.page'].create({
            'url': url,
            'name': name,
            'type': 'qweb',
            'arch': '<t name="%s" t-name="website.page_test_%s"> \
                       <t t-call="website.layout"> \
                         <div id="wrap"><div class="oe_structure"/></div> \
                       </t> \
                     </t>' % (name, name),
            'key': 'website.page_test_%s' % name,
            'is_published': True,
            'website_id': website.id,
            'track': False,
        })
        menu = self.env['website.menu'].create({
            'name': name,
            'url': url,
            'page_id': page.id,
            'website_id': website.id,
            'parent_id': website.menu_id.id
        })
        return (page, menu)

    def test_10_perf_sql_queries_page(self):
        # standard untracked website.page
        self.assertEqual(self._get_url_hot_query(self.page.url), 7)
        self.assertEqual(self._get_url_hot_query(self.page.url, cache=False), 10)
        self.menu.unlink()
        self.assertEqual(self._get_url_hot_query(self.page.url), 9)
        self.assertEqual(self._get_url_hot_query(self.page.url, cache=False), 12)

    def test_15_perf_sql_queries_page(self):
        # standard tracked website.page
        self.page.track = True
        self.assertEqual(self._get_url_hot_query(self.page.url), 15)
        self.assertEqual(self._get_url_hot_query(self.page.url, cache=False), 18)
        self.menu.unlink()
        self.assertEqual(self._get_url_hot_query(self.page.url), 17)
        self.assertEqual(self._get_url_hot_query(self.page.url, cache=False), 20)

    def test_20_perf_sql_queries_homepage(self):
        # homepage "/" has its own controller
        self.assertEqual(self._get_url_hot_query('/'), 14)
        self.assertEqual(self._get_url_hot_query('/', cache=False), 17)

    def test_30_perf_sql_queries_page_no_layout(self):
        # website.page with no call to layout templates
        self.page.arch = '<div>I am a blank page</div>'
        self.assertEqual(self._get_url_hot_query(self.page.url), 7)
        self.assertEqual(self._get_url_hot_query(self.page.url, cache=False), 7)

    def test_40_perf_sql_queries_page_multi_level_menu(self):
        # menu structure should not impact SQL requests
        _, menu_a = self._create_page_with_menu('/a')
        _, menu_aa = self._create_page_with_menu('/aa')
        _, menu_b = self._create_page_with_menu('/b')
        _, menu_bb = self._create_page_with_menu('/bb')
        _, menu_bbb = self._create_page_with_menu('/bbb')
        _, menu_bbbb = self._create_page_with_menu('/bbbb')
        _, menu_bbbbb = self._create_page_with_menu('/bbbbb')
        self._create_page_with_menu('c')
        menu_bbbbb.parent_id = menu_bbbb
        menu_bbbb.parent_id = menu_bbb
        menu_bbb.parent_id = menu_bb
        menu_bb.parent_id = menu_b
        menu_aa.parent_id = menu_a

        self.assertEqual(self._get_url_hot_query(self.page.url), 7)
        self.assertEqual(self._get_url_hot_query(self.page.url, cache=False), 10)

    def test_50_perf_sql_web_assets(self):
        # assets route /web/assets/..
        self.url_open('/')  # create assets attachments
        assets_url = self.env['ir.attachment'].search([('url', '=like', '/web/assets/%/web.assets_common%.js')], limit=1).url
        self.assertEqual(self._get_url_hot_query(assets_url), 2)
        self.assertEqual(self._get_url_hot_query(assets_url, cache=False), 2)
