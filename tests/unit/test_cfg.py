# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import shutil
import sys
import StringIO
import tempfile
import unittest

import stubout

from openstack.common.cfg import *


class ExceptionsTestCase(unittest.TestCase):

    def test_error(self):
        msg = str(Error('foobar'))
        self.assertEquals(msg, 'foobar')

    def test_args_already_parsed_error(self):
        msg = str(ArgsAlreadyParsedError('foobar'))
        self.assertEquals(msg, 'arguments already parsed: foobar')

    def test_no_such_opt_error(self):
        msg = str(NoSuchOptError('foo'))
        self.assertEquals(msg, 'no such option: foo')

    def test_no_such_opt_error_with_group(self):
        msg = str(NoSuchOptError('foo', OptGroup('bar')))
        self.assertEquals(msg, 'no such option in group bar: foo')

    def test_no_such_group_error(self):
        msg = str(NoSuchGroupError('bar'))
        self.assertEquals(msg, 'no such group: bar')

    def test_duplicate_opt_error(self):
        msg = str(DuplicateOptError('foo'))
        self.assertEquals(msg, 'duplicate option: foo')

    def test_template_substitution_error(self):
        msg = str(TemplateSubstitutionError('foobar'))
        self.assertEquals(msg, 'template substitution error: foobar')

    def test_config_files_not_found_error(self):
        msg = str(ConfigFilesNotFoundError(['foo', 'bar']))
        self.assertEquals(msg, 'Failed to read some config files: foo,bar')

    def test_config_file_parse_error(self):
        msg = str(ConfigFileParseError('foo', 'foobar'))
        self.assertEquals(msg, 'Failed to parse foo: foobar')


class BaseTestCase(unittest.TestCase):

    def setUp(self):
        self.conf = ConfigOpts(prog='test',
                               version='1.0',
                               usage='%prog FOO BAR',
                               default_config_files=[])
        self.tempfiles = []
        self.tempdirs = []
        self.stubs = stubout.StubOutForTesting()

    def tearDown(self):
        self.remove_tempfiles()
        self.stubs.UnsetAll()

    def create_tempfiles(self, files, ext='.conf'):
        for (basename, contents) in files:
            if not os.path.isabs(basename):
                (fd, path) = tempfile.mkstemp(prefix=basename, suffix=ext)
            else:
                path = basename + ext
                fd = os.open(path, os.O_CREAT|os.O_WRONLY)
            self.tempfiles.append(path)
            try:
                os.write(fd, contents)
            finally:
                os.close(fd)
        return self.tempfiles[-len(files):]

    def remove_tempfiles(self):
        for p in self.tempfiles:
            os.remove(p)
        for d in self.tempdirs:
            shutil.rmtree(d, ignore_errors=True)


class UsageTestCase(BaseTestCase):

    def test_print_usage(self):
        f = StringIO.StringIO()
        self.conf.print_usage(file=f)
        self.assertTrue('Usage: test FOO BAR' in f.getvalue())


class HelpTestCase(BaseTestCase):

    def test_print_help(self):
        f = StringIO.StringIO()
        self.conf.print_help(file=f)
        self.assertTrue('Usage: test FOO BAR' in f.getvalue())
        self.assertTrue('Options:' in f.getvalue())
        self.assertTrue('-h, --help' in f.getvalue())


class LeftoversTestCase(BaseTestCase):

    def test_leftovers(self):
        self.conf.register_cli_opts([StrOpt('foo'), StrOpt('bar')])

        leftovers = self.conf(['those', '--foo', 'this',
                               'thems', '--bar', 'that', 'these'])

        self.assertEquals(leftovers, ['those', 'thems', 'these'])


class FindConfigFilesTestCase(BaseTestCase):

    def test_find_config_files(self):
        config_files = [os.path.expanduser('~/.blaa/blaa.conf'),
                        '/etc/foo.conf']

        self.stubs.Set(sys, 'argv', ['foo'])
        self.stubs.Set(os.path, 'exists', lambda p: p in config_files)

        self.assertEquals(find_config_files(project='blaa'), config_files)

    def test_find_config_files_with_extension(self):
        config_files = ['/etc/foo.json']

        self.stubs.Set(sys, 'argv', ['foo'])
        self.stubs.Set(os.path, 'exists', lambda p: p in config_files)

        self.assertEquals(find_config_files(project='blaa'), [])
        self.assertEquals(find_config_files(project='blaa', extension='.json'),
                          config_files)


class CliOptsTestCase(BaseTestCase):

    def _do_cli_test(self, opt_class, default, cli_args, value):
        self.conf.register_cli_opt(opt_class('foo', default=default))

        self.conf(cli_args)

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, value)

    def test_str_default(self):
        self._do_cli_test(StrOpt, None, [], None)

    def test_str_arg(self):
        self._do_cli_test(StrOpt, None, ['--foo', 'bar'], 'bar')

    def test_bool_default(self):
        self._do_cli_test(BoolOpt, False, [], False)

    def test_bool_arg(self):
        self._do_cli_test(BoolOpt, None, ['--foo'], True)

    def test_bool_arg_inverse(self):
        self._do_cli_test(BoolOpt, None, ['--foo', '--nofoo'], False)

    def test_int_default(self):
        self._do_cli_test(IntOpt, 10, [], 10)

    def test_int_arg(self):
        self._do_cli_test(IntOpt, None, ['--foo=20'], 20)

    def test_float_default(self):
        self._do_cli_test(FloatOpt, 1.0, [], 1.0)

    def test_float_arg(self):
        self._do_cli_test(FloatOpt, None, ['--foo', '2.0'], 2.0)

    def test_list_default(self):
        self._do_cli_test(ListOpt, ['bar'], [], ['bar'])

    def test_list_arg(self):
        self._do_cli_test(ListOpt, None,
                          ['--foo', 'blaa,bar'], ['blaa', 'bar'])

    def test_multistr_default(self):
        self._do_cli_test(MultiStrOpt, ['bar'], [], ['bar'])

    def test_multistr_arg(self):
        self._do_cli_test(MultiStrOpt, None,
                          ['--foo', 'blaa', '--foo', 'bar'], ['blaa', 'bar'])

    def test_help(self):
        self.stubs.Set(sys, 'stdout', StringIO.StringIO())
        self.assertRaises(SystemExit, self.conf, ['--help'])
        self.assertTrue('FOO BAR' in sys.stdout.getvalue())
        self.assertTrue('--version' in sys.stdout.getvalue())
        self.assertTrue('--help' in sys.stdout.getvalue())
        self.assertTrue('--config-file=PATH' in sys.stdout.getvalue())

    def test_version(self):
        self.stubs.Set(sys, 'stdout', StringIO.StringIO())
        self.assertRaises(SystemExit, self.conf, ['--version'])
        self.assertTrue('1.0' in sys.stdout.getvalue())

    def test_config_file(self):
        paths = self.create_tempfiles([('1', '[DEFAULT]'),
                                       ('2', '[DEFAULT]')])

        self.conf(['--config-file', paths[0], '--config-file', paths[1]])

        self.assertEquals(self.conf.config_file, paths)

    def test_disable_interspersed_args(self):
        self.conf.register_cli_opt(BoolOpt('foo'))
        self.conf.register_cli_opt(BoolOpt('bar'))

        args = ['--foo', 'blaa', '--bar']

        self.assertEquals(self.conf(args), args[1:2])
        self.conf.disable_interspersed_args()
        self.assertEquals(self.conf(args), args[1:])
        self.conf.enable_interspersed_args()
        self.assertEquals(self.conf(args), args[1:2])


class ConfigFileOptsTestCase(BaseTestCase):

    def test_conf_file_str_default(self):
        self.conf.register_opt(StrOpt('foo', default='bar'))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 'bar')

    def test_conf_file_str_value(self):
        self.conf.register_opt(StrOpt('foo'))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'foo = bar\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 'bar')

    def test_conf_file_str_value_override(self):
        self.conf.register_cli_opt(StrOpt('foo'))

        paths = self.create_tempfiles([('1',
                                        '[DEFAULT]\n'
                                        'foo = baar\n'),
                                       ('2',
                                        '[DEFAULT]\n'
                                        'foo = baaar\n')])

        self.conf(['--foo', 'bar',
                   '--config-file', paths[0],
                   '--config-file', paths[1]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 'baaar')

    def test_conf_file_bool_default(self):
        self.conf.register_opt(BoolOpt('foo', default=False))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, False)

    def test_conf_file_bool_value(self):
        self.conf.register_opt(BoolOpt('foo'))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'foo = true\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, True)

    def test_conf_file_bool_value_override(self):
        self.conf.register_cli_opt(BoolOpt('foo'))

        paths = self.create_tempfiles([('1',
                                        '[DEFAULT]\n'
                                        'foo = 0\n'),
                                       ('2',
                                        '[DEFAULT]\n'
                                        'foo = yes\n')])

        self.conf(['--foo', 'bar',
                   '--config-file', paths[0],
                   '--config-file', paths[1]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, True)

    def test_conf_file_int_default(self):
        self.conf.register_opt(IntOpt('foo', default=666))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 666)

    def test_conf_file_int_value(self):
        self.conf.register_opt(IntOpt('foo'))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'foo = 666\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 666)

    def test_conf_file_int_value_override(self):
        self.conf.register_cli_opt(IntOpt('foo'))

        paths = self.create_tempfiles([('1',
                                        '[DEFAULT]\n'
                                        'foo = 66\n'),
                                       ('2',
                                        '[DEFAULT]\n'
                                        'foo = 666\n')])

        self.conf(['--foo', '6',
                   '--config-file', paths[0],
                   '--config-file', paths[1]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 666)

    def test_conf_file_float_default(self):
        self.conf.register_opt(FloatOpt('foo', default=6.66))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 6.66)

    def test_conf_file_float_value(self):
        self.conf.register_opt(FloatOpt('foo'))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'foo = 6.66\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 6.66)

    def test_conf_file_float_value_override(self):
        self.conf.register_cli_opt(FloatOpt('foo'))

        paths = self.create_tempfiles([('1',
                                        '[DEFAULT]\n'
                                        'foo = 6.6\n'),
                                       ('2',
                                        '[DEFAULT]\n'
                                        'foo = 6.66\n')])

        self.conf(['--foo', '6',
                   '--config-file', paths[0],
                   '--config-file', paths[1]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 6.66)

    def test_conf_file_list_default(self):
        self.conf.register_opt(ListOpt('foo', default=['bar']))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, ['bar'])

    def test_conf_file_list_value(self):
        self.conf.register_opt(ListOpt('foo'))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'foo = bar\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, ['bar'])

    def test_conf_file_list_value_override(self):
        self.conf.register_cli_opt(ListOpt('foo'))

        paths = self.create_tempfiles([('1',
                                        '[DEFAULT]\n'
                                        'foo = bar,bar\n'),
                                       ('2',
                                        '[DEFAULT]\n'
                                        'foo = b,a,r\n')])

        self.conf(['--foo', 'bar',
                   '--config-file', paths[0],
                   '--config-file', paths[1]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, ['b', 'a', 'r'])

    def test_conf_file_multistr_default(self):
        self.conf.register_opt(MultiStrOpt('foo', default=['bar']))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, ['bar'])

    def test_conf_file_multistr_value(self):
        self.conf.register_opt(MultiStrOpt('foo'))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'foo = bar\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, ['bar'])

    def test_conf_file_multistr_values_append(self):
        self.conf.register_cli_opt(MultiStrOpt('foo'))

        paths = self.create_tempfiles([('1',
                                        '[DEFAULT]\n'
                                        'foo = bar1\n'),
                                       ('2',
                                        '[DEFAULT]\n'
                                        'foo = bar2\n'
                                        'foo = bar3\n')])

        self.conf(['--foo', 'bar0',
                   '--config-file', paths[0],
                   '--config-file', paths[1]])

        self.assertTrue(hasattr(self.conf, 'foo'))

        self.assertEquals(self.conf.foo, ['bar0', 'bar1', 'bar2', 'bar3'])

    def test_conf_file_multiple_opts(self):
        self.conf.register_opts([StrOpt('foo'), StrOpt('bar')])

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'foo = bar\n'
                                        'bar = foo\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 'bar')
        self.assertTrue(hasattr(self.conf, 'bar'))
        self.assertEquals(self.conf.bar, 'foo')

    def test_conf_file_raw_value(self):
        self.conf.register_opt(StrOpt('foo'))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'foo = bar-%08x\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 'bar-%08x')


class OptGroupsTestCase(BaseTestCase):

    def test_arg_group(self):
        blaa_group = OptGroup('blaa', 'blaa options')
        self.conf.register_group(blaa_group)
        self.conf.register_cli_opt(StrOpt('foo'), group=blaa_group)

        self.conf(['--blaa-foo', 'bar'])

        self.assertTrue(hasattr(self.conf, 'blaa'))
        self.assertTrue(hasattr(self.conf.blaa, 'foo'))
        self.assertEquals(self.conf.blaa.foo, 'bar')

    def test_arg_group_by_name(self):
        self.conf.register_group(OptGroup('blaa'))
        self.conf.register_cli_opt(StrOpt('foo'), group='blaa')

        self.conf(['--blaa-foo', 'bar'])

        self.assertTrue(hasattr(self.conf, 'blaa'))
        self.assertTrue(hasattr(self.conf.blaa, 'foo'))
        self.assertEquals(self.conf.blaa.foo, 'bar')

    def test_arg_group_with_default(self):
        self.conf.register_group(OptGroup('blaa'))
        self.conf.register_cli_opt(StrOpt('foo', default='bar'), group='blaa')

        self.conf([])

        self.assertTrue(hasattr(self.conf, 'blaa'))
        self.assertTrue(hasattr(self.conf.blaa, 'foo'))
        self.assertEquals(self.conf.blaa.foo, 'bar')

    def test_arg_group_in_config_file(self):
        self.conf.register_group(OptGroup('blaa'))
        self.conf.register_opt(StrOpt('foo'), group='blaa')

        paths = self.create_tempfiles([('test',
                                        '[blaa]\n'
                                        'foo = bar\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'blaa'))
        self.assertTrue(hasattr(self.conf.blaa, 'foo'))
        self.assertEquals(self.conf.blaa.foo, 'bar')


class MappingInterfaceTestCase(BaseTestCase):

    def test_mapping_interface(self):
        self.conf.register_cli_opt(StrOpt('foo'))

        self.conf(['--foo', 'bar'])

        self.assertTrue('foo' in self.conf)
        self.assertTrue('config_file' in self.conf)
        self.assertEquals(len(self.conf), 3)
        self.assertEquals(self.conf['foo'], 'bar')
        self.assertEquals(self.conf.get('foo'), 'bar')
        self.assertTrue('bar' in self.conf.values())

    def test_mapping_interface_with_group(self):
        self.conf.register_group(OptGroup('blaa'))
        self.conf.register_cli_opt(StrOpt('foo'), group='blaa')

        self.conf(['--blaa-foo', 'bar'])

        self.assertTrue('blaa' in self.conf)
        self.assertTrue('foo' in self.conf['blaa'])
        self.assertEquals(len(self.conf['blaa']), 1)
        self.assertEquals(self.conf['blaa']['foo'], 'bar')
        self.assertEquals(self.conf['blaa'].get('foo'), 'bar')
        self.assertTrue('bar' in self.conf['blaa'].values())
        self.assertEquals(self.conf.blaa, self.conf['blaa'])


class ReRegisterOptTestCase(BaseTestCase):

    def test_conf_file_re_register_opt(self):
        opt = StrOpt('foo')
        self.assertTrue(self.conf.register_opt(opt))
        self.assertFalse(self.conf.register_opt(opt))

    def test_conf_file_re_register_opt_in_group(self):
        group = OptGroup('blaa')
        self.conf.register_group(group)
        self.conf.register_group(group)  # not an error
        opt = StrOpt('foo')
        self.assertTrue(self.conf.register_opt(opt, group=group))
        self.assertFalse(self.conf.register_opt(opt, group='blaa'))


class TemplateSubstitutionTestCase(BaseTestCase):

    def _prep_test_str_sub(self, foo_default=None, bar_default=None):
        self.conf.register_cli_opt(StrOpt('foo', default=foo_default))
        self.conf.register_cli_opt(StrOpt('bar', default=bar_default))

    def _assert_str_sub(self):
        self.assertTrue(hasattr(self.conf, 'bar'))
        self.assertEquals(self.conf.bar, 'blaa')

    def test_str_sub_default_from_default(self):
        self._prep_test_str_sub(foo_default='blaa', bar_default='$foo')

        self.conf([])

        self._assert_str_sub()

    def test_str_sub_default_from_default_recurse(self):
        self.conf.register_cli_opt(StrOpt('blaa', default='blaa'))
        self._prep_test_str_sub(foo_default='$blaa', bar_default='$foo')

        self.conf([])

        self._assert_str_sub()

    def test_str_sub_default_from_arg(self):
        self._prep_test_str_sub(bar_default='$foo')

        self.conf(['--foo', 'blaa'])

        self._assert_str_sub()

    def test_str_sub_default_from_config_file(self):
        self._prep_test_str_sub(bar_default='$foo')

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'foo = blaa\n')])

        self.conf(['--config-file', paths[0]])

        self._assert_str_sub()

    def test_str_sub_arg_from_default(self):
        self._prep_test_str_sub(foo_default='blaa')

        self.conf(['--bar', '$foo'])

        self._assert_str_sub()

    def test_str_sub_arg_from_arg(self):
        self._prep_test_str_sub()

        self.conf(['--foo', 'blaa', '--bar', '$foo'])

        self._assert_str_sub()

    def test_str_sub_arg_from_config_file(self):
        self._prep_test_str_sub()

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'foo = blaa\n')])

        self.conf(['--config-file', paths[0], '--bar=$foo'])

        self._assert_str_sub()

    def test_str_sub_config_file_from_default(self):
        self._prep_test_str_sub(foo_default='blaa')

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'bar = $foo\n')])

        self.conf(['--config-file', paths[0]])

        self._assert_str_sub()

    def test_str_sub_config_file_from_arg(self):
        self._prep_test_str_sub()

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'bar = $foo\n')])

        self.conf(['--config-file', paths[0], '--foo=blaa'])

        self._assert_str_sub()

    def test_str_sub_config_file_from_config_file(self):
        self._prep_test_str_sub()

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'bar = $foo\n'
                                        'foo = blaa\n')])

        self.conf(['--config-file', paths[0]])

        self._assert_str_sub()

    def test_str_sub_group_from_default(self):
        self.conf.register_cli_opt(StrOpt('foo', default='blaa'))
        self.conf.register_group(OptGroup('ba'))
        self.conf.register_cli_opt(StrOpt('r', default='$foo'), group='ba')

        self.conf([])

        self.assertTrue(hasattr(self.conf, 'ba'))
        self.assertTrue(hasattr(self.conf.ba, 'r'))
        self.assertEquals(self.conf.ba.r, 'blaa')

    def test_config_dir(self):
        snafu_group = OptGroup('snafu')
        self.conf.register_group(snafu_group)
        self.conf.register_cli_opt(StrOpt('foo'))
        self.conf.register_cli_opt(StrOpt('bell'), group=snafu_group)

        dir = tempfile.mkdtemp()
        self.tempdirs.append(dir)

        paths = self.create_tempfiles([(os.path.join(dir, '00-test'),
                                        '[DEFAULT]\n'
                                        'foo = bar-00\n'
                                        '[snafu]\n'
                                        'bell = whistle-00\n'),
                                       (os.path.join(dir, '02-test'),
                                        '[snafu]\n'
                                        'bell = whistle-02\n'
                                        '[DEFAULT]\n'
                                        'foo = bar-02\n'),
                                       (os.path.join(dir, '01-test'),
                                        '[DEFAULT]\n'
                                        'foo = bar-01\n')])

        self.conf(['--foo', 'bar',
                   '--config-dir', os.path.dirname(paths[0])])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 'bar-02')
        self.assertTrue(hasattr(self.conf, 'snafu'))
        self.assertTrue(hasattr(self.conf.snafu, 'bell'))
        self.assertEquals(self.conf.snafu.bell, 'whistle-02')

    def test_config_dir_file_precedence(self):
        snafu_group = OptGroup('snafu')
        self.conf.register_group(snafu_group)
        self.conf.register_cli_opt(StrOpt('foo'))
        self.conf.register_cli_opt(StrOpt('bell'), group=snafu_group)

        dir = tempfile.mkdtemp()
        self.tempdirs.append(dir)

        paths = self.create_tempfiles([(os.path.join(dir, '00-test'),
                                        '[DEFAULT]\n'
                                        'foo = bar-00\n'),
                                       ('01-test',
                                        '[snafu]\n'
                                        'bell = whistle-01\n'
                                        '[DEFAULT]\n'
                                        'foo = bar-01\n'),
                                       ('03-test',
                                        '[snafu]\n'
                                        'bell = whistle-03\n'
                                        '[DEFAULT]\n'
                                        'foo = bar-03\n'),
                                       (os.path.join(dir, '02-test'),
                                        '[DEFAULT]\n'
                                        'foo = bar-02\n')])

        self.conf(['--foo', 'bar',
                   '--config-file', paths[1],
                   '--config-dir', os.path.dirname(paths[0]),
                   '--config-file', paths[2], ])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, 'bar-02')
        self.assertTrue(hasattr(self.conf, 'snafu'))
        self.assertTrue(hasattr(self.conf.snafu, 'bell'))
        self.assertEquals(self.conf.snafu.bell, 'whistle-03')

class ReparseTestCase(BaseTestCase):

    def test_reparse(self):
        self.conf.register_group(OptGroup('blaa'))
        self.conf.register_cli_opt(StrOpt('foo', default='r'), group='blaa')

        paths = self.create_tempfiles([('test',
                                        '[blaa]\n'
                                        'foo = b\n')])

        self.conf(['--config-file', paths[0]])

        self.assertTrue(hasattr(self.conf, 'blaa'))
        self.assertTrue(hasattr(self.conf.blaa, 'foo'))
        self.assertEquals(self.conf.blaa.foo, 'b')

        self.conf(['--blaa-foo', 'a'])

        self.assertTrue(hasattr(self.conf, 'blaa'))
        self.assertTrue(hasattr(self.conf.blaa, 'foo'))
        self.assertEquals(self.conf.blaa.foo, 'a')

        self.conf([])

        self.assertTrue(hasattr(self.conf, 'blaa'))
        self.assertTrue(hasattr(self.conf.blaa, 'foo'))
        self.assertEquals(self.conf.blaa.foo, 'r')


class OverridesTestCase(BaseTestCase):

    def test_no_default_override(self):
        self.conf.register_opt(StrOpt('foo'))
        self.conf([])
        self.assertEquals(self.conf.foo, None)
        self.conf.set_default('foo', 'bar')
        self.assertEquals(self.conf.foo, 'bar')

    def test_default_override(self):
        self.conf.register_opt(StrOpt('foo', default='foo'))
        self.conf([])
        self.assertEquals(self.conf.foo, 'foo')
        self.conf.set_default('foo', 'bar')
        self.assertEquals(self.conf.foo, 'bar')
        self.conf.set_default('foo', None)
        self.assertEquals(self.conf.foo, 'foo')

    def test_override(self):
        self.conf.register_opt(StrOpt('foo'))
        self.conf.set_override('foo', 'bar')
        self.conf([])
        self.assertEquals(self.conf.foo, 'bar')

    def test_group_no_default_override(self):
        self.conf.register_group(OptGroup('blaa'))
        self.conf.register_opt(StrOpt('foo'), group='blaa')
        self.conf([])
        self.assertEquals(self.conf.blaa.foo, None)
        self.conf.set_default('foo', 'bar', group='blaa')
        self.assertEquals(self.conf.blaa.foo, 'bar')

    def test_group_default_override(self):
        self.conf.register_group(OptGroup('blaa'))
        self.conf.register_opt(StrOpt('foo', default='foo'), group='blaa')
        self.conf([])
        self.assertEquals(self.conf.blaa.foo, 'foo')
        self.conf.set_default('foo', 'bar', group='blaa')
        self.assertEquals(self.conf.blaa.foo, 'bar')
        self.conf.set_default('foo', None, group='blaa')
        self.assertEquals(self.conf.blaa.foo, 'foo')

    def test_group_override(self):
        self.conf.register_group(OptGroup('blaa'))
        self.conf.register_opt(StrOpt('foo'), group='blaa')
        self.conf.set_override('foo', 'bar', group='blaa')
        self.conf([])
        self.assertEquals(self.conf.blaa.foo, 'bar')


class SadPathTestCase(BaseTestCase):

    def test_unknown_attr(self):
        self.conf([])
        self.assertFalse(hasattr(self.conf, 'foo'))
        self.assertRaises(NoSuchOptError, getattr, self.conf, 'foo')

    def test_unknown_attr_is_attr_error(self):
        self.conf([])
        self.assertFalse(hasattr(self.conf, 'foo'))
        self.assertRaises(AttributeError, getattr, self.conf, 'foo')

    def test_unknown_group_attr(self):
        self.conf.register_group(OptGroup('blaa'))

        self.conf([])

        self.assertTrue(hasattr(self.conf, 'blaa'))
        self.assertFalse(hasattr(self.conf.blaa, 'foo'))
        self.assertRaises(NoSuchOptError, getattr, self.conf.blaa, 'foo')

    def test_ok_duplicate(self):
        opt = StrOpt('foo')
        self.conf.register_cli_opt(opt)
        self.conf.register_cli_opt(opt)

        self.conf([])

        self.assertTrue(hasattr(self.conf, 'foo'))
        self.assertEquals(self.conf.foo, None)

    def test_error_duplicate(self):
        self.conf.register_cli_opt(StrOpt('foo'))
        self.assertRaises(DuplicateOptError,
                          self.conf.register_cli_opt, StrOpt('foo'))

    def test_error_duplicate_with_different_dest(self):
        self.conf.register_cli_opt(StrOpt('foo', dest='f'))
        self.assertRaises(DuplicateOptError,
                          self.conf.register_cli_opt, StrOpt('foo'))

    def test_error_duplicate_short(self):
        self.conf.register_cli_opt(StrOpt('foo', short='f'))
        self.assertRaises(DuplicateOptError,
                          self.conf.register_cli_opt, StrOpt('bar', short='f'))

    def test_no_such_group(self):
        self.assertRaises(NoSuchGroupError, self.conf.register_cli_opt,
                          StrOpt('foo'), group='blaa')

    def test_already_parsed(self):
        self.conf([])

        self.assertRaises(ArgsAlreadyParsedError,
                          self.conf.register_cli_opt, StrOpt('foo'))

    def test_bad_cli_arg(self):
        self.stubs.Set(sys, 'stderr', StringIO.StringIO())

        self.assertRaises(SystemExit, self.conf, ['--foo'])

        self.assertTrue('error' in sys.stderr.getvalue())
        self.assertTrue('--foo' in sys.stderr.getvalue())

    def _do_test_bad_cli_value(self, opt_class):
        self.conf.register_cli_opt(opt_class('foo'))

        self.stubs.Set(sys, 'stderr', StringIO.StringIO())

        self.assertRaises(SystemExit, self.conf, ['--foo', 'bar'])

        self.assertTrue('foo' in sys.stderr.getvalue())
        self.assertTrue('bar' in sys.stderr.getvalue())

    def test_bad_int_arg(self):
        self._do_test_bad_cli_value(IntOpt)

    def test_bad_float_arg(self):
        self._do_test_bad_cli_value(FloatOpt)

    def test_conf_file_not_found(self):
        paths = self.create_tempfiles([('test', '')])
        os.remove(paths[0])
        self.tempfiles.remove(paths[0])

        self.assertRaises(ConfigFilesNotFoundError,
                          self.conf, ['--config-file', paths[0]])

    def test_conf_file_broken(self):
        paths = self.create_tempfiles([('test', 'foo')])

        self.assertRaises(ConfigFileParseError,
                          self.conf, ['--config-file', paths[0]])

    def _do_test_conf_file_bad_value(self, opt_class):
        self.conf.register_opt(opt_class('foo'))

        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'foo = bar\n')])

        self.conf(['--config-file', paths[0]])

        self.assertRaises(ConfigFileValueError, getattr, self.conf, 'foo')

    def test_conf_file_bad_bool(self):
        self._do_test_conf_file_bad_value(BoolOpt)

    def test_conf_file_bad_int(self):
        self._do_test_conf_file_bad_value(IntOpt)

    def test_conf_file_bad_float(self):
        self._do_test_conf_file_bad_value(FloatOpt)

    def test_str_sub_from_group(self):
        self.conf.register_group(OptGroup('f'))
        self.conf.register_cli_opt(StrOpt('oo', default='blaa'), group='f')
        self.conf.register_cli_opt(StrOpt('bar', default='$f.oo'))

        self.conf([])

        self.assertFalse(hasattr(self.conf, 'bar'))
        self.assertRaises(TemplateSubstitutionError, getattr, self.conf, 'bar')

    def test_set_default_unknown_attr(self):
        self.conf([])
        self.assertRaises(NoSuchOptError, self.conf.set_default, 'foo', 'bar')

    def test_set_default_unknown_group(self):
        self.conf([])
        self.assertRaises(NoSuchGroupError,
                          self.conf.set_default, 'foo', 'bar', group='blaa')

    def test_set_override_unknown_attr(self):
        self.conf([])
        self.assertRaises(NoSuchOptError, self.conf.set_override, 'foo', 'bar')

    def test_set_override_unknown_group(self):
        self.conf([])
        self.assertRaises(NoSuchGroupError,
                          self.conf.set_override, 'foo', 'bar', group='blaa')


class FindFileTestCase(BaseTestCase):

    def test_find_policy_file(self):
        policy_file = '/etc/policy.json'

        self.stubs.Set(os.path, 'exists', lambda p: p == policy_file)

        self.assertEquals(self.conf.find_file('foo.json'), None)
        self.assertEquals(self.conf.find_file('policy.json'), policy_file)

    def test_find_policy_file_with_config_file(self):
        dir = tempfile.mkdtemp()
        self.tempdirs.append(dir)

        paths = self.create_tempfiles([(os.path.join(dir, 'test.conf'),
                                        '[DEFAULT]'),
                                       (os.path.join(dir, 'policy.json'),
                                        '{}')],
                                      ext='')

        self.conf(['--config-file', paths[0]])

        self.assertEquals(self.conf.find_file('policy.json'), paths[1])

    def test_find_policy_file_with_config_dir(self):
        dir = tempfile.mkdtemp()
        self.tempdirs.append(dir)

        path = self.create_tempfiles([(os.path.join(dir, 'policy.json'),
                                       '{}')],
                                     ext='')[0]

        self.conf(['--config-dir', dir])

        self.assertEquals(self.conf.find_file('policy.json'), path)


class OptDumpingTestCase(BaseTestCase):

    class FakeLogger:

        def __init__(self, test_case, expected_lvl):
            self.test_case = test_case
            self.expected_lvl = expected_lvl
            self.logged = []

        def log(self, lvl, fmt, *args):
            self.test_case.assertEquals(lvl, self.expected_lvl)
            self.logged.append(fmt % args)

    def test_log_opt_values(self):
        self.conf.register_cli_opt(StrOpt('foo'))
        self.conf.register_cli_opt(StrOpt('passwd', secret=True))
        self.conf.register_group(OptGroup('blaa'))
        self.conf.register_cli_opt(StrOpt('bar'), 'blaa')
        self.conf.register_cli_opt(StrOpt('key', secret=True), 'blaa')

        self.conf(['--foo', 'this', '--blaa-bar', 'that',
                   '--blaa-key', 'admin', '--passwd', 'hush'])

        logger = self.FakeLogger(self, 666)

        self.conf.log_opt_values(logger, 666)

        self.assertEquals(logger.logged, [
                "*" * 80,
                "Configuration options gathered from:",
                "command line args: ['--foo', 'this', '--blaa-bar', 'that', "\
                "'--blaa-key', 'admin', '--passwd', 'hush']",
                "config files: []",
                "=" * 80,
                "config_dir                     = None",
                "config_file                    = []",
                "foo                            = this",
                "passwd                         = ****",
                 "blaa.bar                       = that",
                "blaa.key                       = *****",
                "*" * 80,
                ])


class CommonOptsTestCase(BaseTestCase):

    def setUp(self):
        super(CommonOptsTestCase, self).setUp()
        self.conf = CommonConfigOpts()

    def test_debug_verbose(self):
        self.conf(['--debug', '--verbose'])

        self.assertEquals(self.conf.debug, True)
        self.assertEquals(self.conf.verbose, True)

    def test_logging_opts(self):
        self.conf([])

        self.assertTrue(self.conf.log_config is None)
        self.assertTrue(self.conf.log_file is None)
        self.assertTrue(self.conf.log_dir is None)

        self.assertEquals(self.conf.log_format,
                          CommonConfigOpts.DEFAULT_LOG_FORMAT)
        self.assertEquals(self.conf.log_date_format,
                          CommonConfigOpts.DEFAULT_LOG_DATE_FORMAT)

        self.assertEquals(self.conf.use_syslog, False)


class ConfigParserTestCase(unittest.TestCase):
    def test_no_section(self):
        with tempfile.NamedTemporaryFile() as tmpfile:
            tmpfile.write('foo = bar')
            tmpfile.flush()

            parser = ConfigParser(tmpfile.name, {})
            self.assertRaises(ParseError, parser.parse)
