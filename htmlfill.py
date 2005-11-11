import HTMLParser
import cgi
import re

class htmlliteral(object):

    def __init__(self, html, text=None):
        if text is None:
            text = re.sub(r'<.*?>', '', html)
            text = html.replace('&gt;', '>')
            text = html.replace('&lt;', '<')
            text = html.replace('&quot;', '"')
            # @@: Not very complete
        self.html = html
        self.text = text

    def __str__(self):
        return self.text

    def __repr__(self):
        return '<%s html=%r text=%r>' % (self.html, self.text)

    def __html__(self):
        return self.html

def html_quote(v):
    if v is None:
        return ''
    elif hasattr(v, '__html__'):
        return v.__html__()
    else:
        return cgi.escape(str(v), 1)

def default_formatter(error):
    return '<span class="error-message">%s</span><br />\n' % html_quote(error)

def none_formatter(error):
    return error

def escape_formatter(error):
    return html_quote(error, 1)

class FillingParser(HTMLParser.HTMLParser):
    r"""
    Fills HTML with default values, as in a form.

    Examples::

        >>> defaults = {'name': 'Bob Jones',
        ...             'occupation': 'Crazy Cultist',
        ...             'address': '14 W. Canal\nNew Guinea',
        ...             'living': 'no',
        ...             'nice_guy': 0}
        >>> parser = FillingParser(defaults)
        >>> parser.feed('<input type="text" name="name" value="fill">\
        ... <select name="occupation"><option value="">Default</option>\
        ... <option value="Crazy Cultist">Crazy cultist</option>\
        ... </select> <textarea cols=20 style="width: 100%" name="address">An address\
        ... </textarea> <input type="radio" name="living" value="yes">\
        ... <input type="radio" name="living" value="no">\
        ... <input type="checkbox" name="nice_guy" checked="checked">')
        >>> print parser.text()
        <input type="text" name="name" value="Bob Jones">
        <select name="occupation">
        <option value="">Default</option>
        <option value="Crazy Cultist" selected="selected">Crazy cultist</option>
        </select>
        <textarea cols=20 style="width: 100%" name="address">14 W. Canal
        New Guinea</textarea>
        <input type="radio" name="living" value="yes">
        <input type="radio" name="living" value="no" selected="selected">
        <input type="checkbox" name="nice_guy">
    """

    def __init__(self, defaults, errors=None, use_all_keys=False,
                 error_formatters=None, error_class='error',
                 add_attributes=None, listener=None,
                 auto_error_formatter=None):
        HTMLParser.HTMLParser.__init__(self)
        self._content = []
        self.source = None
        self.lines = None
        self.source_pos = None
        self.defaults = defaults
        self.in_textarea = None
        self.in_select = None
        self.skip_next = False        
        self.errors = errors or {}
        if isinstance(self.errors, (str, unicode)):
            self.errors = {None: self.errors}
        self.in_error = None
        self.skip_error = False
        self.use_all_keys = use_all_keys
        self.used_keys = {}
        self.used_errors = {}
        if error_formatters is None:
            self.error_formatters = {'default': default_formatter,
                                     'none': none_formatter,
                                     'escape': escape_formatter}
        else:
            self.error_formatters = error_formatters
        self.error_class = error_class
        self.add_attributes = add_attributes or {}
        self.listener = listener
        self.auto_error_formatter = auto_error_formatter

    def feed(self, data):
        self.source = data
        self.lines = data.split('\n')
        self.source_pos = 1, 0
        if self.listener:
            self.listener.reset()
        HTMLParser.HTMLParser.feed(self, data)

    def close(self):
        HTMLParser.HTMLParser.close(self)
        unused_errors = self.errors.copy()
        for key in self.used_errors.keys():
            if unused_errors.has_key(key):
                del unused_errors[key]
        print "UNUSED", unused_errors, self.errors
        if self.auto_error_formatter:
            for key, value in unused_errors.items():
                print 'insert at', key, value
                self.insert_at_marker(
                    key, self.auto_error_formatter(value))
            unused_errors = {}
        if self.use_all_keys:
            unused = self.defaults.copy()
            for key in self.used_keys.keys():
                if unused.has_key(key):
                    del unused[key]
            assert not unused, (
                "These keys from defaults were not used in the form: %s"
                % unused.keys())
            if unused_errors:
                error_text = []
                for key in unused_errors.keys():
                    error_text.append("%s: %s" % (key, self.errors[key]))
                assert False, (
                    "These errors were not used in the form: %s" % 
                    ', '.join(error_text))
        self._text = ''.join([
            t for t in self._content if not isinstance(t, tuple)])

    def add_key(self, key):
        self.used_keys[key] = 1

    def handle_starttag(self, tag, attrs, startend=False):
        self.write_pos()
        if tag == 'input':
            self.handle_input(attrs, startend)
        elif tag == 'textarea':
            self.handle_textarea(attrs)
        elif tag == 'select':
            self.handle_select(attrs)
        elif tag == 'option':
            self.handle_option(attrs)
            return
        elif tag == 'form:error':
            self.handle_error(attrs)
            return
        elif tag == 'form:iferror':
            self.handle_iferror(attrs)
            return
        else:
            return
        if self.listener:
            self.listener.listen_input(self, tag, attrs)

    def handle_misc(self, whatever):
        self.write_pos()
    handle_charref = handle_misc
    handle_entityref = handle_misc
    handle_data = handle_misc
    handle_comment = handle_misc
    handle_decl = handle_misc
    handle_pi = handle_misc
    unknown_decl = handle_misc

    def handle_endtag(self, tag):
        self.write_pos()
        if tag == 'textarea':
            self.handle_end_textarea()
        elif tag == 'select':
            self.handle_end_select()
        elif tag == 'form:iferror':
            self.handle_end_iferror()

    def handle_startendtag(self, tag, attrs):
        return self.handle_starttag(tag, attrs, True)

    def handle_iferror(self, attrs):
        name = self.get_attr(attrs, 'name')
        assert name, "Name attribute in <iferror> required (%s)" % self.getpos()
        self.in_error = name
        if not self.errors.get(name):
            self.skip_error = True
        self.skip_next = True

    def handle_end_iferror(self):
        self.in_error = None
        self.skip_error = False
        self.skip_next = True

    def handle_error(self, attrs):
        name = self.get_attr(attrs, 'name')
        formatter = self.get_attr(attrs, 'format') or 'default'
        if name is None:
            name = self.in_error
        assert name is not None, (
            "Name attribute in <form:error> required if not contained in "
            "<form:iferror> (%i:%i)" % self.getpos())
        error = self.errors.get(name, '')
        if error:
            error = self.error_formatters[formatter](error)
            self.write_text(error)
        self.skip_next = True
        self.used_errors[name] = 1

    def handle_input(self, attrs, startend):
        t = (self.get_attr(attrs, 'type') or 'text').lower()
        name = self.get_attr(attrs, 'name')
        self.write_marker(name)
        value = self.defaults.get(name)
        if self.add_attributes.has_key(name):
            for attr_name, attr_value in self.add_attributes[name].items():
                if attr_name.startswith('+'):
                    attr_name = attr_name[1:]
                    self.set_attr(attrs, attr_name,
                                  self.get_attr(attrs, attr_name, '')
                                  + attr_value)
                else:
                    self.set_attr(attrs, attr_name, attr_value)
        if (self.error_class
            and self.errors.get(self.get_attr(attrs, 'name'))):
            self.add_class(attrs, self.error_class)
        if t in ('text', 'hidden'):
            if value is None:
                value = self.get_attr(attrs, 'value', '')
            self.set_attr(attrs, 'value', value)
            self.write_tag('input', attrs, startend)
            self.skip_next = True
            self.add_key(name)
        elif t == 'checkbox':
            if (str(value) == self.get_attr(attrs, 'value')
                or (self.get_attr(attrs, 'value') is None
                    and value)
                or (isinstance(value, (list, tuple))
                    and self.get_attr(attrs, 'value') in map(str, value))):
                self.set_attr(attrs, 'checked', 'checked')
            else:
                self.del_attr(attrs, 'checked')
            self.write_tag('input', attrs, startend)
            self.skip_next = True
            self.add_key(name)
        elif t == 'radio':
            if str(value) == self.get_attr(attrs, 'value'):
                self.set_attr(attrs, 'checked', 'checked')
            else:
                self.del_attr(attrs, 'checked')
            self.write_tag('input', attrs, startend)
            self.skip_next = True
            self.add_key(name)
        elif t == 'file':
            pass # don't skip next
        elif t == 'password':
            self.set_attr(attrs, 'value', value or
                          self.get_attr(attrs, 'value', ''))
            self.write_tag('input', attrs, startend)
            self.skip_next = True
            self.add_key(name)
        elif t == 'image':
            self.set_attr(attrs, 'src', value or
                          self.get_attr(attrs, 'src', ''))
            self.write_tag('input', attrs, startend)
            self.skip_next = True
            self.add_key(name)
        elif t == 'submit' or t == 'reset' or t == 'button':
            self.set_attr(attrs, 'value', value or
                          self.get_attr(attrs, 'value', ''))
            self.write_tag('input', attrs, startend)
            self.skip_next = True
            self.add_key(name)
        else:
            assert 0, "I don't know about this kind of <input>: %s (pos: %s)" \
                   % (t, self.getpos())

    def handle_textarea(self, attrs):
        name = self.get_attr(attrs, 'name')
        self.write_marker(name)
        if (self.error_class
            and self.errors.get(name)):
            self.add_class(attrs, self.error_class)
        self.write_tag('textarea', attrs)
        value = self.defaults.get(name, '')
        self.write_text(html_quote(value))
        self.write_text('</textarea>')
        self.in_textarea = True
        self.add_key(name)

    def handle_end_textarea(self):
        self.in_textarea = False
        self.skip_next = True

    def handle_select(self, attrs):
        name = self.get_attr(attrs, 'name')
        self.write_marker(name)
        if (self.error_class
            and self.errors.get(name)):
            self.add_class(attrs, self.error_class)
        self.in_select = self.get_attr(attrs, 'name')
        self.write_tag('select', attrs)
        self.skip_next = True
        self.add_key(self.in_select)

    def handle_end_select(self):
        self.in_select = None

    def handle_option(self, attrs):
        assert self.in_select, "<option> outside of <select>: %s" % self.getpos()
        if str(self.defaults.get(self.in_select, '')) == \
               self.get_attr(attrs, 'value'):
            self.set_attr(attrs, 'selected', 'selected')
            self.add_key(self.in_select)
        else:
            self.del_attr(attrs, 'selected')
        self.write_tag('option', attrs)
        self.skip_next = True

    def write_text(self, text):
        self._content.append(text)

    def write_marker(self, marker):
        self._content.append((marker,))

    def insert_at_marker(self, marker, text):
        for i, item in enumerate(self._content):
            if item == (marker,):
                self._content.insert(i, text)
                break
        else:
            raise ValueError(
                "Marker %r not found when trying to insert %r"
                % (marker, text))

    def write_tag(self, tag, attrs, startend=False):
        attr_text = ''.join([' %s="%s"' % (n, html_quote(v))
                             for (n, v) in attrs
                             if not n.startswith('form:')])
        if startend:
            attr_text += " /"
        self.write_text('<%s%s>' % (tag, attr_text))

    def write_pos(self):
        cur_line, cur_offset = self.getpos()
        if self.in_textarea or self.skip_error:
            self.source_pos = self.getpos()
            return
        if self.skip_next:
            self.skip_next = False
            self.source_pos = self.getpos()
            return
        if cur_line == self.source_pos[0]:
            self.write_text(
                self.lines[cur_line-1][self.source_pos[1]:cur_offset])
        else:
            self.write_text(
                self.lines[self.source_pos[0]-1][self.source_pos[1]:])
            self.write_text('\n')
            for i in range(self.source_pos[0]+1, cur_line):
                self.write_text(self.lines[i-1])
                self.write_text('\n')
            self.write_text(self.lines[cur_line-1][:cur_offset])
        self.source_pos = self.getpos()

    def get_attr(self, attr, name, default=None):
        for n, value in attr:
            if n.lower() == name:
                return value
        return default

    def set_attr(self, attr, name, value):
        for i in range(len(attr)):
            if attr[i][0].lower() == name:
                attr[i] = (name, value)
                return
        attr.append((name, value))

    def del_attr(self, attr, name):
        for i in range(len(attr)):
            if attr[i][0].lower() == name:
                del attr[i]
                break

    def add_class(self, attr, class_name):
        current = self.get_attr(attr, 'class', '')
        new = current + ' ' + class_name
        self.set_attr(attr, 'class', new.strip())
            
    def text(self):
        return self._text
