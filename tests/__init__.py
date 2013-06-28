import __builtin__
setattr(__builtin__, '_', lambda x: x)

import eventlet
eventlet.monkey_patch(all=False, thread=True)
