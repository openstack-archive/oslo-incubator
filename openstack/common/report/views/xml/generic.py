from collections import Mapping
from collections import Sequence
from copy import deepcopy
import xml.etree.ElementTree as ET


class KeyValueView(object):
    def __call__(self, model):
        # this part deals with subviews that were already serialized
        cpy = deepcopy(model)
        for key, valstr in model.items():
            if getattr(valstr, '__is_xml__', False):
                cpy[key] = ET.fromstring(valstr)

        def serialize(rootmodel, rootkeyname):
            res = ET.Element(rootkeyname)

            if isinstance(rootmodel, Mapping):
                for key in rootmodel:
                    res.append(serialize(rootmodel[key], key))
            elif isinstance(rootmodel, Sequence):
                for val in rootmodel:
                    ET.SubElement(res, 'item').text = val
            elif isinstance(rootmodel, ET.Element):
                res.append(rootmodel)
            else:
                res.text = str(rootmodel)

            return res

        res = ET.tostring(serialize(model, 'model'))
        res.__is_xml__ = True
        return res
