from oslo.report.views.jinja_view import JinjaView


class StackTraceView(JinjaView):

    # Can't use a docstring here b/c line too long (as per pep8)
    VIEW_TEXT = (
        "{% if root_exception is not none %}" +
        "Exception: {{ root_exception }}\n" +
        "------------------------------------\n" +
        "\n" +
        "{% endif %}" +
        "{% for line in lines %}\n" +
        "{{ line.filename }}:{{ line.line }} in {{ line.name }}\n" +
        "    {% if line.code is not none %}" +
        "`{{ line.code }}`" +
        "{% else %}" +
        "(source not found)" +
        "{% endif %}\n" +
        "{% else %}\n" +
        "No Traceback!\n" +
        "{% endfor %}"
    )


class GreenThreadView(object):
    FORMAT_STR = "------{thread_str: ^60}------" + "\n" + "{stack_trace}"

    def __call__(self, model):
        return self.FORMAT_STR.format(
            thread_str=" Green Thread ",
            stack_trace=model.stack_trace
        )


class ThreadView(object):
    FORMAT_STR = "------{thread_str: ^60}------" + "\n" + "{stack_trace}"

    def __call__(self, model):
        return self.FORMAT_STR.format(
            thread_str=" Thread #{0} ".format(model.thread_id),
            stack_trace=model.stack_trace
        )


class ConfigView(JinjaView):

    VIEW_TEXT = """
    [DEFAULT]{% for optname, optval in default_group %}
        {{ optname }} = {{ optval }}{% endfor %}
    {% for groupname, groupopts in groups %}
    {{ groupname }}:{% for optname, optval in groupopts %}
        {{ optname }} = {{ optval }}{% endfor %}
    {% endfor %}
    """
