# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import os
import subprocess
import sys
from builtins import object
from builtins import str

from forex_python.bitcoin import BtcConverter
from future import standard_library
from mechanicalsoup import StatefulBrowser

standard_library.install_aliases()

if sys.version_info > (3, 0):
    from urllib.request import urlopen
else:
    from urllib2 import urlopen

AVG_TX_SIZE = 226
SATOSHI_TO_BTC = 0.00000001


def determine_currency(text):
    """
    Determine currency of text
    :param text: text cointaining a currency symbol
    :return: currency name of symbol
    """
    # Naive approach, for example NZ$ also contains $
    if '$' in text or 'usd' in text.lower():
        return 'USD'
    elif '€' in text or 'eur' in text.lower():
        return 'EUR'
    else:
        return None


def get_rate(currency='USD'):
    """
    Return price of 1 currency in BTC
    Supported currencies available at 
    http://forex-python.readthedocs.io/en/latest/currencysource.html#list-of-supported-currency-codes
    :param currency: currency to convert to
    :return: conversion rate from currency to BTC
    """
    if currency is None:
        return None
    b = BtcConverter()
    factor = b.get_latest_price(currency)
    if factor is None:
        factor = 1.0 / fallback_get_rate(currency)
    return 1.0 / factor


def fallback_get_rate(currency):
    # Sometimes the method above gets rate limited, in this case use
    # https: // blockchain.info / tobtc?currency = USD & value = 500
    return float(urlopen('https://blockchain.info/tobtc?currency={0}&value=1'.format(currency)).read())


def get_rates(currencies):
    """
    Return rates for all currencies to BTC.
    :return: conversion rates from currencies to BTC
    """
    rates = {cur: get_rate(cur) for cur in currencies}
    return rates


def get_price(amount, currency='USD'):
    """
    Convert price from one currency to bitcoins
    :param amount: number of currencies to convert
    :param currency: currency to convert from
    :return: price in bitcoins
    """
    price = amount * get_rate(currency)
    return price


def _get_network_cost(speed):
    br = StatefulBrowser(user_agent='Firefox')
    page = br.open('https://bitcoinfees.21.co/api/v1/fees/recommended')
    response = page.json()
    satoshirate = float(response[speed])
    return satoshirate


def get_network_fee(speed='halfHourFee'):
    """
    Give an estimate of network fee for the average bitcoin transaction for given speed.
    Supported speeds are available at https://bitcoinfees.21.co/api/v1/fees/recommended
    :return: network cost
    """
    network_fee = _get_network_cost(speed) * SATOSHI_TO_BTC
    return network_fee * AVG_TX_SIZE


class Wallet(object):
    """
    Wallet implements an adapter to the wallet handler.
    Currently Wallet only supports electrum wallets without passwords for automated operation.
    Wallets with passwords may still be used, but passwords will have to be entered manually.
    """

    def __init__(self, wallet_command=None, wallet_path=None, testnet=None):
        if wallet_command is None:
            if os.path.exists('/usr/local/bin/electrum'):
                wallet_command = ['/usr/local/bin/electrum']
            else:
                wallet_command = ['/usr/bin/env', 'electrum']
        if testnet:
            wallet_command.append('--testnet')
        self.command = wallet_command
        self.wallet_handler = ElectrumWalletHandler(wallet_command, wallet_path)

    def get_balance(self, confirmed=True, unconfirmed=True):
        """
        Return the balance of the default electrum wallet
        Confirmed and unconfirmed can be set to indicate which balance to retrieve.
        :param confirmed: default: True
        :param unconfirmed: default: True
        :return: balance of default wallet
        """
        balance_output = self.wallet_handler.get_balance()
        balance = 0.0
        if confirmed:
            balance = balance + float(balance_output.get('confirmed', 0.0))
        if unconfirmed:
            balance = balance + float(balance_output.get('unconfirmed', 0.0))
        return balance

    def get_balance_confirmed(self):
        """
        Return confirmed balance of default electrum wallet
        :return: 
        """
        return self.get_balance(confirmed=True, unconfirmed=False)

    def get_balance_unconfirmed(self):
        """
        Return unconfirmed balance of default electrum wallet
        :return: 
        """
        return self.get_balance(confirmed=False, unconfirmed=True)

    def get_addresses(self):
        """
        Return the list of addresses of the default electrum wallet
        :return: 
        """
        address_output = self.wallet_handler.get_addresses()
        return address_output

    def pay(self, address, amount, fee=None):
        tx_fee = 0 if fee is None else fee
        if self.get_balance() < amount + tx_fee:
            print('Not enough funds')
            return

        transaction_hex = self.wallet_handler.create_transaction(amount, address)
        success, transaction_hash = self.wallet_handler.broadcast(transaction_hex)
        if not success:
            print(('Transaction not successfully broadcast, do error handling: {0}'.format(transaction_hash)))
        else:
            print('Transaction successful')
        print(transaction_hex)
        print(success)
        return transaction_hash


class ElectrumWalletHandler(object):
    """
    ElectrumWalletHandler ensures the correct opening and closing of the electrum wallet daemon
    """

    def __init__(self, wallet_command=None, wallet_path=None):
        """
        Allows wallet_command to be changed to for example electrum --testnet
        :param wallet_command: command to call wallet
        """
        self._wallet_path = wallet_path

        if wallet_command is None:
            if os.path.exists('/usr/local/bin/electrum'):
                wallet_command = ['/usr/local/bin/electrum']
            else:
                wallet_command = ['/usr/bin/env', 'electrum']
        self.command = wallet_command
        p, e = subprocess.Popen(self.command + ['daemon', 'status'], stdout=subprocess.PIPE).communicate()
        self.not_running_before = b'not running' in p
        if self.not_running_before:
            subprocess.call(self.command + ['daemon', 'start'])

        if wallet_path is not None:
            print('Using wallet: ', wallet_path)
        self._command(['daemon', 'load_wallet'], output=False)

    def __del__(self):
        if self.not_running_before:
            subprocess.call(self.command + ['daemon', 'stop'])

    def create_transaction(self, amount, address, fee=None):
        """
        Create a transaction
        :param amount: amount of bitcoins to be transferred
        :param address: address to transfer to
        :param fee: None for autofee, or specify own fee
        :return: transaction details
        """
        if fee is None:
            transaction = self._command(['payto', str(address), str(amount)])
        else:
            transaction = self._command( ['payto', str(address), str(amount), '-f', str(fee)])
        jtrs = json.loads(transaction)
        return jtrs['hex']

    def broadcast(self, transaction):
        """
        Broadcast a transaction
        :param transaction: hex of transaction
        :return: if successful returns success and
        """
        broadcast = self._command(['broadcast', transaction])
        jbr = json.loads(broadcast)
        return tuple(jbr)

    def get_balance(self):
        """
        Return the balance of the default electrum wallet
        :return: balance of default wallet
        """
        output = self._command(['getbalance'])
        print('\n\n', output, '\n\n')
        balance_dict = json.loads(output)
        return balance_dict

    def get_addresses(self):
        """
        Return the list of addresses of default wallet
        :return: 
        """
        address = self._command(['listaddresses'])
        addr = json.loads(address)
        return addr

    def _command(self, c, output=True):
        command = self.command + c
        if self._wallet_path is not None:
            command += ['-w', self._wallet_path]

        if output:
            return subprocess.check_output(command).decode()
        else:
            subprocess.call(command)


class TriblerWallet(object):
    """
    This class expects Tribler to be running and uses the wallet created via Tribler
    """

    def __init__(self, testnet=None):
        if testnet:
            self.coin = 'TBTC'
        else:
            self.coin = 'BTC'

    def get_balance(self):
        data = ['curl', '-X', 'GET', 'http://localhost:8085/wallets/' + self.coin + '/balance']

        response = subprocess.Popen(data, stdout=subprocess.PIPE).communicate()[0]
        available = json.loads(response)['balance']['available']
        return float(available)

    def pay(self, address, amount, fee=None):

        """ Make call to Tribler wallet for paying to address """
        tx_fee = 0 if fee is None else fee

        if self.get_balance() < amount + tx_fee:
            print('Not enough funds')
            return

        data = ['curl', '-X', 'POST', 'http://localhost:8085/wallets/' + self.coin + '/transfer',
                '--data', 'amount=' + str(amount + tx_fee) + '&destination=' + address]

        response = subprocess.Popen(data, stdout=subprocess.PIPE).communicate()[0]

        if not response:
            print('Transaction unsuccessfull')
        else:
            print('Transaction successful')
            transaction_hash = json.loads(response)['txid']
            print(transaction_hash)
            return transaction_hash
