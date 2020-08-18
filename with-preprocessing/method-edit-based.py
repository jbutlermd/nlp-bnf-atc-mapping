import pandas as pd
import os
import time
import datetime
import math
import configparser
import jellyfish as jf
from fuzzywuzzy import utils
from nltk.tokenize import word_tokenize

config_file = '../config.ini'
config = configparser.ConfigParser()
config.read(config_file)


# Modified Function from StackOverflow -- written by Erfan
# Credit: https://stackoverflow.com/questions/13636848/is-it-possible-to-do-fuzzy-match-merge-with-python-pandas

def fuzzy_merge(df_1, df_2, key1, key2, scorer=jf.levenshtein_distance, threshold=90, limit=2, distance=True):
    """
    df_1 is the left table to join
    df_2 is the right table to join
    key1 is the key column of the left table
    key2 is the key column of the right table
    threshold is how close the matches should be to return a match
    limit is the amount of matches will get returned, these are sorted high to low
    """
    s = df_2['name_without_sw']

    m = df_1[key1].apply(lambda x: extract(str(x), s, scorer=scorer, limit=limit, distance=distance))
    m_revised = m.apply(lambda x: revert_original_name(x, key2))

    df_1['matches'] = m_revised
    m2 = df_1['matches'].apply(lambda x: ', '.join([atc_df.loc[i[2], 'ATC code'] for i in x]))
    m3 = df_1['matches'].apply(lambda x: ', '.join([atc_df.loc[i[2], 'ATC code'] for i in x if i[1] >= threshold]))
    df_1['atc_matches'] = m2
    df_1['atc_best_match'] = m3
    df_1['matches_count'] = df_1['matches'].apply(lambda x: len(x))
    df_1['best_match_count'] = df_1['matches'].apply(lambda x: sum(i[1] >= threshold for i in x))

    return df_1


def revert_original_name(x, key):
    m = []
    for i in x:
        m.append((atc_df.loc[i[2], key], i[1], i[2]))
    return m


def extract(query, choices, processor=utils.full_process, scorer=jf.levenshtein_distance, limit=5, distance=True):
    tmp = choices.to_frame('name')
    tmp['name'] = tmp['name'].apply(lambda x: processor(x))

    tmp['distance'] = tmp['name'].apply(lambda x: scorer(remove_stop_words(processor(query)), str(x)))
    if distance:
        tmp['score'] = tmp.apply(lambda x: calculate_score(x['distance'], query, x['name']), axis=1)
    else:
        tmp['score'] = tmp['distance'].apply(lambda x: round(x * 100))

    tmp.sort_values(by=['score'], ascending=False, inplace=True)

    results = tmp[0:limit]
    best_results = []
    for key, value in results.iterrows():
        best_results.append((value['name'], value['score'], key))

    return best_results


def remove_stop_words(x):
    if x not in whitelist:
        x_tokenized = x.split(" ")
        itertokens = iter(x_tokenized)
        next(itertokens)
        tokens_without_sw = [word for word in itertokens if word not in stop_words]
        tokens_without_sw.insert(0,x_tokenized[0])
        text_without_sw = " ".join(tokens_without_sw)
        return text_without_sw
    else:
        return x


def calculate_score(distance, x, y):
    return (1 - distance / max(len(x), len(y))) * 100


def number_format(x):
    if x - math.trunc(x) > 0:
        return '{:.2f}'.format(x)
    else:
        return '{:.0f}'.format(x)


def control_scorer(a, b):
    if a.lower() == b.lower():
        return 1
    else:
        return 0


start_time = time.time()
# Load source file
# bnf_df = pd.read_csv(os.path.join(config['DEFAULT']['output_dir'], 'bnf_code_clean.csv'))
# bnf_df = pd.read_csv(os.path.join(config['DEFAULT']['output_dir'], 'bnf_code_clean_test.csv'))
bnf_df = pd.read_csv(os.path.join('../data/test_analysis_set.csv'))
#bnf_df = pd.read_csv(os.path.join('../data/misspelling_test_analysis_set.csv'))

# Load stop words and whitelist
stop_words = pd.read_csv(os.path.join('../data/stop_words.csv'), header=None)[0].values.tolist()
whitelist = pd.read_csv(os.path.join('../data/whitelist.csv'), header=None)[0].values.tolist()

# Load RxNorm ATC data file
atc_df = pd.read_csv('../data/rxnorm_atc_code_info.csv')
atc_df.columns = ['i', 'rxcui', 'rxaui', 'sab', 'tty', 'ATC code', 'ATC level name', 'suppress']
atc_df.drop('i', axis=1, inplace=True)
atc_df = atc_df.loc[atc_df['tty'].isin(['IN','RXN_IN'])]
atc_df['name_without_sw'] = atc_df['ATC level name'].apply(lambda x: remove_stop_words(x))

# Perform fuzzy merge and save results in each individual sheet

scorer_list = [control_scorer, jf.levenshtein_distance, jf.damerau_levenshtein_distance, jf.jaro_distance,
               jf.jaro_winkler, jf.hamming_distance]
scorer_title = ["Control", "Levenshtein", "Damerau-Levenshtein", "Jaro", "Jaro-Winkler", "Hamming"]
scorer_type = [False, True, True, False, False, True]
column_width = {'A:A': 37, 'B:B': 40, 'C:C': 40, 'D:D': 19, 'E:E': 34, 'L:Q': 5}

with pd.ExcelWriter(os.path.join(config['DEFAULT']['output_dir'], 'method-edit-based-results.xlsx')) as writer:
    for i, scorer in enumerate(scorer_list):
        section_start_time = time.time()
        header = f"\nNow performing fuzzy match using {scorer_title[i]} algorithm\n"
        underscore = "-" * len(header)
        print(header + underscore)

        merged_df = fuzzy_merge(bnf_df, atc_df, 'bnf_chemical_substance', 'ATC level name', threshold=90, limit=5,
                                scorer=scorer, distance=scorer_type[i])
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
        for j in range(2, len(merged_df) + 2):
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
                                    offset, num_rows + 1), percent_format)
        worksheet.write_formula('O' + str(offset),
                                '=COUNTA(INDIRECT("\'"&A{0}&"\'!$O$2:$O${1}"))/B{0}'.format(
                                    offset, num_rows + 1), percent_format)
        worksheet.write_formula('P' + str(offset),
                                '=(COUNTIF(INDIRECT("\'"&A{0}&"\'!$N$2:$N${1}"),">0")+COUNTA(INDIRECT("\'"&A{0}&"\'!$O$2:$O${1}")))/(B{0}+C{0})'.format(
                                    offset, num_rows + 1), percent_format)
    writer.save()

end_time = time.time()
uptime = end_time - start_time
human_uptime = str(datetime.timedelta(seconds=int(uptime)))
print('Jellyfish matching & merging is completed.')
print(f'Total Time Elapsed: {human_uptime}')
