from cone.app import testing
from cone.app.browser.ajax import AjaxAction
from cone.app.browser.form import Form
from cone.app.browser.form import ProtectedAttributesForm
from cone.app.browser.form import YAMLForm
from cone.app.model import BaseNode
from cone.tile import render_tile
from cone.tile import tile
from cone.tile.tests import TileTestCase
from plumber import plumbing
from pyramid.security import ACLAllowed
from pyramid.security import ACLDenied
from webob.exc import HTTPFound
from yafowil.base import factory


class TestBrowserForm(TileTestCase):
    layer = testing.security

    def test_Form(self):
        formtile = Form(None, None, 'plainform')
        err = self.expectError(
            NotImplementedError,
            formtile.prepare
        )
        expected = '``prepare`` function must be provided by deriving object.'
        self.assertEqual(str(err), expected)

        subscriptions = []

        with self.layer.hook_tile_reg():
            @tile(name='subscriptionform')
            class SubscriptionForm(Form):
                _ajax = False  # test flag
                _show = False  # test flag

                @property
                def ajax(self):
                    return self._ajax

                @property
                def show(self):
                    return self._show

                def prepare(self):
                    form = factory(
                        u'form',
                        name='subscriptionform',
                        props={
                            'action': self.nodeurl
                        })
                    form['email'] = factory(
                        'field:label:error:text',
                        props={
                            'required': 'No email given',
                            'label': 'E-Mail',
                        })
                    form['subscribe'] = factory(
                        'submit',
                        props={
                            'action': 'subscribe',
                            'expression': True,
                            'handler': self.subscribe,
                            'next': self.next,
                            'label': 'Subscribe',
                        })
                    self.form = form

                def subscribe(self, widget, data):
                    # Do subscription here
                    subscriptions.append('subscribe on "%s"' % self.model.name)

                def next(self, request):
                    url = 'http://example.com'
                    if self.ajax_request:
                        # return as single value, gets list on request.environ
                        return AjaxAction(url, 'content', 'inner', '#content')
                    return HTTPFound(url)

        model = BaseNode()
        model.__name__ = 'dummymodel'
        request = self.layer.new_request()

        # Render form. ``form.show`` returns false, render empty string
        with self.layer.authenticated('max'):
            rendered = render_tile(model, request, 'subscriptionform')
            self.assertEqual(rendered, u'')

        # Set show to True
        SubscriptionForm._show = True
        # Render form. no action is triggered and no input is given
        with self.layer.authenticated('max'):
            rendered = render_tile(model, request, 'subscriptionform')

        expected = 'action="http://example.com/dummymodel"'
        self.assertTrue(rendered.find(expected) != -1)

        expected = 'id="form-subscriptionform"'
        self.assertTrue(rendered.find(expected) != -1)

        expected = 'name="subscriptionform.email"'
        self.assertTrue(rendered.find(expected) != -1)

        expected = 'name="action.subscriptionform.subscribe"'
        self.assertTrue(rendered.find(expected) != -1)

        # Trigger subscribe action and set empty email value. Results in a form
        # with error message since email is required
        request.params['action.subscriptionform.subscribe'] = '1'
        request.params['subscriptionform.email'] = ''

        with self.layer.authenticated('max'):
            rendered = render_tile(model, request, 'subscriptionform')

        expected = 'No email given'
        self.assertTrue(rendered.find(expected) != -1)

        # Trigger subscribe action and set valid email value. Now the action
        # handler and next handler are triggered
        request.params['subscriptionform.email'] = 'john.doe@example.com'

        with self.layer.authenticated('max'):
            rendered = render_tile(model, request, 'subscriptionform')

        self.assertEqual(subscriptions, ['subscribe on "dummymodel"'])
        subscriptions = []

        # The form was rendered as non ajax form, so we expect an HTTPFound
        # instance on request
        self.assertTrue(isinstance(request.environ['redirect'], HTTPFound))

        del request.environ['redirect']

        # Even if we commit as ajax form, it is treaten as normal form since
        # ajax flag is set to False (defaults to True)
        request.params['ajax'] = '1'
        with self.layer.authenticated('max'):
            rendered = render_tile(model, request, 'subscriptionform')

        self.assertEqual(subscriptions, ['subscribe on "dummymodel"'])
        subscriptions = []

        self.assertTrue(isinstance(request.environ['redirect'], HTTPFound))

        del request.environ['redirect']
        del request.params['ajax']

        # Try with ajax True. First if submitted without ajax flag, still
        # expect HTTPFound instance
        SubscriptionForm._ajax = True
        with self.layer.authenticated('max'):
            rendered = render_tile(model, request, 'subscriptionform')

        self.assertEqual(subscriptions, ['subscribe on "dummymodel"'])
        subscriptions = []

        self.assertTrue(isinstance(request.environ['redirect'], HTTPFound))

        # Submit with ajax flag
        request.params['ajax'] = '1'
        with self.layer.authenticated('max'):
            rendered = render_tile(model, request, 'subscriptionform')

        self.assertEqual(subscriptions, ['subscribe on "dummymodel"'])
        subscriptions = []

        self.assertTrue(isinstance(
            request.environ['cone.app.continuation'][0],
            AjaxAction
        ))

    def test_YAMLForm(self):
        with self.layer.hook_tile_reg():
            @tile(name='yamlsubscriptionform')
            @plumbing(YAMLForm)
            class YAMLSubscriptionForm(Form):
                action_resource = 'yamlsubscriptionform'
                form_template = 'cone.app.testing:dummy_form.yaml'

        model = BaseNode()
        model.__name__ = 'dummymodel'
        request = self.layer.new_request()

        with self.layer.authenticated('max'):
            rendered = render_tile(model, request, 'yamlsubscriptionform')

        expected = (
            'action="http://example.com/dummymodel/yamlsubscriptionform"'
        )
        self.assertTrue(rendered.find(expected) > -1)

        # Instead of ``form_template`` attribute, ``form_template_path`` can be
        # used for backward compatibility
        with self.layer.hook_tile_reg():
            @tile(name='yamlsubscriptionform2')
            class YAMLSubscriptionForm2(YAMLSubscriptionForm):
                action_resource = 'yamlsubscriptionform2'
                form_template = None
                form_template_path = 'cone.app.testing:dummy_form.yaml'

        with self.layer.authenticated('max'):
            rendered = render_tile(model, request, 'yamlsubscriptionform2')

        expected = (
            'action="http://example.com/dummymodel/yamlsubscriptionform2"'
        )
        self.assertTrue(rendered.find(expected) > -1)

    def test_ProtectedAttributesForm(self):
        # ProtectedAttributesForm plumbing behavior
        with self.layer.hook_tile_reg():
            @tile(name='protectedattributesform')
            @plumbing(ProtectedAttributesForm)
            class MyProtectedAttributesForm(Form):
                attribute_permissions = {
                    'protectedfield': ('manage', 'edit')
                }

                def prepare(self):
                    form = factory(
                        u'form',
                        name='protectedattributesform',
                        props={
                            'action': self.nodeurl,
                        })
                    form['protectedfield'] = factory(
                        u'field:label:text',
                        value=u'Protectedfield',
                        mode=self.mode_for('protectedfield')
                    )
                    self.form = form

        model = BaseNode()
        model.__name__ = 'dummymodel'
        request = self.layer.new_request()

        with self.layer.authenticated('viewer'):
            rule = request.has_permission('edit', model)
            self.assertTrue(isinstance(rule, ACLDenied))
            rendered = render_tile(model, request, 'protectedattributesform')

        self.checkOutput("""
        <form
        action="http://example.com/dummymodel"
        class="ajax"
        enctype="multipart/form-data"
        id="form-protectedattributesform"
        method="post"
        novalidate="novalidate"></form>
        """, rendered)

        with self.layer.authenticated('editor'):
            rule = request.has_permission('edit', model)
            self.assertTrue(isinstance(rule, ACLAllowed))
            rendered = render_tile(model, request, 'protectedattributesform')

        self.checkOutput("""
        <form ...<div class="display-text"
        id="display-protectedattributesform-protectedfield">Protectedfield</div></div></form>
        """, rendered)

        with self.layer.authenticated('manager'):
            rule = request.has_permission('manage', model)
            self.assertTrue(isinstance(rule, ACLAllowed))
            rendered = render_tile(model, request, 'protectedattributesform')

        self.checkOutput("""
        <form ...<input class="text"
        id="input-protectedattributesform-protectedfield"
        name="protectedattributesform.protectedfield"
        type="text" value="Protectedfield" /></div></form>
        """, rendered)

    def test_form_misc(self):
        with self.layer.hook_tile_reg():
            @tile(name='otherform')
            class OtherForm(Form):

                def prepare(self):
                    form = factory(
                        u'form',
                        name='otherform',
                        props={
                            'action': self.nodeurl,
                            # if class is set and ajax is true class 'ajax'
                            # gets added to existing class
                            'class': 'foo'
                        })
                    form['save'] = factory(
                        'submit',
                        props={
                            'action': 'save',
                            'expression': True,
                            'handler': None,
                            'next': self.next,
                            'label': 'Save',
                        })
                    self.form = form

                def next(self, request):
                    url = 'http://example.com'
                    if self.ajax_request:
                        # return as list
                        return [AjaxAction(url, 'content', 'inner', '#content')]
                    # return anything else to be rendered
                    return '<div>foo</div>'

        model = BaseNode()
        model.__name__ = 'dummymodel'
        request = self.layer.new_request()

        with self.layer.authenticated('max'):
            request = self.layer.new_request()
            request.params['action.otherform.save'] = '1'
            self.assertEqual(
                render_tile(model, request, 'otherform'),
                '<div>foo</div>'
            )

            request.params['ajax'] = '1'
            self.assertEqual(render_tile(model, request, 'otherform'), u'')

        self.assertTrue(isinstance(
            request.environ['cone.app.continuation'][0],
            AjaxAction
        ))
