from copy import deepcopy
import json
from openstack.common.utils import StringWithAttrs


class BasicKeyValueView(object):
    def __call__(self, model):
        res = StringWithAttrs(json.dumps(model.data))
        res.__is_json__ = True
        return res


class KeyValueView(object):
    def __call__(self, model):
        # this part deals with subviews that were already serialized
        cpy = deepcopy(model)
        for key, valstr in model.items():
            if getattr(valstr, '__is_json__', False):
                cpy[key] = json.loads(valstr)

        res = StringWithAttrs(json.dumps(cpy.data))
        res.__is_json__ = True
        return res
