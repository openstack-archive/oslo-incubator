import gc


class StringWithAttrs(str):
    pass


def _find_objects(t):
    return filter(lambda o: isinstance(o, t), gc.get_objects())
