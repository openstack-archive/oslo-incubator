
from __future__ import print_function

import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))

sys.path.insert(0, ROOT)
sys.path.insert(0, BASE_DIR)

# This is required for ReadTheDocs.org, but isn't a bad idea anyway.
os.environ['DJANGO_SETTINGS_MODULE'] = 'openstack_dashboard.settings'


def write_autodoc_index():

    def find_autodoc_modules(module_name, sourcedir):
        """Return a list of modules in the SOURCE directory."""
        modlist = []
        os.chdir(os.path.join(sourcedir, module_name))
        print("SEARCHING %s" % sourcedir)
        for root, dirs, files in os.walk("."):
            for filename in files:
                if filename.endswith(".py"):
                    # remove the pieces of the root
                    elements = root.split(os.path.sep)
                    # replace the leading "." with the module name
                    elements[0] = module_name
                    # and get the base module name
                    base, extension = os.path.splitext(filename)
                    if not (base == "__init__"):
                        elements.append(base)
                    result = ".".join(elements)
                    #print result
                    modlist.append(result)
        return modlist

    RSTDIR = os.path.abspath(os.path.join(BASE_DIR, "sourcecode"))
    SRCS = {'openstack': ROOT}

    EXCLUDED_MODULES = ()
    CURRENT_SOURCES = {}

    if not(os.path.exists(RSTDIR)):
        os.mkdir(RSTDIR)
    CURRENT_SOURCES[RSTDIR] = ['autoindex.rst']

    INDEXOUT = open(os.path.join(RSTDIR, "autoindex.rst"), "w")
    INDEXOUT.write("=================\n")
    INDEXOUT.write("Source Code Index\n")
    INDEXOUT.write("=================\n")

    for modulename, path in SRCS.items():
        sys.stdout.write("Generating source documentation for %s\n" %
                         modulename)
        INDEXOUT.write("\n%s\n" % modulename.capitalize())
        INDEXOUT.write("%s\n" % ("=" * len(modulename),))
        INDEXOUT.write(".. toctree::\n")
        INDEXOUT.write("   :maxdepth: 1\n")
        INDEXOUT.write("\n")

        MOD_DIR = os.path.join(RSTDIR, modulename)
        CURRENT_SOURCES[MOD_DIR] = []
        if not(os.path.exists(MOD_DIR)):
            os.mkdir(MOD_DIR)
        for module in find_autodoc_modules(modulename, path):
            if any([module.startswith(exclude)
                    for exclude
                    in EXCLUDED_MODULES]):
                print("Excluded module %s." % module)
                continue
            mod_path = os.path.join(path, *module.split("."))
            generated_file = os.path.join(MOD_DIR, "%s.rst" % module)

            INDEXOUT.write("   %s/%s\n" % (modulename, module))

            # Find the __init__.py module if this is a directory
            if os.path.isdir(mod_path):
                source_file = ".".join((os.path.join(mod_path, "__init__"),
                                        "py",))
            else:
                source_file = ".".join((os.path.join(mod_path), "py"))

            CURRENT_SOURCES[MOD_DIR].append("%s.rst" % module)
            # Only generate a new file if the source has changed or we don't
            # have a doc file to begin with.
            if not os.access(generated_file, os.F_OK) or \
                    os.stat(generated_file).st_mtime < \
                    os.stat(source_file).st_mtime:
                print("Module %s updated, generating new documentation." \
                      % module)
                FILEOUT = open(generated_file, "w")
                header = "The :mod:`%s` Module" % module
                FILEOUT.write("%s\n" % ("=" * len(header),))
                FILEOUT.write("%s\n" % header)
                FILEOUT.write("%s\n" % ("=" * len(header),))
                FILEOUT.write(".. automodule:: %s\n" % module)
                FILEOUT.write("  :members:\n")
                FILEOUT.write("  :undoc-members:\n")
                FILEOUT.write("  :show-inheritance:\n")
                FILEOUT.write("  :noindex:\n")
                FILEOUT.close()

    INDEXOUT.close()
    # Delete auto-generated .rst files for sources which no longer exist
    for directory, subdirs, files in list(os.walk(RSTDIR)):
        for old_file in files:
            if old_file not in CURRENT_SOURCES.get(directory, []):
                print("Removing outdated file for %s" % old_file)
                os.remove(os.path.join(directory, old_file))


write_autodoc_index()

# -- General configuration ----------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx']

# autodoc generation is a bit aggressive and a nuisance when doing heavy
# text edit cycles.
# execute "export SPHINX_DEBUG=1" in your terminal to disable

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'Oslo'
copyright = '2012, OpenStack Foundation'

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# -- Options for HTML output --------------------------------------------------

# The theme to use for HTML and HTML Help pages.  Major themes that come with
# Sphinx are currently 'default' and 'sphinxdoc'.
html_theme_path = ["."]
html_theme = '_theme'
html_static_path = ['static']

# Output file base name for HTML help builder.
htmlhelp_basename = '%sdoc' % project

git_cmd = "git log --pretty=format:'%ad, commit %h' --date=local -n1"
html_last_updated_fmt = os.popen(git_cmd).read()

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass
# [howto/manual]).
latex_documents = [
        ('index',
         '%s.tex' % project,
         '%s Documentation' % project,
         'OpenStack Foundation', 'manual'),
]

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {'http://docs.python.org/': None}
