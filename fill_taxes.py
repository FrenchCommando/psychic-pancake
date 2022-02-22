import os
import json
from utils.forms_constants import *
from utils.forms_utils import fill_pdf_from_keys, logging, process_logger, map_folders, load_keys, output_pdf_folder
from pdfrw import PdfReader, PdfWriter
from utils.user_interface import update_dict
from utils.forms_core_2018 import fill_taxes_2018
from utils.forms_core_2019 import fill_taxes_2019
from utils.forms_core_2020 import fill_taxes_2020
from utils.forms_core_2021 import fill_taxes_2021


logger = logging.getLogger('fill_taxes')
process_logger(logger, file_name='fill_taxes')


def fill_pdfs(forms_state, forms_year_folder):
    map_folders(output_pdf_folder, forms_year_folder)
    form_year_folder = os.path.join(forms_folder, forms_year_folder)
    output_year_folder = os.path.join(output_pdf_folder, forms_year_folder)

    all_out_files = []
    for f, d_contents in forms_state.items():
        d_mapping = load_keys(os.path.join(form_year_folder, f + keys_extension))

        def fill_one_pdf(contents, suffix=""):
            ddd = {k: contents[val[0]] for k, val in d_mapping.items() if val[0] in contents}
            outfile = os.path.join(output_year_folder, f + suffix + pdf_extension)
            all_out_files.append(outfile)
            fill_pdf_from_keys(file=os.path.join(form_year_folder, f + pdf_extension),
                               out_file=outfile, d=ddd)
        if isinstance(d_contents, list):
            for i, one_content in enumerate(d_contents):
                fill_one_pdf(one_content, "_" + str(i))
        elif isinstance(d_contents, dict):
            fill_one_pdf(d_contents)
    return all_out_files


def merge_pdfs(files, out):
    writer = PdfWriter()
    for inpfn in files:
        writer.addpages(PdfReader(inpfn).pages)
    writer.write(out)


def gather_inputs(input_year_folder):
    input_folder = os.path.join("input_data", input_year_folder)
    j = json.load(open(os.path.join(input_folder, 'input.json'), 'rb'))

    additional_info = {
        'single': True,  # if you're not single too bad for you
        'dependents': False,  # same if you have dependents
        'occupation': "Analyst",
        'full_year_health_coverage_or_exempt': True,  # ignored starting 2019
        'presidential_election_self': True,
        'resident': True,  # if you're not it's not done yet
        'scheduleD': True,
        'checking': True,
        'routing_number': "11111111",
        'account_number': "444444444",
        'foreign_account': 'FRANCE',
        'phone': '6465555555',
        'email': 'martialren@gmail.com',
        'health_savings_account': True,
        'health_savings_account_contributions': 3600,
        'health_savings_account_employer_contributions': 0,
        'health_savings_account_distributions': 57.80,
        'medical_expenses': 0,
        'virtual_currency': True
    }

    override_stuff = {
        'address_street_and_number': next(iter(j['W2']))['Address'],
        'address_apt': next(iter(j['W2']))['Address_apt'],
        'address_city': next(iter(j['W2']))['Address_city'],
        'address_state': next(iter(j['W2']))['Address_state'],
        'address_zip': next(iter(j['W2']))['Address_zip'],
        'ssn': '200112222'
    }

    # update_dict(additional_info)
    # update_dict(override_stuff)
    # update_dict(j, modify=False)

    data = {}
    data.update(j)
    data.update(additional_info)
    data[override_keyword] = override_stuff

    if '1099' not in data:
        data['1099'] = []
    data['1099'].extend(
        [
            # {"Institution": "JPMORGAN CHASE BANK NA", "Interest": 3.11},
            # {"Institution": "JPMORGAN CHASE BANK NA", "Interest": 10.29},
        ]
    )

    return data


def main():
    # data2018 = gather_inputs(input_year_folder="2018")
    # states2018, worksheets_all2018 = fill_taxes_2018(data2018)
    # pdf_files2018 = fill_pdfs(states2018, "2018")
    # outfile2018 = "forms" + "2018" + pdf_extension
    # merge_pdfs(pdf_files2018, outfile2018)

    # data2019 = gather_inputs(input_year_folder="2019")
    # states2019, worksheets_all2019 = fill_taxes_2019(data2019, (states2018, worksheets_all2018))
    # pdf_files2019 = fill_pdfs(states2019, "2019")
    # outfile2019 = "forms" + "2019" + pdf_extension
    # merge_pdfs(pdf_files2019, outfile2019)

    # data2020 = gather_inputs(input_year_folder="2020")
    # states2020, worksheets_all2020 = fill_taxes_2020(data2020, (states2019, worksheets_all2019))
    # pdf_files2020 = fill_pdfs(states2020, "2020")
    # outfile2020 = "forms" + "2020" + pdf_extension
    # merge_pdfs(pdf_files2020, outfile2020)

    data2021 = gather_inputs(input_year_folder="2021")
    states2021, worksheets_all2021 = fill_taxes_2021(data2021)
    pdf_files2021 = fill_pdfs(states2021, "2021")
    outfile2021 = "forms" + "2021" + pdf_extension
    merge_pdfs(pdf_files2021, outfile2021)


if __name__ == "__main__":
    # year_folder = "2019"
    main()

    # outfile = "forms" + pdf_extension
    # pdf_files = [
    #     'output\\2018\\Federal\\f1040sd.pdf',
    #     'output\\2018\\Federal\\f1040s1.pdf',
    #     # 'output\\2018\\Federal\\f8949_0.pdf',
    #     # 'output\\2018\\Federal\\f8949_1.pdf',
    #     'output\\2018\\Federal\\f1040.pdf',
    #     # 'output\\2018\\Federal\\f1040sb.pdf',
    #     # 'output\\2018\\Federal\\f1040s3.pdf',
    # ]
    # merge_pdfs(pdf_files, outfile)
