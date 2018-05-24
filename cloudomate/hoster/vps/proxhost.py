from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import itertools
import json
from builtins import int
from builtins import round
from builtins import super

import ssl
import requests

from forex_python.converter import CurrencyRates
from future import standard_library
from future.moves.urllib import request
from mechanicalsoup.utils import LinkNotFoundError

from cloudomate.gateway.bitpay import BitPay
from cloudomate.hoster.vps.solusvm_hoster import SolusvmHoster
from cloudomate.hoster.vps.vps_hoster import VpsOption

standard_library.install_aliases()


class ProxHost(SolusvmHoster):

    BASE_URL = 'https://codesalad.nl:5000/cloudomate'

    def __init__(self, settings):
        super(ProxHost, self).__init__(settings)

    '''
    Information about the Hoster
    '''

    @staticmethod
    def get_clientarea_url():
        return 'https://panel.linevast.de/clientarea.php'

    @staticmethod
    def get_gateway():
        return BitPay

    @staticmethod
    def get_metadata():
        return 'proxhost', 'https://codesalad.nl:5000/'

    @staticmethod
    def get_required_settings():
        return {
            'user': ['firstname', 'lastname', 'email', 'phonenumber', 'password'],
            'address': ['address', 'city', 'state', 'zipcode'],
        }

    '''
    Action methods of the Hoster that can be called
    '''

    @classmethod
    def get_options(cls):
        """
        Linux (OpenVZ) and Windows (KVM) pages are slightly different, therefore their pages are parsed by different
        methods. Windows configurations allow a selection of Linux distributions, but not vice-versa.
        :return: possible configurations.
        """
        context = ssl._create_unverified_context()
        url = ProxHost.BASE_URL + '/options'
        response = request.urlopen(url, context=context)
        response_json = json.loads(response.read().decode('utf-8'))

        options = []
        for joption in response_json:
            options.append(VpsOption(
                name=joption['name'],
                storage=joption['storage'],
                cores=joption['cores'],
                memory=joption['memory'],
                bandwidth='unmetered',
                connection=joption['connection'],
                price=joption['price'],
                purchase_url=joption['vmid']
            ))

        return list(options)

    def get_configuration(self):
        data = {
            'firstname': self._settings.get('user', "firstname"),
            'lastname': self._settings.get('user', "lastname"),
            'username': self._settings.get('user', "username"),
            'email': self._change_email_provider(self._settings.get('user', "email"), '@gmail.com'),
            'phonenumber': self._settings.get('user', "phonenumber"),
            'companyname': self._settings.get('user', "companyname"),
            'address1': self._settings.get('address', "address"),
            'city': self._settings.get('address', "city"),
            'state': self._settings.get('address', "state"),
            'postcode': self._settings.get('address', "zipcode"),
            'country': self._settings.get('address', 'countrycode'),
            'password': self._settings.get('user', "password"),
            'password2': self._settings.get('user', "password")
        }

        res = requests.post(self.BASE_URL+'/getconfiguration', json=data, verify=False)
        print(res)
        config = res.content.decode('utf8')
        return config

    def get_status(self):
        data = {
            'firstname': self._settings.get('user', "firstname"),
            'lastname': self._settings.get('user', "lastname"),
            'username': self._settings.get('user', "username"),
            'email': self._change_email_provider(self._settings.get('user', "email"), '@gmail.com'),
            'phonenumber': self._settings.get('user', "phonenumber"),
            'companyname': self._settings.get('user', "companyname"),
            'address1': self._settings.get('address', "address"),
            'city': self._settings.get('address', "city"),
            'state': self._settings.get('address', "state"),
            'postcode': self._settings.get('address', "zipcode"),
            'country': self._settings.get('address', 'countrycode'),
            'password': self._settings.get('user', "password"),
            'password2': self._settings.get('user', "password")
        }

        res = requests.post(self.BASE_URL+'/getstatus', json=data, verify=False)
        print(res)
        status = res.content.decode('utf8')
        return status

    def purchase(self, wallet, option):
        data = {
            'vmid': option.purchase_url,
            'price': option.price,
            'firstname': self._settings.get('user', "firstname"),
            'lastname': self._settings.get('user', "lastname"),
            'username': self._settings.get('user', "username"),
            'email': self._change_email_provider(self._settings.get('user', "email"), '@gmail.com'),
            'phonenumber': self._settings.get('user', "phonenumber"),
            'companyname': self._settings.get('user', "companyname"),
            'address1': self._settings.get('address', "address"),
            'city': self._settings.get('address', "city"),
            'state': self._settings.get('address', "state"),
            'postcode': self._settings.get('address', "zipcode"),
            'country': self._settings.get('address', 'countrycode'),
            'password': self._settings.get('user', "password"),
            'password2': self._settings.get('user', "password")
        }

        res = requests.post(self.BASE_URL+'/purchase', json=data, verify=False)
        print(res)
        pay_url = res.content.decode('utf8')
        print(pay_url)
        self.pay(wallet, self.get_gateway(), pay_url)

    '''
    Hoster-specific methods that are needed to perform the actions
    '''

    def _server_form(self):
        """
        Fills in the form containing server configuration.
        :return:
        """
        form = self._browser.select_form('form#frmConfigureProduct')
        self._fill_server_form()
        try:
            form['configoption[61]'] = '657'  # Ubuntu 16.04
        except LinkNotFoundError:
            form['configoption[125]'] = '549'  # Ubuntu 16.04
        self._browser.submit_selected()

    @classmethod
    def _parse_openvz_hosting(cls, page):
        table = page.find('table', {'class': 'plans-block'})
        details = table.tbody.tr
        names = table.findAll('div', {'class': 'plans-title'})
        i = 0
        for plan in details.findAll('div', {'class': 'plans-content'}):
            name = names[i].text.strip() + ' OVZ'
            option = cls._parse_openvz_option(plan, name)
            i = i + 1
            yield option

    @staticmethod
    def _parse_openvz_option(plan, name):
        elements = plan.findAll("div", {'class': 'info'})
        eur = float(plan.find('div', {'class': 'plans-price'}).span.text.replace('\u20AC', ''))
        option = VpsOption(
            name=name,
            storage=elements[0].text.split(' GB')[0],
            cores=elements[1].text.split(' vCore')[0],
            memory=elements[2].text.split(' GB')[0],
            bandwidth='unmetered',
            connection=int(elements[4].text.split(' GB')[0]) * 1000,
            price=round(CurrencyRates().convert("EUR", "USD", eur), 2),
            purchase_url=plan.a['href'],
        )
        return option

    @classmethod
    def _parse_kvm_hosting(cls, page):
        table = page.find('table', {'class': 'plans-block'})
        details = table.tbody.tr
        names = table.findAll('div', {'class': 'plans-title'})
        i = 0
        for plan in details.findAll('div', {'class': 'plans-content'}):
            name = names[i].text.strip() + ' KVM'
            option = cls._parse_kvm_option(plan, name)
            i = i + 1
            yield option

    @staticmethod
    def _parse_kvm_option(plan, name):
        elements = plan.findAll("div", {'class': 'info'})
        eur = float(plan.find('div', {'class': 'plans-price'}).span.text.replace('\u20AC', ''))
        option = VpsOption(
            name=name,
            storage=elements[0].text.split(' GB')[0],
            cores=elements[1].text.split(' vCore')[0],
            memory=elements[3].text.split(' GB')[0],
            bandwidth='unmetered',
            connection=int(elements[4].text.split(' GB')[0]) * 1000,
            price=round(CurrencyRates().convert("EUR", "USD", eur), 2),
            purchase_url=plan.a['href'],
        )
        return option

    @staticmethod
    def _extract_vi_from_links(links):
        for link in links:
            if "_v=" in link.url:
                return link.url.split("_v=")[1]
        return False

    @staticmethod
    def _check_login(text):
        data = json.loads(text)
        if data['success'] and data['success'] == '1':
            return True
        return False
