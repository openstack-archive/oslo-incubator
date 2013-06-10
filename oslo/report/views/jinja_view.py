from jinja2 import Template


class JinjaView(object):
    def __init__(self, path=None, text=None):
        try:
            self._text = self.VIEW_TEXT
        except AttributeError:
            if path is not None:
                with open(path, 'r') as f:
                    self._text = f.read()
            elif text is not None:
                self._text = text
            else:
                self._text = ""

        if self._text[0] == "\n":
            self._text = self._text[1:]

        newtext = self._text.lstrip()
        amt = len(self._text) - len(newtext)
        if (amt > 0):
            base_indent = self._text[0:amt]
            lines = self._text.splitlines()
            newlines = []
            for line in lines:
                if line.startswith(base_indent):
                    newlines.append(line[amt:])
                else:
                    newlines.append(line)
            self._text = "\n".join(newlines)

        if self._text[-1] == "\n":
            self._text = self._text[:-1]

        self._regentemplate = True
        self._templatecache = None

    def __call__(self, model):
        return self.template.render(**model)

    def _gettemplate(self):
        if self._templatecache is None or self._regentemplate:
            self._templatecache = Template(self._text)
            self._regentemplate = False

        return self._templatecache

    def _gettext(self):
        return self._text

    def _settext(self, textval):
        self._text = textval
        self.regentemplate = True

    template = property(_gettemplate)
    text = property(_gettext, _settext)
