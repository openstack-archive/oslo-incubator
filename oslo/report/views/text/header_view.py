class HeaderView(object):
    """A simple view that renders the given
       header above the any model that it
       is called with.
    """

    def __init__(self, header):
        self.header = header

    def __call__(self, model):
        return str(self.header) + "\n" + str(model)


class TitledView(HeaderView):
    """A simplified version of header view that
       automatically formats the given title
       into an appropriate header
    """

    FORMAT_STR = ('=' * 72) + "\n" + "===={: ^64}====" + "\n" + ('=' * 72)

    def __init__(self, title):
        super(TitledView, self).__init__(self.FORMAT_STR.format(title))
