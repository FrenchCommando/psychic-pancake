from itertools import islice
from utils.forms_functions import get_main_info, computation_2020 as computation
from utils.form_worksheet_names import *
from utils.forms_constants import logger


def fill_taxes_2020(d, output_2019=None):
    if output_2019 is not None:
        states_2019, worksheets_all_2019 = output_2019

    main_info = get_main_info(d)
    wages = sum(w['Wages'] for w in d['W2'])
    federal_tax = sum(w['Federal_tax'] for w in d['W2'])
    social_security_tax = sum(w['SocialSecurity_tax'] for w in d['W2'])
    medicare_tax = sum(w['Medicare_tax'] for w in d['W2'])
    state_tax = sum(w['State_tax'] for w in d['W2'])
    local_tax = sum(w['Local_tax'] for w in d['W2'])

    has_1099 = '1099' in d
    dividends_qualified = None
    additional_income = None
    health_savings_account = d.get('health_savings_account', False)

    if has_1099:
        n_trades = sum(len(i['Trades']) for i in d['1099'] if 'Trades' in i)
        # additional_income = n_trades > 0
        sum_trades = {"SHORT": {"Proceeds": 0, "Cost": 0, "Adjustment": 0, "Gain": 0},
                      "LONG": {"Proceeds": 0, "Cost": 0, "Adjustment": 0, "Gain": 0}}  # from 8949 to fill 1040sd

    standard_deduction = 12400  # if single or married filing separately
    qualified_business_deduction = 0

    forms_state = {}  # mapping name of forms with content
    worksheets = {}  # worksheets need not be printed

    class Form:
        def __init__(self, key):
            self.key = key
            self.d = {}
            forms_state[self.key] = self.d

        def push_to_dict(self, key, value, round_i=2):
            if value != 0:
                self.d[key] = round(value, round_i)

        def push_name_ssn(self, prefix="", suffix=""):
            self.d[prefix + 'name' + suffix] = forms_state[k_1040]['self_first_name_initial'] \
                             + " " + forms_state[k_1040]['self_last_name']
            self.d[prefix + 'ssn' + suffix] = main_info['ssn']

        def push_sum(self, key, it):
            self.d[key] = sum(self.d.get(k, 0) for k in it)

        def revert_sign(self, key):
            if key in self.d:
                self.d[key] = -self.d[key]

        def build(self):
            raise NotImplementedError()

    class Form1040(Form):
        def __init__(self):
            Form.__init__(self, k_1040)

        def build(self):
            first_name_and_initial = main_info['first_name']
            if main_info['initial'] != "":
                first_name_and_initial += " " + main_info['initial']
            self.d.update({
                'single': True,
                'self_first_name_initial': first_name_and_initial,
                'self_last_name': main_info['last_name'],
                'self_ssn': main_info['ssn'],
                'address': main_info['address_street_and_number'],
                'apt': main_info['address_apt'],
                'city': main_info['address_city'],
                'state': main_info['address_state'],
                'zip': main_info['address_zip'],
                'full_year_health_coverage_or_exempt': d['full_year_health_coverage_or_exempt'],
                'presidential_election_self': d['presidential_election_self'],
                'self_occupation': d['occupation'],
                'phone': d['phone'],
                'email': d['email'],
            })

            if d.get('virtual_currency', False):
                self.push_to_dict('virtual_currency_y', True)
                self.push_to_dict('virtual_currency_n', False)
            else:
                self.push_to_dict('virtual_currency_y', False)
                self.push_to_dict('virtual_currency_n', True)

            self.push_to_dict('1', wages)

            if has_1099:
                Form1040sb().build()
                self.push_to_dict('2_b', forms_state[k_1040sb]['4_value'])
                self.push_to_dict('3_b', forms_state[k_1040sb]['6_value'])

                if forms_state[k_1040sb]['4_value'] == 0 \
                        and forms_state[k_1040sb]['6_value'] == 0 \
                        and 'foreign_account' not in d:
                    del forms_state[k_1040sb]

                nonlocal dividends_qualified
                dividends_qualified = sum(i.get('Qualified Dividends', 0) for i in d['1099'])
                self.push_to_dict('3_a', dividends_qualified)

            self.d["7_n"] = not d['scheduleD']
            if d['scheduleD']:
                Form8949().build()  # build 8949 first
                Form1040sd().build()
                if '21' in forms_state[k_1040sd]:
                    self.push_to_dict('7_value', -forms_state[k_1040sd]['21'])
                else:
                    self.push_to_dict('7_value', forms_state[k_1040sd]['16'])

            if health_savings_account or additional_income:
                # fill 8889 and schedule 1
                Form8889().build()
                Form1040s1().build()
                self.push_to_dict('8', forms_state[k_1040s1]['9'])
                self.push_to_dict('10_a', forms_state[k_1040s1].get('22', 0))

            self.push_sum('9', ['1', '2_b', '3_b', '4_b', '5_b', '6_b', '7_value', '8'])  # total income

            # 10_b charitable contributions

            self.push_sum('10_c', ['10_a', '10_b'])  # total adjustments to income

            self.push_to_dict('11', self.d['9'] - self.d.get('10_c', 0))  # Adjusted Gross Income

            Form1040sa().build()
            itemized_deduction = forms_state[k_1040sa].get('17', 0)
            if itemized_deduction > standard_deduction:
                self.push_to_dict('12', itemized_deduction)
            else:
                self.push_to_dict('12', standard_deduction)

            self.push_to_dict('13', qualified_business_deduction)
            self.push_sum('14', ['12', '13'])
            self.push_to_dict('15', max(0, self.d.get('11', 0) - self.d.get('14', 0)))  # Taxable income

            if dividends_qualified:
                qualified_dividend_worksheet = QualifiedDividendsCapitalGainTaxWorksheet()
                qualified_dividend_worksheet.build()
                self.push_to_dict('16', worksheets[w_qualified_dividends_and_capital_gains][25])
            else:
                self.push_to_dict('16', computation(self.d['15']))

            # # add from 11b
            # should_fill = ShouldFill6251Worksheet()
            # should_fill.build()
            # awt = 0
            # if should_fill.fill6251:
            #     Form1040s2().build()
            #     Form6251().build()
            #     awt = forms_state[k_6251]['11_dollar']
            # if awt > 0:
            #     self.d['11b'] = True
            #     self.push_to_dict('11_dollar', self.d['11a_tax'] + awt)
            # else:
            #     self.push_sum('11_dollar', ['11a_tax'])
            # if has_1099:
            #     Form1040s3().build()
            #     foreign_tax = forms_state[k_1040s3]['55_dollar']
            #     if foreign_tax != 0:
            #         self.d['12b'] = True
            #         self.push_to_dict('12_dollar', forms_state[k_1040s3]['55_dollar'])
            #     else:
            #         del forms_state[k_1040s3]

            self.push_to_dict('17', 0)  # schedule 2 line 3
            self.push_sum('18', ['16', '17'])  # plus schedule 2 line 3
            self.push_to_dict('19', 0)  # child tax credit
            self.push_to_dict('20', 0)  # schedule 3 line 7
            self.push_sum('21', ['19', '20'])
            self.push_to_dict('22', max(0, self.d.get('18', 0) - self.d.get('21', 0)))
            self.push_to_dict('23', 0)  # other taxes from Schedule 2 line 10
            self.push_sum('24', ['22', '23'])  # total tax

            self.push_to_dict('25_a', federal_tax)  # from W2
            self.push_to_dict('25_b', 0)  # from 1099
            self.push_to_dict('25_c', 0)  # from other
            self.push_sum('25_d', ['25_a', '25_b', '25_c'])

            self.push_to_dict('26', 0)  # estimated payments

            self.push_to_dict('27', 0)  # Earned Income Credit
            self.push_to_dict('28', 0)  # Additional child tax Credit
            self.push_to_dict('29', 0)  # American opportunity credit Form 8863, line 8
            self.push_to_dict('30', 0)  # Recovery rebate credit
            self.push_to_dict('31', 0)  # Schedule 3, line 13
            self.push_sum('32', ['27', '28', '29', '30', '31'])  # total other payments and refundable credit

            self.push_sum('33', ['25_d', '26', '32'])  # total payments

            # refund
            overpaid = self.d['33'] - self.d['24']
            if overpaid > 0:
                self.push_to_dict('34', overpaid)
                # all refunded
                self.push_to_dict('35a_value', overpaid)
                self.d['35b'] = d['routing_number']
                if d['checking']:
                    self.d['35c_checking'] = True
                else:
                    self.d['35c_savings'] = True
                self.d['35d'] = d['account_number']
                self.d['36'] = "-0-"
            else:
                self.push_to_dict('37', -overpaid)
                self.push_to_dict('38', 0)

    class Form1040NR(Form):
        def __init__(self):
            Form.__init__(self, k_1040nr)

    class Form1040s1(Form):
        def __init__(self):
            Form.__init__(self, k_1040s1)

        def build(self):
            self.push_name_ssn()
            if k_8889 in forms_state:
                hsa_deduction = forms_state[k_8889].get('13', 0)
                if hsa_deduction > 0:
                    self.push_to_dict('12', hsa_deduction)
                hsa_taxable_distribution = forms_state[k_8889].get('16', 0)
                if hsa_taxable_distribution > 0:
                    self.push_to_dict('8_amount', hsa_taxable_distribution)
                    self.push_to_dict('8_type1', "HSA")
            self.push_sum('9', ['1', '2_a', '3', '4', '5', '6', '7', '8_amount'])
            # to 1040 line 8

            self.push_sum('22', ['10', '11', '12', '13', '14', '15', '16', '17'
                                 '18_a', '19', '20', '21'])
            # to 1040 line 10a

    class Form1040s2(Form):
        def __init__(self):
            Form.__init__(self, k_1040s2)

        def build(self):
            self.push_name_ssn()

    class Form1040s3(Form):
        def __init__(self):
            Form.__init__(self, k_1040s3)

        def build(self):
            self.push_name_ssn()
            # I don't need the 1116
            # https://turbotax.intuit.com/tax-tips/military/filing-irs-form-1116-to-claim-the-foreign-tax-credit/L2ODfqp89
            foreign_tax = sum(i.get('Foreign Tax', 0) for i in d['1099'])
            self.push_to_dict('48_dollar', foreign_tax)
            self.push_sum('55_dollar', [str(i) + "_dollar" for i in range(48, 55)])

    class Form1040sa(Form):
        def __init__(self):
            Form.__init__(self, k_1040sa)

        def build(self):
            self.push_name_ssn()

            self.push_to_dict('1', d.get('medical_expenses', 0))
            self.push_to_dict('2', forms_state[k_1040]['11'])
            self.push_to_dict('3', self.d['2'] * 0.075)
            self.push_to_dict('4', max(0, self.d.get('1', 0) - self.d['3']))

            if d.get('deduct_sales_tax', False):
                self.push_to_dict('5_a_y', True)
                self.push_to_dict('5_a', d.get('deduct_sales_tax_amount', 0))
            else:
                self.push_to_dict('5_a', state_tax + local_tax)

            self.push_sum('5_d', ['5_a', '5_b', '5_c'])
            self.push_to_dict('5_e', min(self.d.get('5_d', 0), 10000))
            # 6 is other
            self.push_sum('7', ['5_e', '6'])

            # mortgage interest
            # charity
            # theft
            # other

            self.push_sum('17', ['4', '7', '10', '14', '15', '16'])
            # to 1040 line 12

            # tick 18 if you want to lose money

    class Form1040sb(Form):
        def __init__(self):
            Form.__init__(self, k_1040sb)

        def build(self):
            self.push_name_ssn()

            if len(d['1099']) > 14:
                logger.error("1040sb - too many brokers")

            def fill_value(index, key):
                i = 1
                for f in d['1099']:
                    if key in f and f[key] != 0:
                        self.d["{}_{}_payer".format(index, str(i))] = f['Institution']
                        self.push_to_dict("{}_{}_value".format(index, str(i)), f[key])
                        i += 1
            fill_value("1", "Interest")
            fill_value("5", "Ordinary Dividends")

            self.push_sum('2_value', ['1_{}_value'.format(str(i)) for i in range(1, 15)])
            self.push_to_dict('4_value', self.d.get('2_value', 0) - self.d.get('3_value', 0))
            self.push_sum('6_value', ['5_{}_value'.format(str(i)) for i in range(1, 17)])

            if 'foreign_account' in d:
                self.d['7a_y'] = True
                self.d['7a_yes_y'] = True
                self.d['7b'] = d['foreign_account']
                self.d['8_n'] = True

    class Form1040sd(Form):
        def __init__(self):
            Form.__init__(self, k_1040sd)

        def build(self):
            self.push_name_ssn()

            self.d['dispose_opportunity_n'] = True

            # short / long term gains
            def fill_gains(ls_key, index):
                self.push_to_dict('{}b_proceeds'.format(index), sum_trades[ls_key]['Proceeds'], 2)
                self.push_to_dict('{}b_cost'.format(index), sum_trades[ls_key]['Cost'], 2)
                self.push_to_dict('{}b_adjustments'.format(index), sum_trades[ls_key]['Adjustment'], 2)
                self.push_to_dict('{}b_gain'.format(index), sum_trades[ls_key]['Gain'], 2)
            fill_gains("SHORT", "1")
            fill_gains("LONG", "8")

            # fill capital loss carryover worksheet
            capital_loss = CapitalLossCarryoverWorksheet()
            capital_loss.build()
            self.push_to_dict('6', -worksheets[w_capital_loss_carryover][8])
            self.push_to_dict('14', -worksheets[w_capital_loss_carryover][13])

            self.push_sum('7', ['1a_gain', '1b_gain', '2_gain', '3_gain', '4', '5', '6'])
            self.push_sum('15', ['8a_gain', '8b_gain', '9_gain', '10_gain', '11', '12', '13', '14'])
            self.push_sum('16', ['7', '15'])

            self.revert_sign('6')
            self.revert_sign('14')

            if self.d['16'] > 0:
                if self.d['15'] < 0 or self.d['16'] < 0:
                    self.d['17_n'] = True

                else:
                    self.d['17_y'] = True

                    # 18 is '28% Rate Gain Worksheet'
                    # 19 is `Unrecaptured Section 1250 Gain Worksheet`
                    # 20 more worksheet and 4952
                    form_4952 = False
                    if self.d.get('18', 0) == 0 and self.d.get('19', 0) == 0 and not form_4952:
                        self.d['20_y'] = True
                    else:
                        self.d['20_n'] = True
                    return  # don't fill 22

            elif self.d['16'] < 0:
                capital_loss_limit = 3000 if d['single'] else 1500
                self.push_to_dict('21', min(capital_loss_limit, -self.d['16']))

            if dividends_qualified > 0:
                self.d['22_y'] = True
            else:
                self.d['22_n'] = True

    class Form6251(Form):
        def __init__(self):
            Form.__init__(self, k_6251)

        def build(self):
            self.push_name_ssn()

    class Form8889(Form):
        def __init__(self):
            Form.__init__(self, k_8889)

        def build(self):
            self.push_name_ssn()

            self.d['1_self'] = True

            self.push_to_dict('2', d.get('health_savings_account_contributions', 0))
            self.push_to_dict('3', 3550)
            self.push_to_dict('4', 0)
            self.push_to_dict('5', self.d['3'] - self.d.get('4', 0))
            self.push_to_dict('6', self.d['5'])  # except if you have separate for spouse
            self.push_to_dict('7', 0)
            self.push_sum('8', ['6', '7'])
            self.push_to_dict('9', d.get('health_savings_account_employer_contributions', 0))
            self.push_to_dict('10', 0)
            self.push_sum('11', ['9', '10'])
            self.push_to_dict('12', max(0, self.d['8'] - self.d['11']))
            self.push_to_dict('13', min(self.d.get('2', 0), self.d['12']))  # to Schedule 1-II-12

            self.push_to_dict('14_a', d.get('health_savings_account_distributions', 0))
            self.push_to_dict('14_b', 0)  # distribution rolled over
            self.push_to_dict('14_c', self.d['14_a'] - self.d.get('14_b', 0))
            self.push_to_dict('15', self.d['14_c'])  # I don't assume it to be different

            self.push_to_dict('16', self.d['14_c'] - self.d['15'])
            # if positive, Schedule 1-I-8 HSA

            # Then is part III, not implemented

    class Form8949(Form):  # may need several of them when many transactions
        def __init__(self):
            Form.__init__(self, k_8949)

        def build(self):
            def yield_trades(long_short, form_code):
                for uu in d['1099']:
                    if 'Trades' in uu:
                        for tt in uu['Trades']:
                            if long_short in tt['LongShort'] and form_code == tt['FormCode']:
                                yield tt

            # need a-b-c granularity here
            # a means "Covered/Uncovered" == 'COVERED' --  "FormCode" == "A"
            # b means "Covered/Uncovered" == 'UNCOVERED' --  "FormCode" == "B"

            trades_subsets = []
            trades_per_page_limit = 14
            for code in ["A", "B", "C", "D", "E", "F"]:
                trades_short = yield_trades(long_short='SHORT', form_code=code)
                trades_long = yield_trades(long_short='LONG', form_code=code)
                while True:
                    trades = {
                        'SHORT': list(islice(trades_short, trades_per_page_limit)),
                        'LONG': list(islice(trades_long, trades_per_page_limit))
                    }
                    if len(trades['SHORT']) == 0 and len(trades['LONG']) == 0:
                        break
                    trades_subsets.append((code, trades))

            # accumulate the proceeds/cost/adjustment/gain for 1040sd

            if len(trades_subsets) == 1:
                # if few enough trades
                forms_state[k_8949] = self.build_one(trades_subsets[0])
            else:
                # if many -> use a list of content dictionaries
                ll = [self.build_one(l) for l in trades_subsets]
                forms_state[k_8949] = ll

        def build_one(self, code_trades):
            code, trades = code_trades
            self.d = {}
            self.push_name_ssn(prefix="I_")
            self.push_name_ssn(prefix="II_")

            def fill_trades(ls_key, check_key, index):
                if len(trades[ls_key]) > 0:
                    self.d[check_key] = True
                    s_proceeds, s_cost, s_adj, s_gain = 0, 0, 0, 0
                    for i, t in enumerate(trades[ls_key], 1):
                        self.d['{}_1_{}_description'.format(index, str(i))] = t['SalesDescription']
                        self.d['{}_1_{}_date_acq'.format(index, str(i))] = t['DateAcquired']
                        self.d['{}_1_{}_date_sold'.format(index, str(i))] = t['DateSold']

                        proceeds = t['Proceeds']
                        self.push_to_dict('{}_1_{}_proceeds'.format(index, str(i)), proceeds, 2)
                        cost = t['Cost']
                        self.push_to_dict('{}_1_{}_cost'.format(index, str(i)), cost, 2)

                        if 'WashSaleValue' in t:
                            adj = t['WashSaleValue']
                            self.push_to_dict('{}_1_{}_adjustment'.format(index, str(i)), adj, 2)
                            self.d['{}_1_{}_code'.format(index, str(i))] = t['WashSaleCode']
                        else:
                            adj = 0

                        gain = proceeds - cost + adj
                        self.push_to_dict('{}_1_{}_gain'.format(index, str(i)), gain, 2)

                        s_proceeds += proceeds
                        s_cost += cost
                        s_adj += adj
                        s_gain += gain

                    self.push_to_dict('{}_2_proceeds'.format(index), s_proceeds, 2)
                    self.push_to_dict('{}_2_cost'.format(index), s_cost, 2)
                    self.push_to_dict('{}_2_adjustment'.format(index), s_adj, 2)
                    self.push_to_dict('{}_2_gain'.format(index), s_gain, 2)

                    sum_trades[ls_key]['Proceeds'] += s_proceeds
                    sum_trades[ls_key]['Cost'] += s_cost
                    sum_trades[ls_key]['Adjustment'] += s_adj
                    sum_trades[ls_key]['Gain'] += s_gain

            # code is A, B, or C

            fill_trades('SHORT', f'short_{code.lower()}', 'I')
            fill_trades('LONG', f'long_{code.lower()}', 'II')
            return self.d.copy()

    class Worksheet:
        def __init__(self, key, n):
            self.key = key
            self.d = [0 for i in range(n + 1)]
            worksheets[self.key] = self.d

        def build(self):
            raise NotImplementedError()

    class CapitalLossCarryoverWorksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_capital_loss_carryover, 13)

        def build(self):
            ddd = d
            fff = forms_state
            www = worksheets
            self.d[1] = states_2019[k_1040]['11_b']
            self.d[2] = max(0, states_2019[k_1040sd]['21'])
            self.d[3] = max(0, self.d[1] + self.d[2])
            self.d[4] = min(self.d[2], self.d[3])
            self.d[5] = max(0, -states_2019[k_1040sd]['7'])
            self.d[6] = max(0, states_2019[k_1040sd]['15'])
            self.d[7] = self.d[4] + self.d[6]
            self.d[8] = max(0, self.d[5] - self.d[7])
            if self.d[6] == 0:
                self.d[9] = max(0, -states_2019[k_1040sd]['15'])
                self.d[10] = max(0, states_2019[k_1040sd]['7'])
                self.d[11] = max(0, self.d[4] - self.d[5])
                self.d[12] = self.d[10] + self.d[11]
                self.d[13] = max(0, self.d[9] - self.d[12])

    class QualifiedDividendsCapitalGainTaxWorksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_qualified_dividends_and_capital_gains, 27)

        def build(self):
            self.d[1] = forms_state[k_1040]['15']
            self.d[2] = forms_state[k_1040]['3_a']
            if d['scheduleD']:
                self.d[3] = max(0, min(forms_state[k_1040sd]['15'], forms_state[k_1040sd]['16']))
            else:
                self.d[3] = forms_state[k_1040s1]['7']
            self.d[4] = self.d[2] + self.d[3]
            self.d[5] = max(0, self.d[1] - self.d[4])
            self.d[6] = 40000  # single
            self.d[7] = min(self.d[1], self.d[6])
            self.d[8] = min(self.d[5], self.d[7])
            self.d[9] = self.d[7] - self.d[8]  # taxed 0%
            self.d[10] = min(self.d[1], self.d[4])
            self.d[11] = self.d[9]
            self.d[12] = self.d[11] - self.d[10]
            self.d[13] = 441450  # single
            self.d[14] = min(self.d[1], self.d[13])
            self.d[15] = self.d[5] + self.d[9]
            self.d[16] = max(0, self.d[14] - self.d[15])
            self.d[17] = min(self.d[12], self.d[16])
            self.d[18] = self.d[17] * 0.15
            self.d[19] = self.d[9] + self.d[17]
            self.d[20] = self.d[10] - self.d[19]
            self.d[21] = self.d[20] * 0.2
            self.d[22] = computation(amount=self.d[5])
            self.d[23] = self.d[18] + self.d[21] + self.d[22]
            self.d[24] = computation(self.d[1])
            self.d[25] = min(self.d[23], self.d[24])

    class ShouldFill6251Worksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_should_fill_6251, 13)
            self.fill6251 = None

        def build(self):
            if k_1040sa in forms_state:
                self.d[1] = forms_state[k_1040]['10_dollar']
                self.d[2] = forms_state[k_1040sa]['7']
                self.d[3] = self.d[1] + self.d[2]
            self.d[4] = forms_state[k_1040s1].get('10_dollar', 0) \
                + forms_state[k_1040s1].get('21_dollar', 0) \
                if k_1040s1 in forms_state else 0
            self.d[5] = self.d[3] - self.d[4]
            self.d[6] = 70300  # single
            if self.d[5] <= self.d[6]:
                self.fill6251 = False
                return
            self.d[7] = self.d[5] - self.d[6]
            self.d[8] = 500000  # single
            if self.d[5] <= self.d[8]:
                self.d[9] = 0
                self.d[11] = self.d[7]
            else:
                self.d[9] = self.d[5] - self.d[8]
                self.d[10] = min(self.d[9] * 0.25, self.d[6])
                self.d[11] = self.d[7] + self.d[10]
            if self.d[11] >= 191100:  # single
                self.fill6251 = True
                return
            self.d[12] = self.d[11] * 0.26
            self.d[13] = forms_state[k_1040]['11a'] \
                + forms_state[k_1040s2]['46']
            self.fill6251 = (self.d[13] < self.d[12])

    if d['resident']:
        Form1040().build()  # one other version for NR
    else:
        logger.error("Non-resident not yet implemented")
        # Form1040NR().build()  # one other version for NR
    return forms_state, worksheets
