from openstack.common.models.with_default_views import ModelWithDefaultViews
import openstack.common.views.text.generic as generic_text_views
import openstack.common.views.text.openstack as text_views
import traceback


class StackTraceModel(ModelWithDefaultViews):
    def __init__(self, stack_state):
        super(StackTraceModel, self).__init__(
            text_view=text_views.StackTraceView()
        )

        if (stack_state is not None):
            self['lines'] = [
                {'filename': fn, 'line': ln, 'name': nm, 'code': cd}
                for fn, ln, nm, cd in traceback.extract_stack(stack_state)
            ]
        else:
            self['lines'] = None

        if stack_state.f_exc_type is not None:
            self['root_exception'] = {
                'type': stack_state.f_exc_type,
                'value': stack_state.f_exc_value
            }
        else:
            self['root_exception'] = None


class ThreadModel(ModelWithDefaultViews):

    # threadId, stack in sys._current_frams().items()
    def __init__(self, thread_id, stack):
        super(ThreadModel, self).__init__(text_view=text_views.ThreadView())

        self['thread_id'] = thread_id
        self['stack_trace'] = StackTraceModel(stack)


class GreenThreadModel(ModelWithDefaultViews):

    # gr in greenpool.coroutines_running  --> gr.gr_frame
    def __init__(self, stack):
        super(GreenThreadModel, self).__init__(
            {'stack_trace': StackTraceModel(stack)},
            text_view=text_views.GreenThreadView()
        )


class ConfigModel(ModelWithDefaultViews):

    def __init__(self, conf_obj):
        super(ConfigModel, self).__init__(text_view=text_views.ConfigView())

        self['default_group'] = [
            [conf_obj._opts[optname]['opt'].name, conf_obj[optname]]
            for optname in conf_obj._opts
        ]

        groups = {}
        for groupname in conf_obj._groups:
            group_obj = conf_obj._groups[groupname]
            curr_group_opts = [
                [
                    group_obj._opts[optname]['opt'].name,
                    conf_obj[groupname][optname]
                ]
                for optname in group_obj._opts
            ]
            groups[group_obj.name] = curr_group_opts

        self['groups'] = [
            [groupname, groups[groupname]] for groupname in groups
        ]


class PackageModel(ModelWithDefaultViews):

    def __init__(self, vendor, product, version):
        super(PackageModel, self).__init__(
            text_view=generic_text_views.KeyValueView()
        )

        self['vendor'] = vendor
        self['product'] = product
        self['version'] = version


class ServicesModel(ModelWithDefaultViews):
    def __init__(self, hosts):
        view = generic_text_views.TableView(
            ['Service', 'Host', 'Alive?'],
            ['service', 'host', 'alive'],
            'services'
        )
        super(ServicesModel, self).__init__(text_view=view)

        self['services'] = hosts
