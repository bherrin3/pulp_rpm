# coding=utf-8
"""Tests that validate content in updateinfo.xml."""
import unittest

from pulp_smash import api, config
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
    sync,
)

from pulp_rpm.tests.functional.constants import (
    RPM_CONTENT_PATH,
    RPM_WITH_NON_ASCII_NAME,
    RPM_WITH_NON_ASCII_URL,
    RPM_UNSIGNED_URL,
    RPM_REMOTE_PATH,
)
from pulp_rpm.tests.functional.utils import (
    gen_rpm_remote,
    get_repodata,
    get_xml_content_from_fixture,
)

from pulp_rpm.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

class VerifyChecksumTypeUpdateInfo(unittest.TestCase):
    """Verify ``updateinfo.xml`` sum type is not unknown."""

    @classmethod
    def setUpClass(cls):
        """Create an RPM repository with a feed and a distributor."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide resources."""
        delete_orphans(cls.cfg)

    def test_all(self):
        """Sync and Publish a remote repo without "unknown checksum".

        1. Create a repository and a remote.
        2. Sync the remote
        3. Assert that the content of the summary does not contain
           "unknown checksum".
        """
        # Repo creation
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        # Create a remote
        body = gen_rpm_remote()
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])

        # Sync the repository
        repo = self.client.get(repo['_href'])

        # XML will need to be parsed
        # getting the update info from the fixtures repo
        update_info_fixtures = get_xml_content_from_fixture(
            fixture_path=RPM_UNSIGNED_URL,
            data_type='updateinfo',
        )
        # Does not contain <sum type="Unknown checksum"></sum>
    
    def test_set_repo_and_get_repo_data(self):
        """Create and Publish the required repo for this class.

        This method does the following:

        1. Create, sync and publish a repo with
           ``RPM_UNSIGNED_FEED_URL``
        2. Get ``updateinfo.xml`` of the published repo.

        :returns: A tuple containing the repo that is created, along with
            the ``updateinfo.xml`` of the created repo.
        """
        body = gen_repo(
            importer_config={'feed': RPM_UNSIGNED_URL},
            distributors=[gen_distributor(auto_publish=True)]
        )
        repo = self.client.post(REPO_PATH, body)
        self.addCleanup(self.client.delete, repo['_href'])
        sync(self.cfg, remote, repo)

        # getting the updateinfo from the published repo
        repo = self.client.get(repo['_href'], params={'details': True})
        return repo, get_repodata(
            self.cfg,
            repo['distributors'][0], 'updateinfo'
        )