def stub_out_compute_api_snapshot(stubs):

    def snapshot(self, context, instance, name, extra_properties=None):
        # emulate glance rejecting image names which are too long
        if len(name) > 256:
            raise exc.Invalid
        return dict(id='123', status='ACTIVE', name=name,
                    properties=extra_properties)
        
        stubs.Set(compute_api.API, 'snapshot', snapshot)
