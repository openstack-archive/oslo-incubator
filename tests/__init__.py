try:
    import __builtin__
except ImportError:
    import builtins as __builtin__
setattr(__builtin__, '_', lambda x: x)
