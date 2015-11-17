import collections
import contextlib
import datetime
import os
import sys

import tabulate

from gitinspector.changes import Changes
from gitinspector.metrics import MetricsLogic

Repository = collections.namedtuple('Repository', 'name,location')

CORE_SKIPS = frozenset([
    u'Julien Danjou',
    u'Davanum Srinivas',
    u'Ben Nemec',
    u'Joshua Harlow',
    u'Brant Knudson',
    u'Doug Hellmann',
    u'Victor Stinner',
    u'Michael Still',
    u'Flavio Percoco',
    u'Mehdi Abaakouk',
    u'Robert Collins',
])
EMAIL_SKIPS = frozenset([
    'openstack-infra@lists.openstack.org',
    'flaper87@gmail.com',
    'fpercoco@redhat.com',
])
OLDEST_COMMIT_YEAR = 2014


@contextlib.contextmanager
def auto_cwd(target_dir):
    old_dir = os.getcwd()
    if old_dir == target_dir:
        yield
    else:
        os.chdir(target_dir)
        try:
            yield
        finally:
            os.chdir(old_dir)


def new_core_compare(c1, c2):
    # Sort by insertions, deletions...
    c1_info = (c1[3], c1[4], c1[5])
    c2_info = (c2[3], c2[4], c2[5])
    if c1_info == c2_info:
        return 0
    if c1_info < c2_info:
        return -1
    else:
        return 1


def should_discard(change_date, author_name, author_email, author_info):
    if author_name in CORE_SKIPS:
        return True
    if author_email in EMAIL_SKIPS:
        return True
    if change_date is not None:
        if change_date.year < OLDEST_COMMIT_YEAR:
            return True
    return False


def dump_changes(repo):
    with auto_cwd(repo.location):
        print("Analyzing repo %s (%s):" % (repo.name, repo.location))
        print("Please wait...")
        Changes.authors.clear()
        Changes.authors_dateinfo.clear()
        Changes.authors_by_email.clear()
        Changes.emails_by_author.clear()

        changes = Changes(repo)
        # This is needed to flush out changes progress message...
        sys.stdout.write("\n")
        # Force population of this info...
        changes_per_author = changes.get_authordateinfo_list()
        just_authors = changes.get_authorinfo_list()
        better_changes_per_author = {}
        maybe_new_cores = {}
        for c in changes.get_commits():
            change_date = c.timestamp
            author_name = c.author
            author_email = c.email
            change_date = datetime.datetime.fromtimestamp(int(change_date))
            try:
                author_info = changes.authors[author_name]
                better_changes_per_author[(change_date, author_name)] = author_info
            except KeyError:
                pass
        for (change_date, author_name) in better_changes_per_author.keys():
            author_email = changes.get_latest_email_by_author(author_name)
            author_info = better_changes_per_author[(change_date, author_name)]
            author_info.email = author_email
            if not should_discard(change_date, author_name, author_email, author_info):
                if author_name in maybe_new_cores:
                    existing_info = maybe_new_cores[author_name]
                    if existing_info[2] < change_date:
                        existing_info[2] = change_date
                else:
                    maybe_core = [
                        author_name.encode("ascii", errors='replace'),
                        author_email,
                        change_date,
                        author_info.insertions,
                        author_info.deletions,
                        author_info.commits,
                    ]
                    maybe_new_cores[author_name] = maybe_core
        if maybe_new_cores:
            print("%s potential new cores found!!" % len(maybe_new_cores))
            tmp_maybe_new_cores = sorted(list(maybe_new_cores.values()),
                                              cmp=new_core_compare, reverse=True)
            headers = ['Name', 'Email', 'Last change made', 'Insertions', 'Deletions', 'Commits']
            print(tabulate.tabulate(tmp_maybe_new_cores, headers=headers,
                                    tablefmt="grid"))
        else:
            print("No new cores found!!")
        return changes.authors.copy()


def main(repos):
    raw_repos = [os.path.abspath(p) for p in repos]
    parsed_repos = []
    for repo in raw_repos:
        parsed_repos.append(Repository(os.path.basename(repo), repo))
    all_authors = []
    for repo in parsed_repos:
        all_authors.append(dump_changes(repo))
    if all_authors:
        print("Combined changes of %s repos:" % len(parsed_repos))
        maybe_new_cores = {}
        for repo_authors in all_authors:
            for author_name, author_info in repo_authors.items():
                change_date = datetime.datetime.now()
                if not should_discard(None, author_name, author_info.email, author_info):
                    if author_name in maybe_new_cores:
                        prior_author_info = maybe_new_cores[author_name]
                        prior_author_info[3] = prior_author_info[3] + author_info.insertions
                        prior_author_info[4] = prior_author_info[4] + author_info.deletions
                        prior_author_info[5] = prior_author_info[5] + author_info.commits
                    else:
                        maybe_new_cores[author_name] = [
                            author_name.encode("ascii", errors='replace'),
                            author_info.email,
                            u"N/A",
                            author_info.insertions,
                            author_info.deletions,
                            author_info.commits,
                        ]
        tmp_maybe_new_cores = sorted(list(maybe_new_cores.values()),
                                          cmp=new_core_compare, reverse=True)
        headers = ['Name', 'Email', 'Last change made', 'Insertions', 'Deletions', 'Commits']
        print(tabulate.tabulate(tmp_maybe_new_cores, headers=headers,
                                tablefmt="grid"))

if __name__ == '__main__':
    main(sys.argv[1:])
