from views.text.header_view import TitledView


class BasicReport(object):
    def __init__(self):
        self.sections = []
        self._state = 0

    def add_section(self, view, generator, index=None):
        if (index is None):
            self.sections.append(ReportSection(view, generator))
        else:
            self.sections.insert(index, ReportSection(view, generator))

    def run(self):
        return "\n".join(str(sect) for sect in self.sections)


class ReportOfType(BasicReport):
    def __init__(self, tp):
        self.output_type = tp
        super(ReportOfType, self).__init__()

    def add_section(self, view, generator, index=None):
        def with_type(gen):
            def newgen():
                res = gen()
                try:
                    res.set_current_view_type(self.output_type)
                except AttributeError:
                    pass

                return res
            return newgen

        super(ReportOfType, self).add_section(
            view,
            with_type(generator),
            index
        )


class TextReport(BasicReport):
    def __init__(self, name):
        super(TextReport, self).__init__()
        self.name = name
        # add a title with a generator that creates an empty result model
        self.add_section(name, lambda: ('|' * 72) + "\n\n")

    def add_section(self, heading, generator, index=None):
        def with_text(generator):
            def gen():
                res = generator()
                try:
                    res.set_current_view_type('text')
                except AttributeError:
                    pass

                return res

            return gen

        super(TextReport, self).add_section(
            TitledView(heading),
            with_text(generator),
            index
        )


class ReportSection(object):
    def __init__(self, view, generator):
        self.view = view
        self.generator = generator

    def __str__(self):
        return self.view(self.generator())
