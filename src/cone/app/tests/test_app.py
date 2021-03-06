from cone.app import main_hook
from cone.app import make_remote_addr_middleware
from cone.app.model import BaseNode
from node.tests import NodeTestCase
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.router import Router
from pyramid.static import static_view
from yafowil import resources
from yafowil.base import factory as yafowil_factory
import cone.app


class TestApp(NodeTestCase):

    def test_get_root(self):
        root = cone.app.get_root()
        self.assertTrue(str(root).startswith("<AppRoot object 'None' at"))

        # AppRoot contains a settings node by default
        self.assertTrue('settings' in root.factories.keys())

        # Settings contains metadata.title by default
        self.assertEqual(list(root['settings'].metadata.keys()), ['title'])
        self.assertEqual(root['settings'].metadata.title, u'settings')

        # Settings is displayed in navtree by default
        self.assertEqual(
            sorted(root['settings'].properties.keys()),
            ['icon', 'in_navtree', 'skip_mainmenu']
        )
        self.assertFalse(root['settings'].properties.in_navtree)
        self.assertTrue(root['settings'].properties.skip_mainmenu)

    def test_register_plugin(self):
        cone.app.register_plugin('dummy', BaseNode)

        root = cone.app.get_root()
        self.assertTrue('dummy' in root.factories.keys())

        err = self.expect_error(
            ValueError,
            lambda: cone.app.register_plugin('dummy', BaseNode)
        )
        expected = "Entry with name 'dummy' already registered."
        self.assertEqual(str(err), expected)

    def test_register_plugin_config(self):
        cone.app.register_plugin_config('dummy', BaseNode)

        root = cone.app.get_root()
        self.assertTrue('dummy' in root['settings'].factories.keys())

        err = self.expect_error(
            ValueError,
            lambda: cone.app.register_plugin_config('dummy', BaseNode)
        )
        expected = "Config with name 'dummy' already registered."
        self.assertEqual(str(err), expected)

    def test_main(self):
        # main hook
        hooks = dict(called=0)

        def custom_main_hook(configurator, global_config, settings):
            hooks['called'] += 1

        cone.app.register_main_hook(custom_main_hook)

        @main_hook
        def decorated_main_hook(configurator, global_config, settings):
            hooks['called'] += 1

        # set auth tkt factory``
        factory = cone.app.auth_tkt_factory(secret='12345')
        self.assertTrue(isinstance(factory, AuthTktAuthenticationPolicy))

        # ACL factory
        factory = cone.app.acl_factory()
        self.assertTrue(isinstance(factory, ACLAuthorizationPolicy))

        # yafowil resources
        def dummy_get_plugin_names(ns=None):
            return ['yafowil.addon']

        get_plugin_names_origin = resources.get_plugin_names
        resources.get_plugin_names = dummy_get_plugin_names

        yafowil_addon_name = 'yafowil.addon'
        js = [{
            'group': 'yafowil.addon.common',
            'resource': 'widget.js',
            'order': 20,
        }]
        css = [{
            'group': 'yafowil.addon.common',
            'resource': 'widget.css',
            'order': 20,
        }]
        yafowil_factory.register_theme(
            'default',
            yafowil_addon_name,
            'yafowil_addon_resources',
            js=js,
            css=css
        )

        # settings
        settings = {
            'cone.admin_user': 'admin',
            'cone.admin_password': 'admin',
            'cone.auth_secret': '12345',
            'cone.auth_reissue_time': '300',
            'cone.auth_max_age': '600',
            'cone.plugins': 'cone.app.tests'  # ensure dummy main hooks called
        }

        # main
        router = cone.app.main({}, **settings)
        self.assertTrue(isinstance(router, Router))
        self.assertEqual(hooks['called'], 2)

        # Remove custom main hook after testing
        cone.app.main_hooks.remove(custom_main_hook)
        cone.app.main_hooks.remove(decorated_main_hook)

        # Check created yafowil addon static view
        self.assertTrue(isinstance(
            cone.app.yafowil_addon_resources,
            static_view
        ))

        # Remove dummy yafowil theme, reset get_plugin_names patch
        # and delete created yafowil addon static view
        resources.get_plugin_names = get_plugin_names_origin
        del yafowil_factory._themes['default'][yafowil_addon_name]
        del cone.app.yafowil_addon_resources

    def test_remote_addr_middleware(self):
        # Remote address middleware
        class DummyApp(object):
            remote_addr = None

            def __call__(self, environ, start_response):
                self.remote_addr = environ['REMOTE_ADDR']

        app = DummyApp()
        middleware = make_remote_addr_middleware(app, {})

        environ = {}
        environ['HTTP_X_REAL_IP'] = '1.2.3.4'
        middleware(environ, None)
        self.assertEqual(app.remote_addr, '1.2.3.4')
