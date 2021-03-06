# coding=utf-8
#
# This file is part of SickGear.
#
# SickGear is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickGear is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickGear.  If not, see <http://www.gnu.org/licenses/>.

import re
import traceback

from . import generic
from sickbeard import logger
from sickbeard.bs4_parser import BS4Parser
from sickbeard.helpers import tryInt
from lib.unidecode import unidecode


class WOPProvider(generic.TorrentProvider):

    def __init__(self):
        generic.TorrentProvider.__init__(self, 'WOP', cache_update_freq=10)

        self.url_home = ['https://www.worldofp2p.net/']

        self.url_vars = {'login': 'getrss.php', 'search': 'browse.php?%s' % '&'.join(
            ['search=%s', 'searchin=title', 'incldead=0', 'sort=4', 'type=desc', '%s'])}
        self.url_tmpl = {'config_provider_home_uri': '%(home)s', 'login': '%(home)s%(vars)s',
                         'search': '%(home)s%(vars)s'}

        self.categories = {'Season': [41], 'Episode': [35, 5, 58, 42, 36, 55, 39, 37, 54, 38]}
        self.categories['Cache'] = self.categories['Season'] + self.categories['Episode']

        self.digest, self.freeleech, self.minseed, self.minleech = 4 * [None]

    def _authorised(self, **kwargs):

        return super(WOPProvider, self)._authorised(
            logged_in=(lambda y=None: all(
                [(None is y or re.search('(?i)rss\slink', y)), self.has_all_cookies()] +
                [(self.session.cookies.get(x) or 'sg!no!pw') in self.digest for x in ['hashv']])),
            failed_msg=(lambda y=None: u'Invalid cookie details for %s. Check settings'))

    @staticmethod
    def _has_signature(data=None):
        return generic.TorrentProvider._has_signature(data) or (data and re.search(r'(?sim)<title[^<]+WOP', data))

    def _search_provider(self, search_params, **kwargs):

        results = []
        if not self._authorised():
            return results

        items = {'Cache': [], 'Season': [], 'Episode': [], 'Propers': []}

        rc = dict((k, re.compile('(?i)' + v)) for (k, v) in {
            'info': 'detail', 'get': 'download', 'filter': 'fa-(?:heart|star)'}.items())
        for mode in search_params.keys():
            for search_string in search_params[mode]:
                search_string = isinstance(search_string, unicode) and unidecode(search_string) or search_string
                search_url = self.urls['search'] % (search_string, self._categories_string(mode, 'cats2[]=%s'))

                html = self.get_url(search_url, timeout=90)

                cnt = len(items[mode])
                try:
                    if not html or self._has_no_results(html):
                        raise generic.HaltParseException

                    with BS4Parser(html, features=['html5lib', 'permissive']) as soup:
                        torrent_table = soup.find('table', class_='yenitorrenttable')
                        torrent_rows = [] if not torrent_table else torrent_table.find_all('tr')

                        if 2 > len(torrent_rows):
                            raise generic.HaltParseException

                        head = None
                        for tr in torrent_rows[1:]:
                            cells = tr.find_all('td')
                            if 5 > len(cells):
                                continue
                            try:
                                head = head if None is not head else self._header_row(
                                    tr, custom_tags=[('span', 'data-original-title')])
                                seeders, leechers, size = [n for n in [
                                    cells[head[x]].get_text().strip() for x in 'seed', 'leech', 'size']]
                                if (self.freeleech and not tr.find('i', class_=rc['filter'])) \
                                        or self._peers_fail(mode, seeders, leechers):
                                    continue

                                title = tr.find('a', href=rc['info']).get_text().strip()
                                download_url = self._link(tr.find('a', href=rc['get'])['href'])
                            except (AttributeError, TypeError, ValueError, KeyError):
                                continue

                            if title and download_url:
                                items[mode].append((title, download_url, seeders, self._bytesizer(size)))

                except generic.HaltParseException:
                    pass
                except (StandardError, Exception):
                    logger.log(u'Failed to parse. Traceback: %s' % traceback.format_exc(), logger.ERROR)

                self._log_search(mode, len(items[mode]) - cnt, search_url)

            results = self._sort_seeding(mode, results + items[mode])

        return results

    def _season_strings(self, ep_obj, **kwargs):

        return self._search_params(super(WOPProvider, self)._season_strings(ep_obj, **kwargs))

    def _episode_strings(self, ep_obj, **kwargs):

        return self._search_params(super(WOPProvider, self)._episode_strings(ep_obj, **kwargs))

    @staticmethod
    def _search_params(search_params):

        return [dict((k, ['*%s*' % re.sub('[.\s]', '*', v) for v in v]) for k, v in d.items()) for d in search_params]

    @staticmethod
    def ui_string(key):

        return 'wop_digest' == key and 'use... \'uid=xx; pass=yy; hashv=zz\'' or ''


provider = WOPProvider()
