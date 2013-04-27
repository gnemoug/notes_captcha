from captcha.conf import settings
from captcha.models import CaptchaStore, get_safe_now
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse,  NoReverseMatch
from django.forms import ValidationError
from django.forms.fields import CharField, MultiValueField
from django.forms.widgets import TextInput, MultiWidget, HiddenInput
from django.utils.translation import ugettext_lazy as _


class CaptchaTextInput(MultiWidget):
    def __init__(self, attrs=None, **kwargs):
        self._args = kwargs
        widgets = (
            HiddenInput(attrs),
            TextInput(attrs),
        )
#output_format可以用于指定自己的验证码的输出表现，但是必须包含下面这三个
#u'%(image)s %(hidden_field)s %(text_field)s'
        for key in ('image', 'hidden_field', 'text_field'):
            if '%%(%s)s' % key not in self._args.get('output_format'):
                raise ImproperlyConfigured('All of %s must be present in your CAPTCHA_OUTPUT_FORMAT setting. Could not find %s' % (
                    ', '.join(['%%(%s)s' % k for k in ('image', 'hidden_field', 'text_field')]),
                    '%%(%s)s' % key
                ))
        super(CaptchaTextInput, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return value.split(',')
        return [None, None]

#最后调用这个函数,在调用父类的render时调用
    def format_output(self, rendered_widgets):
    #Given a list of rendered widgets (as strings), returns a Unicode string representing the HTML for the whole lot.
        hidden_field, text_field = rendered_widgets
        return self._args.get('output_format') % dict(image=self.image_and_audio, hidden_field=hidden_field, text_field=text_field)

#dummy:假的
    def render(self, name, value, attrs=None):
        try:
            reverse('captcha-image', args=('dummy',))
        except NoReverseMatch:
            raise ImproperlyConfigured('Make sure you\'ve included captcha.urls as explained in the INSTALLATION section on http://readthedocs.org/docs/django-simple-captcha/en/latest/usage.html#installation')

        challenge, response = settings.get_challenge()()
        store = CaptchaStore.objects.create(challenge=challenge, response=response)
        key = store.hashkey
        value = [key, u'']

        self.image_and_audio = '<img src="%s" alt="captcha" class="captcha" />' % reverse('captcha-image', kwargs=dict(key=key))
        if settings.CAPTCHA_FLITE_PATH:
            self.image_and_audio = '<a href="%s" title="%s">%s</a>' % (reverse('captcha-audio', kwargs=dict(key=key)), unicode(_('Play captcha as audio file')), self.image_and_audio)
        return super(CaptchaTextInput, self).render(name, value, attrs=attrs)

    # This is probably all the love it needs
    def id_for_label(self, id_):
        return id_ + '_1'


class CaptchaField(MultiValueField):
    def __init__(self, *args, **kwargs):
        fields = (
            CharField(show_hidden_initial=True),
            CharField(),
        )
        
        ############更改了默认的invalid对应的提示语句###############
        if 'error_messages' not in kwargs or 'invalid' not in kwargs.get('error_messages'):
            if 'error_messages' not in kwargs:
                kwargs['error_messages'] = dict()
            kwargs['error_messages'].update(dict(invalid=_('Invalid CAPTCHA')))

        #决定表单项目内容
        widget_kwargs = dict(
            output_format=kwargs.get('output_format', None) or settings.CAPTCHA_OUTPUT_FORMAT
        )
        
        for k in ('output_format',):
            if k in kwargs:
                del(kwargs[k])
        super(CaptchaField, self).__init__(fields=fields, widget=CaptchaTextInput(**widget_kwargs), *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            return ','.join(data_list)
        return None

    #用于表单验证时
    def clean(self, value):
        super(CaptchaField, self).clean(value)
        response, value[1] = value[1].strip().lower(), ''
        CaptchaStore.remove_expired()
        try:#判断是否还有未过期的项目
            store = CaptchaStore.objects.get(response=response, hashkey=value[0], expiration__gt=get_safe_now())
            store.delete()
        except Exception:
            raise ValidationError(getattr(self, 'error_messages', dict()).get('invalid', _('Invalid CAPTCHA')))
        return value
