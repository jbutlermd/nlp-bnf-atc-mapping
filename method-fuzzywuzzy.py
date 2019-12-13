import pandas as pd
import os
import time
import datetime
import math
import configparser
from fuzzywuzzy import process
from fuzzywuzzy import fuzz

config_file = 'config.ini'
config = configparser.ConfigParser()
config.read(config_file)


def extract_cache(x, s, cache, scorer, limit):
    if x in cache:
        return cache[x]
    match = process.extract(x, s, scorer, limit)
    cache[x] = match
    return cache[x]


# Modified Function from StackOverflow -- written by Erfan
# Credit: https://stackoverflow.com/questions/13636848/is-it-possible-to-do-fuzzy-match-merge-with-python-pandas

def fuzzy_merge(df_1, df_2, key1, key2, scorer=fuzz.partial_ratio, threshold=90, limit=2):
    """
    df_1 is the left table to join
    df_2 is the right table to join
    key1 is the key column of the left table
    key2 is the key column of the right table
    threshold is how close the matches should be to return a match
    limit is the amount of matches will get returned, these are sorted high to low
    """
    s = df_2[key2]
    cache = {}

    # m = df_1[key1].apply(lambda x: extract_cache(str(x), s, cache, scorer=scorer, limit=limit))
    m = df_1[key1].apply(lambda x: process.extract(str(x), s, scorer=scorer, limit=limit))

    df_1['matches'] = m
    m2 = df_1['matches'].apply(lambda x: ', '.join([atc_df.loc[i[2], 'ATC code'] for i in x]))
    m3 = df_1['matches'].apply(lambda x: ', '.join([atc_df.loc[i[2], 'ATC code'] for i in x if i[1] >= threshold]))
    df_1['atc_matches'] = m2
    df_1['atc_best_match'] = m3
    df_1['matches_count'] = df_1['matches'].apply(lambda x: len(x))
    df_1['best_match_count'] = df_1['matches'].apply(lambda x: sum(i[1] >= threshold for i in x))

    return df_1


def number_format(x):
    if x - math.trunc(x) > 0:
        return '{:.2f}'.format(x)
    else:
        return '{:.0f}'.format(x)


def match_ddd_by_atc(x, s, scorer=fuzz.partial_ratio, limit=2):
    l = list()
    atc_codes = x['atc_best_match'].split(',')
    for code in atc_codes:
        z = s[(s['ATC code'] == code) & (s['dosage'].notnull())]
        if not z.empty:
            d = process.extract(str(x['dose']), z['dosage'], scorer=scorer, limit=limit)
            if len(d):
                l = l + d
    return l


start_time = time.time()
# Load source file
# bnf_df = pd.read_csv(os.path.join(config['DEFAULT']['output_dir'], 'bnf_code_clean.csv'))
#bnf_df = pd.read_csv(os.path.join(config['DEFAULT']['output_dir'], 'bnf_code_clean_test.csv'))
bnf_df = pd.read_csv(os.path.join('data/test_analysis_set2.csv'))

# Load ATC-DDD data file
# atc_df = pd.read_excel('data/2016_atc_index_electronic_eksempel.xlsx')

# Load RxNorm ATC data file
atc_df = pd.read_csv('data/rxnorm_atc_code_info.csv')
atc_df.columns = ['i', 'rxcui', 'rxaui', 'sab', 'tty', 'ATC code', 'ATC level name', 'suppress']
atc_df.drop('i', axis=1, inplace=True)

# Combine DDD fields into one for easier match
# atc_df['dosage'] = atc_df[['DDD', 'U']].apply(lambda x: number_format(x.DDD) + str(x.U) if x.DDD > 0 else None, axis=1)

# Perform fuzzy merge and save results in each individual sheet
# Scorers available: ratio, partial_ratio, token_set_ratio, token_sort_ratio, partial_token_set_ratio,
#     partial_token_sort_ratio

scorer_list = [fuzz.ratio, fuzz.partial_ratio, fuzz.token_set_ratio, fuzz.partial_token_set_ratio,
               fuzz.token_sort_ratio, fuzz.partial_token_sort_ratio]
scorer_title = ["Ratio", "Partial Ratio", "Token Set Ratio", "Partial Token Set Ratio",
                "Token Sort Ratio", "Partial Token Sort Ratio"]
column_width = {'A:A': 37, 'B:B': 40, 'C:C': 40, 'D:D': 19, 'E:E': 34, 'L:Q': 5}

with pd.ExcelWriter(os.path.join(config['DEFAULT']['output_dir'], 'bnf-atc-map-combined.xlsx')) as writer:
    for i, scorer in enumerate(scorer_list):
        section_start_time = time.time()
        header = f"\nNow performing fuzzy match using {scorer_title[i]} algorithm\n"
        underscore = "-" * len(header)
        print(header + underscore)

        merged_df = fuzzy_merge(bnf_df, atc_df, 'bnf_chemical_substance', 'ATC level name', threshold=90, limit=5,
                                scorer=scorer)
        print(merged_df.head(5))

        # Add empty columns for manual tallying for statistical analysis on accuracy
        merged_df['tp'] = ""
        merged_df['fn'] = ""
        merged_df['fp'] = ""
        merged_df['tn'] = ""
        merged_df['combo'] = ""

        # Save output to Excel sheet and format column width
        merged_df.to_excel(writer, sheet_name=scorer_title[i], freeze_panes=(1, 0), index=False)
        workbook = writer.book
        format1 = workbook.add_format({'text_wrap': True})
        worksheet = writer.sheets[scorer_title[i]]
        for key, col in column_width.items():
            worksheet.set_column(key, col, None)
        worksheet.set_column('I:I', 70, format1)
        worksheet.set_column('J:K', 30, format1)
        worksheet.set_column('A:A', None, None, {'hidden': True})
        worksheet.set_column('C:C', None, None, {'hidden': True})
        worksheet.set_column('E:H', None, None, {'hidden': True})
        formula = '=L{0}-SUM(N{0}:P{0})'
        for j in range(2, len(merged_df)):
            worksheet.write_formula('N' + str(j), '=M{}'.format(j))
            worksheet.write_formula('Q' + str(j), formula.format(j))

        end_time = time.time()
        uptime = end_time - section_start_time
        human_uptime = str(datetime.timedelta(seconds=int(uptime)))
        print(f'Time required to complete: {human_uptime}')

    # Create Summary sheet
    columns = ['No Match', 'Match', 'Num of Match', 'TP', 'FN', 'FP', 'TN', 'Sensitivity', 'Specificity', 'Precision',
               'Accuracy', 'F1 Score', 'Overall Match', 'Missed Opportunity', 'Gain if not missed']
    df = pd.DataFrame(scorer_title)
    df.columns = ['Scorer']
    for col in columns:
        df[col] = ""
    df.to_excel(writer, sheet_name='Analysis Summary', index=False)

    worksheet = writer.sheets['Analysis Summary']
    num_rows = len(merged_df)
    for row, scorer_name in enumerate(scorer_title):
        offset = row + 2
        cell = 'A' + str(offset)
        formula = '={0}(INDIRECT("\'"&A{1}&"\'!${2}$2:${2}${3}"))'
        percent_format = workbook.add_format({'num_format': '0.0%'})
        decimal_format = workbook.add_format({'num_format': '0.000'})
        worksheet.write_formula('B' + str(offset), formula.format('COUNTBLANK', offset, 'K', num_rows + 1))
        worksheet.write_formula('C' + str(offset), formula.format('COUNTA', offset, 'K', num_rows + 1))
        worksheet.write_formula('D' + str(offset), formula.format('SUM', offset, 'M', num_rows + 1))
        worksheet.write_formula('E' + str(offset), formula.format('SUM', offset, 'N', num_rows + 1))
        worksheet.write_formula('F' + str(offset), formula.format('SUM', offset, 'O', num_rows + 1))
        worksheet.write_formula('G' + str(offset), formula.format('SUM', offset, 'P', num_rows + 1))
        worksheet.write_formula('H' + str(offset), formula.format('SUM', offset, 'Q', num_rows + 1))
        worksheet.write_formula('I' + str(offset), '=E{0}/(E{0}+F{0})'.format(offset), decimal_format)
        worksheet.write_formula('J' + str(offset), '=H{0}/(H{0}+G{0})'.format(offset), decimal_format)
        worksheet.write_formula('K' + str(offset), '=E{0}/(E{0}+G{0})'.format(offset), decimal_format)
        worksheet.write_formula('L' + str(offset), '=(E{0}+H{0})/SUM(E{0}:H{0})'.format(offset), decimal_format)
        worksheet.write_formula('M' + str(offset), '=(2*E{0})/((2*E{0})+G{0}+F{0})'.format(offset), decimal_format)
        worksheet.write_formula('N' + str(offset),
                                '=(COUNTIF(INDIRECT("\'"&A{0}&"\'!$N$2:$N${1}"), ">0")/(B{0}+C{0}))'.format(
                                    offset, num_rows+1), percent_format)
        worksheet.write_formula('O' + str(offset),
                                '=COUNTA(INDIRECT("\'"&A{0}&"\'!$O$2:$O${1}"))/B{0}'.format(
                                    offset, num_rows+1), percent_format)
        worksheet.write_formula('P' + str(offset),
                                '=(COUNTIF(INDIRECT("\'"&A{0}&"\'!$N$2:$N${1}"),">0")+COUNTA(INDIRECT("\'"&A{0}&"\'!$O$2:$O${1}")))/(B{0}+C{0})'.format(
                                    offset, num_rows+1), percent_format)
    writer.save()
# m = merged_df.apply(lambda x: match_ddd_by_atc(x, atc_df, scorer=fuzz.ratio, limit=2), axis=1)
# merged_df['ddd_matched'] = m
# merged_df['DDD'] = merged_df['ddd_matched'].apply(
#     lambda x: ', '.join([str(atc_df.loc[i[2], 'DDD']) for i in x if i[1] >= 90]))

end_time = time.time()
uptime = end_time - start_time
human_uptime = str(datetime.timedelta(seconds=int(uptime)))
print('Fuzzy match & merging is completed.')
print(f'Total Time Elapsed: {human_uptime}')
