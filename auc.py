import pandas as pd
import os
import configparser
import warnings
from sklearn.metrics import confusion_matrix
from sklearn.metrics import classification_report
from sklearn.metrics import roc_curve
from sklearn.metrics import roc_auc_score


config_file = '../config.ini'
config = configparser.ConfigParser()
config.read(config_file)

y_test_ref = {"tp":1, "fp":0, "fn":1, "tn":0}
y_pred_ref = {"tp":1, "fp":1, "fn":0, "tn":0}

warnings.filterwarnings('ignore')
config_file = 'config.ini'
config = configparser.ConfigParser()
config.read(config_file)


def convert_confusion_matrix(y_test, y_pred, row):
    for i in ['tp', 'fp', 'tn', 'fn']:
        for j in range(int(row[i])):
            y_test.append(y_test_ref[i])
            y_pred.append(y_pred_ref[i])


def get_y_score(y_score, matches):
    for i in matches:
        tmp = eval(i)
        for j in tmp:
            y_score.append(j[1] / 100)
            # y_score.append((j[1]/100)/5)
            # y_score.append(1/6896)


def get_y_true(y_test, y_pred):
    return [x == y_pred[i] and x == True for i, x in enumerate(y_test)]


files = []
for (dirpath, dirnames, filenames) in os.walk(os.path.join('output/graded/')):
    f = [x for x in filenames if x.endswith('.xlsx')]
    files.extend(f)
    break

header = ['filename', 'scorer', 'auc']

auc_df = pd.DataFrame(columns=header)

for filename in files:

    header = f"\nNow reading {filename}\n"
    underscore = "-" * len(header)
    print(header + underscore)

    xlsx = pd.read_excel(os.path.join('output/graded/', filename), None)
    scorer_title = list(xlsx.keys())
    scorer_title.pop()

    for i, scorer in enumerate(scorer_title):
        df = xlsx[scorer]
        #df.fillna(value='0', inplace=True)

        y_test = []
        y_pred = []
        y_score = []
        row_data = {}

        df_records = df.to_dict('records')
        [convert_confusion_matrix(y_test, y_pred, x) for x in df_records]

        print('\n\n', scorer, '\n')
        print(confusion_matrix(y_test, y_pred))
        print(classification_report(y_test, y_pred))

        y = get_y_true(y_test, y_pred)
        get_y_score(y_score, df.matches)
        (fpr, tpr, thresholds) = roc_curve(y, y_score, drop_intermediate=False)

        #plot_roc_curve(fpr, tpr, scorer)
        roc_auc = roc_auc_score(y, y_score)
        print('ROC AUC:', roc_auc)
        row_data['filename'] = filename
        row_data['scorer'] = scorer
        row_data['auc'] = roc_auc
        auc_df = auc_df.append(row_data, ignore_index=True)

auc_df.to_csv(os.path.join('output/auc.csv'))
