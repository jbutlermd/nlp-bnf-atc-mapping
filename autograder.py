import pandas as pd
import os
import time
import datetime
import math
import configparser
import warnings

warnings.filterwarnings('ignore')
config_file = 'config.ini'
config = configparser.ConfigParser()
config.read(config_file)

labeled_df = pd.read_csv(os.path.join('data/test_analysis_atc_labeled.csv'))
labeled_df.set_index('bnf_code', inplace=True)


def evaluate_match(key, labeled_data, data, threshold=90):
    cm = {}
    label = labeled_data.at[key, 'label']
    if isinstance(label, str):
        label_set = label.split(', ')
    else:
        label_set = []
    match_set = data['atc_matches'].split(', ')
    match_size = len(match_set)
    score = eval("list({})".format(data['matches']))
    score_df = pd.DataFrame(score, columns=['drug', 'score', 'id'])
    score_df['atc'] = match_set

    tp = list(score_df.loc[score_df['score'] >= threshold]['atc'])
    fn = list(score_df.loc[score_df['score'] < threshold]['atc'])

    cm['tp'] = len(intersect(label_set, tp))
    cm['fn'] = len(intersect(label_set, fn))
    cm['fp'] = len(symmetric_diff(label_set, tp))
    cm['tn'] = match_size - cm['tp'] - cm['fn'] - cm['fp']

    return cm


def intersect(a, b):
    c = list(set(a) & set(b))
    return c


def symmetric_diff(a, b):
    c = [x for x in b if x not in a]
    return c


def grade_match(labeled_data, data, threshold):
    for index, row in data.iterrows():
        cm = evaluate_match(row['bnf_code'], labeled_data, row, threshold)
        for key in cm:
            data.at[index, key] = cm[key]
    return


files = []
for (dirpath, dirnames, filenames) in os.walk(os.path.join('output/not-graded')):
    f = [x for x in filenames if x.endswith('.xlsx')]
    files.extend(f)
    break

for filename in files:

    header = f"\nNow reading {filename}\n"
    underscore = "-" * len(header)
    print(header + underscore)

    xlsx = pd.read_excel(os.path.join('output/not-graded/', filename), None)
    scorer_title = list(xlsx.keys())
    scorer_title.pop()
    column_width = {'A:A': 37, 'B:B': 40, 'C:C': 40, 'D:D': 19, 'E:E': 34, 'L:Q': 5}

    with pd.ExcelWriter(os.path.join(config['DEFAULT']['graded_dir'], filename)) as writer:
        for i, scorer in enumerate(scorer_title):
            section_start_time = time.time()
            header = f"\nNow grading performance match using {scorer} algorithm"
            print(header)

            match_df = xlsx[scorer]
            match_df[['tp', 'fn', 'fp', 'tn']] = match_df[['tp', 'fn', 'fp', 'tn']].fillna(value=0)

            if scorer.startswith('threshold-'):
                threshold = int(scorer.split('-')[1])
                print(f'threhold: {threshold}')
            else:
                threshold = 90

            grade_match(labeled_df, match_df, threshold)

            # Save output to Excel sheet and format column width
            match_df.to_excel(writer, sheet_name=scorer, freeze_panes=(1, 0), index=False)
            workbook = writer.book
            format1 = workbook.add_format({'text_wrap': True})
            worksheet = writer.sheets[scorer]
            for key, col in column_width.items():
                worksheet.set_column(key, col, None)
            worksheet.set_column('I:I', 70, format1)
            worksheet.set_column('J:K', 30, format1)
            worksheet.set_column('A:A', None, None, {'hidden': True})
            worksheet.set_column('C:C', None, None, {'hidden': True})
            worksheet.set_column('E:H', None, None, {'hidden': True})

        # Create Summary sheet
        # columns = ['No Match', 'Match', 'Num of Match', 'TP', 'FN', 'FP', 'TN', 'Sensitivity', 'Specificity', 'Precision',
        #           'Accuracy', 'F1 Score', 'Match Rate', 'Missed Opportunity', 'Adj Match Rate']
        columns = ['No Match', 'Match', 'Num of Match', 'TP', 'FN', 'FP', 'TN', 'Sensitivity', 'Specificity',
                   'Precision', 'Accuracy', 'F1 Score', 'Match Rate', 'Adj Match Rate']
        df = pd.DataFrame(scorer_title)
        df.columns = ['Scorer']
        for col in columns:
            df[col] = ""
        df.to_excel(writer, sheet_name='Analysis Summary', index=False)

        worksheet = writer.sheets['Analysis Summary']
        num_rows = len(match_df)
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
            # worksheet.write_formula('O' + str(offset),
            #                         '=COUNTIF(INDIRECT("\'"&A{0}&"\'!$O$2:$O${1}"), ">0")/B{0}'.format(
            #                             offset, num_rows + 1), percent_format)
            worksheet.write_formula('O' + str(offset),
                                    '=(COUNTIF(INDIRECT("\'"&A{0}&"\'!$N$2:$N${1}"),">0")+COUNTIF(INDIRECT("\'"&A{0}&"\'!$O$2:$O${1}"), ">0"))/(B{0}+C{0})'.format(
                                        offset, num_rows + 1), percent_format)
        writer.save()
        writer.close()
