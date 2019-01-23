# coding=utf-8
"""Utilities for tests for the rpm plugin."""
import os
from functools import partial
from io import StringIO
from unittest import SkipTest

from pulp_smash import api, cli, selectors
from pulp_smash.pulp3.constants import (
    REPO_PATH
)
from pulp_smash.pulp3.utils import (
    gen_publisher,
    gen_remote,
    gen_repo,
    get_content,
    require_pulp_3,
    require_pulp_plugins,
    sync,
)

from pulp_rpm.tests.functional.constants import (
    RPM_CONTENT_PATH,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_REMOTE_PATH,
    RPM_SIGNED_FIXTURE_URL,
    RPM_UNSIGNED_FIXTURE_URL,
)


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp_rpm isn't installed."""
    require_pulp_3(SkipTest)
    require_pulp_plugins({'pulp_rpm'}, SkipTest)


def get_repodata_repomd_xml(cfg, distributor, response_handler=None):
    """Download the given repository's ``repodata/repomd.xml`` file.

    :param cfg: Information about a Pulp
        host.
    :param distributor: A dict of information about a repository distributor.
    :param response_handler: The callback function used by
        ``pulp_smash.api.Client`` after downloading the ``repomd.xml`` file.
        Defaults to :func:`xml_handler`. Use ``pulp_smash.api.safe_handler`` if
        you want the raw response.
    :returns: Whatever is dictated by ``response_handler``.
    """
    path = urljoin('/pulp/repos/', distributor['config']['relative_url'])
    if not path.endswith('/'):
        path += '/'
    path = urljoin(path, 'repodata/repomd.xml')
    if response_handler is None:
        response_handler = xml_handler
    return api.Client(cfg, response_handler).get(path)


def gen_rpm_remote(url=None, **kwargs):
    """Return a semi-random dict for use in creating a RPM remote.

    :param url: The URL of an external content source.
    """
    if url is None:
        url = RPM_UNSIGNED_FIXTURE_URL

    return gen_remote(url, **kwargs)


def gen_rpm_publisher(**kwargs):
    """Return a semi-random dict for use in creating a Remote.

    :param url: The URL of an external content source.
    """
    publisher = gen_publisher()
    rpm_extra_fields = {
        **kwargs
    }
    publisher.update(rpm_extra_fields)
    return publisher


def get_rpm_package_paths(repo):
    """Return the relative path of content units present in a RPM repository.

    :param repo: A dict of information about the repository.
    :returns: A list with the paths of units present in a given repository.
    """
    return [
        content_unit['location_href']
        for content_unit in get_content(repo)[RPM_PACKAGE_CONTENT_NAME]
        if 'location_href' in content_unit
    ]


def populate_pulp(cfg, url=RPM_SIGNED_FIXTURE_URL):
    """Add RPM contents to Pulp.

    :param pulp_smash.config.PulpSmashConfig: Information about a Pulp
        application.
    :param url: The RPM repository URL. Defaults to
        :data:`pulp_smash.constants.RPM_UNSIGNED_FIXTURE_URL`
    :returns: A list of dicts, where each dict describes one RPM content in
        Pulp.
    """
    client = api.Client(cfg, api.json_handler)
    remote = {}
    repo = {}
    try:
        remote.update(client.post(RPM_REMOTE_PATH, gen_rpm_remote(url)))
        repo.update(client.post(REPO_PATH, gen_repo()))
        sync(cfg, remote, repo)
    finally:
        if remote:
            client.delete(remote['_href'])
        if repo:
            client.delete(repo['_href'])
    return client.get(RPM_CONTENT_PATH)['results']


def gen_yum_config_file(cfg, repositoryid, baseurl, name, **kwargs):
    """Generate a yum configuration file and write it to ``/etc/yum.repos.d/``.

    Generate a yum configuration file containing a single repository section,
    and write it to ``/etc/yum.repos.d/{repositoryid}.repo``.

    :param cfg: The system on which to create
        a yum configuration file.
    :param repositoryid: The section's ``repositoryid``. Used when naming the
        configuration file and populating the brackets at the head of the file.
        For details, see yum.conf(5).
    :param baseurl: The required option ``baseurl`` specifying the url of repo.
        For details, see yum.conf(5)
    :param name: The required option ``name`` specifying the name of repo.
        For details, see yum.conf(5).
    :param kwargs: Section options. Each kwarg corresponds to one option. For
        details, see yum.conf(5).
    :returns: The path to the yum configuration file.
    """
    # required repo options
    kwargs.setdefault('name', name)
    kwargs.setdefault('baseurl', baseurl)
    # assume some common used defaults
    kwargs.setdefault('enabled', 1)
    kwargs.setdefault('gpgcheck', 0)
    kwargs.setdefault('metadata_expire', 0)  # force metadata load every time
    # if sslverify is not provided in kwargs it is inferred from cfg
    kwargs.setdefault(
        'sslverify',
        'yes' if cfg.get_hosts('api')[0].roles['api'].get('verify') else 'no'
    )

    path = os.path.join('/etc/yum.repos.d/', repositoryid + '.repo')
    with StringIO() as section:
        section.write('[{}]\n'.format(repositoryid))
        for key, value in kwargs.items():
            section.write('{}: {}\n'.format(key, value))
        # machine.session is used here to keep SSH session open
        cli.Client(cfg).machine.session().run(
            'echo "{}" | {}tee {} > /dev/null'.format(
                section.getvalue(),
                '' if cli.is_root(cfg) else 'sudo ',
                path
            )
        )
    return path


def get_xml_content_from_fixture(fixture_path, data_type):
    """Return the required xml content from the given ``fixture_path``.

    This method should be called when an xml object of the following
    is ``data_type`` are required.

    * group
    * filelists
    * updateinfo
    * group_gz
    * modules
    * primary
    * other

    This function should be called only when the data of type xml is
    required. These ``data_type`` are present in repodata/repomd.xml
    file. The function parses the ``repomd.xml`` file, gathers the
    location of the data_type object, downloads the file and handles
    it using the ``xml_handler`` and finally returns
    ``xml.etree.Element`` of the root node.

    :param fixture_path: Url path containing the fixtures.
    :param data_type: The required xml file content that needs
        to be downloaded.
    :returns: An``xml.etree.Element`` object of the requested xml_file.

    """
    repo_path = urljoin(fixture_path, 'repodata/repomd.xml')
    response = utils.http_get(repo_path)
    root_elem = ElementTree.fromstring(response)

    xpath = '{{{}}}data'.format(RPM_NAMESPACES['metadata/repo'])
    data_elements = [
        elem for elem in root_elem.findall(xpath)
        if elem.get('type') == data_type
    ]
    xpath = '{{{}}}location'.format(RPM_NAMESPACES['metadata/repo'])
    relative_path = str(data_elements[0].find(xpath).get('href'))
    if 'xml' not in relative_path:
        raise Exception(
            "get_xml_content_from_fixture doesn't support non-xml data."
        )
    unit = requests.get(urljoin(fixture_path, relative_path))
    return xml_handler(None, unit)


def xml_handler(_, response):
    """Decode a response as if it is XML.

    This API response handler is useful for fetching XML files made available
    by an RPM repository. When it handles a response, it will check the status
    code of ``response``, decompress the response if the request URL ended in
    ``.gz``, and return an ``xml.etree.Element`` instance built from the
    response body.

    Note:

    * The entire response XML is loaded and parsed before returning, so this
      may be unsafe for use with large XML files.
    * The ``Content-Type`` and ``Content-Encoding`` response headers are
      ignored due to https://pulp.plan.io/issues/1781.
    """
    response.raise_for_status()
    if response.request.url.endswith('.gz'):  # See bug referenced in docstring
        with io.BytesIO(response.content) as compressed:
            with gzip.GzipFile(fileobj=compressed) as decompressed:
                xml_bytes = decompressed.read()
    else:
        xml_bytes = response.content
    # A well-formed XML document begins with a declaration like this:
    #
    #     <?xml version="1.0" encoding="UTF-8"?>
    #
    # We are trusting the parser to handle this correctly.
    return ElementTree.fromstring(xml_bytes)

skip_if = partial(selectors.skip_if, exc=SkipTest)
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""
