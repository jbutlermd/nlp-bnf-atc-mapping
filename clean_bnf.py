import pandas as pd
import os
import re
import operator
import configparser

config_file = 'config.ini'
config = configparser.ConfigParser()
config.read(config_file)


def shift_data(data):
    if data[2]:
        data[1] = str(data[1]) + ' ' + str(data[2])
    data[2] = data[3]
    data[3] = None
    return data


def bnf_name_split(string):
    pattern = r"(.*)_([A-Za-z \/\-]*) ([\d\.\-]+[A-Za-z\%]+[\/]*[\d\.\-]*[A-Za-z\%]*[\/]*[\d\.\-]*[A-Za-z\%]*)(.*)|(.*)_([A-Za-z\/]*)(.*)(.*)"
    matches = re.findall(pattern, string)

    if (not matches):
        return [None, None, None, None]
    else:
        groups = list(matches[0])
        groups = [string.strip() if string else None for string in groups]

    if (groups[0]):
        data = groups[0:4]
    else:
        data = groups[4:8]

    for i in range(2):
        if data[2]:
            matchObj = re.match(r"^(\d+)", data[2])
            if not matchObj:
                data = shift_data(data)

    if data[3]:
        matchObj = re.match(r"^(\d+)", data[3])
        if matchObj:
            words = data[3].split(' ')
            new_data = ''.join(words[1:])
            data[2] = str(data[2]) + ' ' + str(words[0])
            data[3] = new_data

        if data[3]:
            data[1] = str(data[1]) + ' ' + str(data[3])
            data[3] = None

    return data


def filter_unwanted_bnf(df, field, pattern_list):
    for pattern in pattern_list:
        regex = r'' + pattern
        mask = list(map(operator.not_, df[field].str.match(regex).astype(bool)))
        df = df[mask]
    return df


# Load bnf code information file

bnf_code_df = pd.read_csv('data/BNF_Code_information.csv', dtype='U')

# Select relevant columns
keep_columns = ['BNF Chapter','BNF Chemical Substance', 'BNF Presentation', 'BNF Presentation Code']
tmp_df = bnf_code_df[keep_columns]
tmp_df.columns = ['bnf_chapter','bnf_chemical_substance','bnf_name','bnf_code']

# Remove irrelevant rows
pattern_list = ['^23', '^22', '^21', '^20']
bnf_code_trimmed_df = filter_unwanted_bnf(tmp_df, 'bnf_code', pattern_list)

# Unmangle bnf name string to extract dosage and drug form
new = [bnf_name_split(string) for string in bnf_code_trimmed_df['bnf_name']]
new_df = pd.DataFrame(new)
new_df.columns = ['drug', 'form', 'dose', 'misc1']
bnf_code_clean_df = bnf_code_trimmed_df.join(new_df)

# Save to a new CSV file
bnf_code_clean_df.to_csv(os.path.join(config['DEFAULT']['output_dir'], 'bnf_code_clean.csv'), index=False)

print("Statistics of cleaned up file")
print(bnf_code_clean_df.info())
